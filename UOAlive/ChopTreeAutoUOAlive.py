"""
ChopTreeAutoUOAlive.py - Automated Roaming Lumberjacking Script for UOAlive

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)
Target Shard: UOAlive

Description:
    Automates lumberjacking across an area with an interactive control Gump:
    - Automatically enables the configured "Lumberjack" dress profile.
    - Scans for nearby tree statics using TazUO's native static detection.
    - Selects the nearest unvisited tree within SEARCH_RADIUS.
    - Pathfinds adjacent to the tree (within chopping reach: distance <= 2).
    - Repeatedly swings the equipped axe until the tree is depleted.
    - Automatically converts harvested logs into boards using the axe,
      halving wood weight and keeping backpack space organized.
    - Keeps track of the last 50 visited trees in a FIFO history queue
      to prevent repeating recently chopped trees.
    - Moves on to the next nearest tree when nothing is left.
    - Features an interactive control Gump styled identically to FesterUO's
      ChopTreeAuto, displaying real-time Status, Trees Harvested, Boards,
      Lumberjacking skill with gain tracking, and STR / DEX / Weight monitoring.
    - Features a Pause/Resume button to pause manually at any time to make new
      tools (Tinkering), fletch shafts/bows, or do log/board management.
    - Automatically pauses and triggers an audible and visual overhead alert
      when weight capacity is reached, resuming smoothly once unloaded.

Usage:
    1. Ensure you have an axe equipped or in your backpack.
    2. Configure a "Lumberjack" dress profile in TazUO (optional but recommended).
    3. Stand near an area with trees.
    4. Start the script in TazUO.
    5. Use the on-screen Gump to monitor progress, Pause/Resume, or Stop.
"""

from collections import deque
from typing import List, Optional, Set, Tuple
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Enable verbose logging in the client console/journal
DEBUG: bool = False

# Delay in seconds between swings. Fast shards like UOAlive support 1.0s - 1.25s.
SWING_DELAY: float = 1.0

# Dress configuration profile to load at startup (set to None or "" to disable)
DRESS_PROFILE: str = "Lumberjack"

# Search radius in tiles around the player to locate trees
SEARCH_RADIUS: int = 25

# Maximum number of recent trees to remember and avoid revisiting (FIFO queue)
TREE_HISTORY_LIMIT: int = 50

# Stop/Pause script if backpack weight is near capacity
MAX_WEIGHT_CHECK: bool = True
WEIGHT_BUFFER: int = 15  # Pause when Weight >= WeightMax - WEIGHT_BUFFER

# Maximum seconds allowed to pathfind to a tree before skipping it
PATHFIND_TIMEOUT: float = 12.0

# Alert sound played when auto-pausing (0x1F8 = classic system notice chime)
ALERT_SOUND: int = 0x1F8

# ==============================================================================
# Graphics Definitions
# ==============================================================================

# Common woodcutting axes
AXE_GRAPHICS: List[int] = [
    0x0F43, 0x0F44,  # Hatchet
    0x0F45, 0x0F46,  # Executioner's Axe
    0x0F47, 0x0F48,  # Battle Axe
    0x0F49, 0x0F4A,  # Axe
    0x0F4B, 0x0F4C,  # Double Axe
    0x0F4D, 0x0F4E,  # Bardiche
    0x13AF, 0x13B0,  # War Axe
    0x13FA, 0x13FB,  # Large Battle Axe
    0x1442, 0x1443,  # Two Handed Axe
]

# Log graphics (standard, alternate single/piles)
LOG_GRAPHICS: List[int] = [
    0x1BDD,  # Standard log
    0x1BDE,  # Alternate log pile
    0x1BDF,  # Alternate log pile
    0x1BE0,  # Alternate log pile
]

# Board graphics (all standard and special wood varieties)
BOARD_GRAPHICS: List[int] = [
    0x1BD7, 0x1BD8, 0x1BD9, 0x1BDA, 0x1BDB, 0x1BDC, 0x1BE1, 0x1BE2
]

# Journal keywords indicating a tree has no more wood or cannot be harvested
DEPLETED_KEYWORDS: List[str] = [
    "no wood here",
    "not enough wood",
    "nothing here to chop",
    "cannot see that",
    "can't reach",
    "no line of sight",
    "too far away",
    "target cannot be seen",
    "have no line of sight",
    "try chopping elsewhere",
    "you have depleted",
    "someone has already",
    "it appears immune to your blow",
    "immune to your axe",
    "cannot be chopped",
    "use an axe on that",
    "use an axe"
]

