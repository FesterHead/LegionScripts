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
- **Integrated Control Gump with Live Ratio Tuning:** Displays real-time activity status, dual skill bars for **Mining** and **Lumberjacking** with automatic gain announcements, combined counters for **Veins Mined / Total Ore** and **Trees Chopped / Total Logs**, Strength and Dexterity stats, Weight monitoring, interactive stepper buttons (`[-]` / `[+]`) to dynamically tune **Veins/Cycle** and **Trees/Cycle** live in-game to suit whatever area you are harvesting without restarting or editing the script, and interactive **Pause/Resume** and **Stop** buttons.
- **Backpack Weight Protection:** Continuously checks player weight against maximum capacity (`MAX_WEIGHT_CHECK`, `WEIGHT_BUFFER = 15`) and halts safely before becoming overburdened.
- **Attribution:** Created by FesterHead.

#### [MiningAndLumberjackAndMageryAuto.py](FesterUO/MiningAndLumberjackAndMageryAuto.py)

A unified roaming mining, lumberjacking, and Magery skill training script that alternates between harvesting ore veins and chopping trees while training Magery during node downtime:

- **Integrated Tri-Skill Training Loop:** Seamlessly combines roaming mining, roaming lumberjacking, and batch Magery training in a single engine, completely eliminating targeting cursor and equip conflicts.
- **Configurable Harvest Ratio Workflow:** Automatically alternates between mining and lumberjacking with configurable cycle targets (`TREES_PER_MINING_SPOT = 4`, `MINING_SPOTS_PER_CYCLE = 1` by default).
- **Spot-Depletion Batch Magery Cycle:** Whenever an ore vein or tree is depleted, the script enters a dedicated spell session to burn available mana on skill-appropriate Magery spells up to a configurable cast limit before moving to the next node.
- **Interactive Control Gump with Live Ratio Tuning:** Displays real-time status, tri-skill progress (**Mining**, **Lumberjacking**, **Magery**) with automatic gain tracking, Mana / Max Mana, Lower Reagent Cost (LRC %), **Veins Mined / Total Ore**, **Trees Chopped / Total Logs**, Strength and Dexterity stats, Weight monitoring, interactive stepper buttons (`[-]` / `[+]`) to dynamically tune **Veins/Cycle** and **Trees/Cycle** live in-game, a live two-column 8-reagent matrix, and interactive **Pause/Resume** and **Stop** buttons.
- **Dual Magery Training Modes:** Supports Resist Training (Mind Blast, Energy Bolt, Flamestrike with automated self-healing) and Non-Resist Training (Mana Drain, Invisibility, Mana Vampire).
- **Equipment & Dress Management:** Automatically switches between `"Mining"`, `"Lumberjack"`, and optional `"Mage"` dress profiles at each phase.
- **Attribution:** Created by FesterHead.

#### [HuntAnimals.py](FesterUO/HuntAnimals.py)

An autonomous wildlife and bird hunting script with an interactive control Gump, multi-category wildlife selection, automated combat, and corpse carving / autolooting:

- **Multi-Category Wildlife Detection:**
  - Real-time scanning for wild animals within a configurable search radius (`SEARCH_RADIUS = 15` tiles).
  - **Birds (`HUNT_BIRDS = True`, default):** Targets birds, eagles, chickens, turkeys, and cranes to generate feathers and poultry.
  - **Passive Animals (`HUNT_PASSIVE_ANIMALS = True`, default):** Targets hinds, great harts (deer), cows, bulls, pigs, boars, sheep, goats, and rabbits to generate leather/hides, raw ribs/meat, and wool.
  - **Predators (`HUNT_PREDATORS = False`, optional):** Optional toggle to hunt wolves, bears, cougars, and panthers.
  - **Karma Protection (`PROTECT_KARMA = True`, default):** Explicitly ignores horses, llamas, ostards, dolphins, dogs, and cats to prevent negative karma hits.
  - Explicitly ignores the player, friends, guildmates, and tamed player pets (`IGNORE_TAMED_PETS = True`).
