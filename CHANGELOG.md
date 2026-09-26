# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added `FesterUO/TrainMagery.py`: Automated Magery skill training script derived from [PlayTazUO/PublicLegionScripts](https://github.com/PlayTazUO/PublicLegionScripts/blob/main/Skills/Any/Train%20Magery.py) by FesterHead:
  - Features an interactive control Gump displaying real-time training status (`Casting`, `Meditating`, `Healing`, `Waiting for Mana`, `Paused`, `Finished`), live Magery skill level and cap (`XX.X / XXX.X`) with automatic skill gain announcements, current Mana / Max Mana, Lower Reagent Cost (LRC %), and a live two-column inventory counter for all 8 standard reagents (Black Pearl, Bloodmoss, Garlic, Ginseng, Mandrake Root, Nightshade, Sulfurous Ash, and Spiders' Silk).
  - Includes interactive **Pause/Resume** and **Stop** buttons with responsive time-sliced UI event processing.
  - Supports dual training modes: Resist Training (`RESIST_TRAIN = True`) casting offensive circle spells on self with automatic self-healing (Spirit Speak or Greater Heal) to train Resisting Spells simultaneously, and Non-Resist Training (`RESIST_TRAIN = False`) casting non-damaging spells (Mana Drain, Invisibility, Mana Vampire).
  - Features smart startup validation, vendor training recommendations for low skill levels, mana threshold detection, Lower Reagent Cost (LRC) checking, and automated Meditation recovery.

### Changed

- Updated `FesterUO/MiningAuto.py` to automatically load `DRESS_PROFILE` and refresh the equipped mining tool before every individual mine swing in addition to initial startup.

### Fixed

- Fixed runtime `SystemError: MakeGenericType on non-generic type` in `FesterUO/TrainMagery.py` by removing subscripted generic built-ins (`dict[...]`, `tuple[...]`, `list[...]`) that fail under Python.NET's type reflection.

## [1.1.0] - 2026-09-20

### Added

- Added `.markdownlintignore` and `.markdownlint.json` mirroring `cygnus-player` standards to ignore AI artifact files (`implementation_plan.md`, `walkthrough.md`) and configure markdownlint rules.
- Added `FesterUO/MiningAuto.py`: Automated roaming mining script that loads the "Mining" dress profile, scans nearby mountain land tiles, cave floors/walls, rock outcroppings, boulders, and ore nodes using the complete 200+ tile ServUO mining definition, filters candidate deposits by current Mining skill tier, pathfinds within reach, swings pickaxe or shovel with automatic click-target fallback until depleted, remembers the last 30 visited veins, and tracks veins mined, ores mined, live Mining skill, and STR/DEX on an interactive control Gump with Pause/Resume and Stop buttons.
- Added an interactive control Gump to `FesterUO/Fish.py` featuring:
  - An interactive "Start" button to initiate the water targeting selector and automated fishing loop.
  - Toggling button state to "Stop" during casting to allow safe early cancellation of the current fishing spot.
  - Current activity status (`Ready`, `Click water to fish...`, `Fishing (Cast #N)...`, `Spot Depleted`, `Stopped`).
  - Spot cast counter that restarts at zero whenever "Start" is clicked.
  - Persistent running totals of regular Fish, Small Fish, and Junk caught while the Gump remains open across spots.
  - Live Fishing skill value/cap tracking with automatic skill gain announcements.
  - Multi-source catch detection utilizing both backpack delta checks and client journal parsing.

### Changed

- Configured `FesterUO/FishAuto.py` for dual-side (Northwest & Southeast) boat railing harvesting:
  - Targets water tiles off the two sides of the vessel (Northwest and Southeast) at 2–4 tiles distance, completely avoiding line-of-sight obstructions caused by the mast, sail, bowsprit, and stern.
  - Set boat movement advancement to 8 spaces (`BOAT_STEPS = 8`, `"forward one"`) to advance across an $8 \times 8$ resource block between side-harvesting cycles.
  - Added live catch statistics to the control Gump: tracks and displays **Fish Caught** and **Junk Caught** totals in real-time alongside Live Skill, Status, and Enemies Defeated counters.
  - Added configurable TazUO Organizer agent execution (`RUN_ORGANIZER = True`, `ORGANIZER_NAME = "FishOrganizer"`) triggered automatically via journal detection (`"you pull out"`, `"you catch"`) whenever any fish (raw fish, named fish like amberjack, or steaks) is caught.
  - Streamlined catch detection to rely directly on in-game system messages, eliminating the need for hardcoded raw fish graphic IDs.
  - Simplified resource depletion and tool breakage detection across `FesterUO/FishAuto.py`, `FesterUO/Fish.py`, `FesterUO/MiningAuto.py`, `FesterUO/ChopTree.py`, and `FesterUO/ChopTreeAuto.py`:
    - Replaced redundant uppercase/lowercase string duplicates and punctuation permutations with concise, case-insensitive keyword root lists (`DEPLETED_KEYWORDS`, `TOOL_BROKEN_KEYWORDS`).
    - Standardized depletion and tool breaking checks to scan lowercased recent journal entries with an `InJournal` fallback.
  - Updated in-code docstrings, usage instructions, and `README.md` to reflect dual-side railing harvesting, 8-step navigation, and automatic fish organizing.

### Fixed

- Fixed `NameError: name 't' is not defined` during resource depletion and tool breakage checks in `FesterUO/ChopTreeAuto.py`, `FesterUO/ChopTree.py`, and `FesterUO/MiningAuto.py` caused by shadowing `kw` instead of using `t` in list comprehension iterations over `recent_text`.
- Fixed junk catch detection and Gump counter tracking in `FesterUO/FishAuto.py`:
  - Added `JUNK_JOURNAL_KEYWORDS` (`"waterlogged junk"`, `"pull out an item"`, `"an item :"`, `"toss waterlogged"`, etc.) to intercept junk catches directly from client journal and server auto-toss system messages.
  - Resolved an issue where `"You pull out an item : shoes"` matched `"you pull out"`, incorrectly incrementing the fish counter instead of the junk counter.
  - Updated `dispose_junk(already_counted=True)` to support journal-detected catches, preventing double-counting while maintaining a backpack scan fallback for shards without automatic server-side disposal.
- Fixed combat weapon switching in `FesterUO/FishAuto.py` when encountering sea enemies:
  - Corrected `API.Notoriety.CanBeAttacked` to `API.Notoriety.Gray` to resolve runtime `AttributeError` when scanning for hostiles.
  - Unconditionally invokes `API.Undress("Fishing")` before applying `"Archery"` to free all gear and hand slots.
  - Excluded dolphins (`IGNORED_MOBILES = ["dolphin"]`) from hostile targeting in `find_hostile_enemy()`, preventing harmless sea creatures from triggering attack mode.
  - Switched combat response from an automated kill loop to an engaging attack halt: after undressing fishing, equipping archery, entering war mode, and sending the attack command, the script halts automated fishing and displays a **"Start"** button on the Gump so players can manually fight and loot, then click "Start" to seamlessly re-equip fishing gear and resume.
  - Added fallback bow equipping directly from the backpack, iterating each bow graphic individually to match `API.FindType(graphic: int)`'s `UInt32` signature.
  - Added startup and combat verification via `API.GetAvailableDressOutfits()` to warn the user if the configured combat profile name does not match their TazUO dress configurations.
- Fixed obstruction errors and water tile detection in `FesterUO/FishAuto.py`:
  - Corrected `is_open_water` to recognize water land tiles (`tile.Graphic in LAND_WATER_GRAPHICS` or `IsWet`) without false rejection by the land `Impassable` flag.
  - Adjusted quadrant target search distance from 4-6 tiles down to 2-4 tiles (defaulting to 2 tiles directly over the railing), ensuring casts remain within UO's 4-tile fishing limit and clear distant cliffs.
  - Added `"obstructed"`, `"Obstructed"`, `"that is obstructed"`, and `"target is obstructed"` to `DEPLETED_MESSAGES` and `is_spot_depleted()` so that any quadrant blocked by the boat mast, sail, or cliff walls is skipped immediately on the first cast instead of stalling.
- Fixed water land tile targeting in `FesterUO/FishAuto.py` by sending `API.Target(tx, ty, tz)` without passing static graphic parameters on terrain water tiles to eliminate target packet mismatches.
- Added graceful target fail recovery in `FesterUO/FishAuto.py` to automatically skip an obstructed quadrant spot (such as shorelines or obstacles) after 2 failed attempts rather than stalling.
- Fixed mountain land tile targeting in `FesterUO/MiningAuto.py` by distinguishing land tiles from statics and invoking `API.TargetLandRel(dx, dy)` / `API.Target(tx, ty, tz)` (omitting the static graphic parameter for terrain tiles) to prevent repeatedly re-popping `"Where do you wish to dig?"`.
- Fixed vein depletion tracking in `FesterUO/MiningAuto.py` by storing depleted vein center points and checking distance rather than pushing 169 individual tile coordinates into a fixed-size FIFO queue, preventing premature cache eviction that previously caused the miner to bounce back and forth between two spots.
- Fixed mountain pathfinding in `FesterUO/MiningAuto.py` by using direct native pathfinding (`distance=1` and `distance=2`) along mountain edges with a walkable perimeter stand fallback rather than prematurely filtering deposits out of candidate discovery.
- Added instant vein smelting detection in `FesterUO/MiningAuto.py` by parsing journal messages (`"You instantly smelt the vein into X ingots and stow them."`) to accurately increment the ores mined count when ore is immediately smelted.
- Fixed `'LegionAPI' object has no attribute 'GetAllItems'` in `FesterUO/MiningAuto.py` by replacing the non-existent method call with `API.FindTypeAll` on mineable ground graphics and focusing on static tile scanning via `API.GetStaticsInArea`.
- Fixed `UnboundLocalError: local variable 'start_requested' referenced before assignment` in `FesterUO/Fish.py` by properly declaring `global start_requested, is_stopped, is_fishing` inside `main()`.

## [1.0.0] - 2026-09-19

### Added

- Base client install files providing IDE IntelliSense and API support for TazUO Legion scripting:
  - `API.py`: Legion Python API stub and interface definitions.
  - `__builtins__.py`: Global import hook enabling IDE language servers to resolve `API` symbols.
  - `_ScriptContext.cs`: Static API context definition for C# script IntelliSense.
  - `LegionScripts.csproj`: C# project configuration referencing TazUO assemblies.
  - `LegionScripts.code-workspace`: VS Code workspace configuration.
- `FesterUO/ChopTree.py`: Automated lumberjacking script with tree targeting and depletion detection, housed in dedicated `FesterUO/` scripts folder.
- `FesterUO/ChopTreeAuto.py`: Automated roaming lumberjacking script that scans nearby tree statics, pathfinds to trees, chops until depleted, remembers the last 30 visited trees, and respects player weight capacity.
- `FesterUO/TrainAnatomy.py`: Automated Anatomy skill training script with configurable standard UO skill wait timer, self/custom targeting, and auto-cap termination.
- `FesterUO/Fish.py`: Automated targeted fishing script prompting player for water location, locking coordinates, and harvesting until spot depletion.
- `FesterUO/FishAuto.py`: Automated boat fishing and combat defense script featuring interactive control Gump, dynamic dual-spot Northeast harvesting, 8-step sequential boat forward movements, backpack ocean junk disposal, live Fishing skill tracking, and automatic combat switching to Archery to attack and kill hostile enemies before stopping cleanly.
- `FesterUO/TrainChivalry.py`: Automated Chivalry skill training script casting tier-appropriate spells with auto-meditation support, low tithing alerts, and an interactive control Gump (adapted from Public Legion Scripts).
- Project scaffolding and community standards:
  - `README.md` with architecture breakdown, setup instructions, and script descriptions.
  - `LICENSE` under MIT license (FesterHead).
  - `CONTRIBUTING.md` guidelines for scripting, development, and subfolder organization by author name or shard name.
  - `AGENTS.md` and `.github/copilot-instructions.md` agent and Copilot guardrails.
  - `.github/PULL_REQUEST_TEMPLATE.md` pull request template with subfolder verification.
  - `.gitignore` for Python and .NET build artifacts.

### Changed

- Added descriptive header docstring with author attribution and usage instructions to `FesterUO/ChopTree.py`.
- Added configurable `DEBUG` flag and `debug_msg()` helper in `FesterUO/ChopTree.py` to optionally output verbose targeting and swing progress messages.
- Added configurable `SWING_DELAY` setting in `FesterUO/ChopTree.py` (defaults to 1.0s for FesterUO; configurable to 4.5s–5.0s for standard UO shards).
- Added interactive on-screen control Gump to `FesterUO/ChopTreeAuto.py` with real-time status display, trees harvested counter, Pause/Resume toggle, and Stop button.
- Added `"can't use an axe on that"`, `"cannot use an axe on that"`, and `"it appears immune to your axe"` to `DEPLETED_MESSAGES` in `FesterUO/ChopTreeAuto.py` and `FesterUO/ChopTree.py` to flag unharvestable/invalid tree statics as done and automatically move on to the next tree.
- Added live Lumberjacking skill level/cap, Strength, and Dexterity displays to the `FesterUO/ChopTreeAuto.py` control Gump with automatic updates and gain announcements.
- Added configurable `DRESS_PROFILE` (default `"Lumberjack"`) to `FesterUO/ChopTree.py` and `FesterUO/ChopTreeAuto.py` to automatically equip saved lumberjacking outfits at startup.
- Relocated `TrainChivalry.py` to `FesterUO/TrainChivalry.py` with full source reference attribution, adding an interactive on-screen control Gump featuring real-time training status, current Mana and Max Mana, Tithing Points, Chivalry skill score/cap with gain announcements, and Pause/Resume and Stop buttons.
- Added smart startup validation to `FesterUO/TrainChivalry.py` that verifies mana and tithing requirements for the initial spell before training begins, displaying clear status warnings on the Gump and in client chat before stopping safely.
- Enhanced `README.md` with top metadata badges and section heading iconography matching the `cygnus-player` style aesthetic.
- Modernized all Gump creation and control binding in `FesterUO/FishAuto.py`, `FesterUO/ChopTreeAuto.py`, and `FesterUO/TrainChivalry.py` to use the updated `API.Gumps.*` methods (`API.Gumps.CreateGump`, `API.Gumps.CreateGumpLabel`, `API.Gumps.CreateSimpleButton`, `API.Gumps.AddControlOnClick`, `API.Gumps.AddGump`, etc.) to eliminate client deprecation warnings.
- Optimized Chivalry training progression in `FesterUO/TrainChivalry.py` to cast **Consecrate Weapon up to 45.0** (aligning with standard UO 50% success difficulty curve) before switching to Divine Fury, added hand detection for an equipped weapon when casting Consecrate Weapon, and added skill lock detection.
- Added configurable `DRESS_PROFILE = "Archer"` in `FesterUO/TrainChivalry.py` to automatically load and re-equip saved weapon profiles at startup, after meditation un-equips hands, and prior to casting Consecrate Weapon.

### Fixed

- Fixed `SystemError: MakeGenericType on non-generic type` in TazUO Legion's PythonNet runtime by removing PEP 604 pipe union type annotations from `FesterUO/TrainChivalry.py`.
- Re-architected `FesterUO/Fish.py` to directly mirror the proven `ChopTree.py` loop structure: prompt for target, lock coordinates, cast with configurable timing (`FISHING_DELAY = 2.0s`), retry on cursor latency, and added dual-layer case-insensitive and unicode apostrophe-safe depletion detection (`is_spot_depleted`) so messages like `"The fish don't seem to be biting here."` reliably halt execution.
