# TazUO Legion Scripts

[![Client](https://img.shields.io/badge/Client-TazUO-78DCE8?style=flat-square&labelColor=221F22&logo=windows&logoColor=white)](https://tazuo.org/)
[![Engine](https://img.shields.io/badge/Engine-Legion%20Scripting-AB9DF2?style=flat-square&labelColor=221F22)](https://tazuo.org/legion/legionapi/)
[![Python](https://img.shields.io/badge/Language-Python%203-FFD866?style=flat-square&labelColor=221F22&logo=python&logoColor=white)](https://www.python.org/)
[![C#](https://img.shields.io/badge/Language-C%23%20.NET%2010-7F52FF?style=flat-square&labelColor=221F22&logo=csharp&logoColor=white)](https://dotnet.microsoft.com/)
[![License](https://img.shields.io/badge/License-MIT-FC9867?style=flat-square&labelColor=221F22)](LICENSE)

A collection of automation and utility scripts developed for the [TazUO](https://tazuo.org/) Ultima Online client using the built-in **Legion Scripting** engine.

---

## 📖 Table of Contents

- [⚔️ Overview](#️-overview)
- [📜 Official Resources & Documentation](#-official-resources--documentation)
- [🏛️ Base Client Files Explained](#️-base-client-files-explained)
- [🤖 AI-Assisted Development](#-ai-assisted-development)
- [🛠️ Development Environment Setup](#️-development-environment-setup)
- [📦 Available Scripts](#-available-scripts)
- [⚖️ Best Practices for Writing Legion Scripts](#️-best-practices-for-writing-legion-scripts)
- [🤝 Contributing](#-contributing)

---

## ⚔️ Overview

TazUO includes a modern scripting engine known as **Legion Scripting**, supporting both **Python** and **C#** scripts executed directly within the client process. This repository houses custom scripts, utilities, and workflows created by **FesterHead**.

---

## 📜 Official Resources & Documentation

- **TazUO Wiki:** [tazuo.org/wiki/home/](https://tazuo.org/wiki/home/)
- **Scripting Setup Guide:** [tazuo.org/wiki/legion-scripting-setup/](https://tazuo.org/wiki/legion-scripting-setup/)
- **Legion API Reference:** [tazuo.org/legion/legionapi/](https://tazuo.org/legion/legionapi/)
- **Official Public Example Scripts:** [PlayTazUO/PublicLegionScripts](https://github.com/PlayTazUO/PublicLegionScripts/)

---

## 🏛️ Base Client Files Explained

When setting up TazUO Legion scripting, several files are provided directly from the base client install to power IDE IntelliSense, type checking, and auto-completion. Here is what each file does:

| File                               | Type                       | Purpose                                                                                                                                                                                                                                                                             |
| :--------------------------------- | :------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`API.py`**                       | Python Interface / Stubs   | Contains class, method, and signature stubs with docstrings for all functions exposed by TazUO to Python scripts. It serves as an offline API reference and enables IDE code navigation and hover documentation.                                                                    |
| **`__builtins__.py`**              | Python Shim                | Contains `import API`. At runtime, TazUO injects `API` into the global runtime environment. This file signals to language servers (such as Pyright, Pylance, or VS Code's Python extension) that `API` exists globally, preventing false "undefined variable" warnings.             |
| **`_ScriptContext.cs`**            | C# Static Context          | Declares `public static LegionAPI API { get; } = null!;` so that C# scripts (`.cs`) can access `API` with full IntelliSense in the editor. At runtime, TazUO provides the live API instance.                                                                                        |
| **`LegionScripts.csproj`**         | .NET Project Configuration | A .NET 10 project file referencing `TazUO.dll` and `FNA.dll` from the parent directory. It configures default imports and assembly references for C# scripts. Note: Build errors in this project during compilation are expected and harmless, as scripts run dynamically in TazUO. |
| **`LegionScripts.code-workspace`** | VS Code Workspace          | A workspace configuration file that allows you to open this directory as a pre-configured workspace in Visual Studio Code.                                                                                                                                                          |

> [!NOTE]
> These base files should not be modified directly. They are maintained by TazUO updates.

---

## 🤖 AI-Assisted Development

This project is developed and managed using Google AI models. The architecture, implementation, and repository maintenance are guided by specialized AI agents to ensure high-performance, minimalist engineering standards.

---

## 🛠️ Development Environment Setup

1. **Visual Studio Code:**
   - Open this folder in VS Code or open `LegionScripts.code-workspace`.
   - Install the recommended **Python** extension (by Microsoft).
   - If developing in C#, install the **C# Dev Kit** extension.
2. **Code Completion:**
   - With `API.py` and `__builtins__.py` present in the workspace root, typing `API.` in any `.py` script will display available methods, properties, parameter lists, and docstrings.

---

## 📦 Available Scripts

Scripts in this repository are organized into subfolders categorized by **author name** (e.g., [`FesterUO/`](FesterUO/)) or **shard name** to keep community scripts structured and cleanly separated from the base client files.

### FesterUO

#### [ChopTree.py](FesterUO/ChopTree.py)

An automated lumberjacking script that prompts the player to select a target tree, captures the tree coordinates and graphic, and repeatedly chops until the tree's wood is depleted or the script is stopped.

**Key Features:**

- **Dress Profile Auto-Load:** Configurable `DRESS_PROFILE` (default `"Lumberjack"`) automatically equips your saved lumberjacking outfit on startup.
- **Hand Detection:** Checks `OneHanded` and `TwoHanded` equipment layers for an equipped axe.
- **Interactive Tree Selection:** Uses the axe to open the targeting cursor, prompting the player with a system message (`"Click the tree you want to chop..."`).
- **Coordinate Locking:** Captures `API.LastTargetPos` and `API.LastTargetGraphic` to lock in target location (`X, Y, Z, Graphic`).
- **Automated Chopping Loop:** Swings at the tree repeatedly with a 1-second pause between swings.
- **Depletion Detection:** Clears and monitors the client journal for tree depletion messages (`"no wood here to harvest"`, `"not enough wood here"`, `"nothing here to chop"`, etc.).
- **Graceful Stop Handling:** Listens to `API.StopRequested` and registers an `API.OnStop` callback.

#### [ChopTreeAuto.py](FesterUO/ChopTreeAuto.py)

An automated roaming lumberjacking script that scans for nearby trees, navigates to them, harvests them until depleted, and moves to the next available tree.

**Key Features:**

- **Dress Profile Auto-Load:** Automatically loads your saved `"Lumberjack"` dress configuration on startup.
- **Area Static Scanning:** Scans for static objects within `SEARCH_RADIUS` (default 25 tiles) using TazUO's native `IsTree` classifier.
- **Tree Memory & Skip History:** Remembers the last 30 visited tree coordinates via a FIFO queue (`TREE_HISTORY_LIMIT = 30`) to avoid revisiting recently chopped trees.
- **Automatic Pathfinding:** Uses `API.Pathfind` to navigate adjacent to candidate trees (within 2 tiles). Skips unreachable trees and handles timeouts safely.
- **Automated Chopping Loop:** Continuously chops until depletion journal messages are observed.
- **Capacity & Weight Protection:** Automatically monitors player weight and halts execution when backpack is full (`MAX_WEIGHT_CHECK`).
- **Interactive Control Gump:** Displays an on-screen movable Gump showing real-time action status, total trees harvested, Lumberjacking skill level/cap, and Strength/Dexterity stats.
- **Live Skill & Stat Gain Tracking:** Automatically updates values on the Gump and announces increases in the client log when Lumberjacking, Strength, or Dexterity rises.
- **Pause & Stop Controls:** Includes interactive **Pause/Resume** and **Stop** buttons right on the Gump.
- **Configurable Settings:** Includes settings for `SWING_DELAY`, `SEARCH_RADIUS`, `TREE_HISTORY_LIMIT`, `MAX_WEIGHT_CHECK`, `DRESS_PROFILE`, and `DEBUG` logging.

#### [ChopTreeAndMageryAuto.py](FesterUO/ChopTreeAndMageryAuto.py)

A unified roaming lumberjacking and Magery skill training script that coordinates chopping, spellcasting, equips, and targeting cursors within a single engine to eliminate script conflicts:

- **Coordinated Target Cursor Management:** Eliminates target cursor collisions and equip race conditions that occur when running separate chopping and spell training scripts.
- **Spot-Depletion Batch Training Cycle:** Chops each tree continuously until depleted, then enters a dedicated spell session to burn available mana on skill-appropriate Magery spells up to a configurable cast limit (`MAX_MAGERY_CASTS_PER_CYCLE = 8`, or `0` for unlimited until mana is dry) before returning to chopping the next tree.
- **Configurable Cast Limit:** Prevents extended pauses when mana pools are high by bounding the number of Magery casts per tree cycle (`MAX_MAGERY_CASTS_PER_CYCLE = 8`), automatically switching back to roaming lumberjacking when reached.
- **Synergized Mana Regeneration:** Mana naturally regenerates while walking and chopping subsequent trees, creating an uninterrupted, efficient training loop.
- **Lumberjack & Mage Dress Profiles:** Automatically applies the configured `"Lumberjack"` dress profile before every axe swing, and optionally equips `"Mage"` during spell training cycles.
- **Dual Training Modes:** Supports Resist Training (Mind Blast, Energy Bolt, Flamestrike with automated healing) and Non-Resist Training (Mana Drain, Invisibility, Mana Vampire).
- **Interactive Control Gump:** Displays trees harvested, live Lumberjacking and Magery skills with gain announcements, Mana / Max Mana, Lower Reagent Cost (LRC %), a live two-column reagent counter, and Pause/Resume/Stop controls.

#### [MiningAuto.py](FesterUO/MiningAuto.py)

An automated roaming mining script designed for caves, mountainsides, and ore nodes with an interactive control Gump:

- **Mining Dress Profile:** Automatically applies the saved `"Mining"` dress profile before every mine swing and at startup.
- **Skill-Tier Deposit Filtering:** Scans nearby cave tiles, rock outcroppings, boulders, and ore nodes within `SEARCH_RADIUS`, filtering candidate deposits to match your player's current Mining skill tier (Valorite, Verite, Agapite, Gold, Bronze, Copper, Shadow, Dull Copper, Iron).
- **Autonomous Navigation & Pathfinding:** Intelligently pathfinds adjacent to candidate ore veins within reach (distance <= 2) using TazUO's native pathfinder.
- **History Tracking:** Remembers the last 30 visited veins (`DEPOSIT_HISTORY_LIMIT`) to prevent repeatedly revisiting depleted spots.
- **Tool Detection & Auto-Recovery:** Supports pickaxes and shovels (in hands or backpack), detecting broken tools and switching to spares automatically.
- **Capacity & Weight Protection:** Automatically monitors player weight and halts execution safely before becoming overburdened (`MAX_WEIGHT_CHECK`).
- **Interactive Control Gump:** Displays real-time status, total veins mined counter, total ores mined counter, live Mining skill (`XX.X / XXX.X`), and STR/DEX stats with gain announcements.
- **Pause & Stop Controls:** Interactive on-screen **Pause/Resume** and **Stop** buttons.

#### [MiningAndMageryAuto.py](FesterUO/MiningAndMageryAuto.py)

A unified roaming mining and Magery skill training script that coordinates ore vein mining, spellcasting, equips, and targeting cursors within a single engine to eliminate script conflicts:

- **Coordinated Target Cursor Management:** Eliminates target cursor collisions and equip race conditions that occur when running separate mining and spell training scripts.
- **Spot-Depletion Batch Training Cycle:** Mines each ore deposit continuously until depleted, then enters a dedicated spell session to burn available mana on skill-appropriate Magery spells up to a configurable cast limit (`MAX_MAGERY_CASTS_PER_CYCLE = 8`, or `0` for unlimited until mana is dry) before returning to mining the next vein.
- **Configurable Cast Limit:** Prevents extended pauses when mana pools are high by bounding the number of Magery casts per node cycle (`MAX_MAGERY_CASTS_PER_CYCLE = 8`), automatically switching back to roaming mining when reached.
- **Synergized Mana Regeneration:** Mana naturally regenerates while walking and mining subsequent veins, creating an uninterrupted, efficient training loop.
- **Mining & Mage Dress Profiles:** Automatically applies the configured `"Mining"` dress profile before every pickaxe/shovel swing, and optionally equips `"Mage"` during spell training cycles.
- **Dual Training Modes:** Supports Resist Training (Mind Blast, Energy Bolt, Flamestrike with automated healing) and Non-Resist Training (Mana Drain, Invisibility, Mana Vampire).
- **Interactive Control Gump:** Displays veins mined, ores mined, live Mining and Magery skills with gain announcements, Mana / Max Mana, Lower Reagent Cost (LRC %), a live two-column reagent counter, and Pause/Resume/Stop controls.

#### [MiningAndLumberjackAuto.py](FesterUO/MiningAndLumberjackAuto.py)

- **Configurable Harvest Ratio Workflow:** Automatically alternates between mining and lumberjacking with a configurable ratio (`TREES_PER_MINING_SPOT = 8`, `MINING_SPOTS_PER_CYCLE = 1` by default). Mines an ore deposit until depleted, then automatically switches to lumberjack gear and chops eight trees until depleted, repeating seamlessly (`Mine 1 -> Chop 8 -> Mine 1 -> Chop 8...`).
- **Autonomous Equipment & Dress Switching:** Automatically equips your `"Mining"` profile (pickaxe/shovel) during the mining phase, and switches to your `"Lumberjack"` profile (axe) during the woodcutting phase, avoiding redundant dress delays across consecutive trees.
- **Combined Spatial Scanning:** Scans for cave floors, mountain edges, rock outcroppings, and boulders for mining, and scans static trees via TazUO's native vegetation detection for lumberjacking.
- **Pathfinding & Depletion Memory:** Safely pathfinds within reach (`distance <= 2`) of candidate nodes, maintaining separate depletion history queues for both veins (`DEPOSIT_HISTORY_LIMIT = 150`) and trees (`TREE_HISTORY_LIMIT = 50`) to avoid revisiting depleted spots.
- **Integrated Control Gump:** Displays real-time activity status, dual skill bars for **Mining** and **Lumberjacking** with automatic gain announcements, combined counters for **Veins Mined / Total Ore** and **Trees Chopped / Total Logs**, Strength and Dexterity stats, Weight monitoring, and interactive **Pause/Resume** and **Stop** buttons.
- **Backpack Weight Protection:** Continuously checks player weight against maximum capacity (`MAX_WEIGHT_CHECK`, `WEIGHT_BUFFER = 15`) and halts safely before becoming overburdened.

#### [TrainAnatomy.py](FesterUO/TrainAnatomy.py)

An automated Anatomy skill training script with configurable skill cooldowns, automatic self-targeting, and skill cap tracking:

- **Self or Custom Targeting:** Set `TARGET_SELF = True` to inspect yourself, or `False` to pick a creature/player target on launch.
- **Standard Skill Timer:** Default `SKILL_DELAY = 10.0` seconds matching classic UO skill delays (configurable for faster custom shards).
- **Automatic Cap Detection:** Inspects `API.GetSkill("Anatomy").Cap` and automatically halts when the goal is reached.
- **Skill Gain Tracking:** Announces incremental skill gains in the game client log.

#### [Fish.py](FesterUO/Fish.py)

An automated fishing script featuring an interactive on-screen control Gump, dynamic water target selector, and persistent catch statistics:

- **Interactive Control Gump:** Displays real-time status (`Ready`, `Click water to fish...`, `Fishing (Cast #N)...`, `Spot Depleted`), cast counts, running catch totals, and live Fishing skill tracking (`XX.X / XXX.X`).
- **Start / Stop Selector Button:** Features an interactive "Start" button that prompts the player with `"Click the water where you want to fish..."` and begins automated fishing on that spot. Toggles to "Stop" during active casting to permit early cancellation.
- **Spot Cast Counter:** Accurately counts casts made at the current fishing spot and automatically resets to zero whenever "Start" is clicked.
- **Persistent Catch Totals:** Maintains running totals of standard **Fish**, **Small Fish**, and **Junk** caught across multiple spots for the entire duration the Gump remains open.
- **Multi-Source Catch Detection:** Detects catches using both backpack inventory deltas and client journal parsing.
- **Coordinate & Graphic Locking:** Captures `API.LastTargetPos` and `API.LastTargetGraphic` to repeatedly target the exact water tile.
- **Depletion Detection:** Monitors the client journal for spot exhaustion messages (`"the fish don't seem to be biting here"`, `"there are no fish here"`, etc.) and finishes cleanly.
- **Pole Detection & Outfits:** Automatically detects equipped fishing poles or finds one inside your backpack, with optional `DRESS_PROFILE` support.

#### [FishAuto.py](FesterUO/FishAuto.py)

An automated boat fishing and combat defense script featuring interactive control Gump, dual-side (Northwest & Southeast) railing harvesting, 8-space boat movement advances, ocean junk disposal, and automatic enemy combat resolution:

- **Dress Profile Auto-Equip:** Automatically equips the saved `"Fishing"` profile at startup.
- **Zero-Prompt Automated Targeting:** Starts immediately without requiring manual water targeting; dynamically samples open water directly off the vessel's sides (Northwest and Southeast).
- **Dual-Side Railing Harvesting:** Sequentially fishes off both sides of the boat (Northwest and Southeast) within 2–4 tiles, completely avoiding line-of-sight obstructions from the mast, sail, bow, and stern.
- **Automatic Boat Navigation:** Once both side spots are depleted, pulses `"forward one"` 8 times sequentially (`API.Msg("forward one")`) to advance the vessel 8 tiles into the next resource bank.
- **Automated Catch Stowing:** Detects fish caught and optionally runs the configured TazUO Organizer agent (`RUN_ORGANIZER = True`, `ORGANIZER_NAME = "FishOrganizer"`) via `API.Organizer(name)` to automatically move catches into your hold or designated container.
- **Junk Disposal:** Detects fished-up junk items (boots, shoes, sandals, seaweed, twigs) in the backpack and automatically throws them back into the ocean (`API.MoveItemOffset`).
- **Combat Detection & Execution:** Actively monitors for hostile sea creatures (sea serpents, water elementals, krakens, etc.), explicitly ignoring harmless dolphins. When an enemy is detected:
  1. Undresses the `"Fishing"` profile and clears hand slots.
  2. Equips the `"Archery"` dress profile (with automatic backpack bow equip fallback).
  3. Enters War Mode (`API.SetWarMode(True)`).
  4. Attacks the enemy mobile (`API.Attack(enemy.Serial)`).
  5. Halts automated fishing, keeping the Gump open with a **"Start"** button so the player can manually finish combat and loot, then click "Start" to resume fishing.
- **Interactive Control Gump:** On-screen movable Gump displaying:
  - Real-time action status (Fishing NW/SE, Combat mode, Moving boat, Paused, Stopped)
  - Live Fishing skill value and cap (`XX.X / XXX.X`) with automatic skill gain announcements
  - Running **Fish Caught** and **Junk Caught** statistics
  - Enemies defeated counter
  - Interactive **Start / Pause / Resume** and **Stop** buttons.

#### [TrainChivalry.py](FesterUO/TrainChivalry.py)

An automated skill training script for Chivalry with an interactive control Gump that casts spells corresponding to the player's current skill tier:

- **Skill Tiers:**
  - **0 – 44.9:** Consecrate Weapon (requires weapon in hand)
  - **45.0 – 59.9:** Divine Fury
  - **60.0 – 69.9:** Enemy Of One
  - **70.0 – 89.9:** Holy Light
  - **90.0 – 114.9:** Noble Sacrifice
  - **115.0+:** Training complete

- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (Casting, Meditating, Waiting for Mana, Low Tithe, Paused)
  - Current Mana and Max Mana tracking (`API.Player.Mana / ManaMax`)
  - Live Tithing Points display (`API.Player.TithingPoints`)
  - Chivalry skill level, skill cap, and automatic gain announcements
  - Interactive **Pause/Resume** and **Stop** buttons
- **Smart Startup Validation:** Inspects initial mana, max mana, and tithing points against the first spell to cast before training begins; displays clear warnings and terminates cleanly if requirements are not met.
- **Dress Profile Auto-Equip:** Configurable `DRESS_PROFILE` (default `"Archer"`) automatically equips your saved profile at startup, re-arms after meditation, and equips a weapon if hands are empty before casting Consecrate Weapon.
- **Auto-Meditation & Depletion Protection:** Automatically meditates or pauses when mana drops during training, and immediately halts when tithing points are depleted.
- **Attribution:** Adapted from [PlayTazUO/PublicLegionScripts](https://github.com/PlayTazUO/PublicLegionScripts/blob/main/Skills/Any/Train%20Chiv.py) by FesterHead.

#### [TrainMagery.py](FesterUO/TrainMagery.py)

An automated skill training script for Magery with an interactive control Gump, real-time reagent tracking, and automatic self-healing:

- **Skill Tiers & Training Modes:**
  - **Resist Training (`RESIST_TRAIN = True`, default):** Casts offensive spells on yourself (Mind Blast, Energy Bolt, Flamestrike) to train Resisting Spells concurrently with automated healing.
    - **0 – 29.9:** Clumsy (if `ALLOW_LOW_SKILL = True`)
    - **30.0 – 44.9:** Fireball
    - **45.0 – 59.9:** Mind Blast
    - **60.0 – 84.9:** Energy Bolt
    - **85.0 – 100.0+:** Flamestrike
  - **Non-Resist Training (`RESIST_TRAIN = False`):** Casts non-damaging spells on yourself for safe, passive leveling.
    - **0 – 29.9:** Clumsy (if `ALLOW_LOW_SKILL = True`)
    - **30.0 – 54.9:** Mana Drain
    - **55.0 – 74.9:** Invisibility
    - **75.0 – 100.0+:** Mana Vampire
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (Casting, Meditating, Healing, Waiting for Mana, Paused, Finished)
  - Current Mana and Max Mana tracking (`API.Player.Mana / ManaMax`)
  - Lower Reagent Cost percentage (`API.Player.LowerReagentCost`)
  - Live Magery skill level, skill cap, and automatic skill gain announcements
  - Live two-column backpack reagent counter for all 8 standard reagents: Black Pearl, Bloodmoss, Garlic, Ginseng, Mandrake Root, Nightshade, Sulfurous Ash, and Spiders' Silk
  - Interactive **Pause/Resume** and **Stop** buttons
- **Automated Healing & Mana Recovery:** Automatically restores health using Spirit Speak or Greater Heal during Resist Training, and meditates when mana drops below threshold.
- **Smart Startup Validation:** Verifies minimum skill, mana, and required reagents (if LRC < 100%) before starting; displays clear warnings and cleanly stops if prerequisites are not met.
- **Attribution:** Adapted from [PlayTazUO/PublicLegionScripts](https://github.com/PlayTazUO/PublicLegionScripts/blob/main/Skills/Any/Train%20Magery.py) by FesterHead.

#### [TrainBlacksmith.py](FesterUO/TrainBlacksmith.py)

An automated, resource-efficient Blacksmithing training engine with interactive control Gump, resource satchel support, auto-smelting, and Tinkering tool upkeep:

- **Ingot-Efficient Skill Progression:** Automatically tracks your Blacksmithing skill and crafts the lowest-ingot items in each tier from 0 to 120 (GM / Legendary):
  - **30.0 – 45.0:** Mace (6 ingots)
  - **45.0 – 50.0:** Maul (6 ingots)
  - **50.0 – 95.0:** Short Spear (6 ingots — _primary training workhorse_)
  - **95.0 – 106.4:** Platemail Gorget (10 ingots — _cheapest platemail piece_)
  - **106.4 – 108.9:** Platemail Gloves (12 ingots)
  - **108.9 – 116.3:** Platemail Arms (18 ingots)
  - **116.3 – 118.8:** Platemail Legs (20 ingots)
  - **118.8 – 120.0:** Platemail Tunic (25 ingots)
- **Resource Satchel Integration:** Prompts player on launch to target their resource satchel or bag. Maintains a lightweight working buffer of ingots in the main backpack (default 40–80 ingots) so your character is never overburdened, pulling fresh batches as needed.
- **Automated Smelting (Recycling):** Automatically smelts crafted items at the forge to reclaim 50%–90% of raw ingots, automatically returning the recovered ingots back into your satchel.
- **Tool Upkeep via Tinkering:** Detects broken or missing tools and automatically crafts replacements on the fly using Tinker's Tools and ingots, prioritizing **Tongs** (only 1 ingot at 45.0+ Tinkering) over Smith's Hammers (4 ingots).
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (`Crafting Short Spear...`, `Smelting...`, `Tinkering Hammer...`, `Restocking Ingots...`, `Paused`, `Finished`)
  - Live Blacksmith skill level, skill cap, and automatic skill gain announcements
  - Running counters for **Crafted**, **Smelted**, and **Failed** items
  - Live Satchel and Backpack ingot counts
  - Interactive **Pause/Resume**, **Set Recipe**, **Set Satchel**, and **Stop** buttons
- **Attribution:** Created by FesterHead.

#### [TrainTinkering.py](FesterUO/TrainTinkering.py)

An automated, ingot-efficient Tinkering training engine with interactive control Gump, resource satchel support, perpetual tool self-crafting, auto-smelting, and milestone tracking:

- **Ingot-Efficient Skill Progression:** Automatically tracks your Tinkering skill and crafts the lowest-ingot items in each tier from 0 to 100 (GM):
  - **0.0 – 45.0:** Tinker's Tools (2 ingots) — _self-perpetuating tool crafting_
  - **45.0 – 60.0:** Tongs (1 ingot)
  - **60.0 – 95.0:** Lockpicks (1 ingot) — _stackable and lowest cost per attempt_
  - **95.0 – 100.0:** Heating Stand (4 ingots)
- **Blacksmithing Milestones:**
  - **40.0 Tinkering:** Unlocks Smith's Hammer crafting (for Blacksmithing training).
  - **45.0 Tinkering:** Unlocks Tongs crafting (for Blacksmithing training).
  - Emits clear system messages when both milestones are reached.
- **Perpetual Tool Self-Crafting:** Monitors backpack Tinker's Tools and automatically crafts fresh replacement tools whenever your supply drops below the safety threshold (`MIN_TOOLS = 2`).
- **Resource Satchel Integration:** Prompts player on launch to target their resource satchel or bag. Maintains a lightweight working buffer of ingots in the main backpack (default 20–50 ingots) so your character is never overburdened, pulling fresh batches as needed. Protects colored/special ingots (Dull Copper, Shadow, Bronze, Gold, etc.).
- **Automated Trash Barrel Disposal:** Auto-detects nearby Trash Barrels or allows targeting one at startup. Automatically deposits newly crafted non-stackable items (Tongs, Heating Stands, excess tools) into the trash barrel via backpack serial diff, while preserving stackable lockpicks and working tool reserves. Includes a **"Trash Can"** button on the Gump to change/set trash barrels at any time.
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (`Crafting Tinker's Tools...`, `Trashing...`, `Crafting Tool...`, `Restocking Ingots...`, `Paused`, `Finished`)
  - Live Tinkering skill level, skill cap, and automatic skill gain announcements
  - Running counters for **Crafted**, **Trashed**, and **Failed** items
  - Live Satchel and Backpack ingot counts, plus tool and trash indicators
  - Interactive **Pause/Resume**, **Set Recipe**, **Satchel**, **Trash Can**, and **Stop** buttons
- **Attribution:** Created by FesterHead.

#### [TrainCarpentry.py](FesterUO/TrainCarpentry.py)

An automated, board-efficient Carpentry training engine with interactive control Gump, resource satchel support, auto-trashing of crafted furniture/weapons, and milestone tracking:

- **Board-Efficient Skill Progression:** Automatically tracks your Carpentry skill and crafts the lowest-board items in each tier from 0 to 120 (GM / Legendary):
  - **0.0 – 42.1:** Wooden Box (5 boards)
  - **42.1 – 47.3:** Vesper-Style Chair (15 boards)
  - **47.3 – 70.0:** Ballot Box Deed (5 boards)
  - **70.0 – 73.6:** Bokuto (6 boards) [or Wooden Shield (9 boards)]
  - **73.6 – 78.9:** Quarter Staff (6 boards)
  - **78.9 – 120.0:** Gnarled Staff (7 boards)
- **Milestone Recommendations & "Set Recipe" Override:** Proactively announces when your skill levels past a tier bracket and recommends the next recipe. Players can click **"Set Recipe"** on the Gump at any time to manually choose any recipe from the open craft menu.
- **Automated Trash Barrel Disposal:** Auto-detects nearby Trash Barrels or allows targeting one at startup. Automatically deposits newly crafted items into the trash barrel via backpack serial diff, preventing overweight and backpack clutter. Includes a **"Trash Can"** button on the Gump to change/set trash barrels at any time.
- **Resource Satchel Integration:** Prompts player on launch to target their wood/resource satchel. Maintains a lightweight working buffer of boards in the main backpack (default 20–60 boards) so characters are never overburdened, pulling fresh batches as needed. Protects colored/special woods (Frostwood, Heartwood, Bloodwood).
- **Tool Upkeep:** Works with any carpentry tool (Saw, Dovetail Saw, Plane, Scorp, Draw Knife, Hammer). Automatically crafts replacement Dovetail Saws (30.0+ Tinkering) or Saws via Tinkering using iron ingots from your satchel.
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (`Crafted`, `Trashing...`, `Tinkering Saw...`, `Restocking boards...`, `Paused`, `Finished`)
  - Live Carpentry skill level, skill cap, and automatic skill gain announcements
  - Running counters for **Crafted**, **Trashed**, and **Failed** items
  - Live Satchel and Backpack board counts, plus tool and trash indicators
  - Interactive **Pause/Resume**, **Set Recipe**, **Satchel**, **Trash Can**, and **Stop** buttons
- **Attribution:** Created by FesterHead.

#### [TrainInscription.py](FesterUO/TrainInscription.py)

An automated, resource-efficient Inscription training engine with interactive control Gump, resource satchel support, smart mana recovery via Meditation, dual storage/trash disposal, and Tinkering pen upkeep:

- **Resource-Efficient Spell Progression:** Automatically monitors your Inscription skill and crafts the lowest-cost, single/dual-reagent spells in each tier from 0 to 120 (GM / Legendary):
  - **0.0 – 30.0:** Reactive Armor (Circle 1, 4 Mana, 1 blank scroll, Garlic / Spiders' Silk / Sulfurous Ash)
  - **30.0 – 45.0:** Poison (Circle 3, 9 Mana, 1 blank scroll, Nightshade — _only 1 reagent!_)
  - **45.0 – 65.0:** Lightning (Circle 4, 11 Mana, 1 blank scroll, Mandrake Root / Sulfurous Ash)
  - **65.0 – 75.0:** Magic Reflection (Circle 5, 14 Mana, 1 blank scroll, Garlic / Mandrake Root / Spiders' Silk)
  - **75.0 – 90.0:** Energy Bolt (Circle 6, 20 Mana, 1 blank scroll, Black Pearl / Nightshade)
  - **90.0 – 120.0:** Flamestrike (Circle 7, 40 Mana, 1 blank scroll, Spiders' Silk / Sulfurous Ash)
- **Milestone Recommendations & "Set Recipe" Override:** Proactively announces when your skill levels past a tier bracket and recommends the next spell. Players can click **"Set Recipe"** on the Gump at any time to manually choose any recipe or custom spell from the open craft menu.
- **Smart Mana Management & Meditation:** Continuously monitors your character's mana against the required spell cost. Automatically activates Meditation whenever mana falls below threshold and meditates until mana is fully replenished, enabling sustained, uninterrupted crafting bursts.
- **Dual Crafted Scroll Management (Storage & Trash Disposal):**
  - **Storage Container:** Allows targeting a scroll book, chest, or pouch on startup or via the Gump's **"Storage"** button to automatically store all completed scrolls.
  - **Trash Barrel:** Auto-detects nearby Trash Barrels or allows targeting one via the Gump's **"Trash Can"** button for players who prefer to discard scrolls to prevent weight and clutter.
  - Deposits newly crafted scrolls via backpack serial diff, ensuring backpack cleanliness.
- **Resource Satchel Integration & LRC Support:**
  - Automatically detects 100% Lower Reagent Cost (LRC) suits and completely bypasses reagent requirements.
  - If LRC < 100%, automatically monitors and restocks required reagents from the resource satchel.
  - Automatically restocks blank scrolls from the satchel when backpack reserves run low.
- **Tool Upkeep via Tinkering:** Detects broken or missing Scribe's Pens and automatically crafts replacements on the fly using Tinker's Tools and iron ingots (1 ingot each).
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (`Crafted`, `Regenerating Mana...`, `Storing...`, `Trashing...`, `Tinkering Scribe's Pen...`, `Paused`, `Finished`)
  - Live Inscription skill level, skill cap, and automatic skill gain announcements
  - Mana and LRC indicators (`Mana: Cur/Max | LRC: XX%`)
  - Running counters for **Crafted**, **Stored**, **Trashed**, and **Failed** items
  - Live Satchel and Backpack blank scroll counts, plus pen count and destination indicator
  - Interactive **Pause/Resume**, **Set Recipe**, **Satchel**, **Storage**, **Trash Can**, and **Stop** buttons

#### [TrainCartography.py](FesterUO/TrainCartography.py)

An automated, resource-efficient Cartography training engine with interactive control Gump, resource satchel support, dual storage/trash disposal, and Tinkering pen upkeep:

- **Optimal Map Progression:** Automatically monitors your Cartography skill and crafts the optimal map in each tier from 0 to 100 (GM) / 120 (Legendary), requiring 1 blank scroll per craft:
  - **0.0 – 50.0:** Local Map (1 blank scroll)
  - **50.0 – 65.0:** City Map (1 blank scroll)
  - **65.0 – 70.0:** Sea Chart (1 blank scroll)
  - **70.0 – 120.0:** World Map (1 blank scroll)
- **Milestone Recommendations & "Set Recipe" Override:** Proactively announces when your skill levels past a tier bracket and recommends the next map. Players can click **"Set Recipe"** on the Gump at any time to manually choose any map from the open craft menu.
- **Dual Crafted Map Management (Storage & Trash Disposal):**
  - **Storage Container:** Allows targeting a container (map case, chest, or pouch) on startup or via the Gump's **"Storage"** button to automatically store all completed maps.
  - **Trash Barrel:** Auto-detects nearby Trash Barrels or allows targeting one via the Gump's **"Trash Can"** button to automatically discard completed maps and avoid overweight.
  - Deposits newly crafted maps via backpack serial diff, ensuring backpack cleanliness.
- **Resource Satchel Integration:**
  - Supports direct satchel crafting or maintains a lightweight working buffer of blank scrolls in the backpack.
  - Automatically restocks blank scrolls from the satchel when backpack reserves run low.
  - Recognizes standard Blank Scrolls (`0x0EF3`, `0x0E34`) with full fallback compatibility for Blank Maps (`0x14EB`, `0x14EC`).
- **Tool Upkeep via Tinkering & Pen Discrimination:** Detects broken or missing Mapmaker's Pens, strictly rejects Scribe's Pens using active tooltip inspection, closes stale craft menus, and automatically crafts replacements on the fly using Tinker's Tools, iron ingots, and blank scrolls (1 ingot + 1 scroll) via serial diff tracking.
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (`Crafted`, `Storing...`, `Trashing...`, `Tinkering Mapmaker's Pen...`, `Paused`, `Finished`)
  - Live Cartography skill level, skill cap, and automatic skill gain announcements
  - Running counters for **Crafted**, **Stored**, **Trashed**, and **Failed** items
  - Live Satchel and Backpack blank scroll counts, plus pen count and destination indicator
  - Live character weight indicator (`Weight: Cur / Max`)
  - Interactive **Pause/Resume**, **Set Recipe**, **Satchel**, **Storage**, **Trash Can**, and **Stop** buttons
- **Attribution:** Created by FesterHead.

#### [TrainCooking.py](FesterUO/TrainCooking.py)

An automated, resource-efficient Cooking training engine with interactive control Gump, resource satchel support, dual storage/trash disposal, heat source awareness, and Tinkering skillet upkeep:

- **Optimal Cooking Progression:** Automatically monitors your Cooking skill and recommends the optimal recipe in each tier from 0 to 100.0 (GM):
  - **0.0 – 50.0:** Fish Steak / Cooked Ribs (1 raw fish steak / cut of ribs)
  - **50.0 – 65.0:** Dough / Bread Loaf (flour + water)
  - **65.0 – 80.0:** Pan of Cookies / Meat Pie (sweet dough / ribs)
  - **80.0 – 100.0:** Baked Fruit Pie / Miso Soup (fruit / miso / dough)
- **Universal Dual-Mode Engine:**
  - **Craft Gump Mode (Default):** Uses standard cooking tools (Skillet, Flour Sifter, Rolling Pin) with high-speed "Make Last" crafting.
  - **Direct Heat Source Mode:** Automatically uses raw food directly on fires, ovens, stoves, forges, or heating stands for classic or shard-specific mechanics.
- **Milestone Recommendations & "Set Recipe" Override:** Proactively announces when your skill levels past a tier bracket and recommends the next recipe. Players can click **"Set Recipe"** on the Gump at any time to open the craft menu and select any custom recipe.
- **Dual Crafted Food Management (Storage & Trash Disposal):**
  - **Storage Container:** Allows targeting a food chest, cooler, or pouch on startup or via the Gump's **"Storage"** button to automatically store all completed cooked food.
  - **Trash Barrel:** Auto-detects nearby Trash Barrels or allows targeting one via the Gump's **"Trash Can"** button to automatically discard cooked food and avoid overweight.
  - Deposits cooked food via backpack serial diff and amount increases, handling both stackable food (fish steaks, ribs) and individual items (pies, loaves).
- **Resource Satchel Integration:**
  - Supports direct satchel crafting or maintains a lightweight working buffer of raw ingredients in the backpack.
  - Automatically restocks raw food from the satchel when backpack reserves run low.
- **Tool Upkeep via Tinkering:** Detects broken or missing Skillets and automatically crafts replacements on the fly using Tinker's Tools and iron ingots (2 ingots each).
- **Heat Source Awareness:** Auto-detects nearby campfires, ovens, stoves, hearths, forges, or portable heating stands.
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (`Crafted`, `Storing...`, `Trashing...`, `Tinkering Skillet...`, `Paused`, `Finished`)
  - Live Cooking skill level, skill cap, and automatic skill gain announcements
  - Running counters for **Crafted**, **Stored**, **Trashed**, and **Failed** items
  - Live Satchel and Backpack ingredient counts, plus tool/mode and destination indicator
  - Live character weight indicator (`Weight: Cur / Max`)
  - Interactive **Pause/Resume**, **Set Recipe**, **Satchel**, **Storage**, **Trash Can**, and **Stop** buttons
- **Attribution:** Created by FesterHead.

#### [MoveItemsBetweenContainers.py](FesterUO/MoveItemsBetweenContainers.py)

A quick and reliable container-to-container item organizer and transfer utility script:

- **Interactive Targeting:** Prompts the player to target the SOURCE container, then the DESTINATION container (with 10-second timeouts and graceful cancellation).
- **Container Pre-Opening:** Automatically opens the source container (`API.UseObject`) to force the game server to send full container contents to the client if not already cached in memory.
- **Validation & Safety:** Verifies that source and destination are valid and distinct entities, refusing to run if both targets are identical or if the source is empty.
- **Graceful Cancellation & Loop Safety:** Checks `API.StopRequested` on each item iteration to ensure immediate, clean script halts when cancelled in the TazUO UI.
- **Client Synchronization:** Uses `API.Pause(0.65)` between moves to prevent item drag/drop desynchronization or server packet drops.
- **Attribution:** Created by FesterHead.

---

## ⚖️ Best Practices for Writing Legion Scripts

When contributing or writing new scripts:

- **Always Check `API.StopRequested`:** Ensure loops can terminate cleanly when stopped from the in-game UI.
- **Use `API.Pause(seconds)`:** Avoid standard Python `time.sleep()`, which can stall or desync the game client thread.
- **Journal Cleanliness:** Always invoke `API.ClearJournal()` immediately before triggering an action whose journal output you need to check.
- **User Notifications:** Report important steps and errors using `API.SysMsg("...")`.

---

## 🤝 Contributing

Please review [CONTRIBUTING.md](CONTRIBUTING.md) for scripting conventions, safety rules, and pull request procedures. All contributions should adhere to the guidelines in [AGENTS.md](AGENTS.md).
