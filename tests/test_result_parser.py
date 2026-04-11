"""
Tests for result_parser.py.

Uses a minimal mock of simc json2 output so no actual simc binary is needed.
"""
import json
import pytest

from result_parser import parse_results, parse_results_from_string, SimResult


# ---------------------------------------------------------------------------
# Fixtures / shared data
# ---------------------------------------------------------------------------

BASELINE_DPS = 100_000.0

MOCK_JSON = {
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
                {
                    "name": "combo_5",
                    "mean_dps": 105_000.0,
                    "median_dps": 105_000.0,
                    "error": 700.0,
                },
            ]
        },
    }
}

# simc raw format uses "mean" / "median" keys (not "mean_dps")
MOCK_JSON_RAW_KEYS = {
    "sim": {
        "players": [{
            "collected_data": {
                "dps": {"mean": BASELINE_DPS, "error": 500.0}
            }
        }],
        "profilesets": {
            "results": [
                {"name": "ps_a", "mean": 102_000.0, "error": 0.0},
                {"name": "ps_b", "median": 99_000.0, "error": 0.0},
            ]
        },
    }
}

MOCK_JSON_NO_PROFILESETS = {
    "sim": {
        "players": [{
            "collected_data": {"dps": {"mean": BASELINE_DPS, "error": 500.0}}
        }],
        "profilesets": {},
    }
}

MOCK_JSON_NO_PLAYERS = {
    "sim": {"players": []}
}


# ---------------------------------------------------------------------------
# parse_results
# ---------------------------------------------------------------------------

class TestParseResults:
    def test_returns_list(self):
        results = parse_results(MOCK_JSON)
        assert isinstance(results, list)

    def test_baseline_included(self):
        results = parse_results(MOCK_JSON)
        labels = [r.label for r in results]
        assert "Baseline" in labels

    def test_baseline_delta_zero(self):
        results = parse_results(MOCK_JSON)
        baseline = next(r for r in results if r.label == "Baseline")
        assert baseline.delta == 0.0
        assert baseline.delta_pct == 0.0

    def test_baseline_dps_correct(self):
        results = parse_results(MOCK_JSON)
        baseline = next(r for r in results if r.label == "Baseline")
        assert baseline.dps == pytest.approx(BASELINE_DPS)

    def test_baseline_error_correct(self):
        results = parse_results(MOCK_JSON)
        baseline = next(r for r in results if r.label == "Baseline")
        assert baseline.dps_error == pytest.approx(500.0)

    def test_total_count(self):
        results = parse_results(MOCK_JSON)
        assert len(results) == 4  # baseline + 3 profilesets

    def test_sorted_descending_by_dps(self):
        results = parse_results(MOCK_JSON)
        dps_values = [r.dps for r in results]
        assert dps_values == sorted(dps_values, reverse=True)

    def test_best_result_is_combo_5(self):
        results = parse_results(MOCK_JSON)
        assert results[0].label == "combo_5"
        assert results[0].dps == pytest.approx(105_000.0)

    def test_positive_delta_for_upgrade(self):
        results = parse_results(MOCK_JSON)
        hood = next(r for r in results if r.label == "Voidlashed_Hood_head")
        assert hood.delta == pytest.approx(3_000.0)

    def test_positive_delta_pct_for_upgrade(self):
        results = parse_results(MOCK_JSON)
        hood = next(r for r in results if r.label == "Voidlashed_Hood_head")
        assert hood.delta_pct == pytest.approx(3.0)

    def test_negative_delta_for_downgrade(self):
        results = parse_results(MOCK_JSON)
        pendant = next(r for r in results if r.label == "Amani_Heartstring_Pendant_neck")
        assert pendant.delta == pytest.approx(-2_000.0)

    def test_negative_delta_pct_for_downgrade(self):
        results = parse_results(MOCK_JSON)
        pendant = next(r for r in results if r.label == "Amani_Heartstring_Pendant_neck")
        assert pendant.delta_pct == pytest.approx(-2.0)

    def test_error_margin_preserved(self):
        results = parse_results(MOCK_JSON)
        hood = next(r for r in results if r.label == "Voidlashed_Hood_head")
        assert hood.dps_error == pytest.approx(600.0)

    def test_all_results_are_simresult_instances(self):
        results = parse_results(MOCK_JSON)
        for r in results:
            assert isinstance(r, SimResult)

    def test_empty_players_returns_empty_list(self):
        assert parse_results(MOCK_JSON_NO_PLAYERS) == []

    def test_no_profilesets_returns_baseline_only(self):
        results = parse_results(MOCK_JSON_NO_PROFILESETS)
        assert len(results) == 1
        assert results[0].label == "Baseline"

    def test_custom_baseline_label(self):
        results = parse_results(MOCK_JSON, baseline_label="Current Gear")
        labels = [r.label for r in results]
        assert "Current Gear" in labels
        assert "Baseline" not in labels

    def test_raw_mean_key_accepted(self):
        results = parse_results(MOCK_JSON_RAW_KEYS)
        ps_a = next(r for r in results if r.label == "ps_a")
        assert ps_a.dps == pytest.approx(102_000.0)

    def test_raw_median_key_accepted(self):
        results = parse_results(MOCK_JSON_RAW_KEYS)
        ps_b = next(r for r in results if r.label == "ps_b")
        assert ps_b.dps == pytest.approx(99_000.0)


# ---------------------------------------------------------------------------
# parse_results_from_string
# ---------------------------------------------------------------------------

class TestParseResultsFromString:
    def test_matches_dict_parse(self):
        json_str = json.dumps(MOCK_JSON)
        from_str = parse_results_from_string(json_str)
        from_dict = parse_results(MOCK_JSON)
        assert len(from_str) == len(from_dict)
        for a, b in zip(from_str, from_dict):
            assert a.label == b.label
            assert a.dps == pytest.approx(b.dps)

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            parse_results_from_string("not valid json {")
