"""
Tests for top_gear_engine.py.

simc is never actually invoked — run_simc_with_input is patched to return a
pre-built JSON dict so these tests run without the simc binary.
"""
import json
import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock

from simc_gv_generator import parse_simc_addon
from profileset_generator import SimOptions
from top_gear_engine import run_top_gear, run_simc_with_input, TopGearConfig

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "sample_simc_string.txt")

BASELINE_DPS = 100_000.0

MOCK_SIMC_JSON = {
    "sim": {
        "players": [{
            "collected_data": {
                "dps": {"mean": BASELINE_DPS, "error": 500.0}
            }
        }],
        "profilesets": {
            "results": [
                {
                    "name": "Voidlashed_Hood_head",
                    "mean_dps": 103_000.0,
                    "median_dps": 103_000.0,
                    "error": 600.0,
                },
                {
                    "name": "Amani_Heartstring_Pendant_neck",
                    "mean_dps": 98_000.0,
                    "median_dps": 98_000.0,
                    "error": 400.0,
                },
            ]
        },
    }
}


@pytest.fixture(scope="module")
def sample_text():
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def base_config():
    return TopGearConfig(
        simc_executable="/fake/simc",
        options=SimOptions(target_error=0.5, threads=2),
        mode="drop_finder",
    )


# ---------------------------------------------------------------------------
# run_simc_with_input
# ---------------------------------------------------------------------------

def _make_simc_run(content: str):
    """Return a subprocess.run side_effect that writes *content* to the temp file."""
    def _run(cmd, **kwargs):
        json2_arg = next((a for a in cmd if a.startswith("json2=")), None)
        if json2_arg:
            tmp_path = json2_arg[len("json2="):]
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
        mock_proc = MagicMock()
        mock_proc.stderr = ""
        return mock_proc
    return _run


