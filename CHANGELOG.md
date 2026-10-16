# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Updated `FesterUO/TrainVeterinary.py` to v1.1.0:
  - Added Resource Satchel & Subcontainer Bandage Support: Automatically recognizes and utilizes bandages held inside specialized resource satchels or subcontainers within the player's backpack.
  - Added Automatic Bandage Restocking (`AUTO_RESTOCK_SATCHEL = True`): Automatically monitors backpack bandages and pulls working batches (`RESTOCK_BATCH_SIZE = 100`) from the satchel into the main backpack whenever supply drops below `MIN_BACKPACK_BANDAGES = 20`.
  - Added interactive Gump "Satchel" button (`btn_satchel`): Allows players to manually target and designate their resource satchel or container at runtime, with fallback auto-detection.
  - Updated Gump bandage display: Displays total available bandages across satchels and subcontainers alongside current backpack count (e.g. `Bandages: 10,000 (BP: 100)`).
  - Enhanced bandage resolution in `apply_bandage_to_pet`: Pulls from root backpack, designated satchel, or subcontainers seamlessly to prevent false "Out of Bandages" stops when bandages reside in satchels.

- Updated `FesterUO/TrainAnimalTaming.py` to v1.0.3:
  - Prioritized direct full-name speech release (`<actual_name> release`, e.g. `a hind release`): directly commands newly tamed wildlife using their exact in-game names to open the release confirmation dialog immediately.
  - Set `confirm_release_gump` primary response to `Button 2` (standard CONTINUE button in ServUO/RunUO `PetReleaseGump.cs`) with fallback to `Button 1`, preventing release dialog cancellations.
  - Fixed `cleanup_stuck_followers` targeting: targets tracked follower serials directly to prevent accidentally clicking ambient untamed wildlife (such as innocent deer or great harts).

- Updated `FesterUO/TrainAnimalTaming.py` to v1.0.2:
  - Removed creature renaming (`API.Rename`): completely eliminated the indexed renaming attempt (`Tame1`, `Tame2`, etc.) which caused server-side validation rejections (`System: That name is unacceptable.`) on wild creatures, eliminating unnecessary delays and journal spam.
  - Added in-game `SysMsg` notification when pet release confirmation dialogs are confirmed.

- Updated `FesterUO/TrainAnimalTaming.py` to v1.0.1:
  - Extended `TAME_DELAY` from 12.0s to 18.0s: prevents premature taming timeouts that aborted successful tames (which take 12-14 seconds in standard UO) right before the server sent completion packets, fixing an issue where tamed animals were abandoned without releasing.
  - Added post-loop journal inspection in `execute_tame_attempt` to catch success messages arriving on the final tick.
  - Fixed pet release dialog confirmation (`confirm_release_gump`): prioritized Button 1 (standard Confirm/OK in ServUO/RunUO BaseCreature release gump) with fallback to Button 2, preventing dialog cancellations caused by sending Button 2 first.
  - Refactored `release_pet` to guarantee both packet Context Menu and universal speech (`all release`) attempts without skipping speech if context menu dispatches, properly targeting pets upon cursor prompt.
  - Enhanced lingering follower detection: automatically triggers `cleanup_stuck_followers` whenever follower counts exceed baseline followers, ensuring abandoned pets from interrupted cycles are promptly released.
  - Expanded `RELEASE_JOURNAL_PHRASES` with additional server release match patterns.

- Standardized script versioning and author branding across all 28 scripts in `FesterUO/`:
  - Added internal version constants (`SCRIPT_VERSION: str = "1.0.0"`) to every script.
  - Standardized Gump author and version labels across all 25 interactive interfaces: `lbl_author = API.Gumps.CreateGumpLabel(f"by FesterHead v{SCRIPT_VERSION}", 996)` positioned uniformly in the top header row, alongside simplified, readable title labels.
  - Included version numbers and author attribution in startup console/SysMsg notifications.

- Updated `AGENTS.md` and `.github/copilot-instructions.md`:
  - Added mandatory script versioning and incrementing rules (`SCRIPT_VERSION: str = "X.Y.Z"`): agents must increment the script version on every modification (PATCH for bug fixes/pacing, MINOR for features/controls, MAJOR for architectural overhauls) and reflect it on Gump author labels and startup messages.
  - Added explicit instructions for AI agents and assistants to enforce workspace markdownlint rules defined in `.markdownlint.json` when creating or modifying Markdown files.
  - Mandated resolving all supported formatting issues (equivalent to running the VS Code command `markdownlint: Fix all supported issues in file`), maintaining clean list hierarchies, proper blank line separation between blocks, and eliminating trailing whitespace.

- Updated `FesterUO/MiningAndLumberjackAuto.py`:
  - Added interactive Gump stepper tuning controls (`[-]` / `[+]`) for **Veins per Cycle** and **Trees per Cycle**, enabling real-time ratio adjustments on the fly in-game to match whatever area or resource density you are working in without modifying or restarting the script.
  - Replaced invalid `API.GetItems` calls with `API.ItemsInContainer` for backpack tool and axe discovery.

- Decoupled `FesterUO/HuntAnimals.py` and resource harvesting scripts to operate as completely standalone scripts:
  - Removed all inter-script combat pause semaphores (`ExternalCombatActive`) and harvester coordination persistent variables (`HarvesterRunning`, `HarvestReadyForHunt`).
  - Restored `FesterUO/ChopTreeAuto.py`, `FesterUO/MiningAuto.py`, and `FesterUO/MiningAndLumberjackAuto.py` as fully independent harvesting scripts without external pause loops or persistent character variable signaling.
  - Refactored `FesterUO/HuntAnimals.py` to operate purely as an independent standalone hunting script with a streamlined Gump UI (removed semaphore signal label).
