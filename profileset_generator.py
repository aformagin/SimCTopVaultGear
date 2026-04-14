"""
Build SimulationCraft profileset input from parsed addon data.

Supports two modes:
  - drop_finder : one profileset per alternative item (test each independently,
                  like Raidbots Droptimizer).
  - top_gear    : Cartesian product of all alternatives per slot (true Top Gear).

The generated string is piped to simc via stdin:
    simc json2=stdout -  <  <(profileset_generator output)
"""
import itertools
import re
from dataclasses import dataclass, field
from typing import Optional

from simc_gv_generator import ParseResult, ParsedItem, GEAR_SLOTS, PAIRED_SLOTS
from item_affixes import apply_reference_item_affixes


@dataclass
class SimOptions:
    fight_style: str = "Patchwerk"
    desired_targets: int = 1
    max_time: int = 300
    target_error: float = 0.2
    threads: int = 4
    iterations: int = 0   # 0 = use target_error, >0 = fixed iterations
    copy_equipped_enchants_gems: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_base_input(result: ParseResult, options: SimOptions) -> str:
    """Return the simc option block + baseline character profile as a string."""
    lines = []

    # Global sim options
    if options.iterations > 0:
        lines.append(f"iterations={options.iterations}")
    lines.append(f"target_error={options.target_error}")
    lines.append(f"fight_style={options.fight_style}")
    lines.append(f"desired_targets={options.desired_targets}")
    lines.append(f"max_time={options.max_time}")
    lines.append(f"threads={options.threads}")
    lines.append("override.bloodlust=1")
    lines.append("")

    # Baseline character (all active lines including equipped gear)
    lines.extend(result.base_profile_lines)

    return "\n".join(lines)


def generate_drop_finder_input(
    result: ParseResult,
    options: Optional[SimOptions] = None,
    bag_items: Optional[list] = None,
) -> tuple:
    """Generate simc profileset input for Drop Finder (Droptimizer) mode.

    Each bag item is tested independently against the current-gear baseline.
    For paired slots (rings, trinkets) the item gets one profileset per
    valid physical sub-slot.

    Args:
        result:    ParseResult from addon_parser.parse_simc_addon()
        options:   SimOptions controlling fight parameters
        bag_items: items to test (default: all result.bag_items)

    Returns:
        (simc_input_string, combo_metadata)
        combo_metadata: {profileset_label -> ParsedItem}
    """
    if options is None:
        options = SimOptions()
    if bag_items is None:
        bag_items = result.bag_items

    base = build_base_input(result, options)
    profileset_lines = []
    combo_metadata = {}

    for bag_item in bag_items:
        target_slots = _resolve_target_slots(bag_item.slot, bag_item, result.equipped)
        for target_slot in target_slots:
            gear_str = _reslot_item(bag_item.simc_string, target_slot)
            if options.copy_equipped_enchants_gems:
                equipped_item = result.equipped.get(target_slot)
                if equipped_item:
                    gear_str = apply_reference_item_affixes(gear_str, equipped_item.simc_string)
            label = _make_label(bag_item.name or f"item_{bag_item.item_id}", target_slot)
            # Ensure label uniqueness
            label = _unique_label(label, combo_metadata)
            profileset_lines.append(f'profileset."{label}"+={gear_str}')
            combo_metadata[label] = bag_item

    if not profileset_lines:
        return base, combo_metadata

    simc_input = base + "\n\n" + "\n".join(profileset_lines) + "\n"
    return simc_input, combo_metadata


