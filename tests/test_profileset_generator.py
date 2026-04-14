"""
Tests for profileset_generator.py.

Verifies that simc profileset input is built correctly from the parsed
sample_simc_string.txt for both Drop Finder and Top Gear modes.
"""
import os
import pytest

from simc_gv_generator import parse_simc_addon
from profileset_generator import (
    SimOptions,
    build_base_input,
    generate_drop_finder_input,
    generate_top_gear_input,
    count_top_gear_combinations,
    _make_label,
    _reslot_item,
    _unique_label,
)

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "sample_simc_string.txt")


@pytest.fixture(scope="module")
def sample_text():
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def parsed(sample_text):
    return parse_simc_addon(sample_text)


@pytest.fixture
def options():
    return SimOptions(fight_style="Patchwerk", target_error=0.5, threads=2, max_time=300)


# ---------------------------------------------------------------------------
# build_base_input
# ---------------------------------------------------------------------------

class TestBuildBaseInput:
    def test_contains_fight_style(self, parsed, options):
        base = build_base_input(parsed, options)
        assert "fight_style=Patchwerk" in base

    def test_contains_target_error(self, parsed, options):
        base = build_base_input(parsed, options)
        assert "target_error=0.5" in base

    def test_contains_bloodlust_override(self, parsed, options):
        base = build_base_input(parsed, options)
        assert "override.bloodlust=1" in base

    def test_contains_threads(self, parsed, options):
        base = build_base_input(parsed, options)
        assert "threads=2" in base

    def test_contains_character_class_line(self, parsed, options):
        base = build_base_input(parsed, options)
        assert 'druid="Gotmilkferya"' in base

    def test_contains_spec(self, parsed, options):
        base = build_base_input(parsed, options)
        assert "spec=balance" in base

    def test_contains_equipped_head(self, parsed, options):
        base = build_base_input(parsed, options)
        assert "id=250024" in base

    def test_iterations_omitted_when_zero(self, parsed, options):
        options.iterations = 0
        base = build_base_input(parsed, options)
        assert "iterations=" not in base

    def test_iterations_included_when_set(self, parsed):
        opts = SimOptions(iterations=10000)
        base = build_base_input(parsed, opts)
        assert "iterations=10000" in base


# ---------------------------------------------------------------------------
# generate_drop_finder_input
# ---------------------------------------------------------------------------

class TestDropFinderInput:
    def test_generates_profileset_lines(self, parsed, options):
        simc_input, meta = generate_drop_finder_input(parsed, options)
        assert 'profileset.' in simc_input

    def test_meta_non_empty(self, parsed, options):
        _, meta = generate_drop_finder_input(parsed, options)
        assert len(meta) > 0

    def test_bag_head_in_profilesets(self, parsed, options):
        simc_input, _ = generate_drop_finder_input(parsed, options)
        # Voidlashed Hood (id=151336) is in bags
        assert "id=151336" in simc_input

    def test_bag_neck_in_profilesets(self, parsed, options):
        simc_input, _ = generate_drop_finder_input(parsed, options)
        # Amani Heartstring Pendant (id=265739)
        assert "id=265739" in simc_input

    def test_ring_alternative_gets_finger2_slot(self, parsed, options):
        # Platinum Star Band (id=193708) is equipped in finger1, so the bag
        # version should only appear as finger2 (not finger1 again)
        simc_input, _ = generate_drop_finder_input(parsed, options)
        assert "finger2=" in simc_input

    def test_meta_items_have_positive_ids(self, parsed, options):
        _, meta = generate_drop_finder_input(parsed, options)
        for label, item in meta.items():
            assert item.item_id > 0

    def test_baseline_character_in_output(self, parsed, options):
        simc_input, _ = generate_drop_finder_input(parsed, options)
        assert 'druid="Gotmilkferya"' in simc_input

    def test_profileset_format_correct(self, parsed, options):
        simc_input, _ = generate_drop_finder_input(parsed, options)
        # Each profileset line must follow: profileset."label"+=slot=...
        import re
        matches = re.findall(r'profileset\."[^"]+"\+=[a-z_]+=', simc_input)
        assert len(matches) > 0

    def test_no_duplicate_labels(self, parsed, options):
        _, meta = generate_drop_finder_input(parsed, options)
        labels = list(meta.keys())
        assert len(labels) == len(set(labels))

    def test_subset_of_bags(self, parsed, options):
        # Passing only the first bag item
        one_item = [parsed.bag_items[0]]
        _, meta = generate_drop_finder_input(parsed, options, bag_items=one_item)
        assert len(meta) >= 1

    def test_copy_equipped_enchants_gems_for_ring_target_slot(self, parsed, options):
        ring = next(i for i in parsed.bag_items if i.item_id == 193708)
        options.copy_equipped_enchants_gems = True

        simc_input, _ = generate_drop_finder_input(parsed, options, bag_items=[ring])

        assert "finger2=,id=193708" in simc_input
        assert "enchant_id=7968" in simc_input
        assert "gem_id=240891" in simc_input