- Updated `FesterUO/HuntAnimals.py`:
  - Added interactive Gump toggle checkboxes (`CreateGumpCheckbox`) for runtime category filtering: **Birds**, **Passives**, **Predators**, and **Defend Threats**. Clicking any checkbox immediately toggles targeting behavior in real-time with client feedback without needing script reloads.
  - Added Pre-Combat Sheep Shearing (`AUTO_SHEAR_SHEEP = True`): Automatically approaches wooly sheep (`0x00CF`) into melee range and shears their wool before engaging in combat, yielding both sheared wool and corpse mutton/hides.
  - Added Backpack Skinning Knife Autodetection: Prioritizes finding a Skinning Knife (`0x0EC4` or by name) directly in the main backpack for shearing and corpse carving, with fallback to shears and other bladed tools.
  - Added interactive Gump checkbox for **Shear Sheep** and real-time counter for **Sheep Sheared** (`Defeated: N | Sheared: N`).
  - Added Karma Protection (`PROTECT_KARMA = True`): Removed horses, llamas, and ostards from passive hunting lists, and added strict exclusions for all karma-losing creatures (`KARMA_LOSS_GRAPHICS` for wild horses, llamas, ostards, dolphins, dogs, and cats) to prevent negative karma loss.
  - Fixed predator false positive prioritization: removed unconditional predator classification from `is_aggressive_mobile` so that ambient predators (wolves, bears, cougars) are only targeted when `HUNT_PREDATORS` is `True` or when actively attacking the player in War Mode, preventing them from overriding `HUNT_PREDATORS = False` and skipping over closer birds and passive animals.
  - Fixed an issue where ambient wildlife was mistakenly rejected due to uninitialized client health packets (`mob.Hits <= 0`), added fallback to `API.NearestMobiles` for mobile discovery, corrected backpack carving tool lookup to `API.FindType`, upgraded combat pursuit to `API.PathfindEntity` with extended corpse approach range, corrected `API.WaitForTarget` keyword argument from `delay` to `timeout`, corrected `API.PathfindEntity` timeout argument to integer (`int`) to prevent `expected Int32, got float` errors, hooked `on_gump_disposed` to `API.Stop()` so right-clicking to close the Gump stops the script immediately without requiring a double toggle on reload, and improved dress profile equipment reliability with increased swap delays (`DRESS_DELAY = 1.25s`), hand verification retries, and War Mode safety checks to prevent equipment change blocks.
- Updated `FesterUO/TrainCooking.py`: Corrected `API.WaitForTarget` keyword argument from `delay` to `timeout`.
- Updated `FesterUO/Fish.py` with hostile mob awareness, automatic combat defense, and Archery dress switching:
  - Actively scans for nearby hostile mobiles (Gray, Criminal, Enemy, Murderer notorieties or sea monsters like Sea Serpents, Krakens, Water Elementals, and Leviathans) within a 12-tile radius.
  - Automatically halts fishing, unquips the fishing pole to backpack, undresses the "Fishing" profile, and switches to the "Archery" dress profile (with backpack bow equip fallback).
  - Enters War Mode and attacks the hostile mobile.
  - Halts automated fishing with a "Combat - Click Start when ready" Gump status, leaving the player in full manual control without automatically resuming fishing until the player clicks "Start".
- Updated `FesterUO/TrainAnimalTaming.py`:
  - Resolved shaky pet release and follower creep issues: fixed a race condition where confirmation gump handling inadvertently sent Button 1 (Cancel) after Button 2 (OK), actively cancelling pet releases on standard RunUO/ServUO servers.
  - Fixed server confirmation gump response targeting (`confirm_release_gump`): omitted invalid gump instance ID from `API.ReplyGump(button)` calls to properly target the active server gump via TazUO's default gump parameter (`1337`), restoring automatic Button 2 (OK) and fallback Button 1 confirmation clicks.
  - Refactored `cleanup_stuck_followers`: added comprehensive follower detection scanning nearby tamed and innocent creatures (`is_innocent_animal`, `(tame)` tooltips, `ignored_mobiles`, and `tamed_pets_pending_release`), dispatches emergency broadcast `all release` with gump confirmation, and resyncs player status packets by interacting with the player paperdoll.
  - Implemented multi-tiered pet release verification (`is_pet_released_state`): expanded release journal keyword detection across 18+ server variants, verified follower count drops, and checked creature notoriety reversion to Gray (`API.Notoriety.Gray`).
  - Enforced server pet command anti-spam pacing: eliminated rapid command bursts, increased general action delay (`ACTION_DELAY = 1.5s`), added explicit command pacing (`COMMAND_DELAY = 1.5s`), spaced server dialog replies (`GUMP_DELAY = 1.0s`), and added detection for server rate-limit messages (`"commands were tried too fast"`) with automatic 2.0s backoff delays.
  - Added follower cap pre-taming safeguard: checks `API.Player.Followers` against `FollowersMax` before attempting to tame and cleans up stuck followers or halts safely.
  - Added indexed pet renaming (`Tame1`, `Tame2`, etc.) upon taming: eliminates pet name ambiguity, spaces, and leading articles during speech release, and permanently flags the creature in the game world.
  - Improved wild mobile target filtering and tamed history: added property/tooltip inspection (`mob.NameAndProps`) to ignore creatures already flagged `[tame]`, `[bonded]`, or `[commandable]`, and automatically skips any wildlife starting with `Tame` to prevent re-taming across script restarts.
  - Added Safe Magery Culling (`ENABLE_MAGERY_CULL`, default `False`): safely casts Energy Bolt on released hostile/gray creatures to clear spawns and train Magery concurrently. Includes strict multi-tier protections against criminal flagging and karma loss (verifies mobile is not owned, strictly forbids casting on `Innocent` (Blue) creatures, checks `KARMA_LOSS_GRAPHICS` and keywords, and verifies mana reserves).
  - Added interactive Gump feature toggle checkboxes (`CreateGumpCheckbox`): provides in-game runtime toggles for **Peacemaking**, **Animal Lore**, **Veterinary**, **Safety Heal**, and **Cull (E-Bolt)**, and added real-time tracking for culled creatures on the statistics label.
- Updated [`.gitignore`](.gitignore) and untracked base TazUO client-generated files (`API.py`, `__builtins__.py`, `_ScriptContext.cs`, `LegionScripts.csproj`) so that client updates and local API stub regenerations do not dirty git status, while keeping user workspace settings (`LegionScripts.code-workspace`) tracked.

### Added

