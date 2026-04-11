# SimC Top Gear — WoW Gear Optimizer

A PyQt5 desktop app that uses SimulationCraft to help World of Warcraft players optimize their gear choices. Paste your SimC addon export string once and use any of the three simulation tabs.

## Tabs Overview

### Great Vault
Picks the best item from your weekly Great Vault choices.

- Parses vault reward options from your SimC export string (`### Weekly Reward Choices`)
- Optionally includes bag items alongside vault rewards
- Runs one simulation per candidate item and compares mean DPS
- Reports the best choice and a full DPS breakdown

**When to use**: On reset day when you need to pick one of your three vault slots.

---

### Drop Finder
Identifies which dungeons and raids are worth running for your character (Droptimizer-style).

- Pulls loot tables from `data/drop_sources.json` (generated from the Blizzard Game Data API)
- Select a source type (M+ Dungeons or Raids), a specific instance, a boss (or all bosses), and an item level track (Champion / Hero / Myth for dungeons; LFR / Normal / Heroic / Mythic for raids)
- Items are automatically filtered to your character's class based on your parsed SimC string
- Each item is simulated independently — one profileset per item — against your current equipped gear
- Results are ranked by DPS gain, showing which drops are the biggest upgrades

**When to use**: Deciding which dungeon key or raid difficulty to run this week to maximize your chances of a meaningful upgrade.

---

### Top Gear
Finds the single best gear loadout from items already in your bags.

- Loads bag items from your SimC export string (`### Gear from Bags`)
- Simulates every combination of selected bag items across all slots simultaneously (Cartesian product)
- Accounts for interactions between items — e.g., whether ring A is better paired with trinket B vs. trinket A
- Shows a combination count before you run so you can deselect items if the number is too large
- Results are ranked combinations, not individual items

**When to use**: You have several unequipped items and want to know the globally optimal loadout, not just which single item is the biggest upgrade in isolation.

---

## Key Difference: Drop Finder vs. Top Gear

| | Drop Finder | Top Gear |
|---|---|---|
| **Item source** | Loot tables (hypothetical drops) | Your actual bag items |
| **Sim approach** | One profileset per item (independent) | Cartesian product of all alternatives |
| **Answers** | "What should I farm?" | "What should I equip?" |
| **Scale** | Scales linearly with item count | Scales exponentially — watch the combination counter |

---

## Prerequisites

- **Python 3.11+**
- **SimulationCraft** — download from [simulationcraft.org](https://www.simulationcraft.org/)
  - The app searches for `simc.exe` in: the project directory → current directory → system PATH
- **SimC Addon** — export your character string from the in-game SimulationCraft addon

## Setup

**PowerShell:**
```powershell
.\setup_venv.ps1
```

**Command Prompt:**
```cmd
setup_venv.bat
```

The setup script creates a virtual environment in `./venv/` and installs all dependencies.

## Running

```powershell
.\venv\Scripts\Activate.ps1
python simc_top_gear.py
```

## Building a Standalone Executable

```powershell
.\build.ps1   # or build.bat
```

Output: `dist\simc_top_gear.exe` — no Python installation required to run.

## Project Structure

```
SimCTopVaultGear/
├── simc_top_gear.py           # Main GUI (PyQt5)
├── simc_gv_generator.py       # SimC string parser (ParsedItem, ParseResult)
├── simc_gv_sims.py            # Legacy Great Vault simc runner
├── profileset_generator.py    # Builds simc profileset input strings
├── top_gear_engine.py         # Orchestrates parse → profilesets → simc → results
├── result_parser.py           # Parses simc json2=stdout into SimResult objects
├── drop_finder_engine.py      # Drop Finder: loads loot tables, filters, builds profilesets
├── data/
│   └── drop_sources.json      # Loot tables (instances, bosses, items, ilvl tracks)
├── scripts/
│   └── generate_drop_sources.py  # Regenerate drop_sources.json via Blizzard API
├── tests/                     # pytest test suite (161 tests)
├── requirements.txt
├── setup_venv.ps1 / .bat
├── build.ps1 / .bat
└── simc_top_gear.spec
```

## Regenerating Loot Tables

`data/drop_sources.json` is bundled and ready to use. To regenerate it at the start of a new season:

1. Create `blizz_api.json` in the project root:
   ```json
   {"client-id": "your_id", "client-secret": "your_secret"}
   ```
   Get credentials at [develop.battle.net](https://develop.battle.net/).

2. Run:
   ```
   python scripts/generate_drop_sources.py
   ```

This fetches current-season M+ dungeons and raid instances from the Blizzard Game Data API and downloads item metadata from Raidbots static files.

## Troubleshooting

**"SimulationCraft executable not found"**
Place `simc.exe` in the same directory as the project, or use the Browse button in the app to set the path manually.

**"PyQt5 import failed" or DLL errors**
Use Python 3.11. Reinstall with `pip uninstall PyQt5 && pip install PyQt5==5.15.9`.

**Too many combinations in Top Gear**
Use the "None" button to deselect all, then manually check only the items you want to compare. The combination counter updates live.

**Drop Finder shows no items**
Click "Refresh Items" after pasting your SimC string — the item list filters to your character's class automatically once the string is parsed.

---

*Not affiliated with Blizzard Entertainment or the SimulationCraft project. World of Warcraft is a trademark of Blizzard Entertainment.*
