"""
LobsterTrapAuto.py - Automated Lobster & Crab Trap Management with Interactive Gump for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Automates lobster and crab trap deployment, monitoring, retrieval, and recycling:
    - Deploys up to 5 lobster traps from your backpack into the surrounding ocean at fixed, well-spaced water offsets.
    - Monitors each deployed trap buoy in real-time, tracking its elapsed timer and listening for journal/bob events.
    - When a trap reaches its bob interval (~60-65s) or catches something:
        1. Double-clicks the buoy to haul the trap into your backpack.
        2. Double-clicks the retrieved trap in your backpack to empty its contents (lobsters and crabs).
        3. Optionally moves the catch into a designated satchel, crate, or container.
        4. Re-tosses the emptied trap right back into the ocean at that spot.
    - Detects sunk or destroyed traps (when a buoy disappears without being hauled):
        - Alerts the player and updates the "Traps Lost" counter.
        - Automatically checks your backpack for a spare trap to replace it.
        - If no spare traps remain, notifies the player to place replacement traps in their backpack.
    - Displays an on-screen interactive control Gump showing:
        - Real-time action status
        - Active deployed traps counter (e.g. 5 / 5)
        - Running total of crustaceans (lobsters & crabs) caught
        - Running total of traps lost / sunk
        - Live Fishing skill and cap with skill gain announcements
        - Interactive Start / Pause / Resume and Stop buttons
        - Interactive "Set Satchel" button to designate a storage bag for catches
        - Interactive "Set Spots" button to customize the 5 water targeting coordinates

Usage:
    1. Board your boat in deep water (at least 5 tiles away from the shore).
    2. Have up to 5 lobster traps in your backpack.
    3. Start the script in TazUO.
    4. Click "Start" on the Gump (or let it auto-start) to deploy the traps.
    5. Keep replacement traps in your backpack (or ship hold) when traps eventually sink or break.
"""

from typing import List, Tuple, Optional, Dict, Set
import time
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Enable verbose debug output in the client console/journal
DEBUG: bool = False

# Maximum number of concurrent traps deployed (up to 5)
MAX_TRAPS: int = 5

# Delay in seconds to wait for a trap to "bob" before hauling (UO bobs occur every 60s)
# 65.0s allows a clean margin for the 60s server tick to complete 1 full bob
BOB_WAIT_SECONDS: float = 65.0

# General pacing pause between actions (in seconds)
ACTION_DELAY: float = 0.6

# Default relative water offsets from the player's position on a boat (dx, dy).
# All spots are separated by >= 2 tiles so buoys obey the "1 tile spacing" rule:
#   Spot 0: Northwest (-2, -2)
#   Spot 1: West      (-2,  0)
#   Spot 2: Southwest (-2,  2)
#   Spot 3: Northeast ( 2, -1)
#   Spot 4: Southeast ( 2,  1)
DEFAULT_OFFSETS: List[Tuple[Tuple[int, int], str]] = [
    ((-2, -2), "Port Bow (NW)"),
    ((-2,  0), "Port Railing (W)"),
    ((-2,  2), "Port Stern (SW)"),
    (( 2, -1), "Starboard Bow (NE)"),
    (( 2,  1), "Starboard Stern (SE)"),
]

# Known keywords matching lobster trap items in backpack
TRAP_KEYWORDS: List[str] = [
    "lobster trap",
    "trap",
]

# Known keywords matching deployed buoys on the water
BUOY_KEYWORDS: List[str] = [
    "buoy",
    "trap",
    "lobster",
]

# Known keywords matching caught crustaceans (lobsters and crabs)
CRUSTACEAN_KEYWORDS: List[str] = [
    "lobster",
    "crab",
]

# Journal keywords indicating a trap bobbed or caught something
BOB_JOURNAL_KEYWORDS: List[str] = [
    "*bob*",
    "bobs",
    "bob",
    "trap bobs",
    "caught",
]

# ==============================================================================
# Global State & Counters
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_active = None
lbl_caught = None
lbl_lost = None
lbl_satchel = None
btn_action = None
btn_stop = None
btn_satchel = None
btn_spots = None

is_paused: bool = False
is_stopped: bool = False
is_waiting_start: bool = False

total_caught_count: int = 0
total_traps_lost: int = 0
last_skill: Optional[float] = None

# Destination container serial for stashing caught crustaceans (0 or None = keep in backpack)
satchel_serial: Optional[int] = None