- Added `FesterUO/TrainAnimalTaming.py`: Automated Animal Taming skill training script with interactive control Gump created by FesterHead:
  - Dual Training Architecture:
    - **Wild Roam Mode (`DEFAULT_MODE = "WILD_ROAM"`):** Autonomously scans for nearby wild animals matching the player's skill level within `SEARCH_RADIUS` (18 tiles), pathfinds to them, actively follows moving/fleeing animals during the taming timer, and automatically releases them upon success.
    - **Target Trainer Mode (`DEFAULT_MODE = "TARGET_TRAIN"`):** Continuously tames, releases, and retames a designated or trapped creature (such as a bull, bear, or horse) to rapidly gain skill up to the cap.
  - Active Range Pursuit:
    - Actively tracks target distance during the 10-12s taming countdown, issuing micro-pathfinding steps to keep the player within the strict 2-tile UO proximity requirement without breaking the taming attempt.
  - Integrated Veterinary Healing:
    - Automatically applies bandages to injured or poisoned creatures before release or during retaming cycles, training Veterinary concurrently with Animal Taming.
  - Automated Pet Release & Gump Handling:
    - Commands pet to stop and come adjacent (1 tile) before dispatching context menu or speech commands (`[Name] release` / `all release`). Automatically confirms standard server `PetReleaseGump` dialogs (responding with button 2 for OK/Confirm, button 1 fallback) and retries up to 3 times with state verification to ensure reliable release.
  - Interactive Movable Control Gump:
    - Displays real-time status (`Scanning...`, `Approaching...`, `Taming <Creature>...`, `Releasing...`, `Paused`, `Complete`), live Animal Taming and Veterinary skills with caps and gain trackers, tamed counter, attempt counter, and vet heals counter.
    - Interactive buttons: `Mode: Wild Roam / Target Trainer`, `Auto-Release: ON / OFF`, `Pause / Resume`, and `Stop`.
  - Safety & Peacemaking Support:
    - Optional Peacemaking integration to pacify hostile or angry wildlife before and after taming attempts.
    - Automated emergency self-healing (bandages or Greater Heal) if player HP drops below threshold.

- Added `FesterUO/TrainVeterinary.py`: Automated Veterinary skill training script with interactive control Gump created by FesterHead:
  - Dual Training Architecture:
    - **Dual Pet Sparring Mode (`DEFAULT_MODE = "SPARRING"`):** Coordinates two pets sparring against each other, continuously monitors both health pools, and applies bandages to whichever pet has lower HP or is poisoned.
    - **Single Pet / Patient Mode (`DEFAULT_MODE = "SINGLE"`):** Continuously monitors a single target pet, mount, or summon, applying bandages whenever damaged or poisoned.
  - Emergency Combat Separation:
    - Automatically broadcasts `"all stop"` and `"all follow me"` if either sparring pet falls below `EMERGENCY_HP_PERCENT` (default 30%), holding combat until both pets are healed back above `RESUME_HP_PERCENT` (default 85%).
  - Poison Curing & Ghost Pet Resurrection:
    - Prioritizes curing poisoned pets immediately before standard healing, and automatically detects bonded pet ghosts to attempt resurrection using bandages (requires 80.0+ Veterinary and Animal Lore).
  - Intelligent Bandage Delays:
    - Computes classic UO Dexterity-based bandage application delays (`AUTO_BANDAGE_DELAY = True`) with manual override support.
  - Backpack Supply Management:
    - Monitors remaining bandages in real-time on the Gump and issues low-supply warnings.
  - Interactive Movable Control Gump:
    - Displays real-time status, live Veterinary skill progress with gain tracker, individual pet health gauges with percentage and status tags (`[POISON]`, `[DEAD]`), bandage counter, heal/cure/resurrection statistics, mode toggle, and Pause/Resume/Stop controls.

- Added `FesterUO/TrainImbuing.py`: Automated resource-efficient Imbuing skill training script with interactive control Gump created by FesterHead:
  - Dual Training Architecture:
    - **Reimbue Loop Training**: Loops the high-speed "Reimbue Last" skill function at a Soulforge on working equipment (daggers, caps, jingasas, etc.), tracking attempts per item up to the optimal 20-imbue limit before diminishing returns.
    - **Mass Unraveling / Recycler Mode**: Automates bulk item and container unraveling at a Soulforge to gain early skill (0.0 to 50.0+) and amass Magical Residues, Enchanted Essences, and Relic Fragments.
  - Resource Recycling & Disposal:
    - Automatically unravels finished items at the Soulforge after reaching maximum imbue attempts (or durability capacity), reclaiming valuable Magical Residues and Enchanted Essences.
    - Alternative Trash Barrel / Discard Bag support for automated non-recyclable item disposal.
  - Resource Satchel & Chest Restocking:
    - Monitors backpack Magical Residues, Enchanted Essences, and Gem reserves (Citrine, Amber, Tourmaline, etc.) and restocks working buffers automatically from a designated resource satchel or chest.
  - Item Supply Management:
    - Automatically draws fresh items to imbue from an Item Supply Container into the backpack when an active item reaches capacity.
  - Interactive Movable Control Gump:
    - Displays real-time status, live Imbuing skill and cap with gain announcements, live item attempt counter (e.g. `Item: Dagger (14/20)`), Imbued / Unraveled / Failed counters, and live Resource counts.
    - Interactive buttons: `Pause / Resume`, `Mode: Reimbue / Unravel`, `Setup Imbue`, `Supply Bag`, `Resources`, `Trash Can`, and `Stop`.

- Added `FesterUO/MiningAndLumberjackAndMageryAuto.py`: Unified roaming mining, lumberjacking, and Magery skill training script with interactive ratio tuning Gump created by FesterHead:
  - Tri-skill training engine combining ore deposit mining, static tree lumberjacking, and batch Magery training without target cursor or equipment race conditions.
  - Alternating harvest ratio cycle (`TREES_PER_MINING_SPOT = 4`, `MINING_SPOTS_PER_CYCLE = 1` by default) with automatic dress profile switching (`"Mining"`, `"Lumberjack"`, `"Mage"`).
  - Spot-depletion Magery training cycle: burns accumulated mana on skill-bracket appropriate spells whenever a vein or tree node is depleted before pathfinding to the next node.
  - Supports both Resist Training (Mind Blast, Energy Bolt, Flamestrike with self-healing) and Non-Resist Training (Mana Drain, Invisibility, Mana Vampire).
  - Interactive Movable Control Gump: Displays real-time status, Mining/Lumberjacking/Magery skill levels with gain announcements, Mana/LRC tracking, two-column 8-reagent inventory matrix, interactive stepper buttons (`[-]` / `[+]`) for **Veins/Cycle** and **Trees/Cycle**, and Pause/Resume/Stop controls.

- Added `FesterUO/HuntAnimals.py`: Automated standalone animal and bird hunting script with interactive control Gump and multi-category wildlife selection created by FesterHead:
  - Multi-Category Wildlife Detection:
    - `HUNT_BIRDS` (default True): Targets wild Birds, Eagles, Chickens, Turkeys, and Cranes to generate feathers and poultry.
    - `HUNT_PASSIVE_ANIMALS` (default True): Targets wild Hinds, Great Harts (deer), Cows, Bulls, Pigs, Boars, Sheep, Goats, Llamas, Horses, and Rabbits to generate hides/leather, raw ribs/meat, and wool.
    - `HUNT_PREDATORS` (default False): Optional toggle to hunt wild Wolves, Bears, Cougars, and Panthers.
    - Explicitly ignores players, friends, guildmates, and tamed player pets.
  - Autonomous combat execution: Equips the `"Fighting"` dress profile, enters War Mode, and pursues/attacks fleeing animals until defeated.
  - TazUO AutoLoot Integration & Corpse Carving: Automatically carves animal corpses with equipped axes or backpack bladed tools to produce leather, meat, feathers, and wool, opens the corpse, and triggers TazUO's native AutoLoot agent (`API.AutoLootContainer`) to handle looting according to client settings.
  - Interactive control Gump: Semi-transparent dark UI with live status, animals defeated counter, active categories indicator, and Pause/Resume and Stop buttons.

