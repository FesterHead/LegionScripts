# AGENTS.md - TazUO Legion Scripts

## Project Context

This project is dedicated to developing and maintaining automation and utility scripts for the **TazUO Ultima Online client** using its built-in **Legion Scripting engine**.

- **Repository Owner:** FesterHead
- **Target Client:** TazUO (ClassicUO fork / modern UO client)
- **Primary Language:** Python (scripts can also be written in C#)
- **Documentation & References:**
  - Setup Guide: <https://tazuo.org/wiki/legion-scripting-setup/>
  - TazUO Wiki: <https://tazuo.org/wiki/home/>
  - Legion API Reference: <https://tazuo.org/legion/legionapi/>
  - Public Legion Script Examples: <https://github.com/PlayTazUO/PublicLegionScripts/>

---

## Architecture & Base Client Files

The following files are generated/supplied by the base TazUO client install for IDE IntelliSense. **DO NOT MODIFY OR DELETE THEM** unless explicitly requested to update API definitions:

- **`API.py`**: The complete Python API stub containing classes, methods, signatures, and docstrings for the TazUO Legion scripting environment. Use this file as your primary offline reference for API signatures.
- **`__builtins__.py`**: Contains `import API` to allow Python language servers (Pyright, Pylance) to resolve `API` symbols globally without warnings.
- **`_ScriptContext.cs`**: Provides the static `API` property for C# script IntelliSense.
- **`LegionScripts.csproj`**: C# project file referencing `TazUO.dll` and `FNA.dll`. Note: Build errors in this project during compilation are expected and harmless; scripts are executed dynamically inside TazUO.
- **`LegionScripts.code-workspace`**: VS Code workspace settings.

---

## Agent Guardrails & Scripting Rules

When generating, modifying, or refactoring scripts in this repository, strictly adhere to these rules:

### 1. Loop Safety & Cancellation

- **Mandatory `API.StopRequested` checks:** In any `while` loop or polling loop, always check `API.StopRequested`. Scripts must terminate immediately when the user stops them from the TazUO client UI.

  ```python
  while not API.StopRequested:
      # script logic
      API.Pause(0.5)
  ```

- **Never use `while True:` without `API.StopRequested`!**

### 2. Timing and Delays

- **Never use `time.sleep()`:** Python's standard `time.sleep` will block or desync the script thread from the client's internal tick cycle. **Always use `API.Pause(seconds)`**.

### 3. Imports and IntelliSense

- **Always include `import API`:** At the top of every Python script, write `import API` so that IDE IntelliSense and linting work seamlessly.
- **Register Stop Callbacks:** When relevant, use `API.OnStop(callback_function)` to notify the player that the script has terminated and perform any necessary cleanup.

### 4. User Feedback

- Use `API.SysMsg("message")` to inform the user of script state, targets selected, errors, or completions.
- Avoid spamming messages every tick; throttle logging and clean journals (`API.ClearJournal()`) before checking journal messages.

### 5. Documentation Maintenance

- Whenever a script is created, modified, or deleted:
  1. Add an entry under `## [Unreleased]` in `CHANGELOG.md` following the [Keep a Changelog](https://keepachangelog.com/) format.
  2. Document the script and its usage in `README.md`.
- Attribution and copyright must always credit **FesterHead**.

### 6. Script Organization

- **No loose scripts in the root directory:** The repository root is strictly reserved for base client install files, IDE configurations, and project documentation.
- **Organize by author name or shard name:** All new or refactored scripts must be placed in a dedicated subfolder categorized by **author name** (e.g., `FesterUO/`, `AuthorName/`) or target **shard name** (e.g., `Outlands/`, `ShardName/`).

### 7. Markdown Formatting & Linting

- When creating or editing Markdown files (`CHANGELOG.md`, `README.md`, etc.):
  - Strictly adhere to the workspace configuration defined in [`.markdownlint.json`](.markdownlint.json).
  - Ensure all formatting satisfies markdownlint standards and resolve all supported issues (equivalent to running the VS Code command `markdownlint: Fix all supported issues in file`).
  - Maintain clean list hierarchies, proper blank line separation between blocks, and eliminate trailing whitespace.

### 8. Script Versioning & Increments

- **Internal Version Constant:** Every script must define an internal version constant: `SCRIPT_VERSION: str = "X.Y.Z"` near the top of the file under the `# Configuration` section.
- **Mandatory Version Increments:** Whenever a script is modified, bugfixed, tuned, or extended with new features, you **MUST** increment its `SCRIPT_VERSION` (following [Semantic Versioning](https://semver.org/)):
  - Increment **PATCH** (e.g., `1.0.0` -> `1.0.1`) for bug fixes, timing/pacing adjustments, reliability improvements, and small maintenance updates.
  - Increment **MINOR** (e.g., `1.0.0` -> `1.1.0`) for new features, new UI controls, new modes, or added configuration options.
  - Increment **MAJOR** (e.g., `1.0.0` -> `2.0.0`) for breaking architectural rewrites or major overhauls.
- **Gump & Startup Reflection:** Ensure the updated version is reflected on the Gump author label (`lbl_author = API.Gumps.CreateGumpLabel(f"by FesterHead v{SCRIPT_VERSION}", 996)`) and in the script's startup console/SysMsg notification.
