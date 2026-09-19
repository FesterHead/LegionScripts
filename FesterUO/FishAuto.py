"""
FishAuto.py - Automated Boat Fishing & Combat Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Automates boat fishing with an interactive control Gump and combat protection:
    - Automatically equips the "Fishing" dress profile at startup.
    - Samples a water tile on launch to determine water depth and graphic.
    - Fishes two spots to the player's Northeast (relative offsets) until depleted.
    - Moves the boat forward ("forward one" spoken 8 times) when both spots are fished out.
    - Detects junk fished up (shoes, boots, sandals, seaweed) and throws them back into the ocean.
    - Actively monitors for hostile enemies (sea serpents, water elementals, deep sea serpents, krakens, etc.).
    - When an enemy is detected:
        1. Switches to the "Archery" dress profile.
        2. Enters War Mode.
        3. Attacks and kills the enemy.
        4. Halts and stops the script.
    - Displays an on-screen status Gump showing:
        - Current activity status
        - Live Fishing skill (value and cap) with skill gain notifications
        - Enemies defeated counter
        - Interactive Pause/Resume and Stop buttons.

Usage:
    1. Ensure you have two Dress profiles configured in TazUO: "Fishing" and "Archery".
    2. Have a fishing pole and your archery weapon/ammo available.
    3. Board your boat facing forward.
    4. Start the script in TazUO.
    5. Target a water tile to your Northeast when prompted.
    6. Monitor and control execution using the on-screen Gump.
"""

from typing import List, Tuple, Optional
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Enable verbose debug messages in the client console/journal
DEBUG: bool = False

# Dress configuration profiles configured in TazUO client
DRESS_PROFILE_FISHING: str = "Fishing"
DRESS_PROFILE_COMBAT: str = "Archery"

# Fishing pole graphic ID
FISHING_POLE_GRAPHIC: int = 0x0DC0

# Delay in seconds between casts. FesterUO allows fast harvesting (1.0s–2.0s).
# For standard / official UO shards, set this to 6.0s–8.0s.
FISHING_DELAY: float = 3.0

# Screen orientation offsets (dX, dY):
# In Ultima Online's 45-degree isometric projection:
# - Directly UP on screen (North) is dX < 0 and dY < 0 (e.g. -2, -2)
# - Directly LEFT-UP (Northwest) on screen is dX < 0 and dY == 0 (e.g. -2, 0)
# SPOT1 and SPOT2 are set twice as far (4 and 6 tiles) to the Left-Up:
SPOT1_OFFSET: Tuple[int, int] = (-4, 0)
SPOT2_OFFSET: Tuple[int, int] = (-6, 0)

# Boat movement settings
BOAT_STEPS: int = 16
BOAT_COMMAND: str = "forward one"
BOAT_STEP_DELAY: float = 1.5

# Combat detection range (tiles)
ENEMY_SCAN_RADIUS: int = 12

# Common sea enemy name keywords
HOSTILE_KEYWORDS: List[str] = [
    "serpent", "elemental", "kraken", "sea", "leviathan", "deep", "dagon"
]

# Common junk items fished up from the ocean
JUNK_GRAPHICS: List[int] = [
    0x170F,  # Shoes
    0x1708,  # Boots
    0x170B,  # Leather Boots / Thigh Boots
    0x1711,  # Thigh Boots
    0x170D,  # Sandals
    0x0DC1,  # Seaweed / Turnip / Kelp
    0x0DC2,  # Fish bones / Twigs
]

JUNK_KEYWORDS: List[str] = [
    "shoes", "boots", "sandals", "seaweed", "kelp", "twigs"
]

