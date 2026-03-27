import os
import re

# Input file
input_filename = "character-simc-string.txt"
# Output directory for modified SimC files
output_dir = "simc_weekly_rewards_variants"
os.makedirs(output_dir, exist_ok=True)

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
def generate_mod_simc_file(reward_items, simc_import):
    # Clear out old gear files before creating new ones
    clear_simc_files(output_dir)

    # Write the unmodified character as Baseline.simc so the sim pipeline can
    # measure current-gear DPS alongside every vault/bag variant.
    baseline_filename = f"{output_dir}/Baseline.simc"
    with open(baseline_filename, "w", encoding="utf-8") as f:
        f.writelines(simc_import)
    print(f"Generated: {baseline_filename}")

    # Generate modified SimC files
    for item_name, gear_line, sec_start, sec_end in reward_items:
        modified_simc = simc_import[:]  # Copy original lines

        # Within the item's source section, uncomment only its gear line
        # and ensure all other commented lines stay commented.
        for i in range(sec_start, sec_end + 1):
            if modified_simc[i].startswith("# "):  # Commented lines
                if gear_line in modified_simc[i]:
                    modified_simc[i] = gear_line + "\n"  # Uncomment the current item
                else:
                    modified_simc[i] = "# " + modified_simc[i].lstrip("# ").strip() + "\n"  # Keep others commented

        # Save to file with item name
        # Clean filename by removing invalid Windows characters
        clean_name = item_name.replace(' ', '_').replace(':', '_').replace('<', '_').replace('>', '_').replace('"', '_').replace('|', '_').replace('?', '_').replace('*', '_').replace('/', '_').replace('\\', '_')
        filename = f"{output_dir}/{clean_name}.simc"
        with open(filename, "w") as f:
            f.writelines(modified_simc)

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
