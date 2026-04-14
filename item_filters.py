"""
Helpers for class-based armor compatibility filtering.
"""

import json
import os
from typing import Optional

from simc_gv_generator import ParsedItem


# Blizzard itemClass for armor items in equippable-items-full.json.
ARMOR_ITEM_CLASS = 4

# Blizzard armor itemSubClass values.
ARMOR_SUBCLASS_CLOTH = 1
ARMOR_SUBCLASS_LEATHER = 2
ARMOR_SUBCLASS_MAIL = 3
ARMOR_SUBCLASS_PLATE = 4

# Slots where armor proficiency matters.
ARMOR_PROFICIENCY_SLOTS = frozenset({
    "head",
    "shoulder",
    "chest",
    "wrist",
    "hands",
    "waist",
    "legs",
    "feet",
})

CLASS_ARMOR_PROFICIENCY = {
    "mage": ARMOR_SUBCLASS_CLOTH,
    "priest": ARMOR_SUBCLASS_CLOTH,
    "warlock": ARMOR_SUBCLASS_CLOTH,
    "demonhunter": ARMOR_SUBCLASS_LEATHER,
    "druid": ARMOR_SUBCLASS_LEATHER,
    "monk": ARMOR_SUBCLASS_LEATHER,
    "rogue": ARMOR_SUBCLASS_LEATHER,
    "evoker": ARMOR_SUBCLASS_MAIL,
    "hunter": ARMOR_SUBCLASS_MAIL,
    "shaman": ARMOR_SUBCLASS_MAIL,
    "deathknight": ARMOR_SUBCLASS_PLATE,
    "paladin": ARMOR_SUBCLASS_PLATE,
    "warrior": ARMOR_SUBCLASS_PLATE,
}


def load_equippable_item_metadata(data_dir: str = "data") -> dict[int, dict]:
    """Return a mapping of item_id -> metadata from equippable-items-full.json."""
    path = os.path.join(data_dir, "_cache", "equippable-items-full.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"equippable-items-full.json not found at {path}. "
            "Run scripts/generate_drop_sources.py first."
        )

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    items = raw if isinstance(raw, list) else raw.get("items") or raw.get("data") or []
    return {item["id"]: item for item in items if "id" in item}


def is_item_armor_compatible(
    item: ParsedItem,
    character_class: Optional[str],
    item_metadata: Optional[dict[int, dict]],
) -> bool:
    """Return whether an item matches the class armor proficiency.

    Unknown classes or missing metadata default to True so the app stays usable
    even without the local cache.
    """
    if not character_class or not item_metadata:
        return True
    if item.slot not in ARMOR_PROFICIENCY_SLOTS:
        return True

    required_subclass = CLASS_ARMOR_PROFICIENCY.get(character_class.lower())
    if required_subclass is None:
        return True

    meta = item_metadata.get(item.item_id)
    if not meta:
        return True
    if meta.get("itemClass") != ARMOR_ITEM_CLASS:
        return True

    return meta.get("itemSubClass") == required_subclass


def is_raw_item_armor_compatible(
    raw_item: dict,
    character_class: Optional[str],
    item_metadata: Optional[dict[int, dict]],
) -> bool:
    """Variant of armor filtering for raw item dicts from drop_sources.json."""
    if not raw_item:
        return True
    return is_item_armor_compatible(
        ParsedItem(
            slot=raw_item.get("slot", ""),
            item_id=raw_item.get("id", 0),
            simc_string="",
            name=raw_item.get("name", ""),
        ),
        character_class,
        item_metadata,
    )