# ==============================================================================
# Global Gump & State Management
# ==============================================================================

gump = None
lbl_status = None
lbl_trees = None
lbl_skill = None
lbl_stats = None
btn_pause = None
btn_stop = None

is_paused: bool = False
is_stopped: bool = False
trees_harvested_count: int = 0

last_skill: Optional[float] = None
last_str: Optional[int] = None
last_dex: Optional[int] = None


def update_status(text: str) -> None:
    """Updates the status display on the Gump and prints to debug if enabled."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"
    debug_msg(text)


def increment_trees_harvested() -> None:
    """Increments the tree counter and updates the Gump label."""
    global trees_harvested_count, lbl_trees
    trees_harvested_count += 1
    if lbl_trees:
        lbl_trees.Text = f"Trees: {trees_harvested_count} | Boards: {get_backpack_board_count()}"


def update_stats() -> None:
    """Updates Lumberjacking skill, Strength, Dexterity, and Weight on the Gump."""
    global last_skill, last_str, last_dex, lbl_skill, lbl_stats, lbl_trees

    # Update Trees & Boards count display
    if lbl_trees:
        lbl_trees.Text = f"Trees: {trees_harvested_count} | Boards: {get_backpack_board_count()}"

    # Update Lumberjacking skill
    skill_obj = API.GetSkill("Lumberjacking") or API.GetSkill("Lumberjack")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        lbl_skill.Text = f"Lumberjack: {val:.1f} / {cap:.1f}"
        if last_skill is not None and val > last_skill:
            gain = val - last_skill
            API.SysMsg(f"Lumberjacking gained +{gain:.1f}! New skill: {val:.1f}")
        last_skill = val

    # Update STR, DEX, and Backpack Weight
    cur_str = API.Player.Strength
    cur_dex = API.Player.Dexterity
    cur_wt = API.Player.Weight
    max_wt = API.Player.WeightMax
    if lbl_stats and cur_str is not None and cur_dex is not None:
        wt_str = f"{cur_wt}/{max_wt}" if cur_wt is not None and max_wt is not None else "--/--"
        lbl_stats.Text = f"STR: {cur_str} | DEX: {cur_dex} | Wt: {wt_str}"
        if last_str is not None and cur_str > last_str:
            API.SysMsg(f"Strength increased to {cur_str}!")
        if last_dex is not None and cur_dex > last_dex:
            API.SysMsg(f"Dexterity increased to {cur_dex}!")
        last_str = cur_str
        last_dex = cur_dex


def trigger_overweight_pause() -> None:
    """Auto-pauses the script when the player is full and triggers an audible and visual alert."""
    global is_paused, btn_pause
    if not is_paused:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused: Too Full!")
        API.HeadMsg("TOO FULL! SCRIPT PAUSED", API.Player, 32)
        API.SysMsg("Weight capacity reached! Auto-paused for log/board management or tool crafting.", 32)
        if ALERT_SOUND > 0:
            API.PlaySound(ALERT_SOUND)


def trigger_tool_missing_pause() -> None:
    """Auto-pauses the script when an axe is missing or broken."""
    global is_paused, btn_pause
    if not is_paused:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused: No Axe!")
        API.HeadMsg("NO AXE! SCRIPT PAUSED", API.Player, 32)
        API.SysMsg("Axe missing or broken! Auto-paused so you can craft or equip a new axe.", 32)
        if ALERT_SOUND > 0:
            API.PlaySound(ALERT_SOUND)


def on_pause_clicked() -> None:
    """Callback triggered when the Pause/Resume button is clicked on the Gump."""
    global is_paused, btn_pause
    if is_paused:
        # Player is attempting to resume. Check if they are still overburdened.
        if is_overburdened():
            API.SysMsg("Still too full! Please store boards or lighten your pack before resuming.", 32)
            API.HeadMsg("STILL OVERWEIGHT!", API.Player, 32)
            return

        # Check if an axe is available before resuming
        if not get_equipped_axe() and not equip_axe():
            API.SysMsg("No axe equipped or found in backpack! Please equip an axe first.", 32)
            API.HeadMsg("NO AXE FOUND!", API.Player, 32)
            return

        is_paused = False
        if btn_pause:
            btn_pause.SetText("Pause")
        update_status("Resuming...")
        API.SysMsg("Auto lumberjack resumed.")
    else:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused")
        API.SysMsg("Auto lumberjack paused.")


def on_stop_clicked() -> None:
    """Callback triggered when the Stop button is clicked on the Gump."""
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


def create_control_gump():
    """Initializes and renders the interactive UOAlive Auto Lumberjack Gump."""
    global gump, lbl_status, lbl_trees, lbl_skill, lbl_stats, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 240, 150)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 240, 150)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("UOAlive Auto Lumberjack", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 30)
    gump.Add(lbl_status)

    # Trees harvested and boards counter
    lbl_trees = API.Gumps.CreateGumpLabel("Trees: 0 | Boards: 0", 996)
    lbl_trees.SetPos(10, 50)
    gump.Add(lbl_trees)

    # Skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Lumberjack: --", 996)
    lbl_skill.SetPos(10, 70)
    gump.Add(lbl_skill)

    # Stats and Weight label
    lbl_stats = API.Gumps.CreateGumpLabel("STR: -- | DEX: -- | Wt: --/--", 996)
    lbl_stats.SetPos(10, 90)
    gump.Add(lbl_stats)

    # Pause / Resume button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 70, 22)
    btn_pause.SetPos(15, 116)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 70, 22)
    btn_stop.SetPos(155, 116)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Handle gump right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely removes the Gump window from the screen."""
    global gump
    if gump and not gump.IsDisposed:
        gump.Dispose()