# Depletion and unreachable journal messages
DEPLETED_MESSAGES: List[str] = [
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
# Global Gump & State Management
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_enemies = None
btn_pause = None
btn_stop = None

is_paused: bool = False
is_stopped: bool = False
enemies_defeated_count: int = 0
last_skill: Optional[float] = None


def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def update_status(text: str) -> None:
    """Updates the status line displayed on the Gump."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"
    debug_msg(text)


def increment_enemies_defeated() -> None:
    """Increments the defeated counter and refreshes the Gump."""
    global enemies_defeated_count, lbl_enemies
    enemies_defeated_count += 1
    if lbl_enemies:
        lbl_enemies.Text = f"Enemies Defeated: {enemies_defeated_count}"


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
            API.SysMsg(f"Fishing gained +{gain:.1f}! New skill: {val:.1f}")
        last_skill = val


def on_pause_clicked() -> None:
    """Callback when the Pause / Resume button is clicked."""
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Auto Fisher paused." if is_paused else "Auto Fisher resumed.")


def on_stop_clicked() -> None:
    """Callback when the Stop button is clicked."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_gump_disposed() -> None:
    """Callback triggered if the Gump window is closed by right-click."""
    global is_stopped
    if not is_stopped and not API.StopRequested:
        is_stopped = True
        API.Stop()


def create_control_gump() -> None:
    """Initializes and displays the interactive control Gump."""
    global gump, lbl_status, lbl_skill, lbl_enemies, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 240, 150)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 240, 150)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Auto Fisher", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 32)
    gump.Add(lbl_status)

    # Fishing skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Fishing: --", 996)
    lbl_skill.SetPos(10, 54)
    gump.Add(lbl_skill)

    # Enemies defeated label
    lbl_enemies = API.Gumps.CreateGumpLabel("Enemies Defeated: 0", 996)
    lbl_enemies.SetPos(10, 76)
    gump.Add(lbl_enemies)

    # Pause button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 70, 22)
    btn_pause.SetPos(15, 112)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 70, 22)
    btn_stop.SetPos(155, 112)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Handle gump right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely cleans up and disposes the Gump."""
    global gump
    if gump and not gump.IsDisposed:
        gump.Dispose()


def check_ui_events() -> bool:
    """
    Processes UI callbacks, updates skill display, and handles pause states.
    Returns False if execution should terminate, True to continue.
    """
    global is_paused, is_stopped
    API.ProcessCallbacks()
    update_skill_display()

    if is_stopped or API.StopRequested:
        return False

    # Check button clicks directly in case callbacks were batched
    if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
        on_stop_clicked()
        return False

    if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
        on_pause_clicked()

    # If paused, idle and pump events
    while is_paused and not API.StopRequested and not is_stopped:
        API.Pause(0.2)
        API.ProcessCallbacks()
        update_skill_display()
        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            on_pause_clicked()
            break

    return not (is_stopped or API.StopRequested)


def on_script_stop() -> None:
    """Clean-up callback when script halts."""
    dispose_gump()
    API.SysMsg("Auto Fisher stopped.")


API.OnStop(on_script_stop)

# ==============================================================================
# Helper Functions: Equipment, Junk, Combat & Movement
# ==============================================================================

def get_fishing_pole():
    """Finds an equipped fishing pole or one in the backpack."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and (item.Graphic == FISHING_POLE_GRAPHIC or "pole" in str(item.Name).lower()):
            return item

    pole = API.FindType(FISHING_POLE_GRAPHIC, API.Backpack)
    if pole:
        return pole

    return None


def is_spot_depleted() -> Tuple[bool, str]:
    """
    Checks if the current fishing spot is depleted using direct InJournal
    and recent journal entry string scanning.
    """
    for msg in DEPLETED_MESSAGES:
        if API.InJournal(msg):
            return True, msg

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


def dispose_junk() -> None:
    """
    Scans the player's backpack for junk items (boots, shoes, seaweed, etc.)
    and tosses them back into the water (2 tiles to the Northeast).
    """
    items = API.ItemsInContainer(API.Backpack)
    if not items:
        return

    for item in items:
        if API.StopRequested or is_stopped:
            return

        is_junk = False
        if item.Graphic in JUNK_GRAPHICS:
            is_junk = True
        else:
            name = str(item.Name).lower()
            if any(k in name for k in JUNK_KEYWORDS):
                is_junk = True

        if is_junk:
            debug_msg(f"Tossing junk item: {item.Name} (0x{item.Graphic:04X})")
            # Drop 2 tiles NE into water
            API.MoveItemOffset(item.Serial, 0, 2, -2, 0)
            API.Pause(0.6)