def generate_top_gear_input(
    result: ParseResult,
    options: Optional[SimOptions] = None,
    selected_bag_items: Optional[list] = None,
    max_combinations: int = 500,
) -> tuple:
    """Generate simc profileset input for Top Gear mode.

    Builds the Cartesian product of alternatives per physical slot so every
    possible gear combination is simulated in a single simc run.

    Args:
        result:              ParseResult from addon_parser
        options:             SimOptions (default Patchwerk 300s)
        selected_bag_items:  items to include (default: all result.bag_items)
        max_combinations:    raise ValueError if this is exceeded

    Returns:
        (simc_input_string, combo_metadata)
        combo_metadata: {profileset_label -> list[ParsedItem]}

    Raises:
        ValueError: if number of combinations exceeds max_combinations
    """
    if options is None:
        options = SimOptions()
    if selected_bag_items is None:
        selected_bag_items = result.bag_items

    base = build_base_input(result, options)

    # Build per-physical-slot alternatives: slot -> [ParsedItem, ...]
    slot_alts = _build_physical_slot_alternatives(selected_bag_items, result.equipped)

    if not slot_alts:
        return base, {}

    # Each slot option list: None (keep baseline) + its alternatives
    slot_names = list(slot_alts.keys())
    option_lists = [[None] + slot_alts[s] for s in slot_names]

    # Cartesian product, skip all-None (= unmodified baseline)
    all_combos = [
        c for c in itertools.product(*option_lists)
        if any(item is not None for item in c)
    ]

    if len(all_combos) > max_combinations:
        raise ValueError(
            f"Too many combinations: {len(all_combos)} > {max_combinations}. "
            "Reduce selected items or increase max_combinations."
        )

    profileset_lines = []
    combo_metadata = {}

    for idx, combo in enumerate(all_combos):
        label = f"combo_{idx}"
        changed_items = []
        for slot_name, item in zip(slot_names, combo):
            if item is None:
                continue
            gear_str = _reslot_item(item.simc_string, slot_name)
            if options.copy_equipped_enchants_gems:
                equipped_item = result.equipped.get(slot_name)
                if equipped_item:
                    gear_str = apply_reference_item_affixes(gear_str, equipped_item.simc_string)
            profileset_lines.append(f'profileset."{label}"+={gear_str}')
            changed_items.append(item)
        combo_metadata[label] = changed_items

    if not profileset_lines:
        return base, combo_metadata

    simc_input = base + "\n\n" + "\n".join(profileset_lines) + "\n"
    return simc_input, combo_metadata


def count_top_gear_combinations(
    result: ParseResult,
    selected_bag_items: Optional[list] = None,
) -> int:
    """Return the number of Top Gear combinations without generating input."""
    if selected_bag_items is None:
        selected_bag_items = result.bag_items

    slot_alts = _build_physical_slot_alternatives(selected_bag_items, result.equipped)
    if not slot_alts:
        return 0

    total = 1
    for items in slot_alts.values():
        total *= len(items) + 1  # +1 for "keep baseline"
    return total - 1  # subtract 1 for the all-baseline non-combination


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_physical_slot_alternatives(bag_items: list, equipped: dict) -> dict:
    """Map each physical slot to the list of bag items that can go in it."""
    slot_alts: dict = {}
    for item in bag_items:
        target_slots = _resolve_target_slots(item.slot, item, equipped)
        for ts in target_slots:
            if ts not in GEAR_SLOTS:
                raise ValueError(
                    f"Unsupported gear slot '{item.slot}' for item '{item.name or item.item_id}'."
                )
            if ts not in slot_alts:
                slot_alts[ts] = []
            # Avoid exact duplicates within the same slot
            if not any(
                b.item_id == item.item_id and b.simc_string == item.simc_string
                for b in slot_alts[ts]
            ):
                slot_alts[ts].append(item)
    return slot_alts


def _resolve_target_slots(slot: str, item: ParsedItem, equipped: dict) -> list:
    """Return the physical slot(s) to generate profilesets for.

    For paired slots (rings, trinkets), checks which sub-slot the same item is
    already equipped in and routes the alternative to the other sub-slot(s).
    """
    for _base, (s1, s2) in PAIRED_SLOTS.items():
        if slot in (s1, s2, _base):
            eq_s1 = equipped.get(s1)
            eq_s2 = equipped.get(s2)
            # If the same item_id is equipped in s1, only test in s2 (and vice versa)
            if eq_s1 and eq_s1.item_id == item.item_id and slot != s2:
                return [s2]
            if eq_s2 and eq_s2.item_id == item.item_id and slot != s1:
                return [s1]
            return [s1, s2]
    return [slot]


def _reslot_item(simc_string: str, target_slot: str) -> str:
    """Replace the slot name prefix in a simc item string and strip any inline
    item name so simc resolves the item by ID only.

    e.g. 'wrists=fallen_kings_cuffs,id=12345,bonus_id=...'
      -> 'wrist=,id=12345,bonus_id=...'

    ID-based lookup is always reliable; name-based lookup can fail for items not
    yet fully indexed in the running simc build.
    """
    reslotted = re.sub(r"^\w+=", f"{target_slot}=", simc_string)
    # Strip inline name: slot=name,... -> slot=,...  (no-op when name already empty)
    return re.sub(r"^(\w+=)\w+,", r"\1,", reslotted)


def _make_label(name: str, slot: str) -> str:
    """Create a safe profileset label from item name and slot."""
    safe = re.sub(r"[^a-zA-Z0-9_ -]", "", name).replace(" ", "_")
    return f"{safe}_{slot}"[:60]


def _unique_label(label: str, existing: dict) -> str:
    """Append a numeric suffix if label already exists in existing dict."""
    if label not in existing:
        return label
    i = 2
    while f"{label}_{i}" in existing:
        i += 1
    return f"{label}_{i}"