- **Autonomous Combat Engagement:**
  - Automatically equips the configured `"Fighting"` dress profile to arm weapons.
  - Enters War Mode (`API.SetWarMode(True)`) and issues attack commands.
  - Intelligently pathfinds to and pursues wandering or fleeing animals until in melee range, with timeout protection (`COMBAT_TIMEOUT = 25.0s`).
- **TazUO AutoLoot Integration & Corpse Carving:**
  - Locates the animal corpse upon kill and carves it using an equipped axe or backpack bladed tool (`AUTO_CARVE_CORPSE = True`) to produce leather/hides, feathers, meat, and wool.
  - Automatically opens the corpse (`OPEN_CORPSE_FOR_AUTOLOOT = True`) and explicitly invokes TazUO's native AutoLoot agent (`TRIGGER_TAZUO_AUTOLOOT = True` via `API.AutoLootContainer`) to handle item collection according to your client settings.
- **Pre-Combat Sheep Shearing & Tool Autodetection:**
  - Detects wooly sheep (`0x00CF`) and automatically approaches into melee range to shear their wool before engaging in combat (`AUTO_SHEAR_SHEEP = True`).
  - Autodetects a **Skinning Knife** (`0x0EC4`) directly in your main backpack (with fallback to shears or any equipped/backpack bladed tool) for both pre-combat shearing and corpse carving.
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time status (`Scanning...`, `Hunting <Animal>...`, `Shearing <Sheep>...`, `Chasing...`, `Carving corpse...`, `Opening corpse...`, `AutoLooting...`, `Paused`, `Stopped`)
  - Running counters for **Animals Defeated** and **Sheep Sheared**
  - Interactive toggle checkboxes: Real-time toggles for **Birds**, **Passives**, **Predators**, **Shear Sheep**, and **Defend Threats** directly from the UI without needing to edit or restart the script
  - Interactive **Pause/Resume** and **Stop** buttons
- **Attribution:** Created by FesterHead.

#### [TrainAnatomy.py](FesterUO/TrainAnatomy.py)

An automated Anatomy skill training script with configurable skill cooldowns, automatic self-targeting, and skill cap tracking:

- **Self or Custom Targeting:** Set `TARGET_SELF = True` to inspect yourself, or `False` to pick a creature/player target on launch.
- **Standard Skill Timer:** Default `SKILL_DELAY = 10.0` seconds matching classic UO skill delays (configurable for faster custom shards).
- **Automatic Cap Detection:** Inspects `API.GetSkill("Anatomy").Cap` and automatically halts when the goal is reached.
- **Skill Gain Tracking:** Announces incremental skill gains in the game client log.

#### [TrainAnimalTaming.py](FesterUO/TrainAnimalTaming.py)

An automated Animal Taming skill training script featuring an interactive dark control Gump, active range pursuit, integrated Veterinary healing, and dual training architectures:

- **Dual Training Modes:**
  - **Wild Roam Mode (`DEFAULT_MODE = "WILD_ROAM"`):** Autonomously scans for nearby wild animals matching the player's skill tier within `SEARCH_RADIUS` (18 tiles), pathfinds to them, actively pursues fleeing creatures during the taming timer, and auto-releases them upon success.
  - **Target Trainer Mode (`DEFAULT_MODE = "TARGET_TRAIN"`):** Repeatedly tames, releases, and retames a designated or penned creature (such as a bull, bear, or horse) to rapidly gain skill up to the cap.
