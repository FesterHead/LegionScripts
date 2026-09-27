"""
TrainCarpentry.py - Automated Resource-Efficient Carpentry Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Fully automated Carpentry skill training script for TazUO featuring:
    - Optimal resource-efficient progression ladder from 0.0 to 120.0 Carpentry:
        * 0.0 - 45.0:   Wooden Box (5 boards)
        * 45.0 - 68.0:  Ballot Box Deed (5 boards)
        * 68.0 - 75.0:  Wooden Shield (9 boards)
        * 75.0 - 80.0:  Quarter Staff (6 boards)
        * 80.0 - 120.0: Gnarled Staff (7 boards)
    - Milestone Announcements & "Set Recipe" Manual Override:
        * Proactively notifies the player when reaching a skill threshold to recommend the next item.
        * Includes an interactive "Set Recipe" button allowing players to manually prime any craft recipe.
    - Automated Crafted Item Disposal:
        * Auto-detects nearby Trash Barrels or allows targeting a trash barrel on startup.
        * Automatically deposits newly crafted items into the trash barrel via backpack serial diff,
          preventing overweight and backpack clutter.
        * Includes a "Trash Can" button on the Gump to change/set trash barrels at any time.
    - Resource Satchel Integration:
        * Prompts player on startup to target a Wood / Resource Satchel (or secure container).
        * Maintains a lightweight buffer of boards (default 20-60) in the main backpack.
        * Automatically restocks from the satchel when supplies run low, and deposits excess wood back.
        * Protects colored/special woods (Frostwood, Heartwood, Bloodwood) by default.
    - Tool Upkeep:
        * Works with any carpentry tool (Saw, Dovetail Saw, Plane, Scorp, Draw Knife, Hammer).
        * If tools break and Tinkering tools + iron ingots are available, attempts to auto-craft replacement Saws.
    - Interactive Control Gump:
        * Real-time training status, live Carpentry skill level and cap with gain tracking,
          Crafted / Trashed / Failed counters, Satchel & Backpack wood counters, and tool/trash indicators.
        * Pause / Resume, Set Recipe, Satchel, Trash Can, and Stop buttons.
"""

from typing import List, Tuple, Optional, Set
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Backpack wood buffer limits (prevents overweight while training)
MIN_BACKPACK_BOARDS = 20
TARGET_BACKPACK_BOARDS = 60
RESTOCK_BATCH_SIZE = 50

# Delays in seconds
CRAFT_DELAY = 1.3
TOOL_CRAFT_DELAY = 1.2

# Server Craft Gump button IDs (standard ServUO / RunUO)
GUMP_BTN_MAKE_LAST = 21  # Universal "Make Last" button

# Tool upkeep via Tinkering
AUTO_CRAFT_SAW = True
MAX_TOOL_CRAFT_ATTEMPTS = 5

# Enable verbose debug messages in client console
DEBUG = False


# ==============================================================================
# Item & Graphic Definitions
# ==============================================================================

# Wood graphics (boards & logs)
BOARD_GRAPHIC = 0x1BD7
LOG_GRAPHIC = 0x1BDD
WOOD_GRAPHICS = {BOARD_GRAPHIC, LOG_GRAPHIC}
REGULAR_WOOD_HUE = 0  # Regular plain wood

# Carpentry tools
CARPENTER_TOOL_GRAPHICS = {
    0x1034, 0x1035,  # Saw
    0x1028, 0x1029,  # Dovetail Saw
    0x102C, 0x102D,  # Moulding Plane
    0x1032, 0x1033,  # Smoothing Plane
    0x102E, 0x102F,  # Jointing Plane
    0x10E4, 0x10E5,  # Froe / Draw Knife
    0x10E7, 0x10E8,  # Scorp
    0x102A, 0x102B,  # Hammer
}

# Tinkering tools & materials for auto-crafting saws
TINKER_TOOL_GRAPHICS = {0x1EB8, 0x1EB9, 0x1EBC, 0x1EBD}
INGOT_GRAPHIC = 0x1BF2
IRON_INGOT_HUE = 0

# Trash barrel graphics
TRASH_BARREL_GRAPHICS = {0x0E77}

# Optimal Carpentry Progression Ladder: (min_skill, max_skill, item_name, board_cost)
PROGRESSION_LADDER: List[Tuple[float, float, str, int]] = [
    (0.0, 45.0, "Wooden Box", 5),
    (45.0, 68.0, "Ballot Box Deed", 5),
    (68.0, 75.0, "Wooden Shield", 9),
    (75.0, 80.0, "Quarter Staff", 6),
    (80.0, 120.0, "Gnarled Staff", 7),
]


# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_recipe = None
lbl_counts = None
lbl_wood = None
lbl_tools = None
btn_pause = None
btn_recipe = None
btn_satchel = None
btn_trash = None
btn_stop = None

satchel_serial: Optional[int] = None
trash_barrel_serial: Optional[int] = None
active_tool_serial: Optional[int] = None

is_paused: bool = False
is_stopped: bool = False

total_crafted: int = 0
total_trashed: int = 0
total_failed: int = 0
tools_crafted: int = 0

last_carpentry_skill: Optional[float] = None
current_recipe_name: str = "Make Last"
recommended_recipe_name: str = "Wooden Box"


# ==============================================================================
# UI & Gump Management
# ==============================================================================

def update_status(text: str) -> None:
    """Updates the Gump status label."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def update_stats() -> None:
    """Refreshes all Gump statistic labels."""
    global last_carpentry_skill, recommended_recipe_name
    global lbl_skill, lbl_recipe, lbl_counts, lbl_wood, lbl_tools

    # 1. Carpentry Skill
    c_skill = API.GetSkill("Carpentry")
    if c_skill:
        val = float(c_skill.Value)
        cap = float(c_skill.Cap)
        if lbl_skill:
            lbl_skill.Text = f"Carpentry: {val:.1f} / {cap:.1f}"

        if last_carpentry_skill is not None and val > last_carpentry_skill:
            gain = val - last_carpentry_skill
            API.SysMsg(f"[Carpentry] Skill gained +{gain:.1f}! New skill: {val:.1f}")

            # Check for progression milestone
            old_rec, _ = get_recommended_item(last_carpentry_skill)
            new_rec, cost = get_recommended_item(val)
            if new_rec != old_rec:
                API.SysMsg(f"[Carpentry] *** Milestone reached ({val:.1f})! ***")
                API.SysMsg(f"[Carpentry] Recommended next item: '{new_rec}' ({cost} boards).")
                API.SysMsg(f"[Carpentry] Click 'Set Recipe' on the Gump to switch to '{new_rec}', or continue current recipe.")
                recommended_recipe_name = new_rec
                if lbl_recipe:
                    lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {new_rec})"

        last_carpentry_skill = val

    # 2. Recipe
    if lbl_recipe:
        if current_recipe_name != recommended_recipe_name:
            lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {recommended_recipe_name})"
        else:
            lbl_recipe.Text = f"Recipe: {current_recipe_name}"

    # 3. Counts
    if lbl_counts:
        lbl_counts.Text = f"Crafted: {total_crafted} | Trashed: {total_trashed} | Failed: {total_failed}"

    # 4. Wood Counts
    bp_wood = count_backpack_wood()
    satchel_wood = count_satchel_wood() if satchel_serial else 0
    satchel_label = f"{satchel_wood}" if satchel_serial else "N/A"
    if lbl_wood:
        lbl_wood.Text = f"Satchel: {satchel_label} | Backpack: {bp_wood}"

    # 5. Tool & Trash Status
    tool_cnt = count_carpenter_tools()
    tool_str = f"Tools: {tool_cnt}"
    trash_str = f"Trash: {'Set' if trash_barrel_serial else 'None'}"
    if lbl_tools:
        lbl_tools.Text = f"{tool_str} | {trash_str}"


def on_pause_clicked() -> None:
    """Toggles pause/resume state."""
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Running")
    API.SysMsg("[Carpentry] Script paused." if is_paused else "[Carpentry] Script resumed.")


def on_stop_clicked() -> None:
    """Stops the script execution."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_satchel_clicked() -> None:
    """Allows player to target their wood/resource satchel or container."""
    global satchel_serial
    API.SysMsg("[Carpentry] Target your Resource Satchel / Wood Container (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial:
        satchel_serial = new_serial
        API.SysMsg(f"[Carpentry] Satchel updated: 0x{satchel_serial:X}")
        update_stats()
        if count_backpack_wood() < MIN_BACKPACK_BOARDS:
            restock_wood_from_satchel()
    else:
        API.SysMsg("[Carpentry] Satchel targeting cancelled.")
    update_stats()


def on_trash_clicked() -> None:
    """Allows player to target a trash barrel / container."""
    global trash_barrel_serial
    API.SysMsg("[Carpentry] Target your Trash Barrel (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial:
        trash_barrel_serial = new_serial
        API.SysMsg(f"[Carpentry] Trash barrel updated: 0x{trash_barrel_serial:X}")
    else:
        API.SysMsg("[Carpentry] Trash barrel targeting cancelled.")
    update_stats()


def on_recipe_clicked() -> None:
    """Opens the Carpentry craft gump to allow manually selecting an item recipe."""
    global is_paused, btn_pause
    tool = get_carpenter_tool()
    if tool:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused (Set Recipe)")
        API.SysMsg("[Carpentry] Opening craft menu. Click your desired item once to craft it, then click 'Resume' on the Gump.")
        API.UseObject(tool)
    else:
        API.SysMsg("[Carpentry] No carpentry tool available to open craft menu!")


def on_gump_disposed() -> None:
    global is_stopped
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


def create_control_gump() -> None:
    """Renders the FesterUO Carpentry Trainer Gump."""
    global gump, lbl_status, lbl_skill, lbl_recipe, lbl_counts, lbl_wood, lbl_tools
    global btn_pause, btn_recipe, btn_satchel, btn_trash, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 310, 220)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 310, 220)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Train Carpentry", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skill
    lbl_skill = API.Gumps.CreateGumpLabel("Carpentry: -- / --", 996)
    lbl_skill.SetPos(10, 48)
    gump.Add(lbl_skill)

    # Recipe
    lbl_recipe = API.Gumps.CreateGumpLabel("Recipe: Initializing...", 53)
    lbl_recipe.SetPos(10, 68)
    gump.Add(lbl_recipe)

    # Counts
    lbl_counts = API.Gumps.CreateGumpLabel("Crafted: 0 | Trashed: 0 | Failed: 0", 996)
    lbl_counts.SetPos(10, 88)
    gump.Add(lbl_counts)

    # Wood counts
    lbl_wood = API.Gumps.CreateGumpLabel("Satchel: 0 | Backpack: 0", 996)
    lbl_wood.SetPos(10, 108)
    gump.Add(lbl_wood)

    # Tools & Trash
    lbl_tools = API.Gumps.CreateGumpLabel("Tools: -- | Trash: --", 996)
    lbl_tools.SetPos(10, 128)
    gump.Add(lbl_tools)

    # Buttons Row 1: Pause, Set Recipe, Satchel
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 80, 22)
    btn_pause.SetPos(15, 155)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_recipe = API.Gumps.CreateSimpleButton("Set Recipe", 85, 22)
    btn_recipe.SetPos(105, 155)
    API.Gumps.AddControlOnClick(btn_recipe, on_recipe_clicked)
    gump.Add(btn_recipe)

    btn_satchel = API.Gumps.CreateSimpleButton("Satchel", 85, 22)
    btn_satchel.SetPos(200, 155)
    API.Gumps.AddControlOnClick(btn_satchel, on_satchel_clicked)
    gump.Add(btn_satchel)

    # Buttons Row 2: Trash Can, Stop
    btn_trash = API.Gumps.CreateSimpleButton("Trash Can", 130, 22)
    btn_trash.SetPos(15, 184)
    API.Gumps.AddControlOnClick(btn_trash, on_trash_clicked)
    gump.Add(btn_trash)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 135, 22)
    btn_stop.SetPos(155, 184)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)
    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    global gump
    if gump and not getattr(gump, "IsDisposed", False):
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes UI clicks, stats updates, and handles pause loops."""
    global is_paused, is_stopped
    API.ProcessCallbacks()
    update_stats()

    if is_stopped or API.StopRequested:
        return False

    if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
        on_stop_clicked()
        return False

    if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
        on_pause_clicked()

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


def wait_with_ui(seconds: float) -> bool:
    elapsed = 0.0
    step = 0.1
    while elapsed < seconds:
        if not check_ui_events():
            return False
        API.Pause(step)
        elapsed += step
    return check_ui_events()


# ==============================================================================
# Helper Functions - Tools, Materials & Detection
# ==============================================================================

def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def is_overburdened() -> bool:
    """Returns True if player is near maximum weight capacity."""
    weight = API.Player.Weight
    weight_max = API.Player.WeightMax
    if weight is not None and weight_max is not None and weight_max > 0:
        return weight >= (weight_max - 15)
    return False


def is_regular_wood(item) -> bool:
    """Checks if an item is regular plain boards or logs (Hue 0), protecting special woods."""
    if not item:
        return False
    if item.Graphic not in WOOD_GRAPHICS:
        return False
    hue = getattr(item, "Hue", 0) or 0
    return hue == REGULAR_WOOD_HUE


def get_carpenter_tool():
    """Finds a usable carpentry tool in player hands or backpack."""
    # Check hands
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in CARPENTER_TOOL_GRAPHICS:
            return item

    # Check backpack
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Graphic in CARPENTER_TOOL_GRAPHICS:
                return item
    return None


def count_carpenter_tools() -> int:
    """Counts usable carpentry tools."""
    cnt = 0
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in CARPENTER_TOOL_GRAPHICS:
            cnt += 1
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Graphic in CARPENTER_TOOL_GRAPHICS:
                cnt += 1
    return cnt


def get_tinker_tool():
    """Finds a Tinker's Tool in player hands or backpack."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in TINKER_TOOL_GRAPHICS:
            return item
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Graphic in TINKER_TOOL_GRAPHICS:
                return item
    return None


