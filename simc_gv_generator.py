import os
import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Gear slots that affect DPS
GEAR_SLOTS = frozenset({
    "head", "neck", "shoulder", "back", "chest", "wrist", "hands",
    "waist", "legs", "feet", "finger1", "finger2", "trinket1", "trinket2",
    "main_hand", "off_hand",
})

# Common slot aliases seen in addon exports or hand-edited SimC strings.
SLOT_ALIASES = {
    "wrists": "wrist",
    "shoulders": "shoulder",
    "waists": "waist",
    "mainhand": "main_hand",
    "offhand": "off_hand",
}

# Paired slot base name -> (slot1, slot2)
PAIRED_SLOTS = {
    "finger": ("finger1", "finger2"),
    "trinket": ("trinket1", "trinket2"),
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ParsedItem:
    slot: str           # canonical slot, e.g. "head", "finger1"
    item_id: int
    simc_string: str    # full simc item line, e.g. "head=,id=250024,bonus_id=..."
    name: str = ""      # human-readable name from preceding comment
    ilevel: int = 0     # item level from preceding comment
    origin: str = "equipped"  # "equipped", "bag", or "vault"

    @property
    def uid(self) -> str:
        """Unique identifier based on item_id and bonus_ids."""
        m = re.search(r"bonus_id=([\d/]+)", self.simc_string)
        bonus = m.group(1).replace("/", ":") if m else ""
        return f"{self.item_id}_{bonus}" if bonus else str(self.item_id)


@dataclass
class TalentLoadout:
    name: str
    talent_string: str


@dataclass
class ParseResult:
    character_class: str        # e.g. "druid"
    character_name: str         # e.g. "Gotmilkferya"
    spec: str                   # e.g. "balance"
    active_talents: str         # active talent string
    talent_loadouts: list       # list[TalentLoadout]
    equipped: dict              # slot -> ParsedItem (GEAR_SLOTS only)
    bag_items: list             # list[ParsedItem]
    base_profile_lines: list    # all active (non-comment, non-section) lines
    catalyst_currencies: str    # raw catalyst_currencies string
    upgrade_currencies: str     # raw upgrade_currencies string


# ---------------------------------------------------------------------------
# Full-parse API (used by profileset / Top Gear pipeline)
# ---------------------------------------------------------------------------

def parse_simc_addon(text: str) -> ParseResult:
    """Parse a SimulationCraft addon export string into a ParseResult.

    Handles both old (### Weekly Reward Choices) and new (### Gear from Bags)
    SimC addon formats.  Extracts:
      - Character info (class, name, spec, level, race, …)
      - Active talents and saved talent loadouts
      - Equipped gear (structured, per-slot)
      - Bag / vault alternative items
      - Catalyst and upgrade currency strings
      - base_profile_lines: every active line needed to reconstruct a valid
        simc input for the baseline character
    """
    lines = text.splitlines()

    character_class = ""
    character_name = ""
    spec = ""
    active_talents = ""
    talent_loadouts = []
    equipped = {}
    bag_items = []
    base_profile_lines = []
    catalyst_currencies = ""
    upgrade_currencies = ""

    in_bags = False           # ### Gear from Bags  OR  ### Weekly Reward Choices
    current_origin = "bag"
    in_additional = False     # ### Additional Character Info
    pending_item_name = ""
    pending_item_ilevel = 0
    pending_loadout_name = None

    for line in lines:
        stripped = line.strip()

        # --- Section header detection ---
        if stripped.startswith("###"):
            header = stripped.lstrip("#").strip()
            if "Gear from Bags" in header:
                in_bags = True
                current_origin = "bag"
                in_additional = False
            elif "Weekly Reward Choices" in header:
                in_bags = True
                current_origin = "vault"
                in_additional = False
            elif "Additional Character Info" in header:
                in_bags = False
                in_additional = True
            else:
                in_bags = False
                in_additional = False
            continue

        # --- Additional Character Info section ---
        if in_additional:
            m = re.match(r"#\s*catalyst_currencies=(.*)", stripped)
            if m:
                catalyst_currencies = m.group(1).strip()
                continue
            m = re.match(r"#\s*upgrade_currencies=(.*)", stripped)
            if m:
                upgrade_currencies = m.group(1).strip()
            continue

        # --- Bags / Vault section ---
        if in_bags:
            if not stripped or stripped == "#":
                continue
            name_match = re.match(r"#\s+(.+?)\s+\((\d+)\)\s*$", stripped)
            if name_match:
                pending_item_name = name_match.group(1)
                pending_item_ilevel = int(name_match.group(2))
                continue
            gear_match = re.match(r"#\s+(\w+=.*id=\d+.*)", stripped)
            if gear_match:
                item = _parse_item_string(
                    gear_match.group(1), current_origin, pending_item_name, pending_item_ilevel
                )
                if item:
                    bag_items.append(item)
                pending_item_name = ""
                pending_item_ilevel = 0
            continue

        # --- Main section ---
        if stripped.startswith("#"):
            m = re.match(r"#\s+Saved Loadout:\s+(.+)", stripped)
            if m:
                pending_loadout_name = m.group(1).strip()
                continue
            m = re.match(r"#\s+talents=(.+)", stripped)
            if m and pending_loadout_name:
                talent_loadouts.append(TalentLoadout(
                    name=pending_loadout_name,
                    talent_string=m.group(1).strip(),
                ))
                pending_loadout_name = None
                continue
            name_match = re.match(r"#\s+(.+?)\s+\((\d+)\)\s*$", stripped)
            if name_match:
                pending_item_name = name_match.group(1)
                pending_item_ilevel = int(name_match.group(2))
            else:
                pending_loadout_name = None
            continue

        # --- Non-comment active lines ---
        if not stripped:
            continue

        pending_loadout_name = None

        # Character class/name: druid="Gotmilkferya"
        m = re.match(r'(\w+)="([^"]+)"', stripped)
        if m:
            character_class = m.group(1)
            character_name = m.group(2)
            base_profile_lines.append(stripped)
            continue

        # Active talent string
        m = re.match(r"talents=(.+)", stripped)
        if m:
            active_talents = m.group(1).strip()
            base_profile_lines.append(stripped)
            continue

        # Spec
        m = re.match(r"spec=(\w+)", stripped)
        if m:
            spec = m.group(1)
            base_profile_lines.append(stripped)
            continue

        # Gear lines in GEAR_SLOTS with an item id
        slot = _extract_slot(stripped)
        if slot and slot in GEAR_SLOTS and "id=" in stripped:
            item = _parse_item_string(stripped, "equipped", pending_item_name, pending_item_ilevel)
            if item:
                equipped[slot] = item
            pending_item_name = ""
            pending_item_ilevel = 0
            base_profile_lines.append(stripped)
            continue

        # Everything else (level=, race=, region=, server=, role=, professions=, tabard=, …)
        base_profile_lines.append(stripped)

    return ParseResult(
        character_class=character_class,
        character_name=character_name,
        spec=spec,
        active_talents=active_talents,
        talent_loadouts=talent_loadouts,
        equipped=equipped,
        bag_items=bag_items,
        base_profile_lines=base_profile_lines,
        catalyst_currencies=catalyst_currencies,
        upgrade_currencies=upgrade_currencies,
    )


def _extract_slot(line: str) -> Optional[str]:
    m = re.match(r"(\w+)=", line)
    if not m:
        return None
    return SLOT_ALIASES.get(m.group(1), m.group(1))


def _parse_item_string(
    line: str,
    origin: str,
    name: str = "",
    ilevel: int = 0,
) -> Optional[ParsedItem]:
    slot = _extract_slot(line)
    if not slot:
        return None
    m = re.search(r"id=(\d+)", line)
    if not m:
        return None
    return ParsedItem(
        slot=slot,
        item_id=int(m.group(1)),
        simc_string=line,
        name=name,
        ilevel=ilevel,
        origin=origin,
    )
