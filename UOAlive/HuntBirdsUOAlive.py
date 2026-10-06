"""
HuntBirdsUOAlive.py - Automated Bird & Eagle Targeting Script for UOAlive

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)
Target Shard: UOAlive

Description:
    Assists players in roaming the wilderness to harvest feathers:
    - Automatically enables War Mode on startup and keeps War Mode engaged while hunting.
    - Continuously scans the surrounding area for wild birds, eagles, chickens, and other avian creatures.
    - Automatically acquires and locks onto the nearest valid bird as your combat target:
      * Engages combat via API.Attack(target).
      * Sets the client's Last Target (API.SetLastTarget) for seamless spell/macro/ability targeting.
    - Displays an on-screen interactive control Gump showing:
      * Current hunting status & active target name / distance / HP.
      * Total birds hunted counter.
      * Real-time backpack feather counter.
    - Includes interactive Pause/Resume and Stop controls:
      * Pausing automatically switches you to Peace Mode (War Mode disabled) so you can safely
        vendor, interact with NPCs, or craft without swinging.
      * Resuming immediately re-engages War Mode and resumes bird hunting.
    - Designed to pair with TazUO's native auto-skinning and auto-looting features.

Usage:
    1. Equip your preferred weapon (bow, crossbow, melee) or prepare offensive spells.
    2. Start the script in TazUO.
    3. Run around fields and forests — the script will auto-target every bird in range.
    4. Use the on-screen Gump to monitor catches, Pause (Peace Mode), or Stop.
"""

from typing import List, Optional
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Search radius in tiles around the player to detect birds
SCAN_RADIUS: int = 12

# Delay in seconds between main loop scans (responsive while running)
LOOP_DELAY: float = 0.25

# Minimum seconds between re-sending combat attack packets to the same target
ATTACK_REPEAT_DELAY: float = 1.8

# Mobile body/graphic IDs representing birds, eagles, and fowl
BIRD_GRAPHICS: List[int] = [
    0x0005,  # Eagle (5)
    0x0006,  # Standard Bird (6: Magpie, Kingfisher, Crow, Raven, Swallow, Sparrow, etc.)
    0x00D0,  # Chicken (208)
]

# Known non-avian predator graphics to strictly exclude (wolves, dogs, rats, bears)
EXCLUDED_GRAPHICS: List[int] = [
    23, 25, 27, 34, 37,  # Grey Wolf, Light Grey Wolf, Dark Grey Wolf (0x1B), Arctic Wolf
    0x0017, 0x0019, 0x001B,  # Wolf body hex equivalents
    0x00D7,  # Giant Rat (215)
    0x00E1,  # Timber Wolf / Dire Wolf
    0x00A7, 0x00A9, 0x00D3,  # Bears
]

# Name keywords matched case-insensitively for avian creatures
BIRD_KEYWORDS: List[str] = [
    "bird",
    "eagle",
    "magpie",
    "kingfisher",
    "crow",
    "raven",
    "hawk",
    "chicken",
    "sparrow",
    "dove",
    "phoenix",
    "crane",
    "turkey",
    "falcon",
    "parrot",
    "swallow",
]

# Item graphics for feathers
FEATHER_GRAPHICS: List[int] = [
    0x1BD1,  # Standard feathers
    0x1BD2,  # Alternate feather variety
    0x1BD3,  # White/special feather pile
]

# ==============================================================================
# Global State & Gump Controls
# ==============================================================================

gump = None
lbl_status = None
lbl_target = None
lbl_stats = None
lbl_feathers = None
btn_pause = None
btn_stop = None

is_paused: bool = False
is_stopped: bool = False
birds_hunted_count: int = 0
current_target_serial: Optional[int] = None
last_attack_timestamp: float = 0.0


