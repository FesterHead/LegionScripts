# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/FesterHead/LegionScripts/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/FesterHead/LegionScripts/releases/tag/v1.0.0