class TestRunSimcWithInput:
    def test_success_returns_dict(self):
        with patch("subprocess.run", side_effect=_make_simc_run(json.dumps(MOCK_SIMC_JSON))):
            result = run_simc_with_input("some input", "/fake/simc")
        assert isinstance(result, dict)
        assert result["sim"]["players"][0]["collected_data"]["dps"]["mean"] == BASELINE_DPS

    def test_empty_stdout_raises(self):
        mock_proc = MagicMock()
        mock_proc.stderr = "something went wrong"
        with patch("subprocess.run", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="no JSON output"):
                run_simc_with_input("some input", "/fake/simc")

    def test_whitespace_only_stdout_raises(self):
        with patch("subprocess.run", side_effect=_make_simc_run("   \n\t  ")):
            with pytest.raises(RuntimeError, match="no JSON output"):
                run_simc_with_input("some input", "/fake/simc")

    def test_invalid_json_raises(self):
        with patch("subprocess.run", side_effect=_make_simc_run("not { json")):
            with pytest.raises(RuntimeError, match="Failed to parse"):
                run_simc_with_input("some input", "/fake/simc")

    def test_file_not_found_raises(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(RuntimeError, match="not found"):
                run_simc_with_input("some input", "/nonexistent/simc")

    def test_timeout_raises(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("simc", 600)):
            with pytest.raises(RuntimeError, match="timed out"):
                run_simc_with_input("some input", "/fake/simc")

    def test_simc_called_with_json2_stdout(self):
        with patch("subprocess.run", side_effect=_make_simc_run(json.dumps(MOCK_SIMC_JSON))) as mock_run:
            run_simc_with_input("input", "/fake/simc")
        args = mock_run.call_args[0][0]
        assert any(a.startswith("json2=") for a in args)
        assert "-" in args

    def test_input_piped_via_stdin(self):
        with patch("subprocess.run", side_effect=_make_simc_run(json.dumps(MOCK_SIMC_JSON))) as mock_run:
            run_simc_with_input("my profile", "/fake/simc")
        kwargs = mock_run.call_args[1]
        assert kwargs.get("input") == "my profile"


# ---------------------------------------------------------------------------
# run_top_gear — drop_finder mode
# ---------------------------------------------------------------------------

class TestRunTopGearDropFinder:
    def test_returns_three_tuple(self, sample_text, base_config):
        with patch("top_gear_engine.run_simc_with_input", return_value=MOCK_SIMC_JSON):
            result = run_top_gear(sample_text, base_config)
        assert len(result) == 3

    def test_parse_result_has_correct_class(self, sample_text, base_config):
        with patch("top_gear_engine.run_simc_with_input", return_value=MOCK_SIMC_JSON):
            parse_result, _, _ = run_top_gear(sample_text, base_config)
        assert parse_result.character_class == "druid"

    def test_sim_results_non_empty(self, sample_text, base_config):
        with patch("top_gear_engine.run_simc_with_input", return_value=MOCK_SIMC_JSON):
            _, sim_results, _ = run_top_gear(sample_text, base_config)
        assert len(sim_results) > 0

    def test_sim_results_sorted_descending(self, sample_text, base_config):
        with patch("top_gear_engine.run_simc_with_input", return_value=MOCK_SIMC_JSON):
            _, sim_results, _ = run_top_gear(sample_text, base_config)
        dps = [r.dps for r in sim_results]
        assert dps == sorted(dps, reverse=True)

    def test_combo_metadata_non_empty(self, sample_text, base_config):
        with patch("top_gear_engine.run_simc_with_input", return_value=MOCK_SIMC_JSON):
            _, _, meta = run_top_gear(sample_text, base_config)
        assert len(meta) > 0

    def test_best_result_is_upgrade(self, sample_text, base_config):
        with patch("top_gear_engine.run_simc_with_input", return_value=MOCK_SIMC_JSON):
            _, sim_results, _ = run_top_gear(sample_text, base_config)
        non_baseline = [r for r in sim_results if r.label != "Baseline"]
        assert non_baseline[0].dps > BASELINE_DPS

    def test_baseline_present_in_results(self, sample_text, base_config):
        with patch("top_gear_engine.run_simc_with_input", return_value=MOCK_SIMC_JSON):
            _, sim_results, _ = run_top_gear(sample_text, base_config)
        assert any(r.label == "Baseline" for r in sim_results)


# ---------------------------------------------------------------------------
# run_top_gear — top_gear mode
# ---------------------------------------------------------------------------

class TestRunTopGearMode:
    def test_top_gear_mode_runs(self, sample_text):
        parsed = parse_simc_addon(sample_text)
        # Use only the first 2 bag items so the Cartesian product stays small
        small_set = parsed.bag_items[:2]
        config = TopGearConfig(
            simc_executable="/fake/simc",
            options=SimOptions(target_error=0.5),
            mode="top_gear",
            selected_bag_items=small_set,
            max_combinations=500,
        )
        with patch("top_gear_engine.run_simc_with_input", return_value=MOCK_SIMC_JSON):
            parse_result, sim_results, meta = run_top_gear(sample_text, config)
        assert parse_result.character_class == "druid"
        assert len(sim_results) > 0

    def test_top_gear_max_combos_exceeded_raises(self, sample_text):
        config = TopGearConfig(
            simc_executable="/fake/simc",
            mode="top_gear",
            max_combinations=1,
        )
        with pytest.raises(ValueError, match="Too many combinations"):
            run_top_gear(sample_text, config)

    def test_invalid_selected_items_raise_clear_error(self, sample_text):
        parsed = parse_simc_addon(sample_text)
        bad_item = parsed.bag_items[0]
        config = TopGearConfig(
            simc_executable="/fake/simc",
            options=SimOptions(target_error=0.5),
            mode="top_gear",
            selected_bag_items=[bad_item],
            max_combinations=10,
        )

        def fake_run(simc_input, *_args, **_kwargs):
            if 'profileset."check"+=' in simc_input:
                raise RuntimeError(
                    "simc produced no JSON output. stderr: "
                    "Error: Profileset 'check': Player 'Gotmilkferya': "
                    "Item 'voidlashed_hood' Slot 'head': Invalid type."
                )
            raise RuntimeError("simc produced no JSON output. stderr: startup noise")

        with patch("top_gear_engine.run_simc_with_input", side_effect=fake_run):
            with pytest.raises(RuntimeError, match="Selected items are incompatible"):
                run_top_gear(sample_text, config)


# ---------------------------------------------------------------------------
# run_top_gear — empty alternatives
# ---------------------------------------------------------------------------

class TestRunTopGearNoAlternatives:
    def test_no_bag_items_returns_empty_results(self, sample_text):
        config = TopGearConfig(
            simc_executable="/fake/simc",
            mode="drop_finder",
            selected_bag_items=[],  # force empty
        )
        with patch("top_gear_engine.run_simc_with_input", return_value=MOCK_SIMC_JSON):
            _, sim_results, meta = run_top_gear(sample_text, config)
        # No alternatives => simc not called, empty results
        assert sim_results == []
        assert meta == {}
