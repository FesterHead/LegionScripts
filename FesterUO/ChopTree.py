"""
ChopTree.py - Automated Lumberjacking Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Automates tree chopping by prompting the player to target a tree,
    locking onto the target coordinates and graphic, and repeatedly swinging
    an equipped axe until the resource is depleted or execution is stopped.

Usage:
    1. Equip an axe in either the OneHanded or TwoHanded layer.
    2. Start the script in TazUO.
    3. Target the desired tree when prompted.
"""

import API

# Configuration
DEBUG: bool = False
# Delay in seconds between swings. FesterUO allows fast chopping (1.0s).
# For standard / default UO shards, set this to 4.5 or 5.0.
SWING_DELAY: float = 1.0

# Dress configuration profile to load at startup (set to None or "" to disable)
DRESS_PROFILE: str = "Lumberjack"

# Journal keywords indicating a tree has no more wood or cannot be harvested (matched case-insensitively)
DEPLETED_KEYWORDS = [
    "no wood here",
    "not enough wood",
    "nothing here to chop",
    "cannot see that",
    "can't reach",
    "too far away",
    "use an axe",
    "immune to your axe"
]

def on_stop():
    API.SysMsg("Lumberjack stopped.")

API.OnStop(on_stop)

def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(message)

def get_equipped_axe():
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item:
            return item
    return None

def main():
    if DRESS_PROFILE:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE}'...")
        API.Dress(DRESS_PROFILE)
        API.Pause(1.0)

    axe = get_equipped_axe()
    if not axe:
        API.SysMsg("No axe found in hands!")
        return

    # 1. Use the axe immediately to pop the targeting cursor
    API.SysMsg("Click the tree you want to chop...")
    API.UseObject(axe)

    # 2. Capture the initial coordinates
    old_pos = API.LastTargetPos

    # 3. Wait until you click a tree (LastTargetPos changes or is populated)
    for _ in range(100):  # 10 second timeout
        if API.StopRequested:
            return
        pos = API.LastTargetPos
        graphic = API.LastTargetGraphic
        if pos and graphic and pos != old_pos:
            break
        API.Pause(0.1)
    else:
        # If targeting the exact same tree as before, fall back to current LastTargetPos
        pos = API.LastTargetPos
        graphic = API.LastTargetGraphic

    if not pos or not graphic:
        API.SysMsg("Target selection timed out.")
        return

    tx = int(pos.X)
    ty = int(pos.Y)
    tz = int(pos.Z)
    tg = int(graphic)

    debug_msg(f"Locked tree: ({tx}, {ty}, {tz}) graphic={tg}. Starting loop...")

    # Wait for the initial manual swing to finish
    API.Pause(SWING_DELAY)

    swing = 1

    # 4. Automated loop continues from swing #2 onward
    while not API.StopRequested:
        swing += 1
        debug_msg(f"=== Swing #{swing} ===")
        API.ClearJournal()

        API.UseObject(axe)

        if API.WaitForTarget(timeout=5):
            API.Target(tx, ty, tz, tg)
            API.Pause(SWING_DELAY)
        else:
            debug_msg(f"Swing #{swing}: Target timed out.")
            break

        # Check depletion
        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        depleted = False
        for kw in DEPLETED_KEYWORDS:
            if any(kw in t for t in recent_text) or API.InJournal(kw):
                API.SysMsg(f"Tree finished: '{kw}'")
                depleted = True
                break

        if depleted:
            break

    API.SysMsg("Done.")

main()
