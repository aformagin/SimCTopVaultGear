import os
import re

# Input file
input_filename = "character-simc-string.txt"
# Output directory for modified SimC files
output_dir = "simc_weekly_rewards_variants"
os.makedirs(output_dir, exist_ok=True)

def generate_vault_rewards_from_file(import_string):
    if not import_string == None:
        write_simc_string_to_file(import_string, input_filename)
    
    simc_import = open_simc_import(input_filename)
    if simc_import == None:
        exit(1)
    print(f"Made it past if simc_import check\n")
    start_end = define_start_end_wr(simc_import) if isinstance(simc_import, list) else define_start_end_wr_from_string(import_string)
    if not start_end:
        return None
    print("StartEnd is valid")
    start = start_end["start"]
    end = start_end["end"]
    print(f"{start} - {end}")
    # Extract Weekly Reward Choices block
    weekly_rewards = simc_import[start:end + 1]

    # Parse reward choices and their associated gear lines
    reward_items = parse_weekly_rewards(weekly_rewards)
    print("Rewards:\n")
    print(reward_items)
    print("Weekly Reward Choice SimC variants generated successfully!")
    return (reward_items, simc_import, start, end)

def open_simc_import(input_filename):
    # Read SimC import string from file
    try:
        with open(input_filename, "r") as file:
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

        # Identify gear lines (commented out, starting with "# " followed by "slot=")
        gear_match = re.match(r"# (\w+=,id=\d+,.+)", line)
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

# Generates the modified SimC files from a extracted reward items list
def generate_mod_simc_file(reward_items, simc_import, start_idx, end_idx):
    # Clear out old gear files before creating new ones
    clear_simc_files(output_dir)
    # Generate modified SimC files
    for item_name, gear_line in reward_items:
        modified_simc = simc_import[:]  # Copy original lines

        # Modify the Weekly Reward Choices section
        for i in range(start_idx, end_idx + 1):
            if modified_simc[i].startswith("# "):  # Commented lines
                if gear_line in modified_simc[i]:
                    modified_simc[i] = gear_line + "\n"  # Uncomment the current item
                else:
                    modified_simc[i] = "# " + modified_simc[i].lstrip("# ").strip() + "\n"  # Keep others commented

        # Save to file with item name
        filename = f"{output_dir}/{item_name.replace(' ', '_')}.simc"
        with open(filename, "w") as f:
            f.writelines(modified_simc)

        print(f"Generated: {filename}")


def write_simc_string_to_file(simc_string, input_filename):
    """Writes the given SimC string to a file for debugging."""
    try:
        with open(input_filename, "w", encoding="utf-8") as f:
            f.write(simc_string)
        print(f"✅ Successfully wrote SimC string to {input_filename}")
    except Exception as e:
        print(f"❌ Error writing to file: {e}")

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
    generate_mod_simc_file(rewards, vals[1], vals[2], vals[3])
