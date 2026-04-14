"""
Top Gear Engine: orchestrates the full profileset simulation pipeline.

Pipeline:
  1. Parse SimC addon string  (addon_parser)
  2. Generate simc profileset input  (profileset_generator)
  3. Run simc once via stdin/stdout  (replaces old N-process-per-file approach)
  4. Parse JSON results  (result_parser)

This is dramatically faster than the original approach of spawning one simc
process per item: all alternatives are evaluated in a single simc run.
"""
import json
import os
import re
import subprocess
import sys
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Optional

from simc_gv_generator import parse_simc_addon, ParseResult
from profileset_generator import (
    SimOptions,
    generate_drop_finder_input,
    generate_top_gear_input,
    count_top_gear_combinations,
)
from result_parser import parse_results, SimResult


def find_simc_executable():
    """Find simc.exe in multiple possible locations"""
    
    # Possible names for the SimulationCraft executable
    possible_names = ["simc.exe", "SimulationCraft.exe"]
    
    # Get the directory where this script/exe is located
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        script_dir = os.path.dirname(sys.executable)
    else:
        # Running as Python script
        script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Search locations in order of preference
    search_locations = [
        os.path.join(script_dir, "simc"),  # simc subfolder in script directory
        os.path.join(os.getcwd(), "simc"),  # simc subfolder in current working directory
        script_dir,  # Same directory as the application
        os.getcwd(),  # Current working directory
    ]
    
    # Check each location for each possible executable name
    for location in search_locations:
        for name in possible_names:
            full_path = os.path.join(location, name)
            if os.path.isfile(full_path):
                return full_path
    
    # Try to find in system PATH
    for name in possible_names:
        path_location = shutil.which(name)
        if path_location:
            return path_location
    
    return None


@dataclass
class TopGearConfig:
    simc_executable: str
    options: SimOptions = field(default_factory=SimOptions)
    mode: str = "drop_finder"           # "drop_finder" or "top_gear"
    max_combinations: int = 500
    selected_bag_items: Optional[list] = None   # None = use all bag items
    timeout: int = 600                  # simc hard timeout in seconds


def _normalize_item_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _extract_invalid_item_name(error_text: str) -> Optional[str]:
    m = re.search(r"Item '([^']+)'.*Invalid type", error_text)
    if not m:
        return None
    return m.group(1)


def _diagnose_invalid_items(
    parse_result: ParseResult,
    simc_executable: str,
    bag_items: list,
    timeout: int,
) -> list:
    """Return selected bag items that the current simc build rejects."""
    if not bag_items:
        return []

    base = "\n".join(parse_result.base_profile_lines)
    invalid = []

    for item in bag_items:
        item_line = re.sub(r"^\w+=", f"{item.slot}=", item.simc_string)
        simc_input = base + f'\n\nprofileset."check"+={item_line}\n'
        try:
            run_simc_with_input(simc_input, simc_executable, timeout=min(timeout, 60))
        except RuntimeError as exc:
            bad_name = _extract_invalid_item_name(str(exc))
            if bad_name is None:
                raise
            normalized_bad = _normalize_item_name(bad_name)
            normalized_item = _normalize_item_name(item.name or "")
            if normalized_item and normalized_bad != normalized_item:
                raise
            invalid.append(item)

    return invalid


def run_top_gear(
    simc_text: str,
    config: TopGearConfig,
) -> tuple:
    """Run the full Top Gear simulation pipeline.

    Args:
        simc_text:  Raw SimC addon export string (pasted from the addon).
        config:     TopGearConfig with simc path, options, and mode.

    Returns:
        (parse_result, sim_results, combo_metadata)
          parse_result   – ParseResult from addon_parser
          sim_results    – list[SimResult] sorted by DPS descending
          combo_metadata – {label -> ParsedItem | list[ParsedItem]}
    """
    # Step 1 – parse
    parse_result = parse_simc_addon(simc_text)
    selected_items = config.selected_bag_items if config.selected_bag_items is not None else parse_result.bag_items

    if config.mode == "top_gear":
        count = count_top_gear_combinations(parse_result, selected_bag_items=selected_items)
        if count > config.max_combinations:
            raise ValueError(
                f"Too many combinations: {count} > {config.max_combinations}. "
                "Reduce selected items or increase max_combinations."
            )

    # Step 2 – generate profileset input
    if config.mode == "top_gear":
        simc_input, combo_metadata = generate_top_gear_input(
            parse_result,
            options=config.options,
            selected_bag_items=selected_items,
            max_combinations=config.max_combinations,
        )
    else:
        simc_input, combo_metadata = generate_drop_finder_input(
            parse_result,
            config.options,
            bag_items=selected_items,
        )

    if not combo_metadata:
        return parse_result, [], combo_metadata

    # Step 3 – run simc
    try:
        json_data = run_simc_with_input(simc_input, config.simc_executable, config.timeout)
    except RuntimeError as exc:
        invalid_items = _diagnose_invalid_items(
            parse_result,
            config.simc_executable,
            selected_items,
            config.timeout,
        )
        if not invalid_items:
            raise
        summary = ", ".join(f"{item.name or item.item_id} ({item.item_id})" for item in invalid_items[:5])
        if len(invalid_items) > 5:
            summary += f", +{len(invalid_items) - 5} more"
        raise RuntimeError(
            "Selected items are incompatible with the current SimulationCraft build: "
            f"{summary}. Update simc.exe or deselect these items."
        ) from exc

    # Step 4 – parse results
    sim_results = parse_results(json_data)

    return parse_result, sim_results, combo_metadata


def run_simc_with_input(
    simc_input: str,
    simc_executable: str,
    timeout: int = 600,
) -> dict:
    """Run simc with the given profile string piped to stdin.

    Uses ``json2=stdout`` so the full JSON report is written to stdout, which
    is captured and parsed — no temporary files needed.

    Args:
        simc_input:      Full simc profile / profileset input string.
        simc_executable: Path to the simc binary.
        timeout:         Max seconds before the process is killed.

    Returns:
        Parsed JSON dict from simc's json2 output.

    Raises:
        RuntimeError: on timeout, missing binary, empty output, or bad JSON.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json")
    os.close(tmp_fd)
    try:
        try:
            proc = subprocess.run(
                [simc_executable, f"json2={tmp_path}", "-"],
                input=simc_input,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"simc timed out after {timeout}s")
        except FileNotFoundError:
            raise RuntimeError(f"simc executable not found: {simc_executable}")

        try:
            with open(tmp_path, encoding="utf-8") as f:
                raw = f.read()
        except OSError:
            raw = ""

        if not raw.strip():
            snippet = proc.stderr[-2000:] if proc.stderr else "(no stderr)"
            raise RuntimeError(f"simc produced no JSON output. stderr: {snippet}")

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse simc JSON output: {exc}") from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def combo_count(result: ParseResult, selected_bag_items: Optional[list] = None) -> int:
    """Return the number of Top Gear combinations for the given items."""
    return count_top_gear_combinations(result, selected_bag_items=selected_bag_items)