def check_ui_events() -> bool:
    """
    Processes Gump callbacks, updates stats, and handles pause states.
    Returns False if execution should stop, True to continue.
    """
    global is_paused, is_stopped
    API.ProcessCallbacks()
    update_stats()

    if is_stopped or API.StopRequested:
        return False

    # Check button clicks directly in case callbacks were queued
    if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
        on_stop_clicked()
        return False

    if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
        on_pause_clicked()

    # If paused, hold in a responsive loop while continuing to process UI events
    while is_paused and not API.StopRequested and not is_stopped:
        if API.Pathfinding():
            API.CancelPathfinding()
        API.Pause(0.2)
        API.ProcessCallbacks()
        update_stats()
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
    """Callback when script execution is stopped."""
    if API.Pathfinding():
        API.CancelPathfinding()
    dispose_gump()
    API.SysMsg("Auto lumberjack stopped.")

API.OnStop(on_stop)


def debug_msg(message: str) -> None:
    """Prints debug messages when DEBUG is enabled."""
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def get_equipped_axe():
    """Finds and returns the axe equipped in weapon layers."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item:
            # If graphic matches known axes or layer is occupied by weapon
            if getattr(item, "Graphic", None) in AXE_GRAPHICS:
                return item
            return item
    return None


def equip_axe():
    """
    Attempts to equip an axe by checking the dress profile first,
    then scanning the backpack for any axe graphic.
    """
    axe = get_equipped_axe()
    if axe:
        return axe

    if DRESS_PROFILE:
        API.Dress(DRESS_PROFILE)
        API.Pause(0.8)
        axe = get_equipped_axe()
        if axe:
            return axe

    for graphic in AXE_GRAPHICS:
        item = API.FindType(graphic, API.Backpack)
        if item:
            API.EquipItem(item)
            API.Pause(0.6)
            axe = get_equipped_axe()
            if axe:
                return axe

    return None


def get_all_backpack_items() -> List:
    """
    Safely retrieves all items inside the player's backpack using recursive=False,
    and manually traverses any sub-containers (pouches, bags, wooden boxes)
    to prevent TazUO Legion engine recursive search exceptions.
    """
    all_items = []
    to_scan = [API.Backpack]
    visited = set()

    while to_scan:
        container_id = to_scan.pop(0)
        if not container_id or container_id in visited:
            continue
        visited.add(container_id)

        # Standard TazUO call using non-recursive retrieval
        items = API.ItemsInContainer(container_id, recursive=False)
        if items is None:
            items = API.ItemsInContainer(container_id)
        if items:
            for item in items:
                all_items.append(item)
                # Check if item is a sub-container
                graphic = getattr(item, "Graphic", 0)
                if getattr(item, "IsContainer", False) or graphic in [
                    0x0E75, 0x0E76, 0x0E79, 0x0E7D, 0x0E7E, 0x0E80, 0x09B0, 0x0E40, 0x0E41, 0x0E42, 0x0E43
                ]:
                    sub_serial = getattr(item, "Serial", None)
                    if sub_serial and sub_serial not in visited:
                        to_scan.append(sub_serial)

    return all_items


def get_backpack_board_count() -> int:
    """Counts total boards currently inside the player's backpack."""
    total = 0
    items = get_all_backpack_items()
    for item in items:
        graphic = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()
        if graphic in BOARD_GRAPHICS or ("board" in name and "scoreboard" not in name and "chessboard" not in name):
            total += getattr(item, "Amount", 1) or 1
    return total