class TrapSpot:
    """Tracks state and deployment details for a single trap spot."""

    def __init__(self, index: int, offset: Tuple[int, int], name: str):
        self.index: int = index
        self.offset: Tuple[int, int] = offset
        self.name: str = name
        self.buoy_serial: Optional[int] = None
        self.target_pos: Optional[Tuple[int, int, int]] = None
        self.deployed_at: Optional[float] = None
        self.state: str = "EMPTY"  # EMPTY, DEPLOYED, READY


spots: List[TrapSpot] = [
    TrapSpot(i, offset, name) for i, (offset, name) in enumerate(DEFAULT_OFFSETS[:MAX_TRAPS])
]

# ==============================================================================
# Helper Functions
# ==============================================================================

def debug_msg(message: str) -> None:
    """Logs a debug message to the client if DEBUG mode is enabled."""
    if DEBUG:
        API.SysMsg(f"[LobsterAuto] {message}", 996)


def update_status(status_text: str) -> None:
    """Updates the status label on the Gump and prints to the client journal."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {status_text}"
    debug_msg(status_text)


def update_active_display() -> None:
    """Refreshes the active deployed traps counter on the Gump."""
    global lbl_active
    active_count = sum(1 for s in spots if s.state in ("DEPLOYED", "READY"))
    if lbl_active:
        lbl_active.Text = f"Active Traps: {active_count} / {MAX_TRAPS}"


def increment_caught_count(amount: int = 1) -> None:
    """Increments the caught crustaceans counter and refreshes the Gump."""
    global total_caught_count, lbl_caught
    total_caught_count += amount
    if lbl_caught:
        lbl_caught.Text = f"Crustaceans Caught: {total_caught_count}"


def increment_traps_lost() -> None:
    """Increments the traps lost/sunk counter and refreshes the Gump."""
    global total_traps_lost, lbl_lost
    total_traps_lost += 1
    if lbl_lost:
        lbl_lost.Text = f"Traps Lost / Sunk: {total_traps_lost}"


def update_skill_display() -> None:
    """Updates Fishing skill on the Gump and announces skill gains."""
    global last_skill, lbl_skill

    skill_obj = API.GetSkill("Fishing")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        lbl_skill.Text = f"Fishing: {val:.1f} / {cap:.1f}"
        if last_skill is not None and val > last_skill:
            gain = val - last_skill
            API.SysMsg(f"Fishing gained +{gain:.1f}! New skill: {val:.1f}", 53)
        last_skill = val


def update_satchel_label() -> None:
    """Updates the Satchel destination label on the Gump."""
    global lbl_satchel, satchel_serial
    if not lbl_satchel:
        return
    if satchel_serial:
        item = API.FindItem(satchel_serial)
        name = getattr(item, "Name", "Satchel") if item else "Satchel"
        lbl_satchel.Text = f"Satchel: {name} (0x{satchel_serial:X})"
    else:
        lbl_satchel.Text = "Satchel: None (Backpack)"


# ==============================================================================
# Backpack & Trap Management
# ==============================================================================

def find_trap_in_backpack() -> Optional[int]:
    """
    Finds the first available lobster trap item in the player's backpack.
    Returns its serial, or None if no trap is found.
    """
    backpack_items = API.ItemsInContainer(API.Backpack)
    if not backpack_items:
        return None

    for item in backpack_items:
        name = (getattr(item, "Name", "") or "").lower()
        if not name:
            props = str(API.ItemNameAndProps(item.Serial, wait=False) or "").lower()
            name = f"{name} {props}"

        if any(kw in name for kw in TRAP_KEYWORDS):
            return item.Serial

    return None


def get_backpack_crustaceans() -> List[int]:
    """
    Scans the player's backpack for any crustaceans (lobsters and crabs).
    Returns a list of matching item serials.
    """
    catches: List[int] = []
    backpack_items = API.ItemsInContainer(API.Backpack)
    if not backpack_items:
        return catches

    for item in backpack_items:
        name = (getattr(item, "Name", "") or "").lower()
        if not name:
            props = str(API.ItemNameAndProps(item.Serial, wait=False) or "").lower()
            name = f"{name} {props}"

        if any(kw in name for kw in CRUSTACEAN_KEYWORDS) and "trap" not in name:
            catches.append(item.Serial)

    return catches


def stash_crustaceans() -> int:
    """
    Identifies any caught crustaceans in the backpack, increments the catch counter,
    and moves them to the designated satchel if configured.
    Returns the number of crustaceans processed.
    """
    global satchel_serial
    catches = get_backpack_crustaceans()
    if not catches:
        return 0

    count = len(catches)
    increment_caught_count(count)

    if satchel_serial and API.FindItem(satchel_serial):
        for serial in catches:
            item = API.FindItem(serial)
            item_name = getattr(item, "Name", "crustacean") if item else "crustacean"
            API.SysMsg(f"Stashed {item_name} into satchel.", 68)
            API.MoveItem(serial, satchel_serial)
            API.Pause(0.4)
    else:
        for serial in catches:
            item = API.FindItem(serial)
            item_name = getattr(item, "Name", "crustacean") if item else "crustacean"
            API.SysMsg(f"Caught {item_name}!", 68)

    return count


# ==============================================================================
# Trap Deployment & Buoy Tracking
# ==============================================================================

def find_buoy_at(x: int, y: int, radius: int = 1) -> Optional[int]:
    """
    Scans the ground/water within reach for a trap buoy near coordinate (x, y).
    Returns the serial of the buoy, or None.
    """
    ground_items = API.GetItemsOnGround(distance=6)
    if not ground_items:
        return None

    # 1. Exact coordinate match
    for item in ground_items:
        if item.X == x and item.Y == y:
            return item.Serial

    # 2. Nearby match within radius with matching buoy keyword
    for item in ground_items:
        if abs(item.X - x) <= radius and abs(item.Y - y) <= radius:
            name = (getattr(item, "Name", "") or "").lower()
            if not name:
                props = str(API.ItemNameAndProps(item.Serial, wait=False) or "").lower()
                name = f"{name} {props}"
            if any(kw in name for kw in BUOY_KEYWORDS):
                return item.Serial

    return None


def deploy_trap_at_spot(spot: TrapSpot) -> bool:
    """
    Deploys a lobster trap from backpack at the specified spot's relative offset.
    Returns True if successfully placed, False if no traps are available or target failed.
    """
    trap_serial = find_trap_in_backpack()
    if not trap_serial:
        update_status(f"Need trap in pack for {spot.name}")
        API.SysMsg(f"No lobster traps in backpack to deploy {spot.name}! Please add traps.", 53)
        return False

    update_status(f"Deploying {spot.name}...")
    debug_msg(f"Deploying trap 0x{trap_serial:X} at offset {spot.offset}")

    if API.HasTarget():
        API.CancelTarget()
        API.Pause(0.2)

    API.UseObject(trap_serial)

    if not API.WaitForTarget(timeout=3):
        debug_msg(f"Target cursor timed out while deploying {spot.name}")
        if API.HasTarget():
            API.CancelTarget()
        return False

    tx = API.Player.X + spot.offset[0]
    ty = API.Player.Y + spot.offset[1]
    tz = API.Player.Z

    # Attempt relative targeting first, falling back to absolute coordinates
    API.TargetRel(spot.offset[0], spot.offset[1], False)
    API.Pause(0.3)

    if API.HasTarget():
        API.Target(tx, ty, tz)
        API.Pause(0.3)

    if API.HasTarget():
        API.CancelTarget()
        debug_msg(f"Failed to place trap at {spot.name}")
        return False

    # Allow the server to spawn the buoy in the game world
    API.Pause(ACTION_DELAY)

    buoy_serial = find_buoy_at(tx, ty)
    spot.buoy_serial = buoy_serial
    spot.target_pos = (tx, ty, tz)
    spot.deployed_at = time.time()
    spot.state = "DEPLOYED"

    update_active_display()
    debug_msg(f"Spot {spot.name} deployed! Buoy serial: {buoy_serial}")
    return True


def haul_and_recycle_trap(spot: TrapSpot) -> bool:
    """
    Hauls the trap buoy from the water, empties the caught crustaceans into the backpack,
    moves them to the satchel, and redeploys the trap back into the ocean at this spot.
    """
    if not spot.buoy_serial:
        spot.state = "EMPTY"
        return False

    buoy = API.FindItem(spot.buoy_serial)
    if not buoy:
        # Buoy disappeared (sank/destroyed)
        increment_traps_lost()
        API.SysMsg(f"Trap at {spot.name} was destroyed or sank!", 32)
        spot.buoy_serial = None
        spot.state = "EMPTY"
        update_active_display()
        # Attempt immediate replacement if a spare is in the backpack
        deploy_trap_at_spot(spot)
        return False

    update_status(f"Hauling {spot.name}...")
    debug_msg(f"Hauling buoy 0x{spot.buoy_serial:X}")

    before_crustaceans = set(get_backpack_crustaceans())

    # Double-click buoy to haul it into backpack
    API.UseObject(spot.buoy_serial)
    API.Pause(1.0)

    # Find the hauled trap in the backpack
    trap_serial = find_trap_in_backpack()
    if not trap_serial:
        debug_msg(f"Haul completed but trap not found in backpack for {spot.name}")
        spot.buoy_serial = None
        spot.state = "EMPTY"
        update_active_display()
        return False

    # Double-click the retrieved trap in backpack to open and dump caught lobsters/crabs
    update_status("Opening trap...")
    API.UseObject(trap_serial)
    API.Pause(0.5)

    # If opening the trap brought up a deployment target cursor, cancel it so we can stash first
    if API.HasTarget():
        API.CancelTarget()
        API.Pause(0.2)

    # Process and stash any newly acquired crustaceans
    stash_crustaceans()

    # Redeploy the trap back to the same spot
    update_status(f"Redeploying {spot.name}...")
    success = deploy_trap_at_spot(spot)
    return success


# ==============================================================================
# Interactive Targeting Handlers
# ==============================================================================

def on_set_satchel_clicked() -> None:
    """Prompts the player to target a container / satchel for stashing catches."""
    global satchel_serial
    API.SysMsg("Click the container / satchel to store your lobsters and crabs...", 53)
    update_status("Target satchel...")

    target = API.RequestTarget()
    if target and target > 0:
        satchel_serial = target
        item = API.FindItem(satchel_serial)
        name = getattr(item, "Name", "Container") if item else "Container"
        API.SysMsg(f"Satchel configured: {name} (0x{satchel_serial:X})", 68)
    else:
        satchel_serial = None
        API.SysMsg("Satchel cleared. Catches will remain in your backpack.", 53)

    update_satchel_label()
    update_status("Ready")


def on_set_spots_clicked() -> None:
    """Allows the player to manually click 5 custom water tiles to override default offsets."""
    global spots
    API.SysMsg("Entering Spot Configuration mode: You will click 5 water tiles around your boat.", 53)
    update_status("Configuring spots...")

    for i in range(MAX_TRAPS):
        if API.StopRequested or is_stopped:
            break

        API.SysMsg(f"Click water tile for Spot #{i + 1} of {MAX_TRAPS}...", 53)
        target_pos = API.RequestTarget()
        if not target_pos or target_pos <= 0:
            API.SysMsg(f"Spot #{i + 1} cancelled. Keeping existing configuration.", 32)
            break

        last_pos = API.LastTargetPos
        if last_pos:
            dx = int(last_pos.X) - API.Player.X
            dy = int(last_pos.Y) - API.Player.Y
            spots[i].offset = (dx, dy)
            spots[i].name = f"Custom Spot #{i + 1} ({dx:+d}, {dy:+d})"
            API.SysMsg(f"Spot #{i + 1} set to offset ({dx:+d}, {dy:+d})", 68)
        API.Pause(0.3)

    update_status("Spots updated")
    API.SysMsg("Spot setup completed. Click Start/Resume to begin.", 53)


# ==============================================================================
# Gump UI Construction & Callbacks
# ==============================================================================

def on_action_clicked() -> None:
    """Callback when Start / Pause / Resume button is clicked."""
    global is_paused, is_waiting_start, btn_action
    if is_waiting_start:
        is_waiting_start = False
        update_status("Starting...")
        if btn_action:
            btn_action.SetText("Pause")
    elif is_paused:
        is_paused = False
        if btn_action:
            btn_action.SetText("Pause")
        update_status("Resuming...")
        API.SysMsg("Lobster Trap Auto resumed.", 68)
    else:
        is_paused = True
        if btn_action:
            btn_action.SetText("Resume")
        update_status("Paused")
        API.SysMsg("Lobster Trap Auto paused.", 53)


def on_stop_clicked() -> None:
    """Callback when Stop button is clicked."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_gump_disposed() -> None:
    """Callback when the Gump is closed by right-click."""
    global is_stopped
    if not is_stopped and not API.StopRequested:
        is_stopped = True
        API.Stop()


