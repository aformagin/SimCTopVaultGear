# TopGear - SimulationCraft Great Vault Optimizer

TopGear is a PyQt5-based GUI application that helps World of Warcraft players optimize their Great Vault reward choices using SimulationCraft simulation data. The application automatically generates and runs SimulationCraft scenarios for each vault reward option to determine which item provides the highest DPS increase.

## Features

- **Great Vault Integration**: Import your character's SimulationCraft string with embedded Great Vault options
- **Automated Simulation**: Automatically generates separate SimulationCraft files for each vault reward
- **Multi-threaded Processing**: Runs simulations in background threads to keep the UI responsive  
- **DPS Comparison**: Calculates and compares mean DPS for each vault option
- **Best Item Recommendation**: Identifies which vault reward provides the highest DPS gain
- **Item Management**: Add/remove vault items from consideration before running simulations

## Prerequisites

- **Python 3.11+** (recommended) or Python 3.12
- **SimulationCraft**: Download from [simulationcraft.org](https://www.simulationcraft.org/)
  - TopGear will automatically find SimulationCraft in the following locations (in order):
    1. Same directory as TopGear executable/script
    2. Current working directory
    3. System PATH environment variable
  - Supported executable names: `simc.exe`

## Project Structure

```
TopGear/
├── simc_top_gear.py          # Main GUI application
├── simc_gv_generator.py      # Great Vault reward parser and file generator  
├── simc_gv_sims.py          # SimulationCraft execution and results processing
├── simc_import.ui           # Qt Designer UI file
├── requirements.txt         # Python dependencies
├── setup_venv.ps1          # Virtual environment setup (PowerShell)
├── setup_venv.bat          # Virtual environment setup (Batch)
├── build.ps1               # Build executable (PowerShell) 
├── build.bat               # Build executable (Batch)
├── simc_top_gear.spec      # PyInstaller configuration
└── README.md               # This file
```

## Setup Instructions

### Option 1: PowerShell (Recommended for Windows)

1. **Clone or download** this project to your desired location
2. **Open PowerShell** in the project directory
3. **Run the setup script**:
   ```powershell
   .\setup_venv.ps1
   ```

### Option 2: Command Prompt/Batch

1. **Clone or download** this project to your desired location  
2. **Open Command Prompt** in the project directory
3. **Run the setup script**:
   ```cmd
   setup_venv.bat
   ```

### What the setup script does:

- Verifies Python 3.11+ installation
- Creates a fresh virtual environment in `./venv/`
- Installs PyQt5 5.15.9 and PyInstaller 5.13.2
- Verifies the installation works correctly

## Running the Application

### During Development

After running the setup script, you can run the application directly:

**PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
python simc_top_gear.py
```

**Command Prompt:**
```cmd
venv\Scripts\activate.bat
python simc_top_gear.py
```

### Building a Standalone Executable

To create a single-file executable that doesn't require Python to be installed:

**PowerShell:**
```powershell
.\build.ps1
```

**Command Prompt:**
```cmd
build.bat
```

The executable will be created at `dist\simc_top_gear.exe` - this is a completely self-contained file that can be run anywhere.

## How to Use TopGear

### Step 1: Generate SimulationCraft String with Great Vault Options

1. **In World of Warcraft**:
   - Log into your character normally
   - Open the **Great Vault**
   - Go to **SimulationCraft (Addon)** → **Export SimC String** 
   - Copy the generated SimulationCraft string (it will include vault options as comments)

### Step 2: Import into TopGear

1. **Launch TopGear** (`python simc_top_gear.py` or run the built executable)
2. **Paste your SimulationCraft string** into the large text area
3. **Click "Gather Vault Rewards"** to parse vault options from the string
4. **Review the detected vault items** in the list

### Step 3: Run Simulations

1. **(Optional) Remove unwanted items** using the "Remove Item" button
2. **Click "Run Sim"** to start the simulation process
3. **Wait for completion** - the status will show "Running Sim..." during processing
4. **View results** - the best item and estimated DPS will be displayed

### Step 4: Make Your Choice

- The application will show which vault reward provides the highest mean DPS
- Use this information to make an informed decision about your Great Vault selection

## Technical Details

### Dependencies

- **PyQt5 5.15.9**: GUI framework for cross-platform desktop applications
- **PyInstaller 5.13.2**: Creates standalone executables from Python applications

### Architecture

- **Main Thread**: Handles GUI interactions and updates
- **Worker Thread**: Executes SimulationCraft processes without blocking the UI
- **File Processing**: Generates separate `.simc` files for each vault option in `simc_weekly_rewards_variants/`
- **Results Parsing**: Extracts DPS statistics from SimulationCraft JSON output

### Simulation Process

1. Parses Great Vault options from SimulationCraft import string
2. Creates individual `.simc` files with one vault option active per file
3. Runs `simc.exe` on each file with JSON output enabled
4. Extracts mean DPS values from each simulation result
5. Identifies the vault option with the highest mean DPS

## Troubleshooting

### "SimulationCraft executable not found"
TopGear will automatically search for SimulationCraft in multiple locations. If you see this error:

**Solution 1 - Place in same directory (Easiest)**:
- Download SimulationCraft from [simulationcraft.org](https://www.simulationcraft.org/)
- Extract `simc.exe` to the same directory as TopGear

**Solution 2 - Add to PATH**:
- Add the SimulationCraft installation directory to your system PATH environment variable
- This allows TopGear to find it automatically

**Solution 3 - Run from SimulationCraft directory**:
- Copy TopGear to your SimulationCraft installation directory
- Run TopGear from there

### "PyQt5 import failed" or DLL errors
- Ensure you're using Python 3.11 (most compatible version)
- Try reinstalling: `pip uninstall PyQt5` then `pip install PyQt5==5.15.9`
- On some systems, you may need Visual C++ Redistributables from Microsoft

### "Virtual environment creation failed"  
- Ensure Python is properly installed and added to PATH
- Try running: `python -m pip install --upgrade pip`
- Restart your terminal/command prompt after Python installation

### Application crashes or won't start
- Check that `simc_import.ui` file is present in the same directory
- Verify all Python files are in the same directory
- Try running from command line to see error messages

## SimulationCraft Integration

This application requires SimulationCraft to function. Make sure you have:

1. **Downloaded SimulationCraft** from the official website
2. **Extracted simc.exe** to your TopGear directory or system PATH  
3. **Generated a proper SimulationCraft string** with Great Vault options included

The Great Vault options should appear as commented sections in your SimulationCraft string like:

```
### Weekly Reward Choices ###
# Item Name (Item Level)
# slot=waist,id=12345,bonus_id=1234/5678,...
### End of Weekly Reward Choices ###
```

## Contributing

This project was created to help World of Warcraft players make informed Great Vault decisions. If you encounter bugs or have feature requests, please provide detailed information about:

- Your Python version
- Your SimulationCraft version  
- The error message or unexpected behavior
- Steps to reproduce the issue

## License

This project is provided as-is for educational and personal use. SimulationCraft is a separate project with its own licensing terms.

---

**Note**: This application is not affiliated with Blizzard Entertainment or the SimulationCraft project. World of Warcraft is a trademark of Blizzard Entertainment.