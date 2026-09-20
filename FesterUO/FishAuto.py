"""
FishAuto.py - Automated Boat Fishing & Combat Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Automates boat fishing with an interactive control Gump and combat protection:
    - Automatically equips the "Fishing" dress profile at startup.
    - Automatically fishes both sides of the vessel (Northwest and Southeast) off the railings into open water,
      completely clearing the mast, sail, bow, and stern.
    - Moves the boat forward ("forward one" spoken 8 times) when both side spots are fished out, advancing 8 tiles
      to the next resource block.
    - Detects fish caught and optionally runs the configured TazUO Organizer agent ("FishOrganizer") to stow catches.
    - Detects junk fished up (shoes, boots, sandals, seaweed) and throws them back into the ocean.
    - Actively monitors for hostile enemies (sea serpents, water elementals, deep sea serpents, krakens, etc.), excluding dolphins.
    - When an enemy is detected:
        1. Undresses the "Fishing" profile.
        2. Switches to the "Archery" dress profile (with automatic backpack bow equip fallback).
        3. Enters War Mode.
        4. Attacks the mob.
        5. Halts automated fishing, keeping the Gump open with a "Start" button so the player can manually fight, loot, and click "Start" when ready to resume fishing.
    - Displays an on-screen status Gump showing:
        - Current activity status
        - Live Fishing skill (value and cap) with skill gain notifications
        - Enemies defeated counter
        - Interactive Start / Pause / Resume and Stop buttons.

Usage:
    1. Ensure you have two Dress profiles configured in TazUO: "Fishing" and "Archery".
    2. Have a fishing pole and your archery weapon/ammo available.
    3. Board your boat facing forward.
    4. Start the script in TazUO.
    5. Monitor and control execution using the on-screen Gump.
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

# Organizer agent settings
# Runs the organizer agent by name or index: Organizer(name, source, destination)
# When RUN_ORGANIZER is True, invokes Organizer(ORGANIZER_NAME) after catching a fish to stow it
RUN_ORGANIZER: bool = False
ORGANIZER_NAME: str = "FishOrganizer"

# Fishing pole graphic ID
FISHING_POLE_GRAPHIC: int = 0x0DC0

# Journal keywords indicating a fish catch landed (e.g. 'You pull out amberjack!')
FISH_CAUGHT_KEYWORDS: List[str] = [
    "you pull out",
    "pull out",
    "you catch",
]

# Delay in seconds between casts. FesterUO allows fast harvesting (1.0s–2.0s).
# For standard / official UO shards, set this to 6.0s–8.0s.
FISHING_DELAY: float = 3.0

# Side fishing spots relative to the boat:
# Targeting a few tiles to the Northwest and then Southeast targets directly off the
# sides of the boat into open water, completely clearing the mast, sail, bow, and stern.
FISHING_SPOTS: List[Tuple[Tuple[int, int], str]] = [
    ((-1, -1), "Northwest"),
    (( 1,  1), "Southeast"),
]

# Known UO water graphic ranges (land and static)
LAND_WATER_GRAPHICS = {0x00A8, 0x00A9, 0x00AA, 0x00AB, 0x0136, 0x0137}
STATIC_WATER_GRAPHICS = set(range(0x1796, 0x17B3))

# Boat movement settings
# Advances the boat forward 8 steps between side-harvesting cycles
BOAT_STEPS: int = 8
BOAT_COMMAND: str = "forward one"
BOAT_STEP_DELAY: float = 1.5

# Combat detection range (tiles)
ENEMY_SCAN_RADIUS: int = 12

# Common sea enemy name keywords
HOSTILE_KEYWORDS: List[str] = [
    "serpent", "elemental", "kraken", "sea", "leviathan", "deep", "dagon"
]

# Mobiles to explicitly exclude from combat detection (e.g. harmless sea life)
IGNORED_MOBILES: List[str] = [
    "dolphin"
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
    "target cannot be seen",
    "Target cannot be seen",
    "cannot be seen",
    "Cannot be seen",
    "cannot see that",
    "Cannot see that",
    "can't see that",
    "Can't see that",
    "can't be seen",
    "Can't be seen",
    "obstructed",
    "Obstructed",
    "that is obstructed",
    "That is obstructed",
    "target is obstructed",
    "Target is obstructed",
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
is_waiting_start: bool = False
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


def set_action_button(text: str) -> None:
    """Updates the action button text (Start / Pause / Resume)."""
    global btn_pause
    if btn_pause:
        btn_pause.SetText(text)


def on_action_clicked() -> None:
    """Callback when the Start / Pause / Resume button is clicked."""
    global is_paused, is_waiting_start, btn_pause
    if is_waiting_start:
        is_waiting_start = False
        update_status("Starting...")
    elif is_paused:
        is_paused = False
        if btn_pause:
            btn_pause.SetText("Pause")
        update_status("Resuming...")
        API.SysMsg("Auto Fisher resumed.")
    else:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused")
        API.SysMsg("Auto Fisher paused.")


def wait_for_start(prompt: str) -> bool:
    """
    Idles with the Gump open waiting for the user to click Start.
    Returns True if Start was clicked, False if script was stopped.
    """
    global is_waiting_start, btn_pause
    is_waiting_start = True
    set_action_button("Start")
    update_status(prompt)

    while is_waiting_start and not API.StopRequested and not is_stopped:
        API.Pause(0.2)
        API.ProcessCallbacks()
        update_skill_display()
        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            is_waiting_start = False
            break

    if API.StopRequested or is_stopped:
        return False

    set_action_button("Pause")
    return True


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

    # Action button (Start / Pause / Resume)
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 70, 22)
    btn_pause.SetPos(15, 112)
    API.Gumps.AddControlOnClick(btn_pause, on_action_clicked)
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
        on_action_clicked()

    # If paused, idle and pump events
    while is_paused and not API.StopRequested and not is_stopped:
        API.Pause(0.2)
        API.ProcessCallbacks()
        update_skill_display()
        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            on_action_clicked()
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
            if "cannot be seen" in text or "can't be seen" in text or "cannot see" in text or "can't see" in text:
                return True, entry.Text
            if "obstruct" in text:
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


def is_open_water(tx: int, ty: int) -> bool:
    """
    Checks if the coordinates (tx, ty) represent open fishable water
    and are not obstructed by the boat multi (deck, mast, gunwales) or land obstacles.
    """
    # 1. Check statics: if any static is a boat multi part (deck, mast, gunwale), it's not open water
    statics = API.GetStaticsAt(tx, ty)
    if statics:
        for s in statics:
            if getattr(s, "Graphic", 0) in STATIC_WATER_GRAPHICS:
                return True
            if getattr(s, "IsImpassible", False) or getattr(s, "Impassible", False):
                return False

    # 2. Check land tile
    tile = API.GetTile(tx, ty)
    if not tile:
        return False

    g = getattr(tile, "Graphic", 0)
    if g in LAND_WATER_GRAPHICS:
        return True

    item_data = getattr(tile, "GetItemData", lambda: None)()
    if item_data and getattr(item_data, "IsWet", False):
        return True

    return False


def find_side_water_spot(dir_x: int, dir_y: int, min_dist: int = 2, max_dist: int = 4) -> Tuple[int, int]:
    """
    Finds a clear open water tile offset (dx, dy) to the side of the boat (NW or SE).
    Checks distances 2 to 4 to stay close to the boat railing and well within cast range.
    """
    px = API.Player.X
    py = API.Player.Y

    # 1. Try along the direct ray off the side
    for dist in range(min_dist, max_dist + 1):
        dx = dir_x * dist
        dy = dir_y * dist
        if is_open_water(px + dx, py + dy):
            return dx, dy

    # 2. Try adjacent side angles off the railing
    for dist in range(min_dist, max_dist + 1):
        for off1, off2 in [
            (dist, max(1, dist - 1)),
            (max(1, dist - 1), dist),
            (dist, 1),
            (1, dist),
        ]:
            dx = dir_x * off1
            dy = dir_y * off2
            if is_open_water(px + dx, py + dy):
                return dx, dy

    # Fallback to 2-tile side offset (right off the railing)
    return dir_x * 2, dir_y * 2




def run_fish_organizer() -> None:
    """
    Runs the organizer agent by name or index:
    # Organizer(name, source, destination)
    # Organizer("FishOrganizer")
    """
    if RUN_ORGANIZER and ORGANIZER_NAME:
        debug_msg(f"Running Organizer('{ORGANIZER_NAME}')...")
        API.Organizer(ORGANIZER_NAME)
        API.Pause(0.5)


def find_hostile_enemy():
    """
    Scans for nearby hostile mobiles (Gray, Criminal, Enemy, Murderer)
    or creatures matching sea enemy keywords within ENEMY_SCAN_RADIUS,
    explicitly excluding harmless sea life like dolphins.
    """
    hostile_notorieties = {
        API.Notoriety.Gray,
        API.Notoriety.Criminal,
        API.Notoriety.Enemy,
        API.Notoriety.Murderer
    }

    try:
        mobiles = API.GetAllMobiles(distance=ENEMY_SCAN_RADIUS)
        if mobiles:
            for m in mobiles:
                if not m or m.Serial == API.Player.Serial or m.IsDead:
                    continue
                name = str(m.Name).lower() if m.Name else ""
                # Exclude friendly or ignored mobiles (e.g. dolphins)
                if any(ign in name for ign in IGNORED_MOBILES):
                    continue
                # Check explicit hostile keywords (sea serpent, kraken, water elemental, etc.)
                if any(k in name for k in HOSTILE_KEYWORDS):
                    return m
                # Check hostile notoriety
                if m.Notoriety in hostile_notorieties:
                    return m
    except Exception as ex:
        debug_msg(f"Enemy scan error: {ex}")

    return None


def handle_enemy_combat(enemy) -> bool:
    """
    When an enemy is detected:
    1. Undresses 'Fishing' dress profile to free hands and equipment slots.
    2. Switches to 'Archery' dress profile (or directly equips bow from backpack).
    3. Enters War Mode.
    4. Attacks the mob.
    5. Stops automated fishing so player can manually fight, kill, and loot.
    """
    enemy_name = str(enemy.Name) if enemy.Name else "Hostile Enemy"
    API.SysMsg(f"Hostile detected: {enemy_name}! Switching to Archery...")
    update_status(f"Hostile: {enemy_name}")

    # 1. Undress fishing profile before dressing archery
    if DRESS_PROFILE_FISHING:
        debug_msg(f"Undressing profile '{DRESS_PROFILE_FISHING}'...")
        try:
            API.Undress(DRESS_PROFILE_FISHING)
            API.Pause(0.8)
        except Exception as ex:
            debug_msg(f"Undress error: {ex}")

    # Also ensure any equipped pole in hands is moved to backpack
    pole = get_fishing_pole()
    if pole and pole.Container == API.Player.Serial:
        debug_msg("Unequipping fishing pole from hands...")
        API.MoveItem(pole.Serial, 0, API.Backpack)
        API.Pause(0.6)

    # 2. Dress Archery profile
    if DRESS_PROFILE_COMBAT:
        try:
            available = API.GetAvailableDressOutfits()
            if available and DRESS_PROFILE_COMBAT not in available:
                API.SysMsg(f"Warning: Combat profile '{DRESS_PROFILE_COMBAT}' not found in TazUO! Available: {', '.join(available)}")
            API.Dress(DRESS_PROFILE_COMBAT)
            API.Pause(1.0)
        except Exception as ex:
            debug_msg(f"Dress combat profile error: {ex}")

    # Fallback: if hands still empty or bow not equipped, search backpack for any bow
    bow_graphics = [0x13B2, 0x0F50, 0x13FD, 0x26C2, 0x26C3, 0x27A5, 0x2D1E, 0x2D2B]
    bow = None
    for bg in bow_graphics:
        found = API.FindType(bg, API.Backpack)
        if found:
            bow = found
            break
    if bow:
        debug_msg(f"Equipping bow from backpack: {bow.Name} (0x{bow.Graphic:04X})")
        API.UseObject(bow)
        API.Pause(0.6)

    # 3. Enter War Mode
    API.SetWarMode(True)
    API.Pause(0.3)

    # 4. Attack mob
    API.Attack(enemy.Serial)
    increment_enemies_defeated()

    API.SysMsg(f"Attacking {enemy_name}! Script stopped for manual combat and looting.")
    API.SysMsg("Click 'Start' on the Gump when ready to resume fishing.")
    update_status("Combat - Click Start when ready")
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
    Targets the water tile at the given relative offset.
    Uses TargetLandRel first, then TargetRel, then exact coordinates.
    """
    tx = API.Player.X + offset[0]
    ty = API.Player.Y + offset[1]

    # 1. Try TargetLandRel (standard UO open ocean is Land)
    API.TargetLandRel(offset[0], offset[1])
    API.Pause(0.2)
    if not API.HasTarget():
        return True

    # 2. Try TargetRel
    API.TargetRel(offset[0], offset[1], False)
    API.Pause(0.2)
    if not API.HasTarget():
        return True

    # 3. Exact coordinate targeting
    tile = API.GetTile(tx, ty)
    if tile:
        tz = getattr(tile, "Z", API.Player.Z)
        # Land target packet: do not supply static graphic to avoid packet mismatch
        API.Target(tx, ty, tz)
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
    Repeatedly casts at a relative offset until depleted or interrupted by an enemy.
    Returns True if depleted or skipped, False if stopped.
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

    consecutive_target_fails = 0

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

        cast_completed = False
        if API.WaitForTarget(timeout=5):
            success = cast_at_offset(offset)
            if not success:
                consecutive_target_fails += 1
                debug_msg(f"{spot_name}: Target not accepted (#{consecutive_target_fails}), cancelling cursor.")
                API.CancelTarget()
                if consecutive_target_fails >= 2:
                    API.SysMsg(f"{spot_name}: Boat or obstacle in the way, moving to next spot.")
                    return True
            else:
                consecutive_target_fails = 0
                cast_completed = True
            API.Pause(FISHING_DELAY)
        else:
            debug_msg(f"{spot_name}: Target cursor timeout, retrying...")
            API.Pause(0.8)
            API.UseObject(pole)
            if API.WaitForTarget(timeout=5):
                success = cast_at_offset(offset)
                if not success:
                    consecutive_target_fails += 1
                    API.CancelTarget()
                    if consecutive_target_fails >= 2:
                        API.SysMsg(f"{spot_name}: Target failed, moving to next spot.")
                        return True
                else:
                    consecutive_target_fails = 0
                    cast_completed = True
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

        # 4. Check if a fish was caught and run the Organizer agent
        if cast_completed:
            caught_fish = False
            for kw in FISH_CAUGHT_KEYWORDS:
                if API.InJournal(kw):
                    caught_fish = True
                    break
            if not caught_fish:
                entries = API.GetJournalEntries(FISHING_DELAY + 1.0)
                if entries:
                    for entry in entries:
                        t = str(entry.Text).lower()
                        if "fail to catch" in t or "biting here" in t or "no fish" in t:
                            continue
                        if any(kw in t for kw in FISH_CAUGHT_KEYWORDS):
                            caught_fish = True
                            break

            if caught_fish:
                debug_msg(f"{spot_name}: Fish caught!")
                run_fish_organizer()

        # 5. Check spot depletion
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

    # Outer loop allows stopping for combat, looting, and clicking Start to resume
    while not API.StopRequested and not is_stopped:
        # 1. Leave War Mode if returning from combat
        if API.Player.InWarMode:
            API.SetWarMode(False)
            API.Pause(0.3)

        # 2. Apply Fishing dress profile
        if DRESS_PROFILE_FISHING:
            API.SysMsg(f"Applying dress profile '{DRESS_PROFILE_FISHING}'...")
            API.Dress(DRESS_PROFILE_FISHING)
            API.Pause(1.0)

        # 3. Check for fishing pole
        pole = get_fishing_pole()
        if not pole:
            API.SysMsg("No fishing pole found in hands or backpack!")
            if not wait_for_start("No fishing pole! Click Start when ready"):
                break
            continue

        API.SysMsg("Starting automated boat fishing (Northwest & Southeast)...")
        update_status("Fishing...")
        set_action_button("Pause")

        # 4. Main automated boat fishing loop
        cycle = 0
        combat_triggered = False
        while not API.StopRequested and not is_stopped:
            cycle += 1
            debug_msg(f"=== Fishing Cycle #{cycle} ===")

            # Fish side spots (Northwest, then Southeast) off the boat railings
            for (dir_x, dir_y), spot_name in FISHING_SPOTS:
                if API.StopRequested or is_stopped:
                    break

                # Check combat before starting each spot
                enemy = find_hostile_enemy()
                if enemy:
                    handle_enemy_combat(enemy)
                    combat_triggered = True
                    break

                offset = find_side_water_spot(dir_x, dir_y)

                if not fish_spot(offset, spot_name):
                    combat_triggered = True
                    break

                # Check combat immediately after spot finishes
                enemy = find_hostile_enemy()
                if enemy:
                    handle_enemy_combat(enemy)
                    combat_triggered = True
                    break

            if API.StopRequested or is_stopped or combat_triggered:
                break

            # Both side spots depleted -> Advance boat forward 8 steps
            move_boat_forward()

        # If combat was triggered, idle with Gump open so player can fight & loot, then click Start
        if combat_triggered and not (API.StopRequested or is_stopped):
            if not wait_for_start("Combat mode. Click Start to resume fishing"):
                break

    update_status("Finished")
    API.SysMsg("Auto Fisher finished.")
    dispose_gump()


main()