- Added `FesterUO/TrainTailoring.py`: Automated resource-efficient Tailoring skill training script with interactive control Gump created by FesterHead:
  - Progresses through the optimal resource-efficient progression ladder from 0.0 to 120.0 Tailoring (Short Pants/Skirt -> Skullcap/Bandana -> Body Sash/Cap -> Cloak/Robe -> Oil Cloth [1 cloth!] -> Elven Shirt / Studded Armor).
  - Milestone Recommendations & "Set Recipe" Manual Override: Proactively notifies the player when reaching a skill bracket to recommend the next item, and features an interactive "Set Recipe" button allowing players to manually prime any craft recipe.
  - Automated Cutting & Recycling via Scissors: Detects Scissors in backpack and automatically cuts newly crafted cloth and leather items back into cut cloth and leather, recovering substantial materials.
  - Automated Crafted Item Disposal (Trash Barrel Fallback): Auto-detects nearby Trash Barrels or allows targeting one at startup or via the Gump, automatically depositing items that cannot be cut into the trash barrel.
  - Resource Satchel Integration: Supports direct satchel crafting or automated buffer restocking of cloth and leather into the backpack.
  - Tool Upkeep via Tinkering: Automatically detects broken or missing Sewing Kits and crafts replacements on the fly using Tinker's Tools and iron ingots (1 ingot each).
  - Interactive Control Gump: Features a semi-transparent dark UI displaying real-time training status, live Tailoring skill and cap with gain tracking (+X.X), Recipe recommendation, Crafted / Cut / Trashed / Failed counters, Satchel & Backpack material counts, Tool & Trash indicators, and interactive **Pause/Resume**, **Set Recipe**, **Satchel**, **Trash Can**, and **Stop** buttons.

- Added `FesterUO/MoveArtifacts.py`: Targeted Weapon, Armor, Shield, and Jewelry Artifact and Magic Item Mover with interactive control Gump created by FesterHead:
  - Interactive Container Targeting: Prompts the player to select a SOURCE container and DESTINATION container with timeout and graceful cancellation handling.
  - Active OPL Tooltip Evaluation: Inspects item property lists using `API.ItemNameAndProps` to evaluate exact rarity and artifact tiers directly from the game server.
  - Comprehensive Artifact Tier Coverage: Transfers all artifact tiers including Legendary Artifact, Major Artifact, Greater Artifact, Lesser Artifact, Minor Artifact, and classic Artifact Rarity (Doom, Tokuno, Stealable, and Paragon artifacts).
  - Magic Item Tier Filtering: Supports transferring Greater Magic Items, Major Magic Items, and optional Lesser Magic Items.
  - Wide Equipment Category Support: Filters and moves qualifying Weapons (1H, 2H, ranged, staves, wands), Armor (helms, gorgets, tunics, arms, gloves, leggings), Shields, and Jewelry (rings, bracelets, earrings, necklaces, talismans).
  - Preservation of Non-Qualifying Items: Strictly leaves untouched in the source container all mundane items, low-tier magic equipment, reagents, gems, resources, scrolls, and books.
  - Interactive Control Gump: Features a semi-transparent dark UI with live status, running counters for **Weapons Moved**, **Armor & Shields**, **Jewelry Moved**, **Total Moved**, and **Items Skipped**, and **Pause/Resume** and **Stop** buttons.
- Added `FesterUO/TrainMusicianship.py`: Automated Musicianship skill training script with interactive control Gump created by FesterHead:
  - Multi-Instrument Auto-Detection: Automatically detects and utilizes all standard UO musical instruments (Lute, Lap Harp, Standing Harp, Drum, Tambourine, Bamboo Flute, Fire Horn, and Aud-Char) directly from the player's backpack.
  - Seamless Breakage Recovery: Monitors journal output and backpack inventory for broken or worn-out instruments, automatically cycling to the next spare instrument without interrupting training.
  - Automated Restock Container Integration: Supports setting an instrument restock container (chest, satchel, or crate) via configuration or in-game targeting via the "Set Restock" Gump button, restocking fresh batches when backpack reserves deplete.
  - Graceful Depletion Pausing: Safely pauses training and alerts the player if all instruments are exhausted, leaving the interactive Gump running so the player can restock and click **Resume**.
  - Dynamic Cooldown Management: Enforces standard UO instrument cooldowns (`PLAY_DELAY`, default 6.0s) with active detection and handling of server cooldown wait messages.
  - Interactive Control Gump: Features a semi-transparent dark UI displaying live Musicianship skill with gain tracking (+X.X), active instrument name and backpack count, Played and Broken counters, Restock container indicator, and interactive **Pause/Resume**, **Restock**, and **Stop** buttons.
- Added `FesterUO/LobsterTrapAuto.py`: Automated lobster and crab trap deployment, retrieval, and recycling script with interactive control Gump created by FesterHead:
  - Deploys up to 5 lobster traps from your backpack into the surrounding ocean at well-spaced relative water offsets (Port Bow, Port Railing, Port Stern, Starboard Bow, Starboard Stern).
  - Actively monitors deployed trap buoys with elapsed timers and bob detection (~60-65s cycle).
  - Automatically hauls ready buoys into the backpack, double-clicks retrieved traps to open and dump catches, moves crustaceans (lobsters and crabs) into an optional designated satchel, and immediately re-tosses the emptied traps back into the ocean.
  - Detects sunk or destroyed traps, updating a "Traps Lost" counter and automatically checking the backpack for replacement traps with player notification alerts when spares run out.
  - Features an interactive control Gump displaying real-time action status, active deployed trap count (e.g. 5 / 5), crustaceans caught counter, traps lost/sunk counter, live Fishing skill with gain announcements, Satchel destination indicator, and interactive **Start/Pause/Resume**, **Stop**, **Set Satchel**, and **Set Spots** buttons.