def count_backpack_wood() -> int:
    """Counts regular boards/logs currently in the main backpack."""
    total = 0
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Serial != satchel_serial and is_regular_wood(item):
                total += getattr(item, "Amount", 1) or 1
    return total


def count_backpack_ingots() -> int:
    """Counts regular iron ingots in backpack (for tool crafting)."""
    total = 0
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Serial != satchel_serial and item.Graphic == INGOT_GRAPHIC:
                hue = getattr(item, "Hue", 0) or 0
                if hue == IRON_INGOT_HUE:
                    total += getattr(item, "Amount", 1) or 1
    return total


def count_satchel_wood() -> int:
    """Counts regular boards/logs inside the designated resource satchel."""
    if not satchel_serial:
        return 0
    total = 0
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if items:
        for item in items:
            if is_regular_wood(item):
                total += getattr(item, "Amount", 1) or 1
    return total


def get_satchel_wood():
    """Finds the largest stack of regular boards/logs inside the satchel."""
    if not satchel_serial:
        return None
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if not items:
        return None
    best_item = None
    best_amt = 0
    for item in items:
        if is_regular_wood(item):
            amt = getattr(item, "Amount", 1) or 1
            if amt > best_amt:
                best_amt = amt
                best_item = item
    return best_item


def restock_wood_from_satchel() -> bool:
    """Pulls a batch of boards from the satchel into the main backpack."""
    if not satchel_serial:
        return False

    current_bp = count_backpack_wood()
    if current_bp >= MIN_BACKPACK_BOARDS:
        return True

    satchel_wood_stack = get_satchel_wood()
    if not satchel_wood_stack:
        return False

    amt_available = getattr(satchel_wood_stack, "Amount", 1) or 1
    amt_needed = max(RESTOCK_BATCH_SIZE, TARGET_BACKPACK_BOARDS - current_bp)
    amt_to_move = min(amt_available, amt_needed)

    if amt_to_move <= 0:
        return False

    update_status(f"Restocking {amt_to_move} boards...")
    API.MoveItem(satchel_wood_stack.Serial, API.Backpack, amt=amt_to_move)
    API.Pause(0.6)
    update_stats()
    return count_backpack_wood() >= 5


