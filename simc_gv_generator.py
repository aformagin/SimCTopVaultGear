import os
import re
import hashlib
from dataclasses import dataclass
from typing import Optional
from item_affixes import apply_reference_item_affixes

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Input file (used by the legacy file-based pipeline)
input_filename = "character-simc-string.txt"
# Output directory for modified SimC files (legacy pipeline)
output_dir = "simc_weekly_rewards_variants"
os.makedirs(output_dir, exist_ok=True)

# filename stem -> human-readable label for the current generated variant set
generated_variant_labels = {}

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
    origin: str = "equipped"  # "equipped" or "bag"

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
    in_additional = False     # ### Additional Character Info
    pending_item_name = ""
    pending_item_ilevel = 0
    pending_loadout_name = None

    for line in lines:
        stripped = line.strip()

        # --- Section header detection ---
        if stripped.startswith("###"):
            header = stripped.lstrip("#").strip()
            if "Gear from Bags" in header or "Weekly Reward Choices" in header:
                in_bags = True
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
                    gear_match.group(1), "bag", pending_item_name, pending_item_ilevel
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


# ---------------------------------------------------------------------------
# Legacy section-based parsing (used by the existing file-per-item pipeline)
# ---------------------------------------------------------------------------

def generate_vault_rewards_from_file(import_string, include_bags=False):
    if not import_string == None:
        write_simc_string_to_file(import_string, input_filename)

    simc_import = open_simc_import(input_filename)
    if simc_import == None:
        exit(1)
    print(f"Made it past if simc_import check\n")

    reward_items = []
    vault_start, vault_end = None, None

    # Parse Weekly Reward Choices (vault) section if present
    start_end = define_start_end_wr(simc_import)
    if start_end:
        vault_start = start_end["start"]
        vault_end = start_end["end"]
        print(f"Vault section: {vault_start} - {vault_end}")
        weekly_rewards = simc_import[vault_start:vault_end + 1]
        vault_items = parse_weekly_rewards(weekly_rewards)
        reward_items.extend([(name, gear, vault_start, vault_end) for name, gear in vault_items])
    else:
        print("No Weekly Reward Choices section found.")

    # Parse Gear from Bags section if the checkbox is enabled
    if include_bags:
        bags_start_end = define_start_end_bags(simc_import)
        if bags_start_end:
            b_start = bags_start_end["start"]
            b_end = bags_start_end["end"]
            print(f"Bags section: {b_start} - {b_end}")
            bags_section = simc_import[b_start:b_end + 1]
            bags_items = parse_weekly_rewards(bags_section)
            reward_items.extend([(name, gear, b_start, b_end) for name, gear in bags_items])
            print(f"Found {len(bags_items)} bag item(s).")
        else:
            print("No Gear from Bags section found in SimC string.")

    if not reward_items:
        print("No items found in vault or bags sections.")
        return None

    print("Rewards:\n")
    print(reward_items)
    print("SimC variants generated successfully!")
    return (reward_items, simc_import, vault_start, vault_end)

def open_simc_import(input_filename):
    # Read SimC import string from file
    try:
        with open(input_filename, "r", encoding="utf-8") as file:
            simc_import = file.readlines()
        return simc_import
    except FileNotFoundError:
        print(f"Error: {input_filename} not found. Please ensure the file exists.")
        return None

# Parse reward choices and their associated gear lines
def parse_weekly_rewards(weekly_rewards):
    reward_items = []
    current_item_name = None

    for line in weekly_rewards:
        line = line.strip()

        # Identify item names (lines starting with "# " and containing an item name)
        item_match = re.match(r"# (.+) \(\d+\)", line)
        if item_match:
            current_item_name = item_match.group(1)

        # Identify gear lines (commented out, starting with "# " followed by slot spec)
        # Handles both "slotname=,id=XXXX" and "slot=SLOTNAME,id=XXXX" formats.
        # Trailing fields (bonus_id, drop_level, etc.) are optional.
        gear_match = re.match(r"# (\w+=\w*,id=\d+.*)", line)
        if gear_match and current_item_name:
            reward_items.append((current_item_name, gear_match.group(1)))

    return reward_items


def _get_equipped_items_from_import(simc_import):
    parsed = parse_simc_addon("".join(simc_import))
    return parsed.equipped