- Added `FesterUO/TrainCooking.py`: Automated resource-efficient Cooking skill training script with interactive control Gump created by FesterHead:
  - Progresses through the optimal cooking progression ladder from 0.0 to 100.0 (Fish Steak / Cooked Ribs -> Dough / Bread Loaf -> Pan of Cookies / Meat Pie -> Baked Fruit Pie / Miso Soup).
  - Features universal crafting engine with dual-mode support: Standard Craft Gump with "Make Last" using Skillets, Flour Sifters, or Rolling Pins, and Direct Heat Source cooking mode using raw food directly on fires, ovens, stoves, forges, or heating stands.
  - Supports dual cooked food handling: Automatically transfers completed food into a designated storage container / cooler or nearby Trash Barrel via backpack serial diff, preventing weight overloads and backpack clutter.
  - Features smart resource satchel integration supporting direct satchel crafting or automated restocking of raw ingredients into the backpack.
  - Supports tool upkeep via Tinkering: Automatically detects missing or broken Skillets and crafts replacements on the fly using Tinker's Tools and iron ingots (2 ingots each).
  - Features heat source awareness, auto-detecting nearby campfires, ovens, stoves, hearths, forges, or portable heating stands.
  - Features an interactive control Gump displaying real-time training status, live Cooking skill and cap with gain tracking, Recipe recommendation, Crafted / Stored / Trashed / Failed counters, Satchel & Backpack ingredient counts, Tool & Destination indicators, Weight indicator, and interactive **Pause/Resume**, **Set Recipe**, **Satchel**, **Storage**, **Trash Can**, and **Stop** buttons.
- Added `FesterUO/TrainCartography.py`: Automated resource-efficient Cartography skill training script with interactive control Gump created by FesterHead:
  - Progresses through the optimal map ladder from 0.0 to 100.0/120.0 (Local Map -> City Map -> Sea Chart -> World Map), consuming 1 blank scroll per craft (with fallback support for blank maps).
  - Supports dual crafted map handling: Automatically transfers completed maps into a designated storage container / map box or nearby Trash Barrel via backpack serial diff, preventing weight overloads and backpack clutter.
  - Features smart resource satchel integration supporting direct satchel crafting or automated restocking of blank scrolls into the backpack.
  - Supports tool upkeep via Tinkering: Automatically detects missing or broken Mapmaker's Pens, strictly rejects Scribe's Pens using active OPL tooltip inspection, closes stale craft menus, and crafts replacement Mapmaker's Pens on the fly using Tinker's Tools, iron ingots, and blank scrolls (1 ingot + 1 scroll) via serial diff tracking.
  - Features an interactive control Gump displaying real-time training status, live Cartography skill and cap with gain tracking, Recipe recommendation, Crafted / Stored / Trashed / Failed counters, Satchel & Backpack blank scroll counts, Tool & Destination indicators, Weight indicator, and interactive **Pause/Resume**, **Set Recipe**, **Satchel**, **Storage**, **Trash Can**, and **Stop** buttons.
- Added `FesterUO/MoveItemsBetweenContainers.py`: Interactive container-to-container item organizer and transfer script created by FesterHead:
  - Prompts the player to target a SOURCE container, then a DESTINATION container with timeout and cancellation handling.
  - Automatically sends an open request to the source container prior to querying items, ensuring container contents are fully received from the server.
  - Safely transfers all top-level items between containers while respecting classic drag/drop delays and responsive `API.StopRequested` checks.
- Added `FesterUO/MoveResources.py`: Targeted resource, reagent, and gem sorting and transfer script with interactive control Gump created by FesterHead:
  - Prompts the player to target a SOURCE container, then a DESTINATION container, and automatically transfers all Reagents, Gems, and Crafting Resources (including optional gold/silver currency).
  - Strictly preserves and leaves untouched in the source container all spell scrolls (1st–8th circle, Necro, Weaving, Mysticism), blank scrolls, recipe scrolls, power scrolls, maps, weapons, armor, shields, clothing (including shorts and pants), wearable jewelry (rings, bracelets, necklaces, earrings), and spellbooks.
  - Features comprehensive item graphics and keyword recognition covering Magery, Necromancy, and Pagan reagents; standard and special ML/SA gems; ingots, ore, boards, logs, shafts, feathers, arrows, bolts, leather, hides, cloth, wool, cotton, scales, bones, granite, sand, bandages, bottles, raw meat, and imbuing/special essences.
  - Features an interactive control Gump displaying real-time transfer status, live counters for **Reagents Moved**, **Gems Moved**, **Resources Moved**, **Total Moved**, and **Items Skipped** (equipment/scrolls preserved), and **Pause/Resume** and **Stop** buttons.
  - Safely pre-opens both containers to ensure server synchronization, validates that targets are distinct, and incorporates responsive cancellation with `API.StopRequested` safety.

### Fixed

- Fixed pen tool confusion and premature termination at 65.0 Inscription in `FesterUO/TrainInscription.py`:
  - In Ultima Online, Scribe's Pens and Mapmaker's Pens share identical graphic IDs (`0x0FBF` and `0x0FC0`). Added pen discrimination via `get_pen_info()` and `is_valid_scribe_pen()` with active OPL tooltip querying (`API.ItemNameAndProps`) to strictly verify Scribe's Pens and reject Mapmaker's Pens.
  - Added `active_pen_serial` tracking and backpack serial diff detection during Tinkering auto-crafting, preventing the script from accidentally picking up Mapmaker's Pens or opening the Cartography menu.
  - Extended the **Lightning** training bracket from 45.0 to 70.0 in `PROGRESSION_LADDER` (Circle 4 spells gain skill up to 70.0), allowing players to train to 70 without switching prematurely to Magic Reflection and requiring Garlic when only using Mandrake Root and Sulfurous Ash.
  - Fixed premature script termination on missing reagents, out of scrolls, or weight limit: `craft_cycle()` now pauses execution (`is_paused = True`), leaves the control Gump interactive, and prompts the user to add materials or change spells via **Set Recipe** and click **Resume**, instead of destroying the Gump and exiting.
  - Added `SPELL_REAGENT_MAP` to dynamically check reagents for the active crafted recipe (supporting manual "Set Recipe" selections like Lightning or Recall) rather than strictly forcing the default recommended spell's reagents.
  - Ensured resource satchel container contents are immediately synced with TazUO via `API.UseObject()` upon selection at startup and via the Gump.
  - Added configurable `DRESS_PROFILE = "Sorcery"` to automatically equip the saved "Sorcery" dress macro / outfit at script startup, upon exiting every meditation cycle, and when resuming from pause.
  - Fixed meditation loop hang in `handle_mana_recovery()`: added server `"at peace"` journal detection to immediately resume crafting when mana finishes regenerating, added trance state tracking to prevent spamming `UseSkill("Meditation")` during active trance, and added a 1-mana tolerance threshold to avoid infinite loops caused by bonus stat rounding or desync.