- **Active Range Pursuit:** Continuously calculates distance during the 10-12s taming countdown and issues pathfinding steps to maintain the required 2-tile proximity without breaking the taming attempt.
- **Integrated Veterinary Healing (`ENABLE_VETERINARY = True`):** Automatically applies bandages to injured or poisoned creatures before release (or during retaming) to train Veterinary skill concurrently.
- **Automated Pet Release & Follower Management:** Dispatches direct speech and context menu commands with proper command pacing (0.8s-1.0s) to prevent server rate limiting, safely confirms release dialogs without breaking gump targeting (`confirm_release_gump`), and verifies release via normalized journal inspection, mobile notoriety reversion to Gray, and follower count reduction. Features automated stuck follower recovery (`cleanup_stuck_followers`) scanning nearby innocent/tamed creatures and dispatching emergency broadcast release, alongside follower cap protection to prevent follower creep.
- **Safe Magery Culling (`ENABLE_MAGERY_CULL = False`):** Safely casts Energy Bolt on released hostile/gray creatures to clear spawns and train Magery concurrently. Features multi-tier protections against criminal flagging and karma loss (verifies mobile is not owned, strictly forbids casting on `Innocent` (Blue) creatures, checks `KARMA_LOSS_GRAPHICS` and keywords, and verifies mana reserves).
- **Interactive Control Gump:** Movable, dark on-screen interface displaying real-time status, Animal Taming and Veterinary skill progression with gain announcements, total tamed count, attempt counter, culled counter, interactive checkboxes for runtime toggles (**Peacemaking**, **Animal Lore**, **Veterinary**, **Safety Heal**, and **Cull (E-Bolt)**), mode toggle button, auto-release toggle button, and Pause/Resume/Stop controls.
- **Safety & Peacemaking Support:** Optional Peacemaking integration to soothe agitated animals, plus automated emergency self-healing (bandages or Greater Heal) if player HP drops below threshold.
- **Attribution:** Created by FesterHead.

#### [TrainVeterinary.py](FesterUO/TrainVeterinary.py)

An automated Veterinary skill training script featuring dual training architectures, intelligent Dex-based bandage timers, and a comprehensive pet health monitoring Gump:

- **Dual Training Modes:**
  - **Dual Pet Sparring Mode (`DEFAULT_MODE = "SPARRING"`):** Coordinates two pets sparring against each other, continuously monitors both health pools, and applies bandages to whichever pet has lower HP or is poisoned.
  - **Single Pet / Patient Mode (`DEFAULT_MODE = "SINGLE"`):** Continuously monitors a single target pet, mount, or summon, applying bandages whenever damaged or poisoned.
- **Emergency Combat Separation:** Automatically broadcasts `"all stop"` and `"all follow me"` if either sparring pet falls below `EMERGENCY_HP_PERCENT` (default 30%), holding combat until both pets are healed back above `RESUME_HP_PERCENT` (default 85%).
- **Poison Curing & Resurrection:** Prioritizes curing poisoned pets immediately before standard healing, and automatically detects bonded pet ghosts to attempt resurrection using bandages (requires 80.0+ Veterinary and Animal Lore).
- **Intelligent Bandage Delays:** Computes classic UO Dexterity-based bandage application delays (`AUTO_BANDAGE_DELAY = True`) with manual override support.
- **Resource Satchel & Subcontainer Support:** Automatically discovers and draws bandages from specialized resource satchels or subcontainers in the player's backpack, preventing "Out of Bandages" stops when holding unlimited bandages in a satchel.
- **Automated Bandage Restocking:** Monitors backpack bandages and automatically pulls working batches (`RESTOCK_BATCH_SIZE = 100`) from the satchel whenever backpack reserves fall below threshold (`MIN_BACKPACK_BANDAGES = 20`).
- **Interactive Control Gump:** Displays real-time action status, live Veterinary skill progress with gain tracker, individual pet health gauges with percentage and status tags (`[POISON]`, `[DEAD]`), bandage count breakdown (total and root backpack), heal/cure/resurrection statistics, interactive **"Satchel"** targeting button, mode toggle, and Pause/Resume/Stop controls.
- **Attribution:** Created by FesterHead.

#### [Fish.py](FesterUO/Fish.py)

An automated fishing script featuring an interactive on-screen control Gump, dynamic water target selector, persistent catch statistics, and automatic hostile mob defense:

