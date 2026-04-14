"""
Drop Finder engine: loads drop_sources.json and generates simc profilesets
for items that can drop from selected dungeons/raids.

Simc items are specified as:   slot=,id=ITEM_ID,ilevel=ILVL
SimulationCraft handles stat scaling internally given the item ID + ilevel.
"""

import json
import os
import re
from typing import Optional

from simc_gv_generator import ParsedItem, ParseResult, PAIRED_SLOTS
from profileset_generator import (
    SimOptions,
    build_base_input,
    _reslot_item,
    _make_label,
    _unique_label,
    _resolve_target_slots,
)
from item_affixes import apply_reference_item_affixes

# ---------------------------------------------------------------------------
# WoW class name -> class ID mapping (matches SimC character_class strings)
# ---------------------------------------------------------------------------

CLASS_IDS: dict = {
    "warrior": 1,
    "paladin": 2,
    "hunter": 3,
    "rogue": 4,
    "priest": 5,
    "deathknight": 6,
    "shaman": 7,
    "mage": 8,
    "warlock": 9,
    "monk": 10,
    "druid": 11,
    "demonhunter": 12,
    "evoker": 13,
}


def _class_mask(character_class: str) -> int:
    """Return the bitmask for a character class string, or -1 if unknown."""
    cls_id = CLASS_IDS.get(character_class.lower().replace(" ", "").replace("_", ""))
    if cls_id is None:
        return -1
    return 1 << (cls_id - 1)


# ---------------------------------------------------------------------------
# Load / query drop_sources.json
# ---------------------------------------------------------------------------

def load_drop_sources(data_dir: str = "data") -> dict:
    """Load drop_sources.json.  Returns the parsed dict."""
    path = os.path.join(data_dir, "drop_sources.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"drop_sources.json not found at {path}. "
            "Run scripts/generate_drop_sources.py first."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_instances(sources: dict, type_filter: Optional[str] = None) -> list:
    """Return list of {id, name, type} dicts, optionally filtered by type.

    Args:
        sources:     drop_sources dict from load_drop_sources()
        type_filter: "dungeon", "raid", or None (all)
    """
    instances = sources.get("instances", [])
    if type_filter:
        instances = [i for i in instances if i.get("type") == type_filter]
    return [{"id": i["id"], "name": i["name"], "type": i.get("type", "")}
            for i in instances]


def get_encounters(sources: dict, instance_id: int) -> list:
    """Return list of {id, name} for encounters within the given instance."""
    for inst in sources.get("instances", []):
        if inst["id"] == instance_id:
            return [{"id": e["id"], "name": e["name"]}
                    for e in inst.get("encounters", [])]
    return []


def get_ilvl_tracks(sources: dict, instance_type: str) -> list:
    """Return the list of ilvl track dicts for the given instance type.

    Each entry: {"key": str, "label": str, "ilvl": int}
    """
    return sources.get("ilvl_tracks", {}).get(instance_type, [])


def get_encounter_items(
    sources: dict,
    instance_id: int,
    encounter_id: Optional[int] = None,
    character_class: Optional[str] = None,
) -> list:
    """Return raw item dicts (id, name, slot, class_mask) for an instance/encounter.

    Args:
        sources:         drop_sources dict
        instance_id:     which dungeon/raid
        encounter_id:    specific boss, or None for all bosses
        character_class: SimC class string (e.g. "druid") — filters by class_mask
    """
    char_mask = _class_mask(character_class) if character_class else -1

    result = []
    seen_ids = set()

    for inst in sources.get("instances", []):
        if inst["id"] != instance_id:
            continue
        for enc in inst.get("encounters", []):
            if encounter_id is not None and enc["id"] != encounter_id:
                continue
            for item in enc.get("items", []):
                item_id = item["id"]
                if item_id in seen_ids:
                    continue
                # class_mask: -1 = all classes; otherwise check bitmask
                item_mask = item.get("class_mask", -1)
                if item_mask != -1 and char_mask != -1:
                    if not (item_mask & char_mask):
                        continue  # item not usable by this class
                seen_ids.add(item_id)
                result.append(item)
        break  # found the instance

    return result


# ---------------------------------------------------------------------------
# ParsedItem construction for loot-table items
# ---------------------------------------------------------------------------

def build_item_simc_string(item_id: int, slot: str, ilvl: int) -> str:
    """Return a SimC item string for a hypothetical drop.

    Format:  slot=,id=ITEM_ID,ilevel=ILVL
    SimulationCraft scales item stats to the given ilvl automatically.
    """
    return f"{slot}=,id={item_id},ilevel={ilvl}"


def loot_items_to_parsed(items: list, ilvl: int) -> list:
    """Convert raw loot-table item dicts to ParsedItem objects at the given ilvl."""
    parsed = []
    for raw in items:
        slot = raw["slot"]
        item_id = raw["id"]
        simc_str = build_item_simc_string(item_id, slot, ilvl)
        parsed.append(ParsedItem(
            name=raw["name"],
            simc_string=simc_str,
            slot=slot,
            item_id=item_id,
        ))
    return parsed


# ---------------------------------------------------------------------------
# Profileset generation
# ---------------------------------------------------------------------------

def generate_droptimizer_input(
    parse_result: ParseResult,
    items: list,
    options: Optional[SimOptions] = None,
) -> tuple:
    """Generate simc profileset input for Drop Finder mode.

    Each item is tested independently against the current-gear baseline.
    For paired slots (rings, trinkets) the item gets one profileset per
    valid physical sub-slot.

    Args:
        parse_result: ParseResult from parse_simc_addon()
        items:        list of ParsedItem (from loot_items_to_parsed())
        options:      SimOptions controlling fight parameters

    Returns:
        (simc_input_string, combo_metadata)
        combo_metadata: {profileset_label -> ParsedItem}
    """
    if options is None:
        options = SimOptions()

    base = build_base_input(parse_result, options)
    profileset_lines = []
    combo_metadata = {}

    for item in items:
        target_slots = _resolve_target_slots(item.slot, item, parse_result.equipped)
        for target_slot in target_slots:
            gear_str = _reslot_item(item.simc_string, target_slot)
            if options.copy_equipped_enchants_gems:
                equipped_item = parse_result.equipped.get(target_slot)
                if equipped_item:
                    gear_str = apply_reference_item_affixes(gear_str, equipped_item.simc_string)
            label = _make_label(item.name or f"item_{item.item_id}", target_slot)
            label = _unique_label(label, combo_metadata)
            profileset_lines.append(f'profileset."{label}"+={gear_str}')
            combo_metadata[label] = item

    if not profileset_lines:
        return base, combo_metadata

    simc_input = base + "\n\n" + "\n".join(profileset_lines) + "\n"
    return simc_input, combo_metadata