def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Calculates tile distance between two coordinates."""
    return max(abs(x1 - x2), abs(y1 - y2))


def is_overburdened() -> bool:
    """Checks if the player's weight has reached the safe threshold."""
    if not MAX_WEIGHT_CHECK:
        return False
    weight = API.Player.Weight
    weight_max = API.Player.WeightMax
    if weight is not None and weight_max is not None and weight_max > 0:
        return weight >= (weight_max - WEIGHT_BUFFER)
    return False


def get_backpack_logs() -> List[int]:
    """
    Finds all log item serials inside the player's backpack.
    Uses multi-strategy detection:
    1. Multi-level container item inspection (non-recursive traversal).
    2. API.FindType and API.FindTypeAll across all known log graphics.
    3. Tooltip / OPL inspection fallback for special wood varieties.
    """
    log_serials: List[int] = []

    # Strategy 1: Iterate all items from safe container scan
    items = get_all_backpack_items()
    for item in items:
        graphic = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()

        # Check graphic match
        is_log = graphic in LOG_GRAPHICS

        # Check item name match
        if not is_log and name:
            if "log" in name and "board" not in name and "saw" not in name and "scroll" not in name and "tome" not in name:
                is_log = True

        # Check tooltip text match if name was empty/generic
        if not is_log:
            try:
                props = str(item.NameAndProps() if hasattr(item, "NameAndProps") else API.ItemNameAndProps(item) or "").lower()
                if "log" in props and "board" not in props and "saw" not in props:
                    is_log = True
            except Exception:
                pass

        if is_log:
            serial = getattr(item, "Serial", None)
            if serial and serial not in log_serials:
                log_serials.append(serial)

    # Strategy 2: Directly query API.FindType and API.FindTypeAll across all log graphics
    for g in LOG_GRAPHICS:
        try:
            found_item = API.FindType(g, API.Backpack)
            if found_item:
                s = getattr(found_item, "Serial", found_item)
                if s and s not in log_serials:
                    log_serials.append(s)
            found_all = API.FindTypeAll(g, API.Backpack)
            if found_all:
                for fit in found_all:
                    s = getattr(fit, "Serial", fit)
                    if s and s not in log_serials:
                        log_serials.append(s)
        except Exception:
            pass

    return log_serials


def convert_logs_to_boards(axe=None) -> int:
    """
    Finds all logs in the player's backpack and converts them into boards
    by targeting each log stack with the equipped axe.
    Halves weight and returns the number of log stacks converted.
    """
    if API.StopRequested or is_stopped:
        return 0

    log_serials = get_backpack_logs()
    if not log_serials:
        return 0

    axe_item = get_equipped_axe() or equip_axe()
    if not axe_item:
        debug_msg("Cannot convert logs: No axe equipped or found.")
        return 0

    axe_serial = getattr(axe_item, "Serial", axe_item)

    # Cancel any leftover or dangling target cursor and pause briefly to clear action cooldown
    API.CancelTarget()
    API.Pause(0.6)

    update_status("Cutting logs into boards...")
    API.SysMsg(f"Cutting {len(log_serials)} log stack(s) into boards...")

    converted_count = 0
    for serial in log_serials:
        if API.StopRequested or is_stopped:
            break

        item = API.FindItem(serial)
        if not item:
            continue

        # Re-verify axe is still available
        if not API.FindItem(axe_serial):
            axe_item = equip_axe()
            if not axe_item:
                break
            axe_serial = getattr(axe_item, "Serial", axe_item)

        # Retry up to 3 times for each log stack in case of server action latency
        success = False
        for attempt in range(3):
            if API.StopRequested or is_stopped:
                break

            API.CancelTarget()
            API.ClearJournal()
            API.UseObject(axe_serial)

            if API.WaitForTarget(timeout=2.5):
                API.Target(serial)
                API.Pause(0.15)
                if API.HasTarget():
                    try:
                        if hasattr(item, "Target"):
                            item.Target()
                    except Exception:
                        pass
                API.Pause(0.5)
                success = True
                converted_count += 1
                update_stats()
                break
            else:
                API.Pause(0.5)

        if not success:
            debug_msg(f"Failed to convert log stack {serial} after 3 attempts.")

    if converted_count > 0:
        API.SysMsg(f"Converted logs into boards ({converted_count} stack(s) cut).")

    update_stats()
    return converted_count


