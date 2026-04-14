"""
Tests for drop_finder_engine.py
"""
import os
import pytest
from unittest.mock import patch

from drop_finder_engine import (
    CLASS_IDS,
    _class_mask,
    build_item_simc_string,
    get_instances,
    get_encounters,
    get_encounter_items,
    get_ilvl_tracks,
    loot_items_to_parsed,
    generate_droptimizer_input,
    load_drop_sources,
)
from profileset_generator import SimOptions


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "sample_simc_string.txt")


@pytest.fixture(scope="module")
def sample_text():
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return f.read()

SAMPLE_SOURCES = {
    "generated_at": "2026-04-11",
    "season": "Test Season",
    "instances": [
        {
            "id": 100,
            "name": "Test Dungeon",
            "type": "dungeon",
            "encounters": [
                {
                    "id": 10,
                    "name": "Boss Alpha",
                    "items": [
                        {"id": 1001, "name": "Heroic Helmet", "slot": "head", "class_mask": -1},
                        {"id": 1002, "name": "Druid Chest", "slot": "chest",
                         "class_mask": 1 << (11 - 1)},  # druid only (class_id=11)
                        {"id": 1003, "name": "Ring of Power", "slot": "finger1", "class_mask": -1},
                    ],
                },
                {
                    "id": 11,
                    "name": "Boss Beta",
                    "items": [
                        {"id": 1004, "name": "Warrior Axe", "slot": "main_hand",
                         "class_mask": 1 << (1 - 1)},  # warrior only
                        {"id": 1005, "name": "Cloak of Doom", "slot": "back", "class_mask": -1},
                    ],
                },
            ],
        },
        {
            "id": 200,
            "name": "Test Raid",
            "type": "raid",
            "encounters": [
                {
                    "id": 20,
                    "name": "Raid Boss",
                    "items": [
                        {"id": 2001, "name": "Epic Sword", "slot": "main_hand", "class_mask": -1},
                    ],
                },
            ],
        },
    ],
    "ilvl_tracks": {
        "dungeon": [
            {"key": "champion", "label": "Champion", "ilvl": 250},
            {"key": "hero", "label": "Hero", "ilvl": 263},
        ],
        "raid": [
            {"key": "normal", "label": "Normal", "ilvl": 259},
        ],
    },
}


# ---------------------------------------------------------------------------
# _class_mask
# ---------------------------------------------------------------------------

class TestClassMask:
    def test_druid(self):
        mask = _class_mask("druid")
        assert mask == 1 << (11 - 1)

    def test_warrior(self):
        mask = _class_mask("warrior")
        assert mask == 1 << (1 - 1)  # 1

    def test_case_insensitive(self):
        assert _class_mask("Druid") == _class_mask("druid")

    def test_deathknight_no_space(self):
        assert _class_mask("deathknight") == 1 << (6 - 1)

    def test_demonhunter_no_space(self):
        assert _class_mask("demonhunter") == 1 << (12 - 1)

    def test_unknown_class_returns_minus_one(self):
        assert _class_mask("goblin") == -1

    def test_all_classes_have_ids(self):
        for cls in CLASS_IDS:
            assert _class_mask(cls) > 0


# ---------------------------------------------------------------------------
# build_item_simc_string
# ---------------------------------------------------------------------------

class TestBuildItemSimcString:
    def test_basic_format(self):
        s = build_item_simc_string(12345, "head", 263)
        assert s == "head=,id=12345,ilevel=263"

    def test_ring_slot(self):
        s = build_item_simc_string(99, "finger1", 250)
        assert s == "finger1=,id=99,ilevel=250"

    def test_back_slot(self):
        s = build_item_simc_string(777, "back", 276)
        assert s == "back=,id=777,ilevel=276"


# ---------------------------------------------------------------------------
# get_instances
# ---------------------------------------------------------------------------

class TestGetInstances:
    def test_all_instances(self):
        insts = get_instances(SAMPLE_SOURCES)
        assert len(insts) == 2
        names = [i["name"] for i in insts]
        assert "Test Dungeon" in names
        assert "Test Raid" in names

    def test_filter_dungeon(self):
        insts = get_instances(SAMPLE_SOURCES, type_filter="dungeon")
        assert len(insts) == 1
        assert insts[0]["name"] == "Test Dungeon"

    def test_filter_raid(self):
        insts = get_instances(SAMPLE_SOURCES, type_filter="raid")
        assert len(insts) == 1
        assert insts[0]["name"] == "Test Raid"

    def test_instance_has_id_name_type(self):
        insts = get_instances(SAMPLE_SOURCES)
        for inst in insts:
            assert "id" in inst
            assert "name" in inst
            assert "type" in inst

    def test_empty_sources(self):
        assert get_instances({}) == []