def deposit_excess_wood_to_satchel() -> None:
    """Moves excess boards from backpack back into the satchel."""
    if not satchel_serial:
        return

    current_bp = count_backpack_wood()
    if current_bp <= TARGET_BACKPACK_BOARDS + 30:
        return

    excess = current_bp - TARGET_BACKPACK_BOARDS
    if excess <= 10:
        return

    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not items:
        return

    for item in items:
        if item.Serial != satchel_serial and is_regular_wood(item):
            amt = getattr(item, "Amount", 1) or 1
            amt_to_move = min(amt, excess)
            if amt_to_move > 0:
                API.MoveItem(item.Serial, satchel_serial, amt=amt_to_move)
                API.Pause(0.6)
                excess -= amt_to_move
                if excess <= 0:
                    break


def find_nearby_trash_barrel():
    """Finds a trash barrel within 3 tiles (searching ground items)."""
    ground_items = API.GetItemsOnGround(3)
    if ground_items:
        for item in ground_items:
            g = getattr(item, "Graphic", 0)
            name = str(getattr(item, "Name", "") or "").lower()
            if "trash" in name:
                return item
            if g in TRASH_BARREL_GRAPHICS:
                props = str(item.NameAndProps() if hasattr(item, "NameAndProps") else "").lower()
                if "trash" in props or "barrel" in props:
                    return item
    return None


