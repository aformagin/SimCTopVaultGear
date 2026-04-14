"""
Drop Finder Engine: handles loot table loading, filtering, and item generation.
"""
import os
import json
from typing import Optional

from simc_gv_generator import ParsedItem, ParseResult
from profileset_generator import (
    SimOptions,
    generate_drop_finder_input,
)


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
    if not character_class:
        return -1
    cls_id = CLASS_IDS.get(character_class.lower().replace(" ", "").replace("_", ""))
    if cls_id is None:
        return -1
    return 1 << (cls_id - 1)


# Re-export generate_drop_finder_input as generate_droptimizer_input for compatibility
def generate_droptimizer_input(
    parse_result: ParseResult,
    items: list,
    options: Optional[SimOptions] = None,
) -> tuple:
    """Generate simc profileset input for Drop Finder mode.

    Wrapper around profileset_generator.generate_drop_finder_input.
    """
    return generate_drop_finder_input(parse_result, options, bag_items=items)


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
    """Return list of instance dicts {id, name} for the given type."""
    instances = sources.get("instances", [])
    if type_filter:
        instances = [i for i in instances if i.get("type") == type_filter]
    return instances


def get_encounters(sources: dict, instance_id: int) -> list:
    """Return list of encounter dicts {id, name} for the instance."""
    for inst in sources.get("instances", []):
        if inst["id"] == instance_id:
            return inst.get("encounters", [])
    return []


def get_encounter_items(
    sources: dict,
    instance_id: int,
    encounter_id: Optional[int] = None,
    character_class: Optional[str] = None,
) -> list:
    """Return list of raw item dicts for the instance/encounter.

    If encounter_id is None, returns items from ALL bosses in the instance.
    If character_class is provided, filters items to those usable by that class.
    """
    char_mask = _class_mask(character_class) if character_class else -1
    items = []
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
                        continue
                
                seen_ids.add(item_id)
                items.append(item)
        break
    return items


def get_ilvl_tracks(sources: dict, instance_type: str = "dungeon") -> list:
    """Return list of track dicts {label, ilvl} for the instance type."""
    return sources.get("ilvl_tracks", {}).get(instance_type, [])


def loot_items_to_parsed(loot_items: list, ilvl: int) -> list[ParsedItem]:
    """Convert raw loot-table item dicts into ParsedItem objects for simulation."""
    parsed = []
    for raw in loot_items:
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


def build_item_simc_string(item_id: int, slot: str, ilvl: int) -> str:
    """Build a basic simc item line for a loot item at a specific ilvl."""
    return f"{slot}=,id={item_id},ilevel={ilvl}"