- Fixed Southeast targeting, cross-boat obstruction, and journal cross-contamination in `FesterUO/FishAuto.py`:
  - Aligned `FISHING_SPOTS` with the exact manual fishing locations identified by the player: Northwest (`(-2, 0)`), Southeast Beam (`(2, 1)` - upper starboard spot behind mast), and Southeast Stern (`(2, 2)` - lower starboard spot clear of the sail).
  - Added `SPOT_FALLBACKS` dictionary for every fishing spot to dynamically switch to adjacent clear water tiles if line-of-sight is temporarily blocked or rejected.
  - Updated `is_open_water()` with `API.GetMultisAt()` detection to identify boat deck, mast, and railing multis, preventing the targeting solver from mistaking boat hull tiles for open water.
  - Fixed journal cross-contamination where depletion messages from Northwest carried over to Southeast via historical journal queries; `is_spot_depleted()` now checks `API.InJournal()` strictly reset via `API.ClearJournal()` before each cast.
  - Re-engineered cast execution in `fish_spot()` to wait reactively for server responses (catches, junk, misses, depletion, or obstacles) and dynamically adjust target distances outward if an obstruction is encountered.
  - Decoupled `combat_triggered` in `main()` so that spot skips or target timeouts do not falsely halt the script into combat pause mode unless an actual hostile mobile is verified.
