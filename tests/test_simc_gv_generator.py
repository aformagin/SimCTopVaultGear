"""
Tests for the parsing functions in simc_gv_generator.py.

Uses sample_simc_string.txt as the primary fixture input. This file exercises
both the new parse_simc_addon() full-parse path and the legacy section-based
helpers (parse_weekly_rewards, define_start_end_bags, etc.).
"""
import os
import pytest

from simc_gv_generator import (
    parse_simc_addon,
    parse_weekly_rewards,
    define_start_end_bags,
    define_start_end_wr,
    GEAR_SLOTS,
    ParsedItem,
    TalentLoadout,
    ParseResult,
)

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "sample_simc_string.txt")


@pytest.fixture(scope="module")
def sample_text():
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def parsed(sample_text):
    return parse_simc_addon(sample_text)


# ---------------------------------------------------------------------------
# Character info
# ---------------------------------------------------------------------------

class TestCharacterInfo:
    def test_class(self, parsed):
        assert parsed.character_class == "druid"

    def test_name(self, parsed):
        assert parsed.character_name == "Gotmilkferya"

    def test_spec(self, parsed):
        assert parsed.spec == "balance"

    def test_active_talents_non_empty(self, parsed):
        assert len(parsed.active_talents) > 10

    def test_active_talents_starts_with_expected(self, parsed):
        assert parsed.active_talents.startswith("CYGA")


# ---------------------------------------------------------------------------
# Equipped gear
# ---------------------------------------------------------------------------

class TestEquippedGear:
    def test_head_parsed(self, parsed):
        assert "head" in parsed.equipped

    def test_head_item_id(self, parsed):
        assert parsed.equipped["head"].item_id == 250024

    def test_head_slot(self, parsed):
        assert parsed.equipped["head"].slot == "head"

    def test_head_origin(self, parsed):
        assert parsed.equipped["head"].origin == "equipped"

    def test_head_ilevel(self, parsed):
        assert parsed.equipped["head"].ilevel == 269

    def test_head_name(self, parsed):
        assert parsed.equipped["head"].name == "Branches of the Luminous Bloom"

    def test_finger1_item_id(self, parsed):
        assert parsed.equipped["finger1"].item_id == 193708

    def test_finger2_item_id(self, parsed):
        assert parsed.equipped["finger2"].item_id == 151311

    def test_main_hand_item_id(self, parsed):
        assert parsed.equipped["main_hand"].item_id == 251201

    def test_trinket1_parsed(self, parsed):
        assert "trinket1" in parsed.equipped

    def test_trinket2_parsed(self, parsed):
        assert "trinket2" in parsed.equipped

    def test_all_expected_slots_present(self, parsed):
        expected = {
            "head", "neck", "shoulder", "back", "chest", "wrist", "hands",
            "waist", "legs", "feet", "finger1", "finger2",
            "trinket1", "trinket2", "main_hand",
        }
        assert expected.issubset(set(parsed.equipped.keys()))

    def test_equipped_slots_are_valid(self, parsed):
        for slot in parsed.equipped:
            assert slot in GEAR_SLOTS

    def test_simc_string_present(self, parsed):
        for item in parsed.equipped.values():
            assert "id=" in item.simc_string

    def test_uid_contains_item_id(self, parsed):
        item = parsed.equipped["head"]
        assert str(item.item_id) in item.uid


# ---------------------------------------------------------------------------
# Talent loadouts
# ---------------------------------------------------------------------------

class TestTalentLoadouts:
    def test_loadout_count(self, parsed):
        # sample has: PVP, Raid ST 12.0.1, Raid Cleave, IV M+ 12.0.1, Raid
        assert len(parsed.talent_loadouts) == 5

    def test_pvp_loadout_exists(self, parsed):
        names = [l.name for l in parsed.talent_loadouts]
        assert "PVP" in names

    def test_raid_st_loadout_exists(self, parsed):
        names = [l.name for l in parsed.talent_loadouts]
        assert "Raid ST 12.0.1" in names

    def test_loadout_talent_strings_non_empty(self, parsed):
        for loadout in parsed.talent_loadouts:
            assert len(loadout.talent_string) > 10

    def test_loadouts_are_TalentLoadout_instances(self, parsed):
        for loadout in parsed.talent_loadouts:
            assert isinstance(loadout, TalentLoadout)


