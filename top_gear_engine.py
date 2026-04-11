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
import subprocess
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


@dataclass
class TopGearConfig:
    simc_executable: str
    options: SimOptions = field(default_factory=SimOptions)
    mode: str = "drop_finder"           # "drop_finder" or "top_gear"
    max_combinations: int = 500
    selected_bag_items: Optional[list] = None   # None = use all bag items
    timeout: int = 600                  # simc hard timeout in seconds


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

    # Step 2 – generate profileset input
    if config.mode == "top_gear":
        simc_input, combo_metadata = generate_top_gear_input(
            parse_result,
            options=config.options,
            selected_bag_items=config.selected_bag_items,
            max_combinations=config.max_combinations,
        )
    else:
        bag_items = config.selected_bag_items  # None → all
        simc_input, combo_metadata = generate_drop_finder_input(
            parse_result,
            config.options,
            bag_items=bag_items,
        )

    if not combo_metadata:
        return parse_result, [], combo_metadata

    # Step 3 – run simc
    json_data = run_simc_with_input(simc_input, config.simc_executable, config.timeout)

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
    try:
        proc = subprocess.run(
            [simc_executable, "json2=stdout", "-"],
            input=simc_input,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"simc timed out after {timeout}s")
    except FileNotFoundError:
        raise RuntimeError(f"simc executable not found: {simc_executable}")

    if not proc.stdout.strip():
        snippet = proc.stderr[-2000:] if proc.stderr else "(no stderr)"
        raise RuntimeError(f"simc produced no JSON output. stderr: {snippet}")

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse simc JSON output: {exc}") from exc


def combo_count(result: ParseResult, selected_bag_items: Optional[list] = None) -> int:
    """Return the number of Top Gear combinations for the given items."""
    return count_top_gear_combinations(result, selected_bag_items=selected_bag_items)