def find_nearby_trees(history: Set[Tuple[int, int]]):
    """
    Scans the area around the player for tree statics, excluding recently visited ones.
    Selects the tree trunk (static with Z closest to player's ground level)
    and ignores high-altitude foliage/canopy statics.
    """
    px = API.Player.X
    py = API.Player.Y
    pz = API.Player.Z or 0
    statics = API.GetStaticsInArea(
        px - SEARCH_RADIUS,
        py - SEARCH_RADIUS,
        px + SEARCH_RADIUS,
        py + SEARCH_RADIUS
    )

    if not statics:
        return []

    candidates = {}
    for s in statics:
        if not getattr(s, "IsTree", False):
            continue
        coord = (int(s.X), int(s.Y))
        if coord in history:
            continue

        sz = int(getattr(s, "Z", 0))
        # Strictly ignore tree statics (e.g. leaves/canopy) elevated above ground level
        if abs(sz - int(pz)) > 8:
            continue

        # If multiple tree statics exist at (X, Y), select the trunk closest to player Z
        if coord in candidates:
            existing = candidates[coord]
            if abs(sz - int(pz)) < abs(int(getattr(existing, "Z", 0)) - int(pz)):
                candidates[coord] = s
        else:
            candidates[coord] = s

    tree_list = list(candidates.values())
    tree_list.sort(key=lambda t: chebyshev_distance(px, py, int(t.X), int(t.Y)))
    return tree_list


def navigate_to_tree(tree) -> bool:
    """
    Navigates the player to within chopping reach (distance <= 2) of the target tree.
    Returns True if successfully in reach, False otherwise.
    """
    tx = int(tree.X)
    ty = int(tree.Y)

    # Already adjacent / in reach
    if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
        return True

    update_status(f"Moving to ({tx}, {ty})")
    API.Pathfind(tx, ty, distance=1, run=True)

    elapsed = 0.0
    while API.Pathfinding() and not API.StopRequested:
        if not check_ui_events():
            API.CancelPathfinding()
            return False

        API.Pause(0.2)
        elapsed += 0.2

        # Check if we arrived in chopping reach early
        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
            API.CancelPathfinding()
            return True

        if elapsed >= PATHFIND_TIMEOUT:
            debug_msg(f"Pathfind to ({tx}, {ty}) timed out after {PATHFIND_TIMEOUT}s.")
            API.CancelPathfinding()
            return False

    return chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2


