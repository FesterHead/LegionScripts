"""
ChopTreeAuto.py - Automated Roaming Lumberjacking Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Automates lumberjacking across an area with an interactive control Gump:
    - Scans for nearby tree statics using TazUO's native static detection.
    - Selects the nearest unvisited tree within SEARCH_RADIUS.
    - Pathfinds adjacent to the tree (within chopping reach).
    - Repeatedly swings the equipped axe until the tree is depleted.
    - Remembers the last 30 visited trees to prevent revisiting recently chopped trees.
    - Displays an on-screen status Gump with Pause/Resume and Stop controls.
    - Monitors player weight and stops when full.

Usage:
    1. Equip an axe in either the OneHanded or TwoHanded layer.
    2. Ensure you are in an area with trees.
    3. Start the script in TazUO.
    4. Use the on-screen Gump to monitor progress, Pause/Resume, or Stop.
"""

from collections import deque
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Enable verbose logging in the client console/journal
DEBUG: bool = False

# Delay in seconds between swings.
# FesterUO allows fast chopping (1.0s). Set to 4.5 or 5.0 for standard UO shards.
SWING_DELAY: float = 1.0

# Dress configuration profile to load at startup (set to None or "" to disable)
DRESS_PROFILE: str = "Lumberjack"

# Search radius in tiles around the player to locate trees
SEARCH_RADIUS: int = 25

# Maximum number of recent trees to remember and avoid revisiting
TREE_HISTORY_LIMIT: int = 30

# Stop script if backpack weight is near capacity
MAX_WEIGHT_CHECK: bool = True
WEIGHT_BUFFER: int = 15  # Stop when Weight >= WeightMax - WEIGHT_BUFFER

# Maximum seconds allowed to pathfind to a tree before skipping it
PATHFIND_TIMEOUT: float = 12.0

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

last_skill: float | None = None
last_str: int | None = None
last_dex: int | None = None


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
        lbl_trees.Text = f"Trees Harvested: {trees_harvested_count}"


def update_stats() -> None:
    """Updates Lumberjacking skill, Strength, and Dexterity on the Gump and announces increases."""
    global last_skill, last_str, last_dex, lbl_skill, lbl_stats

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

    # Update STR and DEX
    cur_str = API.Player.Strength
    cur_dex = API.Player.Dexterity
    if lbl_stats and cur_str is not None and cur_dex is not None:
        lbl_stats.Text = f"STR: {cur_str} | DEX: {cur_dex}"
        if last_str is not None and cur_str > last_str:
            API.SysMsg(f"Strength increased to {cur_str}!")
        if last_dex is not None and cur_dex > last_dex:
            API.SysMsg(f"Dexterity increased to {cur_dex}!")
        last_str = cur_str
        last_dex = cur_dex


def on_pause_clicked() -> None:
    """Callback triggered when the Pause/Resume button is clicked."""
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Auto lumberjack paused." if is_paused else "Auto lumberjack resumed.")


def on_stop_clicked() -> None:
    """Callback triggered when the Stop button is clicked."""
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
    """Initializes and renders the interactive FesterUO Auto Lumberjack Gump."""
    global gump, lbl_status, lbl_trees, lbl_skill, lbl_stats, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 240, 150)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 240, 150)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Auto Lumberjack", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 30)
    gump.Add(lbl_status)

    # Trees harvested counter
    lbl_trees = API.Gumps.CreateGumpLabel("Trees Harvested: 0", 996)
    lbl_trees.SetPos(10, 50)
    gump.Add(lbl_trees)

    # Skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Lumberjack: --", 996)
    lbl_skill.SetPos(10, 70)
    gump.Add(lbl_skill)

    # Stats label
    lbl_stats = API.Gumps.CreateGumpLabel("STR: -- | DEX: --", 996)
    lbl_stats.SetPos(10, 90)
    gump.Add(lbl_stats)

    # Pause button
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

    # Check button clicks directly in case callbacks were batched
    if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
        on_stop_clicked()
        return False

    if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
        on_pause_clicked()

    # If paused, hold in loop while continuing to process UI events
    while is_paused and not API.StopRequested and not is_stopped:
        API.Pause(0.2)
        API.ProcessCallbacks()
        update_stats()
        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            on_pause_clicked()
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
            return item
    return None


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