def create_control_gump() -> None:
    """Initializes and displays the interactive control Gump."""
    global gump, lbl_status, lbl_skill, lbl_active, lbl_caught, lbl_lost, lbl_satchel
    global btn_action, btn_stop, btn_satchel, btn_spots

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 260, 240)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 260, 240)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Lobster Trap Auto", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 30)
    gump.Add(lbl_status)

    # Active deployed traps label
    lbl_active = API.Gumps.CreateGumpLabel(f"Active Traps: 0 / {MAX_TRAPS}", 996)
    lbl_active.SetPos(10, 52)
    gump.Add(lbl_active)

    # Crustaceans caught label
    lbl_caught = API.Gumps.CreateGumpLabel(f"Crustaceans Caught: {total_caught_count}", 996)
    lbl_caught.SetPos(10, 74)
    gump.Add(lbl_caught)

    # Traps lost/sunk label
    lbl_lost = API.Gumps.CreateGumpLabel(f"Traps Lost / Sunk: {total_traps_lost}", 996)
    lbl_lost.SetPos(10, 96)
    gump.Add(lbl_lost)

    # Live Fishing skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Fishing: --", 996)
    lbl_skill.SetPos(10, 118)
    gump.Add(lbl_skill)

    # Satchel destination label
    lbl_satchel = API.Gumps.CreateGumpLabel("Satchel: None (Backpack)", 996)
    lbl_satchel.SetPos(10, 140)
    gump.Add(lbl_satchel)

    # Buttons Row 1: Start/Pause and Stop
    btn_action = API.Gumps.CreateSimpleButton("Start", 75, 22)
    btn_action.SetPos(12, 168)
    API.Gumps.AddControlOnClick(btn_action, on_action_clicked)
    gump.Add(btn_action)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 75, 22)
    btn_stop.SetPos(173, 168)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Buttons Row 2: Set Satchel and Set Spots
    btn_satchel = API.Gumps.CreateSimpleButton("Set Satchel", 115, 22)
    btn_satchel.SetPos(12, 200)
    API.Gumps.AddControlOnClick(btn_satchel, on_set_satchel_clicked)
    gump.Add(btn_satchel)

    btn_spots = API.Gumps.CreateSimpleButton("Set Spots", 115, 22)
    btn_spots.SetPos(133, 200)
    API.Gumps.AddControlOnClick(btn_spots, on_set_spots_clicked)
    gump.Add(btn_spots)

    # Handle Gump right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely cleans up and disposes the Gump."""
    global gump
    if gump and not gump.IsDisposed:
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes UI callbacks and button clicks."""
    global is_stopped
    API.ProcessCallbacks()
    update_skill_display()

    if is_stopped or API.StopRequested:
        return False

    return True


def on_script_stop() -> None:
    """Stop callback registered with API.OnStop."""
    dispose_gump()
    API.SysMsg("Lobster Trap Auto stopped.", 53)


# ==============================================================================
# Main Orchestration Loop
# ==============================================================================

def run_lobster_auto() -> None:
    """Main execution loop for managing the lobster trap spots."""
    global is_waiting_start, is_paused, is_stopped

    API.OnStop(on_script_stop)
    create_control_gump()
    update_skill_display()
    update_satchel_label()

    API.SysMsg("Lobster Trap Auto initialized. Click 'Start' on the Gump to begin.", 68)
    is_waiting_start = True
    update_status("Click Start to begin")

    # Idle until user clicks Start on the Gump
    while is_waiting_start and not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return
        API.Pause(0.2)

    update_status("Deploying initial traps...")

    # Main trap management loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Handle user pause
        if is_paused:
            API.Pause(0.3)
            continue

        now = time.time()

        # 1. Fill any empty spots if traps are available in the backpack
        for spot in spots:
            if spot.state == "EMPTY":
                trap_serial = find_trap_in_backpack()
                if trap_serial:
                    deploy_trap_at_spot(spot)
                    API.Pause(ACTION_DELAY)

        # 2. Check deployed spots for bobs, catches, or sinking
        for spot in spots:
            if not check_ui_events() or is_paused:
                break

            if spot.state == "DEPLOYED":
                # Verify buoy is still present in the world
                buoy = API.FindItem(spot.buoy_serial) if spot.buoy_serial else None
                if not buoy:
                    # Buoy vanished (sank/destroyed)
                    increment_traps_lost()
                    API.SysMsg(f"Trap at {spot.name} was destroyed or sank!", 32)
                    spot.buoy_serial = None
                    spot.state = "EMPTY"
                    update_active_display()
                    continue

                elapsed = now - (spot.deployed_at or now)

                # Check if trap has reached the bob timer threshold
                if elapsed >= BOB_WAIT_SECONDS:
                    debug_msg(f"Spot {spot.name} reached bob timer ({elapsed:.1f}s). Hauling...")
                    haul_and_recycle_trap(spot)
                    API.Pause(ACTION_DELAY)

        update_active_display()
        API.Pause(0.5)


if __name__ == "__main__":
    run_lobster_auto()