def update_status(text: str) -> None:
    """Updates the status display on the Gump."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def update_target_display(target_name: str, distance: int, hits: Optional[int] = None) -> None:
    """Updates the current combat target indicator on the Gump."""
    global lbl_target
    if lbl_target:
        if hits is not None and hits >= 0:
            lbl_target.Text = f"Target: {target_name} [{hits} HP] ({distance}t)"
        else:
            lbl_target.Text = f"Target: {target_name} ({distance}t)"


def clear_target_display() -> None:
    """Resets the target display when no bird is in combat range."""
    global lbl_target
    if lbl_target:
        lbl_target.Text = "Target: Searching nearby..."


def update_stats_display() -> None:
    """Refreshes birds hunted count and backpack feather totals on the Gump."""
    global lbl_stats, lbl_feathers, birds_hunted_count
    feathers = count_backpack_feathers()
    if lbl_stats:
        lbl_stats.Text = f"Birds Hunted: {birds_hunted_count}"
    if lbl_feathers:
        lbl_feathers.Text = f"Backpack Feathers: {feathers:,}"


def count_backpack_feathers() -> int:
    """Counts the total number of feathers inside the player's backpack."""
    total = 0
    if not API.Backpack:
        return 0

    # Non-recursive items scan with container traversal
    to_scan = [API.Backpack]
    visited = set()

    while to_scan:
        container_id = to_scan.pop(0)
        if not container_id or container_id in visited:
            continue
        visited.add(container_id)

        items = API.ItemsInContainer(container_id, recursive=False)
        if items is None:
            items = API.ItemsInContainer(container_id)
        if items:
            for item in items:
                graphic = getattr(item, "Graphic", 0)
                name = str(getattr(item, "Name", "") or "").lower()
                amount = getattr(item, "Amount", 1) or 1

                if graphic in FEATHER_GRAPHICS or "feather" in name:
                    total += amount

                # Inspect sub-containers
                if getattr(item, "IsContainer", False) or graphic in [
                    0x0E75, 0x0E76, 0x0E79, 0x0E7D, 0x0E7E, 0x0E80, 0x09B0
                ]:
                    sub_serial = getattr(item, "Serial", None)
                    if sub_serial and sub_serial not in visited:
                        to_scan.append(sub_serial)

    # Strategy 2: Direct FindType check fallback
    if total == 0:
        for g in FEATHER_GRAPHICS:
            found_all = API.FindTypeAll(g, API.Backpack)
            if found_all:
                for fit in found_all:
                    total += getattr(fit, "Amount", 1) or 1

    return total


# ==============================================================================
# Gump Interface
# ==============================================================================

def on_pause_clicked() -> None:
    """
    Toggles between active War Mode hunting and Peace Mode pause.
    Pausing immediately takes the player out of war mode.
    Resuming immediately returns the player to war mode.
    """
    global is_paused, btn_pause
    if is_paused:
        is_paused = False
        if btn_pause:
            btn_pause.SetText("Pause")
        API.SetWarMode(True)
        update_status("Hunting (War Mode)")
        API.SysMsg("[BirdHunter] Resumed: War Mode enabled.", 68)
    else:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        API.SetWarMode(False)
        update_status("Paused (Peace Mode)")
        clear_target_display()
        API.SysMsg("[BirdHunter] Paused: Peace Mode enabled.", 53)