def find_hostile_enemy():
    """
    Scans for nearby hostile mobiles (Gray, Criminal, Enemy, Murderer)
    or creatures matching sea enemy keywords within ENEMY_SCAN_RADIUS.
    """
    hostile_notorieties = [
        API.Notoriety.Gray,
        API.Notoriety.Criminal,
        API.Notoriety.Enemy,
        API.Notoriety.Murderer
    ]

    mob = API.NearestMobile(hostile_notorieties, ENEMY_SCAN_RADIUS)
    if mob and not mob.IsDead:
        return mob

    # Check all mobiles in range by name keywords
    mobiles = API.GetAllMobiles(distance=ENEMY_SCAN_RADIUS)
    if mobiles:
        for m in mobiles:
            if m.Serial == API.Player.Serial or m.IsDead:
                continue
            name = str(m.Name).lower()
            if any(k in name for k in HOSTILE_KEYWORDS):
                return m

    return None


def handle_enemy_combat(enemy) -> bool:
    """
    When an enemy is detected:
    1. Switches to 'Archery' dress profile.
    2. Enters War Mode.
    3. Attacks the enemy until dead.
    4. Announces victory, stops execution, and returns True.
    """
    enemy_name = str(enemy.Name) if enemy.Name else "Hostile Enemy"
    API.SysMsg(f"Hostile detected: {enemy_name}! Switching to Archery...")
    update_status(f"Fighting {enemy_name}...")

    # 1. Dress Archery
    if DRESS_PROFILE_COMBAT:
        API.Dress(DRESS_PROFILE_COMBAT)
        API.Pause(0.8)

    # 2. Enter War Mode
    API.SetWarMode(True)
    API.Pause(0.3)

    # 3. Engage in combat
    API.Attack(enemy.Serial)

    while not API.StopRequested and not is_stopped:
        check_ui_events()

        # Check if enemy is dead or vanished
        target = API.FindMobile(enemy.Serial)
        if not target or target.IsDead or (target.Hits is not None and target.Hits <= 0):
            break

        # Re-verify target in war mode every 1 second
        if not API.Player.InWarMode:
            API.SetWarMode(True)
        API.Attack(enemy.Serial)
        API.Pause(1.0)

    # Enemy defeated
    increment_enemies_defeated()
    API.SysMsg(f"Enemy {enemy_name} defeated! Stopping script as requested.")
    update_status(f"Defeated {enemy_name} - Stopped")

    # Leave war mode
    API.SetWarMode(False)

    # Stop script
    on_stop_clicked()
    return True


def move_boat_forward() -> None:
    """Advances the boat forward 8 steps sequentially."""
    update_status(f"Moving boat ({BOAT_STEPS} steps)...")
    API.SysMsg(f"Advancing boat forward {BOAT_STEPS} steps...")

    for i in range(1, BOAT_STEPS + 1):
        if API.StopRequested or is_stopped:
            return
        if not check_ui_events():
            return

        # Check if an enemy appeared while moving
        enemy = find_hostile_enemy()
        if enemy:
            handle_enemy_combat(enemy)
            return

        API.Msg(BOAT_COMMAND)
        API.Pause(BOAT_STEP_DELAY)

    API.Pause(1.0)


def cast_at_offset(offset: Tuple[int, int]) -> bool:
    """
    Targets the relative Northwest water tile.
    Uses TargetLandRel first (standard UO water is Land),
    then falls back to TargetRel if cursor remains open.
    Returns True if target cursor was consumed, False otherwise.
    """
    # 1. Try TargetLandRel (in UO, open water is almost always a Land tile)
    API.TargetLandRel(offset[0], offset[1])
    API.Pause(0.2)
    if not API.HasTarget():
        return True

    # 2. Try TargetRel (for static / multi water tiles)
    API.TargetRel(offset[0], offset[1], False)
    API.Pause(0.2)
    if not API.HasTarget():
        return True

    # 3. Try exact coordinate Target with Land/Static lookup
    tx = API.Player.X + offset[0]
    ty = API.Player.Y + offset[1]
    tile = API.GetTile(tx, ty)
    if tile:
        tz = getattr(tile, "Z", API.Player.Z)
        tg = getattr(tile, "Graphic", 0)
        API.Target(tx, ty, tz, tg)
        API.Pause(0.2)
        if not API.HasTarget():
            return True

    statics = API.GetStaticsAt(tx, ty)
    if statics:
        s = statics[0]
        API.Target(tx, ty, s.Z, s.Graphic)
        API.Pause(0.2)
        if not API.HasTarget():
            return True

    return not API.HasTarget()