- Fixed infinite cast loop, false spot depletion, and boat obstruction in `FesterUO/FishAuto.py`:
  - Corrected `FISHING_SPOTS` relative directional vectors for Northeast-bound vessels from diagonal `(-1, -1)` / `(1, 1)` (which cast towards the bow/stern along the boat's length) to perpendicular beam offsets `(-1, 0)` for Port (Northwest) and `(1, 0)` for Starboard (Southeast), casting directly into open ocean off the boat railings.
  - Separated `DEPLETED_KEYWORDS` (`"biting here"`, `"no fish here"`, `"already fished"`) from targeting/obstruction errors in `OBSTACLE_KEYWORDS` (`"cannot see that"`, `"can't fish there"`, etc.).
  - Removed `"what water"` from keywords, as `"What water do you want to fish in?"` is the server's standard prompt when double-clicking a fishing pole, which was falsely triggering obstruction aborts.

## [1.3.0] - 2026-09-30

### Added

- Added `FesterUO/TrainInscription.py`: Automated resource-efficient Inscription skill training script with interactive control Gump created by FesterHead:
  - Progresses through the optimal spell scroll ladder from 0.0 to 120.0 (Reactive Armor -> Poison -> Lightning -> Magic Reflection -> Energy Bolt -> Flamestrike), selecting spells with lowest reagent costs and maximum reliability.
  - Features smart mana management: Continuously monitors player mana against spell requirements and automatically meditates to full mana when depleted, maximizing continuous crafting bursts.
  - Supports dual crafted scroll handling: Automatically moves completed scrolls into a designated storage container / scroll book or nearby Trash Barrel via backpack serial diff, preventing weight overloads and clutter.
  - Fully supports Lower Reagent Cost (LRC) suits (bypassing reagent needs at 100% LRC) while also supporting non-LRC players with automatic reagent restocking from the resource satchel.
  - Includes tool upkeep via Tinkering: Detects broken or missing Scribe's Pens and automatically crafts replacements on the fly using Tinker's Tools and iron ingots (1 ingot each).
  - Features an interactive control Gump displaying real-time training status, live Inscription skill and cap with gain tracking, Mana & LRC indicators, Crafted / Stored / Trashed / Failed counters, blank scroll counts, and interactive **Pause/Resume**, **Set Recipe**, **Satchel**, **Storage**, **Trash Can**, and **Stop** buttons.

### Changed

- Refactored `FesterUO/TrainTinkering.py` to follow the unified architecture of `TrainCarpentry.py` and `TrainBlacksmith.py`:
  - Added automated Trash Barrel detection (`find_nearby_trash_barrel()`) and interactive **"Trash Can"** button on the control Gump.
  - Automatically disposes of newly crafted non-stackable items (Tongs, Heating Stands, excess tools) into the trash barrel via backpack serial diff, while preserving stackable lockpicks and maintaining working tool reserves.
  - Standardized the control Gump layout (Pause/Resume, Set Recipe, Satchel, Trash Can, and Stop buttons) and added milestone announcements for Blacksmith tool requirements (Smith's Hammers at 40.0, Tongs at 45.0).
  - Enhanced resource protection strictly enforcing plain iron ingots (`Hue 0`), protecting colored/special ingots.

### Fixed

- Fixed `UnboundLocalError: local variable 'armor_blocks_meditation' referenced before assignment` in `FesterUO/TrainInscription.py` by adding the missing `global armor_blocks_meditation` declaration in `handle_mana_recovery()`.
- Fixed server disconnection (`Invalid gump response, disconnecting...`) in `FesterUO/TrainTinkering.py`:
  - In ServUO/RunUO, the Tinkering `CraftGump` does not have a "Smelt Item" button (`Resmelt = false` in `DefTinkering.cs`). Attempting to send button ID 14 caused the server to reject the response and disconnect the client.
  - Removed invalid smelt gump replies and transitioned item disposal to use nearby Trash Barrels matching `TrainCarpentry.py`.
- Fixed `NameError: name 'j_text' is not defined` in `FesterUO/TrainTinkering.py`.

## [1.2.0] - 2026-09-27

### Added

- Added `FesterUO/TrainMagery.py`: Automated Magery skill training script derived from [PlayTazUO/PublicLegionScripts](https://github.com/PlayTazUO/PublicLegionScripts/blob/main/Skills/Any/Train%20Magery.py) by FesterHead:
  - Features an interactive control Gump displaying real-time training status (`Casting`, `Meditating`, `Healing`, `Waiting for Mana`, `Paused`, `Finished`), live Magery skill level and cap (`XX.X / XXX.X`) with automatic skill gain announcements, current Mana / Max Mana, Lower Reagent Cost (LRC %), and a live two-column inventory counter for all 8 standard reagents (Black Pearl, Bloodmoss, Garlic, Ginseng, Mandrake Root, Nightshade, Sulfurous Ash, and Spiders' Silk).
  - Includes interactive **Pause/Resume** and **Stop** buttons with responsive time-sliced UI event processing.
  - Supports dual training modes: Resist Training (`RESIST_TRAIN = True`) casting offensive circle spells on self with automatic self-healing (Spirit Speak or Greater Heal) to train Resisting Spells simultaneously, and Non-Resist Training (`RESIST_TRAIN = False`) casting non-damaging spells (Mana Drain, Invisibility, Mana Vampire).
  - Features smart startup validation, vendor training recommendations for low skill levels, mana threshold detection, Lower Reagent Cost (LRC) checking, and automated Meditation recovery.
- Added `FesterUO/MiningAndMageryAuto.py`: Unified roaming mining and Magery training engine that coordinates targeting, equips, and skill delays within a single script:
  - Eliminates target cursor collisions and action desyncs caused by running separate mining and spellcasting macros.
  - Features an optimized batch workflow: Mines each deposit continuously until depleted, then enters a dedicated training cycle to burn available mana on skill-appropriate Magery spells until spell points run dry before moving to the next vein.
  - Synergizes passive mana regeneration: Mana regenerates while walking and harvesting the next node, creating an efficient perpetual cycle.
  - Automatically loads the configured mining dress profile before every pickaxe/shovel swing, and supports an optional separate mage dress profile (`DRESS_PROFILE_MAGE`) for casting.
  - Features an interactive control Gump tracking action and mage status, veins mined, ores mined, live Mining and Magery skills with gain announcements, Mana, LRC %, and a live two-column reagent counter.
- Added `FesterUO/MiningAndLumberjackAuto.py`: Unified roaming miner and lumberjack script with integrated control Gump:
  - Alternating harvest cycle: Mines one ore deposit or cave rock until depleted, then automatically equips lumberjack gear and chops one tree until depleted, repeating seamlessly.
  - Autonomous equipment & dress switching: Automatically equips the `"Mining"` dress profile (pickaxe/shovel) during the mining phase, and switches to the `"Lumberjack"` dress profile (axe) during the woodcutting phase.
  - Spatial scanning & memory: Scans for cave floors, mountain edges, and boulders for mining, and scans static trees via TazUO's native vegetation detection for lumberjacking, with independent depletion history queues to prevent revisiting depleted spots.
  - Integrated control Gump displaying real-time activity status, dual live skill tracking for **Mining** and **Lumberjacking** with automatic gain announcements, combined counters for **Veins Mined / Total Ore** and **Trees Chopped / Total Logs**, Strength and Dexterity stats, Weight capacity monitoring, and interactive Pause/Resume and Stop buttons.
  - Backpack weight protection (`MAX_WEIGHT_CHECK`, `WEIGHT_BUFFER = 15`) halting execution before becoming overburdened.
- Added `FesterUO/ChopTreeAndMageryAuto.py`: Unified roaming lumberjacking and Magery training engine that coordinates tree chopping and spellcasting:
  - Eliminates targeting cursor collisions and equip conflicts between simultaneous lumberjacking and spellcasting routines.
  - Features an optimized batch workflow: Chops each tree continuously until depleted, then enters a dedicated training cycle to burn available mana on skill-appropriate Magery spells until spell points run dry before pathfinding to the next tree.
  - Synergizes passive mana regeneration during walking and harvesting phases.
  - Automatically loads the configured lumberjack dress profile before every axe swing, with optional mage outfit switching.
- Added `FesterUO/TrainBlacksmith.py`: Automated resource-efficient Blacksmithing training script with interactive control Gump:
  - Automatically progresses through the lowest ingot-per-attempt items from 0 to 120 (Mace -> Maul -> Short Spear -> Platemail Gorget -> Platemail Gloves/Arms/Legs/Tunic).
  - Features resource satchel integration: Prompts player on launch to target their resource satchel, maintains a lightweight buffer of ingots in the main backpack (default 40–80 ingots) to prevent overburdening, and returns smelted/recycled ingots back into the satchel.
  - Strict resource protection: Exclusively counts, restocks, and consumes regular iron ingots (`Hue 0`), strictly ignoring and protecting colored/special ingots (Dull Copper, Shadow Iron, Copper, Bronze, Gold, Agapite, Verite, Valorite).
  - Automatically smelts and recycles crafted items at a nearby forge to reclaim 50%–90% of raw ingots.
  - Includes tool upkeep via Tinkering: Detects broken or missing tools and automatically crafts replacements on the fly using Tinker's Tools and ingots, prioritizing Tongs (only 1 ingot at 45.0+ Tinkering) over Smith's Hammers (4 ingots).
  - Includes an interactive control Gump with status display, live Blacksmithing skill and cap with gain announcements, running counters for Crafted / Smelted / Failed items, live Satchel and Backpack ingot counts, tool status, and Pause/Resume, Set Recipe, Set Satchel, and Stop buttons.
- Added `FesterUO/TrainTinkering.py`: Automated resource-efficient Tinkering skill training script with interactive control Gump:
  - Progresses through the lowest-ingot items from 0 to 100 (Tinker's Tools -> Tongs -> Lockpicks -> Heating Stand).
  - Highlights critical Blacksmithing synergy milestones: Unlocks crafting Smith's Hammers at 40.0 Tinkering and Tongs at 45.0 Tinkering.
  - Perpetual self-tool crafting: Automatically crafts replacement Tinker's Tools (2 ingots) when tool count falls low, ensuring the training loop never exhausts tools.
  - Resource satchel integration: Prompts player on launch to target their resource satchel, maintains a lightweight buffer of ingots in the main backpack (default 40–80 ingots), and deposits recycled/excess ingots back into the satchel.
  - Strict resource protection: Exclusively counts, restocks, and consumes regular iron ingots (`Hue 0`), protecting colored/special ingots.
  - Auto-smelting: Automatically smelts recyclable items (Tongs) when standing near a forge.
  - Interactive control Gump with real-time status, live Tinkering skill tracking, gain announcements, running statistics (Crafted, Smelted, Failed, Tools Made), satchel/backpack ingot counts, and Pause/Resume, Set Recipe, Set Satchel, and Stop controls.
- Added `FesterUO/TrainCarpentry.py`: Automated resource-efficient Carpentry skill training script with interactive control Gump:
  - Progresses through the lowest-board items from 0.0 to 120.0 (Wooden Box -> Vesper-Style Chair -> Ballot Box Deed -> Bokuto -> Quarter Staff -> Gnarled Staff).
  - Proactive milestone recommendations: Emits system message notifications upon reaching skill brackets recommending the next optimal item, with an interactive "Set Recipe" button to override or switch recipes at any time.
  - Automated Trash Barrel disposal: Auto-detects nearby Trash Barrels or allows targeting one at startup, automatically disposing of newly crafted furniture/weapons via backpack serial diff to eliminate overweight and backpack clutter. Includes an on-screen "Trash Can" button to set/change trash barrels.
  - Resource satchel integration: Prompts player on launch to target their wood/resource satchel or container, maintains a lightweight buffer of boards in the main backpack (default 20–60 boards), and deposits excess boards back into the satchel.
  - Tool upkeep via Tinkering: Automatically detects broken or missing tools and crafts replacement Dovetail Saws (30.0+ Tinkering) or Saws, automatically pulling ingots from the resource satchel and returning leftovers.
  - Interactive control Gump with real-time status, live Carpentry skill tracking with gain announcements, running statistics (Crafted, Trashed, Failed), satchel/backpack board counts, tool and trash status, and Pause/Resume, Set Recipe, Satchel, Trash Can, and Stop controls.

### Changed

- Configurable harvesting ratio in `FesterUO/MiningAndLumberjackAuto.py`:
  - Added configurable `TREES_PER_MINING_SPOT` (defaults to 8, configurable) and `MINING_SPOTS_PER_CYCLE = 1` to harvest multiple trees per mining deposit.
  - Optimized equipment switching to bypass dress delays between consecutive trees when the axe is already equipped.
  - Updated status displays to show cycle step counters (e.g., `Chop 2/8 (X, Y) #3`).
- Enabled direct satchel crafting (`DIRECT_SATCHEL_CRAFTING = True`) across `FesterUO/TrainCarpentry.py`, `FesterUO/TrainBlacksmith.py`, and `FesterUO/TrainTinkering.py`:
  - Scripts now craft directly from the resource satchel with `0` boards/ingots needed in the main backpack, preserving weight capacity.
  - Automatically deposits any reclaimed or loose materials from backpack into the satchel.
  - Includes automatic fallback restocking if a server or container ever requires materials in the root backpack.
- Added configurable retry limit (`MAX_TOOL_CRAFT_ATTEMPTS = 8`, default 8 attempts) to `FesterUO/TrainBlacksmith.py` when auto-crafting replacement smithing tools via Tinkering, with automatic mid-retry ingot restocking from the satchel.
- Added configurable per-cycle spell cast limit (`MAX_MAGERY_CASTS_PER_CYCLE = 8`) to `FesterUO/MiningAndMageryAuto.py` and `FesterUO/ChopTreeAndMageryAuto.py` to bound the Magery training phase after a deposit or tree is depleted, automatically returning to harvesting once the cast limit is reached without waiting for high mana pools to fully empty (set to `0` for unlimited / until mana is depleted).
- Refactored `FesterUO/MiningAndMageryAuto.py` and `FesterUO/ChopTreeAndMageryAuto.py` from interleaved per-swing casting to spot-depletion mana burn cycles (`burn_magery_cycle()`), allowing fast, uninterrupted harvesting swings followed by dedicated mana-burning spell sessions once nodes are depleted.
- Updated `FesterUO/MiningAuto.py` to automatically load `DRESS_PROFILE` and refresh the equipped mining tool before every individual mine swing in addition to initial startup.

### Fixed

- Fixed `navigate_to_deposit()` argument count mismatch in `FesterUO/MiningAndLumberjackAuto.py` by adding `spot_index` and `total_spots` parameters to match cycle progress tracking calls.
- Fixed Carpentry progression plateaus at 46.0 and 72.3 in `FesterUO/TrainCarpentry.py`:
  - On standard UO/ServUO/RunUO mechanics, craft success chance hits 100% at `MinSkill + 25.0`, causing skill gains to stall before reaching the next tier item.
  - Added Vesper-Style Chair (min skill 42.1, 15 boards) to bridge the 42.1–47.3 bracket where Wooden Box capped at 46.0 before Ballot Box Deed unlocked at 47.3.
  - Added Bokuto (min skill 70.0, 6 boards) or Wooden Shield (min skill 52.6, 9 boards) to bridge the 70.0–73.6 bracket where Ballot Box Deed capped at 72.3 before Quarter Staff unlocked at 73.6.
- Fixed continuous hammer crafting loop in `FesterUO/TrainBlacksmith.py`:
  - When auto-crafting a replacement Smith's Hammer via Tinkering, the Tinkering craft gump remained open on the client; the trainer subsequently sent "Make Last" (`ReplyGump(21)`) to the lingering Tinkering gump instead of the Blacksmithing gump.
  - Added explicit Tinkering craft gump closure (`API.ReplyGump(0, gump_id)`) upon hammer completion.
  - Added active tool serial tracking (`active_tool_serial`) to detect tool changes or broken tools, ensuring any non-blacksmith gump is closed and the new hammer is explicitly double-clicked before resuming the craft loop.
  - Added `0x0FB4` to `SLEDGEHAMMER_GRAPHICS` and filtered weapon hammers (e.g. War Hammer) out of smithing tool detection.
- Fixed regular iron ingot detection in `FesterUO/TrainBlacksmith.py` and `FesterUO/TrainTinkering.py`:
  - Standard iron ingots are named `<count> Ingots` rather than containing the word `iron`. The strict name check erroneously rejected standard iron ingots, causing the trainer to report `Out of Ingots` despite ingots being in the backpack and satchel.
  - Refactored `is_regular_iron_ingot` to verify `Hue == 0` and explicitly filter out special ore names (`dull`, `shadow`, `copper`, `bronze`, `gold`, `agapite`, `verite`, `valorite`).
- Fixed `ensure_tinker_tools()` in `FesterUO/TrainTinkering.py` to only attempt auto-crafting spare tools via Make Last when the active recipe is `Tinker's Tools`, preventing tool maintenance from overriding higher-tier recipes (Lockpicks, Tongs).
- Fixed runtime `SystemError: MakeGenericType on non-generic type` in `FesterUO/TrainMagery.py` by removing subscripted generic built-ins (`dict[...]`, `tuple[...]`, `list[...]`) that fail under Python.NET's type reflection.
- Fixed `'LegionAPI' object has no attribute 'GetLandTile'` in `FesterUO/MiningAndMageryAuto.py` by using `API.GetTile(x, y)` for land terrain tile scanning.
- Fixed `"You must wait to perform another action"` stalling and premature deposit depletion in `FesterUO/MiningAndMageryAuto.py` and `FesterUO/ChopTreeAndMageryAuto.py`:
  - Resolved dress profile thrashing by loading the dress profile upon deposit arrival rather than spamming `API.Dress()` 0.2 seconds before every individual swing.
  - Added post-spellcasting recovery cooldowns (1.0s) after `burn_magery_cycle()` completes.
  - Added 3-attempt retry loop with automatic 1.2s delay backoff when the server returns `"must wait to perform another action"`, preventing false target timeouts from aborting deposits.

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