def on_stop_clicked() -> None:
    """Stops the script and disables War Mode."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.SetWarMode(False)
    API.Stop()


def on_gump_disposed() -> None:
    """Cleanly handles Gump closure via right-click."""
    global is_stopped
    if not is_stopped and not API.StopRequested:
        is_stopped = True
        API.SetWarMode(False)
        API.Stop()


def create_control_gump() -> None:
    """Initializes and displays the interactive Bird Hunter Gump."""
    global gump, lbl_status, lbl_target, lbl_stats, lbl_feathers, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 240, 150)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 240, 150)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("UOAlive Bird Hunter", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Current Target label
    lbl_target = API.Gumps.CreateGumpLabel("Target: Searching nearby...", 68)
    lbl_target.SetPos(10, 48)
    gump.Add(lbl_target)

    # Birds hunted counter label
    lbl_stats = API.Gumps.CreateGumpLabel("Birds Hunted: 0", 996)
    lbl_stats.SetPos(10, 68)
    gump.Add(lbl_stats)

    # Feathers counter label
    lbl_feathers = API.Gumps.CreateGumpLabel("Backpack Feathers: 0", 996)
    lbl_feathers.SetPos(10, 88)
    gump.Add(lbl_feathers)

    # Pause button (toggles Peace / War mode)
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 70, 22)
    btn_pause.SetPos(15, 116)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 70, 22)
    btn_stop.SetPos(155, 116)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Disposed handler
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely removes the Gump window from the screen."""
    global gump
    if gump and not gump.IsDisposed:
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes Gump events and handles paused state loop."""
    global is_paused, is_stopped
    API.ProcessCallbacks()
    update_stats_display()

    if is_stopped or API.StopRequested:
        return False

    if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
        on_stop_clicked()
        return False

    if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
        on_pause_clicked()

    # While paused, hold execution in Peace Mode
    while is_paused and not API.StopRequested and not is_stopped:
        if API.Player.InWarMode:
            API.SetWarMode(False)

        API.Pause(0.2)
        API.ProcessCallbacks()
        update_stats_display()

        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            on_pause_clicked()
            if not is_paused:
                break

    return not is_stopped and not API.StopRequested


# ==============================================================================
# Helper Functions
# ==============================================================================

def on_stop() -> None:
    """Callback when script terminates: guarantees War Mode is disabled."""
    API.SetWarMode(False)
    dispose_gump()
    API.SysMsg("[BirdHunter] Script stopped. Peace Mode restored.", 53)

API.OnStop(on_stop)


def is_valid_bird(mobile) -> bool:
    """Determines whether a mobile is a valid targetable bird/eagle."""
    if not mobile:
        return False

    # Cannot target ourselves
    if mobile.Serial == API.Player.Serial:
        return False

    # Ignore dead mobiles or ghosts
    if getattr(mobile, "IsDead", False) or getattr(mobile, "IsGhost", False):
        return False

    # Ignore players and humanoids
    if getattr(mobile, "IsHuman", False) or getattr(mobile, "IsGargoyle", False):
        return False

    name = str(getattr(mobile, "Name", "") or "").lower()

    # Explicitly reject wolves, canines, and non-avian predators by name
    if any(pred in name for pred in ["wolf", "dog", "hound", "rat", "bear", "snake", "spider", "mongbat"]):
        return False

    # Explicitly reject wolves and non-avian predators by body graphic
    graphic = getattr(mobile, "Graphic", 0)
    if graphic in EXCLUDED_GRAPHICS:
        return False

    # Check graphic ID match (5 = Eagle, 6 = Bird, 208 = Chicken)
    if graphic in BIRD_GRAPHICS:
        return True

    # Check name keyword match (only for avian creatures)
    if any(kw in name for kw in BIRD_KEYWORDS):
        return True

    return False


def find_nearest_bird(max_distance: int = SCAN_RADIUS):
    """
    Scans for the closest living bird/eagle within max_distance tiles.
    Returns the nearest matching ApiMobile or None.
    """
    mobiles = API.GetAllMobiles(distance=max_distance, sortby="Distance")
    if not mobiles:
        return None

    for m in mobiles:
        if is_valid_bird(m):
            return m

    return None


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    global current_target_serial, birds_hunted_count, last_attack_timestamp

    create_control_gump()
    update_status("Starting...")
    update_stats_display()

    # Automatically put player into War Mode on startup
    API.SetWarMode(True)
    update_status("Hunting (War Mode)")
    API.SysMsg("[BirdHunter] Started! War Mode engaged. Run around to find birds.", 68)

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Ensure War Mode remains active while hunting
        if not is_paused and not API.Player.InWarMode:
            API.SetWarMode(True)

        target = None
        target_valid = False

        # Verify active target if one is already locked
        if current_target_serial:
            target = API.FindMobile(current_target_serial)
            if target and is_valid_bird(target):
                dist = getattr(target, "Distance", 99)
                # Keep active target as long as it is still within reasonable range
                if dist <= (SCAN_RADIUS + 4):
                    target_valid = True
                else:
                    target = None
            else:
                # Target died or despawned
                birds_hunted_count += 1
                API.SysMsg("[BirdHunter] Bird eliminated! Looting feathers...", 68)
                update_stats_display()
                current_target_serial = None
                target = None

        # If no active target, locate the nearest bird
        if not target_valid:
            target = find_nearest_bird(SCAN_RADIUS)
            if target:
                current_target_serial = target.Serial
                # Announce new target
                name = getattr(target, "Name", "Bird") or "Bird"
                dist = getattr(target, "Distance", 0)
                API.SysMsg(f"[BirdHunter] Target locked: {name} ({dist} tiles away)", 88)

        # Attack and target the acquired bird
        if target:
            name = getattr(target, "Name", "Bird") or "Bird"
            dist = getattr(target, "Distance", 0)
            hits = getattr(target, "Hits", None)

            update_status(f"Attacking {name}")
            update_target_display(name, dist, hits)

            # Keep Last Target locked for player hotkeys/spells/abilities
            API.SetLastTarget(serial=target.Serial)

            # Send combat attack request
            API.Attack(target.Serial)
        else:
            current_target_serial = None
            update_status("Searching for birds...")
            clear_target_display()

        API.Pause(LOOP_DELAY)

    # Clean shutdown
    API.SetWarMode(False)
    dispose_gump()
    API.SysMsg("[BirdHunter] Finished. Peace Mode restored.")


main()