# ---------------------------------------------------------------------------
# get_encounters
# ---------------------------------------------------------------------------

class TestGetEncounters:
    def test_returns_encounters(self):
        encs = get_encounters(SAMPLE_SOURCES, 100)
        assert len(encs) == 2
        names = [e["name"] for e in encs]
        assert "Boss Alpha" in names
        assert "Boss Beta" in names

    def test_unknown_instance_returns_empty(self):
        encs = get_encounters(SAMPLE_SOURCES, 9999)
        assert encs == []

    def test_encounter_has_id_name(self):
        encs = get_encounters(SAMPLE_SOURCES, 100)
        for enc in encs:
            assert "id" in enc
            assert "name" in enc


# ---------------------------------------------------------------------------
# get_encounter_items
# ---------------------------------------------------------------------------

class TestGetEncounterItems:
    def test_all_bosses_no_class_filter(self):
        items = get_encounter_items(SAMPLE_SOURCES, 100)
        # Boss Alpha: 3 items, Boss Beta: 2 items = 5 unique
        assert len(items) == 5

    def test_specific_encounter(self):
        items = get_encounter_items(SAMPLE_SOURCES, 100, encounter_id=10)
        assert len(items) == 3
        names = [i["name"] for i in items]
        assert "Heroic Helmet" in names

    def test_class_filter_druid(self):
        items = get_encounter_items(SAMPLE_SOURCES, 100, character_class="druid")
        # Heroic Helmet (-1=all), Druid Chest (druid only), Ring of Power (-1), Cloak of Doom (-1)
        # Warrior Axe (warrior only) should be excluded
        names = [i["name"] for i in items]
        assert "Warrior Axe" not in names
        assert "Druid Chest" in names
        assert "Heroic Helmet" in names

    def test_class_filter_warrior(self):
        items = get_encounter_items(SAMPLE_SOURCES, 100, character_class="warrior")
        names = [i["name"] for i in items]
        assert "Druid Chest" not in names
        assert "Warrior Axe" in names

    def test_no_duplicates_across_bosses(self):
        items = get_encounter_items(SAMPLE_SOURCES, 100)
        ids = [i["id"] for i in items]
        assert len(ids) == len(set(ids))

    def test_unknown_instance_returns_empty(self):
        items = get_encounter_items(SAMPLE_SOURCES, 9999)
        assert items == []


# ---------------------------------------------------------------------------
# get_ilvl_tracks
# ---------------------------------------------------------------------------

class TestGetIlvlTracks:
    def test_dungeon_tracks(self):
        tracks = get_ilvl_tracks(SAMPLE_SOURCES, "dungeon")
        assert len(tracks) == 2
        assert any(t["key"] == "champion" for t in tracks)
        assert any(t["key"] == "hero" for t in tracks)

    def test_raid_tracks(self):
        tracks = get_ilvl_tracks(SAMPLE_SOURCES, "raid")
        assert len(tracks) == 1
        assert tracks[0]["key"] == "normal"

    def test_each_track_has_ilvl(self):
        for track in get_ilvl_tracks(SAMPLE_SOURCES, "dungeon"):
            assert "ilvl" in track
            assert track["ilvl"] > 0

    def test_unknown_type_returns_empty(self):
        assert get_ilvl_tracks(SAMPLE_SOURCES, "pvp") == []


# ---------------------------------------------------------------------------
# loot_items_to_parsed
# ---------------------------------------------------------------------------