def fish_spot(offset: Tuple[int, int], spot_name: str) -> bool:
    """
    Repeatedly casts at a relative offset (Northwest) until depleted or interrupted by an enemy.
    Returns True if depleted, False if stopped.
    """
    pole = get_fishing_pole()
    if not pole:
        # Re-dress fishing profile if pole unequipped
        if DRESS_PROFILE_FISHING:
            API.Dress(DRESS_PROFILE_FISHING)
            API.Pause(1.0)
        pole = get_fishing_pole()

    if not pole:
        API.SysMsg("Error: Fishing pole not found!")
        return False

    update_status(f"Fishing {spot_name}...")
    debug_msg(f"Fishing {spot_name} at offset {offset}")

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return False

        # 1. Combat check before each cast
        enemy = find_hostile_enemy()
        if enemy:
            handle_enemy_combat(enemy)
            return False

        # Cancel any dangling target cursor before using pole
        if API.HasTarget():
            API.CancelTarget()
            API.Pause(0.2)

        API.ClearJournal()
        API.UseObject(pole)

        if API.WaitForTarget(timeout=5):
            success = cast_at_offset(offset)
            if not success:
                debug_msg(f"{spot_name}: Target not accepted, cancelling cursor.")
                API.CancelTarget()
            API.Pause(FISHING_DELAY)
        else:
            debug_msg(f"{spot_name}: Target cursor timeout, retrying...")
            API.Pause(0.8)
            API.UseObject(pole)
            if API.WaitForTarget(timeout=5):
                success = cast_at_offset(offset)
                if not success:
                    API.CancelTarget()
                API.Pause(FISHING_DELAY)
            else:
                debug_msg(f"{spot_name}: Target failed.")
                return True

        # 2. Check for enemy that may have spawned from the cast
        enemy = find_hostile_enemy()
        if enemy:
            handle_enemy_combat(enemy)
            return False

        # 3. Clean up caught junk
        dispose_junk()

        # 4. Check spot depletion
        depleted, reason = is_spot_depleted()
        if depleted:
            API.SysMsg(f"{spot_name} depleted: '{reason}'")
            return True

    return False

# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    create_control_gump()
    update_status("Initializing...")
    update_skill_display()

    # 1. Apply Fishing dress profile
    if DRESS_PROFILE_FISHING:
        API.SysMsg(f"Applying dress profile '{DRESS_PROFILE_FISHING}'...")
        API.Dress(DRESS_PROFILE_FISHING)
        API.Pause(1.0)

    # 2. Check for fishing pole
    pole = get_fishing_pole()
    if not pole:
        API.SysMsg("No fishing pole found in hands or backpack!")
        update_status("No fishing pole!")
        return

    API.SysMsg("Starting automated boat fishing (Northwest)...")
    update_status("Starting...")

    # 3. Main automated boat fishing loop
    cycle = 0
    while not API.StopRequested and not is_stopped:
        cycle += 1
        debug_msg(f"=== Fishing Cycle #{cycle} ===")

        # Check combat
        enemy = find_hostile_enemy()
        if enemy:
            handle_enemy_combat(enemy)
            return

        # Fish Spot 1 to NW (offset: -2, -2)
        if not fish_spot(SPOT1_OFFSET, "NW Spot 1"):
            break

        # Check combat
        enemy = find_hostile_enemy()
        if enemy:
            handle_enemy_combat(enemy)
            return

        # Fish Spot 2 to NW (offset: -3, -3)
        if not fish_spot(SPOT2_OFFSET, "NW Spot 2"):
            break

        # Check combat
        enemy = find_hostile_enemy()
        if enemy:
            handle_enemy_combat(enemy)
            return

        # Both spots depleted -> Advance boat forward 8 steps
        move_boat_forward()

    update_status("Finished")
    API.SysMsg("Auto Fisher finished.")


main()
