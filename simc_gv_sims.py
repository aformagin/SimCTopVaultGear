import os
import subprocess
import json
import time
import sys
import shutil
import simc_gv_generator

def find_simc_executable():
    """Find simc.exe in multiple possible locations"""
    
    # Possible names for the SimulationCraft executable
    possible_names = ["simc.exe", "SimulationCraft.exe"]
    
    # Get the directory where this script/exe is located
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        script_dir = os.path.dirname(sys.executable)
    else:
        # Running as Python script
        script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Search locations in order of preference
    search_locations = [
        script_dir,  # Same directory as the application
        os.getcwd(),  # Current working directory
    ]
    
    # Check each location for each possible executable name
    for location in search_locations:
        for name in possible_names:
            full_path = os.path.join(location, name)
            if os.path.isfile(full_path):
                print(f"Found SimulationCraft at: {full_path}")
                return full_path
    
    # Try to find in system PATH
    for name in possible_names:
        path_location = shutil.which(name)
        if path_location:
            print(f"Found SimulationCraft in PATH: {path_location}")
            return path_location
    
    # Not found anywhere
    return None

# Configuration
simc_executable = find_simc_executable()
input_dir = "simc_weekly_rewards_variants"
output_json = "data.json"

# List to store DPS results
dps_results = []

# Check if simc.exe exists
if not simc_executable:
    print("Error: SimulationCraft executable not found!")
    print("Please ensure simc.exe or SimulationCraft.exe is:")
    print("  1. In the same directory as this application")
    print("  2. In your system PATH")
    print("  3. Download from: https://www.simulationcraft.org/")
    exit(1)

def run_simc_against_vault():
    dps_results.clear()
    # Delete existing data.json to avoid mixing old and new results
    if os.path.isfile(output_json):
        os.remove(output_json)
    start = time.time()
    # Run each .simc file through SimulationCraft
    for simc_file in os.listdir(input_dir):
        if simc_file.endswith(".simc"):
            simc_path = os.path.join(input_dir, simc_file)
            
            print(f"Running SimC for {simc_file}...")
            
            # Run SimC and save output to data.json
            try:
                result = subprocess.run(
                    [simc_executable, simc_path, "json2=data.json"],
                    capture_output=True,
                    text=True,
                    check=True
                )
            except subprocess.CalledProcessError as e:
                print(f"Error running SimulationCraft on {simc_file}: {e}")
                continue

            # Read and process the newly created data.json
            if not os.path.isfile(output_json):
                print(f"Error: SimulationCraft did not generate {output_json} for {simc_file}")
                continue

            try:
                with open(output_json, "r") as f:
                    simc_data = json.load(f)
            except json.JSONDecodeError:
                print(f"Error: Failed to parse JSON from {output_json} for {simc_file}")
                continue
            
            collected_data = extract_json_data(simc_data)
            if collected_data is None:
                print(f"Warning: No player data found for {simc_file}. Full JSON output:")
                print(json.dumps(simc_data, indent=2))  # Print JSON for debugging
                continue
            dps_data = collected_data.get("dps", {})

            dps_max = dps_data.get("max", 0)
            dps_mean = dps_data.get("mean", 0)
            dps_min = dps_data.get("min", 0)
            item_name = simc_file.replace(".simc", "").replace("_", " ")  # Convert filename to readable item name

            dps_results.append((item_name, dps_mean, dps_min, dps_max))
            print(f"Processed: {item_name} -> Mean DPS: {dps_mean}")

    # Determine highest mean DPS item
    if dps_results:
        best_item = max(dps_results, key=lambda x: x[1])  # Sort by mean DPS
        print(best_item)
        return best_item
    else:
        print("No valid DPS data was found.")

    end = time.time()
    elapsed = end - start
    print(f"All simulations took: {elapsed}")

def extract_json_data(data):
     # Extract DPS statistics from sim.players[0].dps
    player_data = data.get("sim", {}).get("players", [])
    if not player_data:
        return None
    collected_data = player_data[0].get("collected_data",{})
    return collected_data

def print_best_item(best_item):
    print("\n### Best Item by Mean DPS ###")
    print("# Item: " + '{: >20}'.format(best_item[0]))
    print(f"# Mean DPS:\t {best_item[1]:.2f}")
    print(f"# Min DPS:\t {best_item[2]:.2f}")
    print(f"# Max DPS:\t {best_item[3]:.2f}")
    print("#############################\n")

def print_menu():
        print("Please input which script to run:")
        print("[ggv] Generate Great Vault SIMC Input")
        print("[vtg] Vault Top Gear (Sims all vault gear)")
        print("[exit] Exit the master script")
        print("\n")
        print("Selection: ",end ="")

if __name__ == "__main__":
    while True:
        print_menu()
        res = input()
        if res == "ggv":
            vals = simc_gv_generator.generate_vault_rewards_from_file()
            simc_gv_generator.generate_mod_simc_file(vals[0], vals[1], vals[2], vals[3])
        elif res == "vtg":
            print_best_item(run_simc_against_vault())
        elif res == "exit":
            exit(1)
        else:
            print("Invalid response.")