def chop_tree(axe, tree) -> None:
    """
    Repeatedly chops the specified tree until its wood is depleted, stopped,
    or weight limit triggers auto-pause.
    """
    tx = int(tree.X)
    ty = int(tree.Y)
    tz = int(tree.Z)
    tg = int(tree.Graphic)

    swing = 0
    consecutive_idle_swings = 0
    MAX_IDLE_SWINGS = 3
    MAX_TOTAL_SWINGS = 25

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return

        if swing >= MAX_TOTAL_SWINGS:
            debug_msg(f"Tree at ({tx}, {ty}) reached maximum swings limit ({MAX_TOTAL_SWINGS}).")
            break

        if consecutive_idle_swings >= MAX_IDLE_SWINGS:
            debug_msg(f"Tree at ({tx}, {ty}) not yielding wood after {MAX_IDLE_SWINGS} swings, skipping.")
            break

        # Ensure axe is still equipped
        if not API.FindItem(axe.Serial):
            axe = equip_axe()
            if not axe:
                trigger_tool_missing_pause()
                if not check_ui_events():
                    return
                axe = equip_axe()
                if not axe:
                    return

        # Check weight before swinging
        if is_overburdened():
            # First attempt converting any loose logs to boards to halve weight
            convert_logs_to_boards(axe)
            if is_overburdened():
                trigger_overweight_pause()
                if not check_ui_events():
                    return

        # Ensure we haven't drifted out of reach
        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) > 2:
            debug_msg("Player moved out of tree chopping reach.")
            break

        swing += 1
        update_status(f"Chopping ({tx}, {ty}) #{swing}")
        API.ClearJournal()

        API.UseObject(axe)

        if API.WaitForTarget(timeout=2.5):
            dx = tx - API.Player.X
            dy = ty - API.Player.Y
            target_accepted = False

            # Primary: Target static coordinate with graphic
            API.Target(tx, ty, tz, tg)
            API.Pause(0.15)
            if not API.HasTarget():
                target_accepted = True
            else:
                # Fallback 1: TargetTileRel
                API.TargetTileRel(dx, dy, tg)
                API.Pause(0.15)
                if not API.HasTarget():
                    target_accepted = True
                else:
                    # Fallback 2: TargetRel
                    API.TargetRel(dx, dy, tilesOnly=True)
                    API.Pause(0.15)
                    if not API.HasTarget():
                        target_accepted = True

            if not target_accepted and API.HasTarget():
                debug_msg(f"Target at ({tx}, {ty}) not accepted by client/server.")
                API.CancelTarget()
                consecutive_idle_swings += 1
                if consecutive_idle_swings >= MAX_IDLE_SWINGS:
                    break
                continue

            API.Pause(SWING_DELAY)
            update_stats()
        else:
            debug_msg(f"Swing #{swing}: Target cursor timed out.")
            consecutive_idle_swings += 1
            continue

        # Check depletion journal messages
        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        # Check if we produced wood or got an expected swing message
        got_wood = any(
            kw in t
            for kw in ["logs", "wood", "hack", "produce", "fell"]
            for t in recent_text
        )
        if got_wood:
            consecutive_idle_swings = 0
        else:
            consecutive_idle_swings += 1

        depleted = False
        for kw in DEPLETED_KEYWORDS:
            if any(kw in t for t in recent_text) or API.InJournal(kw):
                API.SysMsg(f"Tree finished: '{kw}'")
                depleted = True
                break

        if depleted:
            break

    # Cancel any dangling target cursor and wait for swing action cooldown to settle
    API.CancelTarget()
    API.Pause(0.6)

    # Once tree is depleted or chopping ended, convert logs to boards
    convert_logs_to_boards(axe)


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    if DRESS_PROFILE:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE}'...")
        API.Dress(DRESS_PROFILE)
        API.Pause(1.0)

    axe = equip_axe()
    if not axe:
        API.SysMsg("No axe found in hands or backpack! Equip an axe to start.", 32)
        return

    # Render on-screen control Gump
    create_control_gump()
    update_stats()

    # FIFO history queue to prevent repeating the last 50 trees
    visited_queue: deque[Tuple[int, int]] = deque(maxlen=TREE_HISTORY_LIMIT)
    visited_set: Set[Tuple[int, int]] = set()

    update_status("Started")
    API.SysMsg(f"Auto lumberjack started (Radius: {SEARCH_RADIUS}, History: {TREE_HISTORY_LIMIT}).")

    # Initial conversion of any loose logs already in backpack
    convert_logs_to_boards(axe)

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Verify axe
        axe = equip_axe()
        if not axe:
            trigger_tool_missing_pause()
            if not check_ui_events():
                break
            axe = equip_axe()
            if not axe:
                break

        # Check weight before locating next tree
        if is_overburdened():
            convert_logs_to_boards(axe)
            if is_overburdened():
                trigger_overweight_pause()
                if not check_ui_events():
                    break

        # Find available trees excluding recently visited
        update_status("Searching for trees...")
        candidates = find_nearby_trees(visited_set)
        if not candidates:
            update_status("No more trees")
            API.SysMsg(f"No more harvestable trees found within {SEARCH_RADIUS} tiles. Done.")
            break

        target_tree = None
        for candidate in candidates:
            if not check_ui_events():
                break

            if navigate_to_tree(candidate):
                target_tree = candidate
                break
            else:
                # Tree is unreachable, mark in history so we skip it
                coord = (int(candidate.X), int(candidate.Y))
                visited_queue.append(coord)
                visited_set = set(visited_queue)
                debug_msg(f"Tree at {coord} unreachable, skipping.")

        if not target_tree:
            update_status("No reachable trees")
            API.SysMsg("Could not pathfind to any nearby trees within reach. Done.")
            break

        # Chop the reached tree
        chop_tree(axe, target_tree)

        # Increment tree count on Gump and record in history queue
        increment_trees_harvested()
        tree_coord = (int(target_tree.X), int(target_tree.Y))
        visited_queue.append(tree_coord)
        visited_set = set(visited_queue)
        debug_msg(f"Recorded tree {tree_coord} in history (Total tracked: {len(visited_queue)}/{TREE_HISTORY_LIMIT}).")

        # Convert any leftover logs to boards
        convert_logs_to_boards(axe)

        API.Pause(0.5)

    update_status("Finished")
    API.SysMsg("Auto lumberjack finished.")
    dispose_gump()


main()