def _resolve_target_slots(slot: str, item_id: Optional[int], equipped: dict) -> list:
    """Return valid physical slot targets for an item line.

    Rings and trinkets can occupy either paired slot unless the same item is
    already equipped in one of them, in which case only the other slot is valid.
    """
    for _base, (s1, s2) in PAIRED_SLOTS.items():
        if slot in (s1, s2, _base):
            eq_s1 = equipped.get(s1)
            eq_s2 = equipped.get(s2)
            if item_id is not None:
                if eq_s1 and eq_s1.item_id == item_id and slot != s2:
                    return [s2]
                if eq_s2 and eq_s2.item_id == item_id and slot != s1:
                    return [s1]
            return [s1, s2]
    return [slot]


def _legacy_item_id(gear_line: str) -> Optional[int]:
    match = re.search(r"id=(\d+)", gear_line)
    return int(match.group(1)) if match else None


def _legacy_item_slot(gear_line: str) -> Optional[str]:
    slot = _extract_slot(gear_line)
    return slot if slot in GEAR_SLOTS or slot in PAIRED_SLOTS else slot


def _reslot_gear_line(gear_line: str, target_slot: str) -> str:
    return re.sub(r"^\w+=", f"{target_slot}=", gear_line)


def _slot_display_name(slot: str) -> str:
    display_names = {
        "finger1": "Finger 1",
        "finger2": "Finger 2",
        "trinket1": "Trinket 1",
        "trinket2": "Trinket 2",
    }
    return display_names.get(slot, slot.replace("_", " ").title())


def _build_variant_label(assignments: list[tuple[str, str]]) -> str:
    parts = [f"{name} ({_slot_display_name(slot)})" for name, slot in assignments]
    return " + ".join(parts)


def _clean_variant_filename(label: str) -> str:
    clean_name = label.replace(" ", "_")
    for ch in ':<>\"|?*/\\':
        clean_name = clean_name.replace(ch, "_")
    clean_name = clean_name.strip("._")
    max_len = 110
    if len(clean_name) <= max_len:
        return clean_name
    digest = hashlib.md5(label.encode("utf-8")).hexdigest()[:10]
    trimmed = clean_name[: max_len - len(digest) - 1].rstrip("._")
    return f"{trimmed}_{digest}"


def get_generated_variant_label(stem: str) -> Optional[str]:
    return generated_variant_labels.get(stem)


