"""
Fish.py - Automated Fishing Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Automates fishing by prompting the player to target a water tile,
    locking onto the target coordinates and graphic, and repeatedly fishing
    with an equipped fishing pole until the spot is depleted or execution is stopped.

Usage:
    1. Equip a fishing pole (or have one in your backpack).
    2. Start the script in TazUO.
    3. Target the desired water tile when prompted.
"""

import API

# ==============================================================================
# Configuration
# ==============================================================================

DEBUG: bool = False

# Delay in seconds between casts. FesterUO allows fast harvesting (1.0s–2.0s).
# For standard / default UO shards, set this to 6.0–8.0s.
FISHING_DELAY: float = 2.0

# Optional dress configuration profile to load at startup (set to None or "" to disable)
DRESS_PROFILE: str = ""

# Fishing pole item graphic ID
FISHING_POLE_GRAPHIC: int = 0x0DC0

# Journal messages indicating that the current fishing spot is depleted or unreachable.
# Includes lowercase, uppercase, and substring variants to avoid case/apostrophe mismatches.
DEPLETED_MESSAGES = [
    "biting here",
    "Biting here",
    "The fish don't seem to be biting here",
    "the fish don't seem to be biting here",
    "The fish don’t seem to be biting here",
    "the fish don’t seem to be biting here",
    "There are no fish here to bite",
    "there are no fish here to bite",
    "There are no fish here",
    "there are no fish here",
    "no fish here",
    "No fish here",
    "cannot see that",
    "Cannot see that",
    "can't reach that",
    "Can't reach that",
    "too far away",
    "Too far away",
    "that is too far away",
    "That is too far away",
    "closer to the water",
    "Closer to the water"
]

# ==============================================================================
# Lifecycle Callbacks & Helpers
# ==============================================================================

def on_stop():
    API.SysMsg("Fishing stopped.")

API.OnStop(on_stop)


def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(message)


def get_fishing_pole():
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and (item.Graphic == FISHING_POLE_GRAPHIC or "pole" in str(item.Name).lower()):
            return item

    pole = API.FindType(FISHING_POLE_GRAPHIC, API.Backpack)
    if pole:
        return pole

    return None


def is_spot_depleted():
    """
    Checks if the current fishing spot is depleted.
    Combines direct InJournal checks with case-insensitive journal entry scanning
    to guard against capitalizations or unicode apostrophe (' vs ’) discrepancies.
    """
    # 1. Direct API.InJournal check
    for msg in DEPLETED_MESSAGES:
        if API.InJournal(msg):
            return True, msg

    # 2. Case-insensitive inspection of recent journal entries
    entries = API.GetJournalEntries(4.0)
    if entries:
        for entry in entries:
            text = str(entry.Text).lower()
            if "biting here" in text:
                return True, entry.Text
            if "no fish here" in text:
                return True, entry.Text
            if "cannot see that" in text or "can't reach" in text or "too far away" in text:
                return True, entry.Text
            if "closer to the water" in text:
                return True, entry.Text

    return False, ""


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    if DRESS_PROFILE:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE}'...")
        API.Dress(DRESS_PROFILE)
        API.Pause(1.0)

    pole = get_fishing_pole()
    if not pole:
        API.SysMsg("No fishing pole found in hands or backpack!")
        return

    # 1. Use the fishing pole immediately to pop the targeting cursor
    API.SysMsg("Click the water where you want to fish...")
    API.ClearJournal()
    API.UseObject(pole)

    # 2. Capture the initial coordinates
    old_pos = API.LastTargetPos

    # 3. Wait until you click a water tile (LastTargetPos changes or is populated)
    for _ in range(150):  # 15 second timeout
        if API.StopRequested:
            return
        pos = API.LastTargetPos
        graphic = API.LastTargetGraphic
        # For land tiles (open water), graphic is often 0 or None in TazUO
        if pos and (pos != old_pos or API.InJournal("You pull out") or API.InJournal("You fish a while") or API.InJournal("You reel in")):
            break
        API.Pause(0.1)
    else:
        # Fall back to current LastTargetPos if already targeted
        pos = API.LastTargetPos
        graphic = API.LastTargetGraphic

    if not pos:
        API.SysMsg("Target selection timed out.")
        return

    tx = int(pos.X)
    ty = int(pos.Y)
    tz = int(pos.Z)
    tg = int(graphic) if graphic else 0

    debug_msg(f"Locked water tile: ({tx}, {ty}, {tz}) graphic={tg}. Starting loop...")

    # Wait for the initial manual cast to finish
    API.Pause(FISHING_DELAY)

    # Check if the initial cast depleted the spot
    depleted, reason = is_spot_depleted()
    if depleted:
        API.SysMsg(f"Fishing spot finished: '{reason}'")
        API.SysMsg("Done.")
        return

    cast = 1

    # 4. Automated loop continues from cast #2 onward
    while not API.StopRequested:
        cast += 1
        debug_msg(f"=== Cast #{cast} ===")
        API.ClearJournal()

        API.UseObject(pole)

        if API.WaitForTarget(timeout=5):
            API.Target(tx, ty, tz, tg)
            API.Pause(FISHING_DELAY)
        else:
            # If target cursor was slightly delayed, pause briefly and retry once
            debug_msg(f"Cast #{cast}: Retrying target...")
            API.Pause(1.0)
            API.UseObject(pole)
            if API.WaitForTarget(timeout=5):
                API.Target(tx, ty, tz, tg)
                API.Pause(FISHING_DELAY)
            else:
                debug_msg(f"Cast #{cast}: Target timed out.")
                break

        # Check depletion
        depleted, reason = is_spot_depleted()
        if depleted:
            API.SysMsg(f"Fishing spot finished: '{reason}'")
            break

    API.SysMsg("Done.")


main()