- **Interactive Control Gump:** Displays real-time status (`Ready`, `Click water to fish...`, `Fishing (Cast #N)...`, `Combat - Click Start when ready`, `Spot Depleted`), cast counts, running catch totals, and live Fishing skill tracking (`XX.X / XXX.X`).
- **Start / Stop Selector Button:** Features an interactive "Start" button that prompts the player with `"Click the water where you want to fish..."` and begins automated fishing on that spot. Toggles to "Stop" during active casting to permit early cancellation.
- **Hostile Mob Awareness & Auto-Combat Defense:** Actively scans for nearby hostile mobiles and sea monsters within 12 tiles. When an enemy is detected:
  1. Immediately halts fishing.
  2. Unequips the fishing pole and undresses the `"Fishing"` profile.
  3. Equips the `"Archery"` dress profile (with backpack bow equip fallback).
  4. Enters War Mode and attacks the hostile enemy.
  5. Leaves the player in full manual control without automatically resuming fishing until the player clicks "Start".
- **Spot Cast Counter:** Accurately counts casts made at the current fishing spot and automatically resets to zero whenever "Start" is clicked.
- **Persistent Catch Totals:** Maintains running totals of standard **Fish**, **Small Fish**, and **Junk** caught across multiple spots for the entire duration the Gump remains open.
- **Multi-Source Catch Detection:** Detects catches using both backpack inventory deltas and client journal parsing.
- **Coordinate & Graphic Locking:** Captures `API.LastTargetPos` and `API.LastTargetGraphic` to repeatedly target the exact water tile.
- **Depletion Detection:** Monitors the client journal for spot exhaustion messages (`"the fish don't seem to be biting here"`, `"there are no fish here"`, etc.) and finishes cleanly.
- **Pole Detection & Outfits:** Automatically detects equipped fishing poles or finds one inside your backpack, with `"Fishing"` and `"Archery"` dress profile support.

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

#### [LobsterTrapAuto.py](FesterUO/LobsterTrapAuto.py)

An automated lobster and crab trap management script featuring an interactive on-screen control Gump, automated 5-spot ocean deployment, live buoy tracking, catch retrieval, and trap recycling:

- **Up to 5 Concurrent Traps:** Deploys up to 5 lobster traps from your backpack into the surrounding ocean at well-spaced relative water offsets (Port Bow, Port Railing, Port Stern, Starboard Bow, Starboard Stern) obeying the 1-tile buoy spacing rule.
- **Buoy Tracking & Bob Detection:** Actively tracks deployed trap buoys with elapsed timers (~60-65s cycle) and monitors for server bob/catch events.
- **Automated Haul & Open Cycle:**
  1. Double-clicks the buoy to haul the trap into your backpack.
  2. Double-clicks the retrieved trap in your backpack to open and dump caught lobsters and crabs.
  3. Optionally stashes caught crustaceans into a designated satchel or container.
  4. Immediately re-tosses the emptied trap right back into the ocean at the same spot.