# ---------------------------------------------------------------------------
# Bag items
# ---------------------------------------------------------------------------

class TestBagItems:
    def test_has_bag_items(self, parsed):
        assert len(parsed.bag_items) > 0

    def test_bag_item_origin(self, parsed):
        for item in parsed.bag_items:
            assert item.origin == "bag"

    def test_bag_head_present(self, parsed):
        heads = [i for i in parsed.bag_items if i.slot == "head"]
        assert any(i.item_id == 151336 for i in heads)

    def test_bag_neck_present(self, parsed):
        necks = [i for i in parsed.bag_items if i.slot == "neck"]
        assert len(necks) >= 1

    def test_bag_items_have_simc_string(self, parsed):
        for item in parsed.bag_items:
            assert "id=" in item.simc_string

    def test_bag_items_have_names(self, parsed):
        named = [i for i in parsed.bag_items if i.name]
        assert len(named) > 0

    def test_bag_ring_item_present(self, parsed):
        rings = [i for i in parsed.bag_items if i.slot in ("finger1", "finger2")]
        assert len(rings) >= 1

    def test_bag_item_ilevel_parsed(self, parsed):
        items_with_ilevel = [i for i in parsed.bag_items if i.ilevel > 0]
        assert len(items_with_ilevel) > 0

    def test_bag_item_uid_unique_per_variant(self, parsed):
        # Two entries for the same base item with different bonus_ids should have different uids
        uids = [i.uid for i in parsed.bag_items]
        # At least some uids should be unique (most items differ)
        assert len(set(uids)) > 1


# ---------------------------------------------------------------------------
# Additional character info
# ---------------------------------------------------------------------------

class TestAdditionalInfo:
    def test_catalyst_currencies_parsed(self, parsed):
        assert parsed.catalyst_currencies != ""

    def test_upgrade_currencies_parsed(self, parsed):
        assert parsed.upgrade_currencies != ""

    def test_catalyst_currencies_format(self, parsed):
        # e.g. "3269:8/3378:0/2813:8/3116:8"
        assert ":" in parsed.catalyst_currencies


# ---------------------------------------------------------------------------
# Base profile lines
# ---------------------------------------------------------------------------

class TestBaseProfileLines:
    def test_contains_class_line(self, parsed):
        assert any('druid="' in l for l in parsed.base_profile_lines)

    def test_contains_spec_line(self, parsed):
        assert any(l.startswith("spec=") for l in parsed.base_profile_lines)

    def test_contains_talents_line(self, parsed):
        assert any(l.startswith("talents=") for l in parsed.base_profile_lines)

    def test_contains_head_gear_line(self, parsed):
        assert any("id=250024" in l for l in parsed.base_profile_lines)

    def test_no_section_headers(self, parsed):
        for l in parsed.base_profile_lines:
            assert not l.startswith("###")

    def test_no_pure_comments(self, parsed):
        for l in parsed.base_profile_lines:
            assert not l.startswith("#")


# ---------------------------------------------------------------------------
# Legacy helpers
# ---------------------------------------------------------------------------

class TestLegacyHelpers:
    def test_define_start_end_bags(self, sample_text):
        lines = sample_text.splitlines(keepends=True)
        result = define_start_end_bags(lines)
        assert result is not None
        assert result["start"] < result["end"]

    def test_define_start_end_wr_returns_none_for_new_format(self, sample_text):
        # The sample uses ### Gear from Bags, not ### Weekly Reward Choices
        lines = sample_text.splitlines(keepends=True)
        result = define_start_end_wr(lines)
        assert result is None

    def test_parse_weekly_rewards_extracts_items(self, sample_text):
        lines = sample_text.splitlines(keepends=True)
        bags = define_start_end_bags(lines)
        section = lines[bags["start"]:bags["end"] + 1]
        items = parse_weekly_rewards(section)
        assert len(items) > 0
        for name, gear_line in items:
            assert name
            assert "id=" in gear_line
