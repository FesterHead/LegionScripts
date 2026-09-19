# GitHub Copilot Instructions - TazUO Legion Scripts

This repository contains automation scripts written for the TazUO Ultima Online client's Legion scripting engine.

## Core Directives

1. **Target Environment:** TazUO Legion Scripting (Python and C#). Scripts run directly inside the TazUO client runtime.
2. **Project Author / Attribution:** FesterHead.
3. **Preserve Base Client Files:**
   - Never edit or rewrite `API.py`, `__builtins__.py`, `_ScriptContext.cs`, `LegionScripts.csproj`, or `LegionScripts.code-workspace`.
   - Use `API.py` as the local authority for method names, types, and signatures.
4. **Mandatory Scripting Patterns:**
   - **`API.StopRequested`:** Always verify `not API.StopRequested` in loops so the user can stop the script in-game cleanly.
   - **Pauses:** Always use `API.Pause(seconds)` for delays. Never use Python's built-in `time.sleep()`.
   - **Imports:** Always write `import API` at the beginning of Python script files for IDE resolution.
   - **Feedback:** Use `API.SysMsg(...)` for messages to the game screen / system message log.
   - **Journal Management:** Call `API.ClearJournal()` before triggering an action that writes to the journal, and inspect using `API.InJournal(...)`.
5. **Documentation & Changelog:**
   - Keep `CHANGELOG.md` updated in the `## [Unreleased]` section following Keep a Changelog conventions.
   - Keep `README.md` updated with descriptions and usage guidelines for all scripts.
6. **Script Organization:**
   - Always place contributed or generated scripts into a subfolder named after the **author** (e.g., `FesterUO/`) or target **shard name** (e.g., `Outlands/`). Never place script files in the repository root directory.