def find_nearby_trees(history: set):
    """
    Scans the area around the player for tree statics, excluding recently visited ones.
    Returns a list of candidate static objects sorted by distance to the player.
    """
    px = API.Player.X
    py = API.Player.Y
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
        # Avoid duplicate tree static parts at same coordinate
        if coord not in candidates:
            candidates[coord] = s

    tree_list = list(candidates.values())
    tree_list.sort(key=lambda t: chebyshev_distance(px, py, int(t.X), int(t.Y)))
    return tree_list


def navigate_to_tree(tree) -> bool:
    """
    Navigates the player to within chopping reach (distance <= 2) of the tree.
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
    """Chops the specified tree until wood is depleted, stopped, or weight is exceeded."""
    tx = int(tree.X)
    ty = int(tree.Y)
    tz = int(tree.Z)
    tg = int(tree.Graphic)

    swing = 0

    while not API.StopRequested:
        if not check_ui_events():
            return

        if is_overburdened():
            update_status("Weight limit reached")
            API.SysMsg("Weight limit reached! Stopping lumberjack.")
            return

        # Ensure we haven't drifted out of range
        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) > 2:
            debug_msg("Player moved out of reach.")
            break

        swing += 1
        update_status(f"Chopping ({tx}, {ty}) #{swing}")
        API.ClearJournal()

        API.UseObject(axe)

        if API.WaitForTarget(timeout=5):
            API.Target(tx, ty, tz, tg)
            API.Pause(SWING_DELAY)
            update_stats()
        else:
            debug_msg(f"Swing #{swing}: Target cursor timed out.")
            break

        # Check depletion journal messages
        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        depleted = False
        for kw in DEPLETED_KEYWORDS:
            if any(kw in t for kw in recent_text) or API.InJournal(kw):
                API.SysMsg(f"Tree finished: '{kw}'")
                depleted = True
                break

        if depleted:
            break


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    if DRESS_PROFILE:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE}'...")
        API.Dress(DRESS_PROFILE)
        API.Pause(1.0)

    axe = get_equipped_axe()
    if not axe:
        API.SysMsg("No axe found in hands! Equip an axe to start.")
        return

    # Render on-screen control Gump
    create_control_gump()
    update_stats()

    visited_queue = deque(maxlen=TREE_HISTORY_LIMIT)
    visited_set = set()

    update_status("Started")
    API.SysMsg(f"Auto lumberjack started (Radius: {SEARCH_RADIUS}, History: {TREE_HISTORY_LIMIT}).")

    while not API.StopRequested:
        if not check_ui_events():
            break

        # Check weight before searching for the next tree
        if is_overburdened():
            update_status("Weight limit reached")
            API.SysMsg("Weight limit reached! Stopping lumberjack.")
            break

        # Re-verify equipped axe
        axe = get_equipped_axe()
        if not axe:
            update_status("No axe equipped")
            API.SysMsg("Axe missing or broken! Stopping.")
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
                # Tree is unreachable, mark as visited so we don't try it again immediately
                coord = (int(candidate.X), int(candidate.Y))
                visited_queue.append(coord)
                visited_set = set(visited_queue)
                debug_msg(f"Tree at {coord} unreachable, skipping.")

        if not target_tree:
            update_status("No reachable trees")
            API.SysMsg("Could not pathfind to any nearby trees. Done.")
            break

        # Chop the reached tree
        chop_tree(axe, target_tree)

        # Increment tree count on Gump and record in history
        increment_trees_harvested()
        tree_coord = (int(target_tree.X), int(target_tree.Y))
        visited_queue.append(tree_coord)
        visited_set = set(visited_queue)
        debug_msg(f"Recorded tree {tree_coord} in history (Total tracked: {len(visited_queue)}).")

        API.Pause(0.5)

    update_status("Finished")
    API.SysMsg("Auto lumberjack finished.")
    dispose_gump()


main()