class TestLootItemsToParsed:
    def test_converts_to_parsed_items(self):
        raw = [
            {"id": 1001, "name": "Test Helm", "slot": "head", "class_mask": -1},
        ]
        parsed = loot_items_to_parsed(raw, ilvl=263)
        assert len(parsed) == 1
        assert parsed[0].name == "Test Helm"
        assert parsed[0].slot == "head"
        assert parsed[0].item_id == 1001
        assert parsed[0].simc_string == "head=,id=1001,ilevel=263"

    def test_ilvl_in_simc_string(self):
        raw = [{"id": 42, "name": "Ring", "slot": "finger1", "class_mask": -1}]
        parsed = loot_items_to_parsed(raw, ilvl=276)
        assert "ilevel=276" in parsed[0].simc_string

    def test_empty_list(self):
        assert loot_items_to_parsed([], ilvl=263) == []


# ---------------------------------------------------------------------------
# generate_droptimizer_input
# ---------------------------------------------------------------------------

class TestGenerateDroptimizer:
    def test_produces_profilesets(self, sample_text):
        from drop_finder_engine import loot_items_to_parsed
        from simc_gv_generator import parse_simc_addon

        raw = [
            {"id": 1001, "name": "Test Helm", "slot": "head", "class_mask": -1},
            {"id": 1002, "name": "Test Chest", "slot": "chest", "class_mask": -1},
        ]
        parsed_items = loot_items_to_parsed(raw, ilvl=263)
        parse_result = parse_simc_addon(sample_text)

        simc_input, combo_meta = generate_droptimizer_input(
            parse_result, parsed_items, SimOptions(target_error=0.5)
        )
        assert 'profileset."' in simc_input
        assert len(combo_meta) >= 2  # at least one profileset per item

    def test_combo_meta_keys_match_profilesets(self, sample_text):
        from simc_gv_generator import parse_simc_addon

        raw = [{"id": 999, "name": "Magic Ring", "slot": "finger1", "class_mask": -1}]
        parsed_items = loot_items_to_parsed(raw, ilvl=250)
        parse_result = parse_simc_addon(sample_text)

        simc_input, combo_meta = generate_droptimizer_input(
            parse_result, parsed_items, SimOptions()
        )
        for label in combo_meta:
            assert f'profileset."{label}"' in simc_input

    def test_empty_items_returns_base_only(self, sample_text):
        from simc_gv_generator import parse_simc_addon

        parse_result = parse_simc_addon(sample_text)
        simc_input, combo_meta = generate_droptimizer_input(
            parse_result, [], SimOptions()
        )
        assert "profileset" not in simc_input
        assert combo_meta == {}

    def test_ilevel_in_simc_input(self, sample_text):
        from simc_gv_generator import parse_simc_addon

        raw = [{"id": 1234, "name": "Hat", "slot": "head", "class_mask": -1}]
        parsed_items = loot_items_to_parsed(raw, ilvl=263)
        parse_result = parse_simc_addon(sample_text)

        simc_input, _ = generate_droptimizer_input(parse_result, parsed_items, SimOptions())
        assert "ilevel=263" in simc_input

    def test_copy_equipped_ring_affixes_when_enabled(self, sample_text):
        from simc_gv_generator import parse_simc_addon

        raw = [{"id": 999, "name": "Magic Ring", "slot": "finger1", "class_mask": -1}]
        parsed_items = loot_items_to_parsed(raw, ilvl=250)
        parse_result = parse_simc_addon(sample_text)

        simc_input, combo_meta = generate_droptimizer_input(
            parse_result,
            parsed_items,
            SimOptions(copy_equipped_enchants_gems=True),
        )

        assert len(combo_meta) == 2
        assert "enchant_id=7969" in simc_input
        assert "gem_id=240983" in simc_input
        assert "enchant_id=7968" in simc_input
        assert "gem_id=240891" in simc_input


# ---------------------------------------------------------------------------
# load_drop_sources (integration with real file)
# ---------------------------------------------------------------------------

class TestLoadDropSources:
    def test_loads_real_file(self):
        sources = load_drop_sources()
        assert "instances" in sources
        assert "ilvl_tracks" in sources
        assert len(sources["instances"]) > 0

    def test_instances_have_required_fields(self):
        sources = load_drop_sources()
        for inst in sources["instances"]:
            assert "id" in inst
            assert "name" in inst
            assert "type" in inst
            assert "encounters" in inst

    def test_encounters_have_items(self):
        sources = load_drop_sources()
        total_items = sum(
            len(enc.get("items", []))
            for inst in sources["instances"]
            for enc in inst["encounters"]
        )
        assert total_items > 0

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_drop_sources(data_dir=str(tmp_path))
