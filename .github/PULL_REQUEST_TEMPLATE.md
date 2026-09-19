# Description

Briefly describe the purpose of this pull request (e.g., adding a new script, improving an existing script, fixing a bug).

## Script Details

- **Script Name:** <!-- e.g., ChopTree.py -->
- **Folder Location:** <!-- Must be an author folder (e.g., FesterUO/) or shard folder (e.g., Outlands/) -->
- **Language:** <!-- Python or C# -->
- **Purpose / Features:** <!-- Short summary of what the script does -->

## Testing in TazUO

- [ ] Script was loaded into TazUO client without syntax errors.
- [ ] Tested script execution in-game.
- [ ] Confirmed script responds to `API.StopRequested` and stops gracefully.
- [ ] Tested edge cases (missing required items, out of range, depleted resources, client lag).

## Checklist

- [ ] Script is placed in an author or shard subfolder (not in the repository root).
- [ ] Code follows project conventions (uses `API.Pause` instead of blocking `time.sleep`, includes `import API`).
- [ ] Status and error messages are reported cleanly via `API.SysMsg`.
- [ ] Added/updated entry in `CHANGELOG.md` under `[Unreleased]`.
- [ ] Updated `README.md` if adding a new script or modifying public script behavior.