def get_recommended_item(skill: float) -> Tuple[str, int]:
    """Returns the optimal item name and wood cost for the current skill level."""
    for min_sk, max_sk, name, cost in PROGRESSION_LADDER:
        if min_sk <= skill < max_sk:
            return name, cost
    return "Gnarled Staff", 7


def craft_saw_with_tinkering() -> bool:
    """Crafts a replacement saw using Tinkering tools and iron ingots."""
    global tools_crafted
    if not AUTO_CRAFT_SAW:
        return False

    tinker_tool = get_tinker_tool()
    if not tinker_tool:
        return False

    tinker_skill_obj = API.GetSkill("Tinkering")
    tinker_skill = float(tinker_skill_obj.Value) if tinker_skill_obj else 0.0
    if tinker_skill < 40.0:
        return False

    if count_backpack_ingots() < 4:
        return False

    update_status("Tinkering Saw...")
    API.SysMsg("[Carpentry] Crafting replacement Saw via Tinkering (4 ingots)...")

    count_before = count_carpenter_tools()

    for attempt in range(1, MAX_TOOL_CRAFT_ATTEMPTS + 1):
        if API.StopRequested or is_stopped:
            return False

        if not API.HasGump():
            API.UseObject(tinker_tool)
            if not API.WaitForGump(delay=2.5):
                return False

        if API.GumpContains("haven't made anything"):
            API.SysMsg("[Carpentry] Tinkering 'Make Last' is not set to Saw.")
            return False

        API.ClearJournal()
        API.ReplyGump(GUMP_BTN_MAKE_LAST)
        wait_with_ui(TOOL_CRAFT_DELAY)

        count_after = count_carpenter_tools()
        if count_after > count_before or get_carpenter_tool() is not None:
            tools_crafted += 1
            API.SysMsg("[Carpentry] Successfully crafted new Saw!")
            update_stats()
            if API.HasGump():
                API.ReplyGump(0)
                API.Pause(0.3)
            return True

    if API.HasGump():
        API.ReplyGump(0)
        API.Pause(0.3)

    return False


# ==============================================================================
# Crafting Cycle
# ==============================================================================

def craft_cycle() -> bool:
    """Executes a single craft attempt, restocks materials, and disposes crafted items."""
    global total_crafted, total_failed, total_trashed, current_recipe_name

    # 1. Check weight before crafting
    if is_overburdened():
        update_status("Overweight")
        API.SysMsg("[Carpentry] Weight limit reached! Please lighten your backpack.")
        return False

    # 2. Check and restock wood from satchel
    if count_backpack_wood() < MIN_BACKPACK_BOARDS:
        if not restock_wood_from_satchel():
            if count_backpack_wood() < 5:  # Minimum recipe cost
                update_status("Out of Wood")
                API.SysMsg("[Carpentry] Out of boards/wood in backpack and satchel!")
                return False

    # 3. Ensure carpentry tool is available
    tool = get_carpenter_tool()
    if not tool:
        if not craft_saw_with_tinkering():
            update_status("No Tool")
            API.SysMsg("[Carpentry] Out of carpentry tools! Please equip or carry a saw/plane.")
            return False
        tool = get_carpenter_tool()
        if not tool:
            return False

    # 4. Record pre-craft backpack state for serial diff detection
    bp_before = {item.Serial for item in (API.ItemsInContainer(API.Backpack, recursive=False) or [])}

    # 5. Open craft menu if needed
    if not API.HasGump():
        API.ClearJournal()
        API.UseObject(tool)
        if not API.WaitForGump(delay=2.5):
            debug_msg("Carpentry menu did not appear.")
            return True

    # 6. Click Make Last
    API.ClearJournal()
    API.ReplyGump(GUMP_BTN_MAKE_LAST)
    wait_with_ui(CRAFT_DELAY)

    # 7. Analyze result from journal
    entries = API.GetJournalEntries(CRAFT_DELAY + 0.8)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    # Check if Make Last is uninitialized
    if any("haven't made anything" in t or "have not made" in t for t in j_text) or API.GumpContains("haven't made anything"):
        c_skill_obj = API.GetSkill("Carpentry")
        current_skill = float(c_skill_obj.Value) if c_skill_obj else 0.0
        rec_name, _ = get_recommended_item(current_skill)
        API.SysMsg("[Carpentry] 'Make Last' is not set yet.")
        API.SysMsg(f"[Carpentry] In the open Carpentry menu: Click '{rec_name}' once to craft it, then click Resume on the Gump.")
        update_status(f"Prime '{rec_name}'")
        on_pause_clicked()
        return True

    # Check craft success or failure
    success = any("you create" in t or "put the" in t or "put it into" in t for t in j_text) or API.InJournal("you create")
    failed = any("you fail" in t or "failed" in t or "destroy" in t for t in j_text) or API.InJournal("you fail")

    # Detect newly crafted item via backpack serial diff
    bp_after = API.ItemsInContainer(API.Backpack, recursive=False) or []
    new_item = None
    for it in bp_after:
        if it.Serial not in bp_before:
            if it.Serial != satchel_serial and it.Serial != trash_barrel_serial:
                if it.Graphic not in WOOD_GRAPHICS and it.Graphic not in CARPENTER_TOOL_GRAPHICS:
                    new_item = it
                    break

    if new_item:
        success = True

    if success:
        total_crafted += 1
        update_status("Crafted")
        update_stats()

        # Handle trashing of crafted item
        if new_item and trash_barrel_serial:
            update_status(f"Trashing {new_item.Name or 'item'}...")
            API.MoveItem(new_item.Serial, trash_barrel_serial)
            API.Pause(0.4)
            total_trashed += 1
            update_stats()

    elif failed:
        total_failed += 1
        update_status("Failed attempt")
        update_stats()

    # Re-check wood and deposit excess if any
    deposit_excess_wood_to_satchel()

    return True