def _build_variant_specs(reward_items, equipped: dict, apply_equipped_modifiers: bool = False):
    """Expand legacy reward items into slot-aware single-item variants."""
    variants = []
    seen_signatures = set()

    for item_name, gear_line, sec_start, sec_end in reward_items:
        slot = _legacy_item_slot(gear_line)
        item_id = _legacy_item_id(gear_line)
        target_slots = _resolve_target_slots(slot, item_id, equipped)

        for target_slot in target_slots:
            label = _build_variant_label([(item_name, target_slot)])
            replacement_line = _reslot_gear_line(gear_line, target_slot)
            if apply_equipped_modifiers:
                equipped_item = equipped.get(target_slot)
                if equipped_item:
                    replacement_line = apply_reference_item_affixes(
                        replacement_line,
                        equipped_item.simc_string,
                    )
            section_maps = {
                (sec_start, sec_end): {gear_line: replacement_line}
            }
            signature = tuple(
                sorted(
                    (
                        sec_range,
                        tuple(sorted(section_replacements.items())),
                    )
                    for sec_range, section_replacements in section_maps.items()
                )
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            variants.append((label, section_maps))

    return variants

def clear_simc_files(directory):
    """Deletes all .simc files in the specified directory."""
    if not os.path.exists(directory):
        print(f"Directory {directory} does not exist. No files to delete.")
        return

    file_count = 0
    for file in os.listdir(directory):
        file_path = os.path.join(directory, file)
        if file.endswith(".simc") and os.path.isfile(file_path):
            os.remove(file_path)
            file_count += 1

    print(f"Deleted {file_count} old .simc files from {directory}.")

def define_start_end_wr(simc_import):
# Identify Weekly Reward Choices section
    start_idx = None
    end_idx = None
    for i, line in enumerate(simc_import):
        if "### Weekly Reward Choices" in line:
            start_idx = i
        elif "### End of Weekly Reward Choices" in line:
            end_idx = i
            break

    if start_idx is None or end_idx is None:
        print("Error: Weekly Reward Choices section not found in the file.")
        return None
    return {"start": start_idx, "end": end_idx}

def define_start_end_bags(simc_import):
    """Identify the start and end indices of the Bags section.
    The SimC addon uses '### Gear from Bags' as the section header with no
    explicit closing marker — the section ends at the next '###' header."""
    start_idx = None
    end_idx = None
    for i, line in enumerate(simc_import):
        stripped = line.strip()
        if start_idx is None and "### Gear from Bags" in stripped:
            start_idx = i
        elif start_idx is not None and stripped.startswith("###"):
            end_idx = i
            break

    if start_idx is None:
        return None
    # If no following '###' header was found use the last line of the file
    if end_idx is None:
        end_idx = len(simc_import) - 1
    return {"start": start_idx, "end": end_idx}

# Generates the modified SimC files from a extracted reward items list.
# Each item in reward_items is a (name, gear_line, sec_start, sec_end) tuple carrying
# its own section range so vault and bag items are handled uniformly.
def generate_mod_simc_file(reward_items, simc_import, apply_equipped_modifiers: bool = False):
    # Clear out old gear files before creating new ones
    clear_simc_files(output_dir)
    equipped = _get_equipped_items_from_import(simc_import)
    generated_variant_labels.clear()

    # Write the unmodified character as Baseline.simc so the sim pipeline can
    # measure current-gear DPS alongside every vault/bag variant.
    baseline_filename = f"{output_dir}/Baseline.simc"
    with open(baseline_filename, "w", encoding="utf-8") as f:
        f.writelines(simc_import)
    generated_variant_labels["Baseline"] = "Baseline"
    print(f"Generated: {baseline_filename}")

    # Generate modified SimC files
    for label, section_maps in _build_variant_specs(
        reward_items,
        equipped,
        apply_equipped_modifiers=apply_equipped_modifiers,
    ):
        modified_simc = simc_import[:]  # Copy original lines

        # Within each relevant source section, uncomment the selected gear line(s)
        # and keep all other vault/bag entries commented.
        for (sec_start, sec_end), replacement_map in section_maps.items():
            for i in range(sec_start, sec_end + 1):
                if modified_simc[i].startswith("# "):  # Commented lines
                    matched_gear_line = next(
                        (gear_line for gear_line in replacement_map if gear_line in modified_simc[i]),
                        None,
                    )
                    if matched_gear_line:
                        modified_simc[i] = replacement_map[matched_gear_line] + "\n"
                    else:
                        modified_simc[i] = "# " + modified_simc[i].lstrip("# ").strip() + "\n"  # Keep others commented

        # Save to file with a slot-aware human label.
        clean_name = _clean_variant_filename(label)
        filename = f"{output_dir}/{clean_name}.simc"
        with open(filename, "w") as f:
            f.writelines(modified_simc)
        generated_variant_labels[clean_name] = label

        print(f"Generated: {filename}")


def write_simc_string_to_file(simc_string, input_filename):
    """Writes the given SimC string to a file for debugging."""
    try:
        with open(input_filename, "w", encoding="utf-8") as f:
            f.write(simc_string)
        print(f"Successfully wrote SimC string to {input_filename}")
    except Exception as e:
        print(f"Error writing to file: {e}")

def define_start_end_wr_from_string(simc_string):
    """Identify the start and end indices of the Weekly Reward Choices section from a string."""

    lines = simc_string.splitlines()  # Convert the string into a list of lines
    start_idx = None
    end_idx = None

    # Scan each line to find start and end markers
    for i, line in enumerate(lines):
        stripped_line = line.strip()  # Remove extra spaces

        if stripped_line.startswith("### Weekly Reward Choices"):
            start_idx = i
        elif stripped_line.startswith("### End of Weekly Reward Choices"):
            end_idx = i
            break  # Stop searching once we find the end marker

    # Debugging output to verify if indices were found correctly
    print(f"Start Index: {start_idx}, End Index: {end_idx}")

    if start_idx is None or end_idx is None:
        print("Error: Weekly Reward Choices section not found in the string.")
        return None

    return {"start": start_idx, "end": end_idx}


def remove_rewards(removed, rewards):
    to_remove = sorted(map(int, removed.split(" ")), reverse=True)
    for r in to_remove:
        print(int(r))
        rewards.pop(int(r - 1))
    return rewards

if __name__ == "__main__":
    # For testing
    vals = generate_vault_rewards_from_file(None)
    rewards = vals[0]
    x = 0
    for reward in rewards:
        x = x + 1
        print(f"[{x}] {reward[0]}")
    rewards = remove_rewards("1 5 9", rewards)

    x = 0
    for reward in rewards:
        x = x + 1
        print(f"[{x}] {reward[0]}")
    # # Generate SimC files
    generate_mod_simc_file(rewards, vals[1])
