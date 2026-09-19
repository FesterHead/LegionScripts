# Contributing to TazUO Legion Scripts

Thank you for your interest in contributing! This repository contains Legion automation and utility scripts for the [TazUO](https://tazuo.org/) Ultima Online client.

---

## Guidelines for Legion Scripts

### 1. Script Architecture & Safety

When writing scripts for TazUO's Legion engine, safety and client stability are essential:

- **Always honor `API.StopRequested`:** Any loop that can run more than once or wait for conditions must check `API.StopRequested` and exit promptly.

  ```python
  while not API.StopRequested:
      # Perform action
      API.Pause(0.5)
  ```

- **Never use blocking sleep functions:** Do **not** use Python's built-in `time.sleep()`. It blocks the thread and can freeze or desync client interactions. Always use `API.Pause(seconds)`.
- **Inform the user via `API.SysMsg()`:** Provide informative feedback when scripts start, stop, encounter errors, or finish tasks. Register cleanup or stop notifications with `API.OnStop(callback)`.
- **Targeting and Journals:** When waiting for targets or journal entries, always provide timeouts and clear journals before initiating actions that produce messages to avoid acting on stale data.
- **Top-level `import API`:** Ensure Python scripts include `import API` so that VS Code, Pyright, and linters can provide IntelliSense.

### 2. Base Client Files

Do not edit or delete the base client install files:

- `API.py`: Legion Python API declarations and stubs.
- `__builtins__.py`: Global import shim for language servers.
- `_ScriptContext.cs`: Static C# script context for IDE IntelliSense.
- `LegionScripts.csproj`: C# project configuration.
- `LegionScripts.code-workspace`: VS Code workspace configuration.

These files are provided by the TazUO client installation.

### 3. Folder & Script Organization

To keep the repository clean and structured:

- **Organize by Author or Shard:** All scripts must be placed in a subfolder named after the **author** (e.g., `FesterUO/`, `YourAuthorName/`) or target **shard name** (e.g., `Outlands/`, `UOAlive/`).
- **Keep the Root Clean:** Never place script files directly in the repository root directory. The root is strictly reserved for base client installation files, IDE configurations, and documentation.

---

## Development Workflow

1. **Set Up Your Environment:**

   - Open this repository in Visual Studio Code (or open `LegionScripts.code-workspace`).
   - Install the recommended Python extension (and C# Dev Kit if writing C# scripts).

2. **Create or Modify a Script:**

   - Place scripts in an appropriate author-named or shard-named subfolder (e.g., `FesterUO/ChopTree.py`).
   - Follow standard PEP 8 conventions for Python scripts.

3. **Test In-Game:**

   - Load and test the script using TazUO's Legion script runner.
   - Verify start, pause/stop, error cases, and edge cases (e.g. missing items, disconnected client, full backpack).

4. **Update Documentation:**

   - Document any new script or parameter changes in `README.md`.
   - Add a brief entry in `CHANGELOG.md` under `## [Unreleased]`.

5. **Submit a Pull Request:**

   - Create a feature branch for your changes.
   - Submit a pull request filling out the template in `.github/PULL_REQUEST_TEMPLATE.md`.
