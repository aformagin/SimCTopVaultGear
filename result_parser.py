"""
Parse SimulationCraft json2 output to extract DPS results for
the baseline character and all profileset combinations.

simc is invoked as:
    simc json2=stdout -   (profile piped via stdin)

The JSON structure used here:
    sim.players[0].collected_data.dps.mean   -> baseline DPS
    sim.profilesets.results[].name           -> profileset label
    sim.profilesets.results[].(mean|median)  -> profileset DPS
"""
import json
from dataclasses import dataclass


@dataclass
class SimResult:
    label: str          # profileset name, or "Baseline"
    dps: float          # mean/median DPS value
    dps_error: float    # statistical error margin
    delta: float        # DPS vs baseline (0 for baseline itself)
    delta_pct: float    # delta as a percentage (0 for baseline)


def parse_results(json_data: dict, baseline_label: str = "Baseline") -> list:
    """Parse simc json2 output dict into a sorted list of SimResult objects.

    Args:
        json_data:       Parsed JSON from simc's json2=stdout output.
        baseline_label:  Label to use for the current-gear baseline entry.

    Returns:
        List of SimResult sorted by DPS descending.
        Returns [] if no player data is present.
    """
    sim = json_data.get("sim", {})
    players = sim.get("players", [])
    if not players:
        return []

    player = players[0]
    collected = player.get("collected_data", {})
    dps_data = collected.get("dps", {})

    baseline_dps = float(dps_data.get("mean", 0.0))
    baseline_error = float(dps_data.get("error", 0.0))

    results = [
        SimResult(
            label=baseline_label,
            dps=baseline_dps,
            dps_error=baseline_error,
            delta=0.0,
            delta_pct=0.0,
        )
    ]

    # Profileset results — simc uses different field names across versions:
    # "median_dps"/"mean_dps" (SimHammer schema) or "mean"/"median" (raw simc).
    profilesets = sim.get("profilesets", {})
    for ps in profilesets.get("results", []):
        name = ps.get("name", "")
        dps_val = float(
            ps.get("mean_dps")
            or ps.get("median_dps")
            or ps.get("mean")
            or ps.get("median")
            or ps.get("metric")
            or 0.0
        )
        error = float(ps.get("error", 0.0))
        delta = dps_val - baseline_dps
        delta_pct = (delta / baseline_dps * 100.0) if baseline_dps else 0.0

        results.append(
            SimResult(
                label=name,
                dps=dps_val,
                dps_error=error,
                delta=delta,
                delta_pct=delta_pct,
            )
        )

    results.sort(key=lambda r: r.dps, reverse=True)
    return results


def parse_results_from_string(json_string: str, baseline_label: str = "Baseline") -> list:
    """Parse simc json2 output from a raw JSON string."""
    return parse_results(json.loads(json_string), baseline_label=baseline_label)