# ==============================================================================
# Main Orchestration Loop
# ==============================================================================

def main():
    global satchel_serial, trash_barrel_serial, current_recipe_name, recommended_recipe_name

    API.SysMsg("=== FesterUO Carpentry Trainer ===")

    # 1. Initial skill and recipe recommendation
    c_skill_obj = API.GetSkill("Carpentry")
    current_skill = float(c_skill_obj.Value) if c_skill_obj else 0.0
    recommended_recipe_name, cost = get_recommended_item(current_skill)
    current_recipe_name = recommended_recipe_name

    # 2. Trash Barrel Setup
    auto_barrel = find_nearby_trash_barrel()
    if auto_barrel:
        trash_barrel_serial = auto_barrel.Serial
        API.SysMsg(f"[Carpentry] Auto-detected nearby Trash Barrel: 0x{trash_barrel_serial:X}")
    else:
        API.SysMsg("[Carpentry] Target your Trash Barrel (or press ESC / target yourself to skip auto-trashing)...")
        t_serial = API.RequestTarget(timeout=6.0)
        if t_serial and t_serial != API.Player.Serial:
            trash_barrel_serial = t_serial
            API.SysMsg(f"[Carpentry] Trash barrel set: 0x{trash_barrel_serial:X}")
        else:
            trash_barrel_serial = None
            API.SysMsg("[Carpentry] No trash barrel selected. Crafted items will remain in your backpack.")

    # 3. Satchel Setup
    API.SysMsg("[Carpentry] Target your Wood / Resource Satchel (or press ESC / target yourself for backpack only)...")
    s_serial = API.RequestTarget(timeout=6.0)
    if s_serial and s_serial != API.Player.Serial:
        satchel_serial = s_serial
        API.SysMsg(f"[Carpentry] Satchel set: 0x{satchel_serial:X}")
    else:
        satchel_serial = None
        API.SysMsg("[Carpentry] Using backpack wood only.")

    # 4. Check initial tool
    tool = get_carpenter_tool()
    if not tool:
        API.SysMsg("[Carpentry] No carpentry tool found! Please equip or carry a saw, plane, or hammer.")
        update_status("No Tool")

    # 5. Render Gump & initial stats
    create_control_gump()
    update_stats()

    # Initial check and restock of wood
    if count_backpack_wood() < MIN_BACKPACK_BOARDS:
        restock_wood_from_satchel()

    update_status("Running")
    API.SysMsg(f"[Carpentry] Training started. Current skill: {current_skill:.1f} | Recommended: {recommended_recipe_name}")

    # 6. Main Training Loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        success = craft_cycle()
        if not success:
            break

        API.Pause(0.2)

    update_status("Finished")
    API.SysMsg("[Carpentry] Training finished.")
    dispose_gump()


main()