- **Sunk & Destroyed Trap Detection:** Detects when buoys sink or are torn apart in the ocean, updates the **Traps Lost** counter, and automatically pulls replacement traps from your backpack, alerting you when spare traps run out.
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time action status (Deploying, Waiting for Bobs, Hauling, Opening, Redeploying, Paused, Stopped)
  - Active traps counter (`Active Traps: N / 5`)
  - Running **Crustaceans Caught** and **Traps Lost / Sunk** statistics
  - Live Fishing skill level, cap, and skill gain tracking
  - Satchel destination indicator
  - Interactive **Start / Pause / Resume** and **Stop** buttons
  - Interactive **Set Satchel** button to designate a catch storage container
  - Interactive **Set Spots** button to customize water targeting offsets.

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
  - **45.0 – 70.0:** Lightning (Circle 4, 11 Mana, 1 blank scroll, Mandrake Root / Sulfurous Ash)
  - **70.0 – 75.0:** Magic Reflection (Circle 5, 14 Mana, 1 blank scroll, Garlic / Mandrake Root / Spiders' Silk)
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
- **Autonomous Dress Profile Loading:** Automatically equips the configured dress profile / macro (default `"Sorcery"`) at startup, upon exiting every meditation cycle, and whenever resuming from pause, ensuring your spellcasting gear and LRC suit remain equipped throughout training.
- **Tool Upkeep via Tinkering & Pen Discrimination:** Detects broken or missing Scribe's Pens and automatically crafts replacements on the fly using Tinker's Tools and iron ingots (1 ingot each). Strictly verifies pen tooltips via `API.ItemNameAndProps` to ensure Mapmaker's Pens (which share identical graphics `0x0FBF` / `0x0FC0`) are never mistakenly selected or used.
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

#### [TrainMusicianship.py](FesterUO/TrainMusicianship.py)

An automated Musicianship skill training script with interactive control Gump, multi-instrument auto-detection, breakage recovery, and automated container restocking:

- **Multi-Instrument Auto-Detection:** Automatically scans the player's backpack for any valid musical instrument:
  - Lute, Lap Harp, Standing Harp, Drum, Tambourine, Tambourine with Tassel, Bamboo Flute, Fire Horn, and Aud-Char.
  - Displays the active instrument name and live count of spare instruments in the backpack.
- **Seamless Breakage Recovery:** Monitors journal output and inventory changes for broken or exhausted instruments (`"broke your instrument"`, `"worn out"`, `"destroyed"`), automatically switching to the next available instrument in the backpack without missing a beat.
- **Automated Restock Container Integration:**
  - Allows designating a restock container (chest, satchel, crate, or pouch) via configuration or in-game targeting via the Gump's **"Restock"** button.
  - Automatically opens the container and pulls fresh instruments into the backpack whenever backpack reserves run dry.
- **Graceful Depletion Pausing:** If all instruments are exhausted, the script safely pauses execution with player alerts and keeps the control Gump active so training can be resumed with a single click after restocking.
- **Smart Cooldown & Cooldown Handling:** Respects standard UO instrument delays (`PLAY_DELAY`, default 6.0s) and actively reacts to server cooldown wait messages (`"must wait to perform another action"`).
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (`Playing <Instrument>...`, `Waiting cooldown...`, `Restocking...`, `Out of Instruments`, `Paused`, `Complete!`)
  - Live Musicianship skill level, skill cap, and session gain tracking (`+X.X`) with system message gain announcements
  - Active instrument name and backpack count
  - Running counters for **Played** and **Broken** instruments
  - Restock container indicator (`Set (0xSerial)` or `Not Set`)
  - Interactive **Pause/Resume**, **Restock**, and **Stop** buttons
- **Attribution:** Created by FesterHead.

#### [TrainTailoring.py](FesterUO/TrainTailoring.py)

An automated, resource-efficient Tailoring training engine with interactive control Gump, resource satchel support, automated cutting/recycling with Scissors, trash barrel disposal, and Tinkering sewing kit upkeep:

- **Optimal Tailoring Progression:** Automatically monitors your Tailoring skill and recommends the lowest-cost, most resource-efficient recipe in each tier from 0 to 120 (GM / Legendary):
  - **0.0 – 29.0:** Short Pants / Skirt (1–2 cut cloth)
  - **29.0 – 41.5:** Skullcap / Bandana (2 cut cloth)
  - **41.5 – 54.0:** Body Sash / Cap (4–11 cut cloth)
  - **54.0 – 74.0:** Cloak / Robe (14–16 cut cloth)
  - **74.0 – 99.6:** Oil Cloth (1 cut cloth — _ultra resource-efficient workhorse!_)
  - **99.6 – 120.0:** Elven Shirt / Studded Suit (12 cut cloth / 14 cut leather)
- **Milestone Recommendations & "Set Recipe" Override:** Proactively announces when your skill levels past a tier bracket and recommends the next recipe. Players can click **"Set Recipe"** on the Gump at any time to open the craft menu and select any custom recipe.
- **Automated Cutting & Recycling via Scissors:** Automatically detects Scissors in the backpack and cuts newly crafted cloth and leather items back into raw cut cloth and leather, recovering a substantial percentage of materials and drastically reducing training costs.
- **Automated Trash Barrel Disposal (Fallback):** Auto-detects nearby Trash Barrels or allows targeting one on startup or via the Gump's **"Trash Can"** button to automatically discard items that cannot be cut (e.g. certain hats or shoes), preventing weight overloads and backpack clutter.
- **Resource Satchel Integration:**
  - Supports direct satchel crafting or maintains a lightweight working buffer of cloth and leather in the backpack.
  - Automatically restocks materials from the satchel when backpack reserves run low.
  - Supports Cut Cloth (`0x1766`, `0x1767`), Bolts of Cloth (`0x0F95`), Cut Leather (`0x1067`, `0x1081`), and Hides (`0x1078`, `0x1079`).
- **Tool Upkeep via Tinkering:** Detects broken or missing Sewing Kits (`0x0F9D`) and automatically crafts replacements on the fly using Tinker's Tools and iron ingots (1 ingot each).
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (`Crafted`, `Recycling with Scissors...`, `Trashing...`, `Tinkering Sewing Kit...`, `Restocking materials...`, `Paused`, `Finished`)
  - Live Tailoring skill level, skill cap, and automatic skill gain announcements
  - Running counters for **Crafted**, **Cut**, **Trashed**, and **Failed** items
  - Live Satchel and Backpack material counts, plus tool and trash indicators
  - Live character weight indicator (`Weight: Cur / Max`)
  - Interactive **Pause/Resume**, **Set Recipe**, **Satchel**, **Trash Can**, and **Stop** buttons
- **Attribution:** Created by FesterHead.

#### [TrainImbuing.py](FesterUO/TrainImbuing.py)

An automated, resource-efficient Imbuing skill training script with interactive control Gump, Soulforge awareness, dual training modes, auto-unravel recycling, and resource restocking:

- **Dual Training Architecture:**
  - **Reimbue Loop Training (40.0 – 120.0):** Loops the high-speed "Reimbue Last" skill function at a Soulforge on working equipment (daggers, caps, jingasas, etc.), tracking attempts per item up to the optimal 20-imbue limit before diminishing returns.
  - **Mass Unraveling / Recycler Mode (0.0 – 50.0+ / Material Farming):** Automates bulk item and container unraveling at a Soulforge to gain early skill and amass Magical Residues, Enchanted Essences, and Relic Fragments. Supports both backpack containers and external house chests.
- **External Supply Chest & Backpack Drawing:** Automatically differentiates between backpack containers and external chests (such as chests on house tables or ground). When unraveling from an external chest, automatically pulls items into the backpack individually to comply with server backpack proximity rules (`"This item must be in your backpack to be used"`).
- **Skill-Threshold Auto-Return & Session Blacklist:** Detects server messages when an item requires higher Imbuing skill than your character currently possesses (`"You are not skilled enough to unravel this item"`). Automatically moves the item back into the house supply container and blacklists its serial for the duration of the session so it is never pulled again, halting with status `"Supply Depleted"` once all eligible items are processed.
- **Resource-Efficient Recycling via Soulforge Unraveling:** Automatically unravels finished items at the Soulforge after reaching maximum imbue attempts (default 20), reclaiming valuable Magical Residues and Enchanted Essences. Includes alternative Trash Barrel / Discard Bag support for automated non-recyclable item disposal.
- **Milestone Guidance & Success Rate Optimization:** Tracks progression milestones and recommends optimal properties (Reflect Physical Damage, Hit Dispel, Damage Increase, Lower Reagent Cost, etc.) to maintain the ~50–60% success rate sweet spot for maximum skill gains. Features an interactive **"Setup Imbue"** button allowing manual calibration of properties and intensity at any time.
- **Resource Satchel & Chest Restocking / Stashing:** Automatically stashes newly gained unraveled ingredients (Magical Residue, Enchanted Essence, Relic Fragments) from the backpack directly into the designated resource satchel or chest. During imbuing, monitors backpack reserves and automatically restocks working buffers from the satchel when supplies run low.
- **Item Supply Management:** Automatically draws fresh items to imbue from an Item Supply Container into the backpack when an active item reaches capacity.
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time training status (`Imbuing <Item> (N/20)...`, `Unraveling <Item>...`, `Paused`, `Finished`)
  - Live Imbuing skill level, skill cap, and automatic skill gain announcements
  - Item attempt counter (e.g. `Item: Dagger | Attempts: 14/20`)
  - Running counters for **Imbued**, **Unraveled**, and **Failed** attempts
  - Live backpack resource counts (Residue, Essence, Gems) and container binding indicators
  - Interactive **Pause/Resume**, **Mode Toggle**, **Setup Imbue**, **Supply Bag**, **Resources**, **Trash Can**, and **Stop** buttons
- **Attribution:** Created by FesterHead.

#### [TrainImbuingCraftUnravel.py](FesterUO/TrainImbuingCraftUnravel.py)

An intermediate Imbuing training script designed to bridge the skill gain gap when low on Magical Residue or when direct imbuing success rates are inefficient:

- **Craft & Unravel Training Architecture:**
  - **Make Last Crafting Loop:** Uses saws in the player's backpack to craft Oak Quarterstaves via "Make Last" from the Carpentry crafting menu.
  - **Soulforge Unraveling:** Immediately unravels each crafted oak staff at a nearby Soulforge, extracting valuable Magical Residue and Enchanted Essence while actively advancing Imbuing skill.
- **Multi-Saw Management:** Automatically scans and selects saws from the backpack, cycling to the next available saw whenever a tool breaks without interrupting the loop.
- **Resource Satchel Restocking:** Automatically detects or prompts for an oak board satchel in the player's backpack. When root backpack boards fall below threshold (default 12 boards), automatically restocks a batch from the satchel.
- **Auto-Stashing Ingredients:** Automatically moves newly extracted Magical Residue and Enchanted Essence from the backpack into the resource satchel to keep the main backpack uncluttered.
- **Unravel Confirmation Dialog Handling:** Detects and confirms native server unravel confirmation dialogs automatically.
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time status (`Crafting staff...`, `Unraveling...`, `Restocking boards...`, `Paused`, `Running`)
  - Live Imbuing and Carpentry skill levels, caps, and automatic skill gain announcements
  - Running counters for **Crafted**, **Unraveled**, and **Failed** attempts
  - Live resource tracking for Oak Boards (Backpack + Satchel) and available Saws
  - Total Magical Residue and Enchanted Essence counters with session yield totals
  - Interactive **Pause/Resume**, **Set Satchel**, **Set Trash**, and **Stop** buttons
- **Attribution:** Created by FesterHead.

#### [MoveItemsBetweenContainers.py](FesterUO/MoveItemsBetweenContainers.py)

A quick and reliable container-to-container item organizer and transfer utility script:

- **Interactive Targeting:** Prompts the player to target the SOURCE container, then the DESTINATION container (with 10-second timeouts and graceful cancellation).
- **Container Pre-Opening:** Automatically opens the source container (`API.UseObject`) to force the game server to send full container contents to the client if not already cached in memory.
- **Validation & Safety:** Verifies that source and destination are valid and distinct entities, refusing to run if both targets are identical or if the source is empty.
- **Graceful Cancellation & Loop Safety:** Checks `API.StopRequested` on each item iteration to ensure immediate, clean script halts when cancelled in the TazUO UI.
- **Client Synchronization:** Uses `API.Pause(0.65)` between moves to prevent item drag/drop desynchronization or server packet drops.
- **Attribution:** Created by FesterHead.

#### [MoveResources.py](FesterUO/MoveResources.py)

An intelligent container-to-container resource sorting and transfer script with an interactive control Gump:

- **Targeted Categorical Transfer:** Prompts the player to target a SOURCE container, then a DESTINATION container, and automatically transfers all **Reagents**, **Gems**, and **Crafting Resources** (including optional gold/silver currency).
- **Strict Equipment & Scroll Exclusions:** Strictly ignores and leaves untouched in the source container:
  - All scrolls (Magery 1st–8th circle, Necromancy, Spellweaving, Mysticism, blank scrolls, recipe scrolls, power scrolls, and maps)
  - All weapons (swords, axes, maces, staves, spears, bows, crossbows, wands, etc.)
  - All wearable armor and clothing (helmets, gorgets, tunics, sleeves, gloves, leggings, shorts, pants, cloaks, footwear, shields)
  - All wearable jewelry (rings, bracelets, necklaces, earrings) and spellbooks.
- **Comprehensive Coverage:**
  - **Reagents:** Full Magery (8 standard), Necromancy (5), Mysticism, and Pagan reagents.
  - **Gems:** All standard gems (Amber, Amethyst, Citrine, Diamond, Emerald, Ruby, Sapphire, Star Sapphire, Tourmaline) and Mondain's Legacy / Stygian Abyss special gems.
  - **Resources:** Ingots, ore, boards, logs, shafts, feathers, arrows, bolts, leather, hides, cloth, wool, cotton, scales, bones, granite, sand, bandages, empty bottles, cooking staples, and imbuing/special essences.
- **Interactive Control Gump:** Movable, on-screen Gump displaying:
  - Real-time action status (`Targeting...`, `Transferring...`, `Paused`, `Finished`)
  - Live counters for **Reagents Moved**, **Gems Moved**, **Resources Moved**, **Total Moved**, and **Items Skipped** (equipment/scrolls preserved)
  - Interactive **Pause/Resume** and **Stop** buttons.
- **Container Pre-Opening & Validation:** Automatically opens both source and destination containers to force the game server to send full container contents before filtering, refusing to run if source and destination are identical.
- **Attribution:** Created by FesterHead.

#### [MoveArtifacts.py](FesterUO/MoveArtifacts.py)

A targeted container-to-container equipment mover that scans items via active OPL tooltip inspection (`API.ItemNameAndProps`) to identify and transfer Weapons, Armor, Shields, and Jewelry matching configured Artifact and Magic Item rarity tiers:

- **Comprehensive Artifact Tier Coverage:**
  - Automatically identifies and moves all Artifact tiers: **Legendary Artifact**, **Major Artifact**, **Greater Artifact**, **Lesser Artifact**, **Minor Artifact**, and classic **Artifact Rarity** (Doom, Tokuno, Stealable, and Paragon artifacts).
- **Magic Item Tier Support:**
  - Transfers **Greater Magic Items** and **Major Magic Items** by default, with an optional toggle for **Lesser Magic Items**.
- **Broad Equipment Support:**
  - **Weapons:** One-handed, two-handed, swords, maces, fencing, axes, bows, crossbows, staves, wands, and throwing weapons.
  - **Armor & Shields:** Helmets, caps, masks, gorgets, tunics, breastplates, arms, sleeves, gloves, gauntlets, leggings, pants, kilts, and shields.
  - **Jewelry:** Rings, bracelets, necklaces, earrings, and talismans.
- **Strict Non-Equipment Preservation:**
  - Automatically skips and preserves non-qualifying items in the source container, including mundane equipment, low-tier magic items, crafting resources, ingots, ore, boards, leather, reagents, gems, spell scrolls, and books.
- **Interactive Control Gump:** Movable, on-screen Gump featuring:
  - Real-time status display (`Targeting...`, `Scanning equipment...`, `Moving <Item>...`, `Paused`, `Finished`)
  - Running counters for **Weapons Moved**, **Armor & Shields**, **Jewelry Moved**, **Total Moved**, and **Items Skipped**
  - Interactive **Pause/Resume** and **Stop** buttons
- **Pre-Opening Synchronization & Safety:** Automatically opens both source and destination containers to ensure full server inventory synchronization, validating container uniqueness and respecting `API.StopRequested` cancellation.
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