# ---------------------------------------------------------------------------
# generate_top_gear_input
# ---------------------------------------------------------------------------

class TestTopGearInput:
    def test_generates_combinations(self, parsed, options):
        small_set = parsed.bag_items[:2]
        simc_input, meta = generate_top_gear_input(
            parsed, options=options, selected_bag_items=small_set
        )
        assert len(meta) > 0

    def test_profilesets_in_output(self, parsed, options):
        small_set = parsed.bag_items[:2]
        simc_input, _ = generate_top_gear_input(
            parsed, options=options, selected_bag_items=small_set
        )
        assert 'profileset.' in simc_input

    def test_max_combinations_raises(self, parsed, options):
        with pytest.raises(ValueError, match="Too many combinations"):
            generate_top_gear_input(parsed, options=options, max_combinations=1)

    def test_max_combinations_not_exceeded(self, parsed, options):
        small_set = parsed.bag_items[:2]
        # Should not raise with generous limit
        simc_input, meta = generate_top_gear_input(
            parsed, options=options, selected_bag_items=small_set, max_combinations=500
        )
        assert meta  # at least one combo

    def test_combo_labels_sequential(self, parsed, options):
        small_set = parsed.bag_items[:2]
        _, meta = generate_top_gear_input(
            parsed, options=options, selected_bag_items=small_set
        )
        for label in meta:
            assert label.startswith("combo_")

    def test_baseline_in_output(self, parsed, options):
        small_set = parsed.bag_items[:1]
        simc_input, _ = generate_top_gear_input(
            parsed, options=options, selected_bag_items=small_set
        )
        assert 'druid="Gotmilkferya"' in simc_input

    def test_top_gear_copies_equipped_enchants_gems_when_enabled(self, parsed, options):
        ring = next(i for i in parsed.bag_items if i.item_id == 193708)
        options.copy_equipped_enchants_gems = True

        simc_input, _ = generate_top_gear_input(
            parsed, options=options, selected_bag_items=[ring], max_combinations=10
        )

        assert "finger2=,id=193708" in simc_input
        assert "enchant_id=7968" in simc_input
        assert "gem_id=240891" in simc_input


# ---------------------------------------------------------------------------
# count_top_gear_combinations
# ---------------------------------------------------------------------------

class TestCountCombinations:
    def test_zero_items_returns_zero(self, parsed):
        count = count_top_gear_combinations(parsed, selected_bag_items=[])
        assert count == 0

    def test_one_item_returns_positive(self, parsed):
        one = [parsed.bag_items[0]]
        count = count_top_gear_combinations(parsed, selected_bag_items=one)
        assert count >= 1

    def test_count_matches_generated_combos(self, parsed, options):
        small_set = parsed.bag_items[:3]
        count = count_top_gear_combinations(parsed, selected_bag_items=small_set)
        _, meta = generate_top_gear_input(
            parsed, options=options, selected_bag_items=small_set, max_combinations=10000
        )
        assert count == len(meta)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_make_label_contains_name(self):
        label = _make_label("Voidlashed Hood", "head")
        assert "Voidlashed_Hood" in label

    def test_make_label_contains_slot(self):
        label = _make_label("Voidlashed Hood", "head")
        assert "head" in label

    def test_make_label_max_length(self):
        long_name = "A" * 100
        label = _make_label(long_name, "head")
        assert len(label) <= 60

    def test_make_label_strips_specials(self):
        label = _make_label("Item's/Name: With Specials!", "neck")
        # Should only contain alphanumeric, underscore, hyphen, space
        import re
        assert re.match(r"^[a-zA-Z0-9_ \-]+$", label)

    def test_reslot_item_changes_slot(self):
        original = "finger1=,id=193708,bonus_id=123"
        result = _reslot_item(original, "finger2")
        assert result.startswith("finger2=")

    def test_reslot_item_preserves_rest(self):
        original = "finger1=,id=193708,bonus_id=123"
        result = _reslot_item(original, "finger2")
        assert "id=193708" in result
        assert "bonus_id=123" in result

    def test_reslot_item_canonicalizes_alias_via_target_slot(self):
        original = "wrists=fallen_kings_cuffs,id=249304,bonus_id=123"
        result = _reslot_item(original, "wrist")
        assert result.startswith("wrist=")
        assert "id=249304" in result

    def test_unique_label_no_conflict(self):
        existing = {}
        result = _unique_label("my_label", existing)
        assert result == "my_label"

    def test_unique_label_with_conflict(self):
        existing = {"my_label": object()}
        result = _unique_label("my_label", existing)
        assert result == "my_label_2"

    def test_unique_label_multiple_conflicts(self):
        existing = {"my_label": object(), "my_label_2": object()}
        result = _unique_label("my_label", existing)
        assert result == "my_label_3"
