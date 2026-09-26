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
