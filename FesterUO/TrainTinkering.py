"""
TrainTinkering.py - Automated Resource-Efficient Tinkering Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Fully automated Tinkering skill training script for TazUO featuring:
    - Optimal resource-efficient progression ladder from 0.0 to 100.0 (GM) Tinkering:
        * 0.0 - 45.0:   Tinker's Tools (2 ingots)
            - At 40.0 Tinkering: Unlocks crafting Smith's Hammers!
            - At 45.0 Tinkering: Unlocks crafting Tongs!
        * 45.0 - 60.0:  Tongs (1 ingot)
        * 60.0 - 95.0:  Lockpick (1 ingot - stackable & lightweight)
        * 95.0 - 100.0: Heating Stand (4 ingots - rapid GM finish)
    - Milestone Announcements & "Set Recipe" Manual Override:
        * Proactively notifies the player when reaching a skill threshold to recommend the next item.
        * Announces Blacksmith tool unlocking milestones (Smith's Hammers at 40.0, Tongs at 45.0).
        * Includes an interactive "Set Recipe" button allowing players to manually prime any craft recipe.
    - Automated Crafted Item Disposal:
        * Auto-detects nearby Trash Barrels or allows targeting a trash barrel on startup.
        * Automatically deposits newly crafted items (Tongs, Heating Stands, excess tools) into
          the trash barrel via backpack serial diff, preventing overweight and backpack clutter.
        * Preserves working reserve of Tinker's Tools for perpetual crafting self-sustainability.
        * Stackable lockpicks are preserved in the backpack.
        * Includes a "Trash Can" button on the Gump to change/set trash barrels at any time.
    - Resource Satchel Integration:
        * Prompts player on startup to target an Ingot / Resource Satchel (or secure container).
        * Maintains a lightweight buffer of ingots (default 20-50) in the main backpack.
        * Automatically restocks from the satchel when supplies run low, and deposits excess ingots back.
        * Strict resource protection: Exclusively consumes plain iron ingots (Hue 0), protecting colored ingots.
    - Tool Self-Sustainability:
        * Detects low tool supply and prioritizes crafting replacement Tinker's Tools.
    - Interactive Control Gump:
        * Real-time training status, live Tinkering skill level and cap with gain tracking,
          Crafted / Trashed / Failed counters, Satchel & Backpack ingot counters, and tool/trash indicators.
        * Pause / Resume, Set Recipe, Satchel, Trash Can, and Stop buttons.
"""

from typing import List, Tuple, Optional, Set
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Target Tinkering skill to stop training (e.g. 50.0 for Blacksmith tools, 100.0 for GM)
TARGET_SKILL = 100.0

# Direct Satchel Crafting (crafts directly from resource satchel without pulling to backpack)
DIRECT_SATCHEL_CRAFTING = True

# Fallback limits if direct satchel crafting is disabled or server requires backpack items
MIN_BACKPACK_INGOTS = 0 if DIRECT_SATCHEL_CRAFTING else 20
TARGET_BACKPACK_INGOTS = 50
RESTOCK_BATCH_SIZE = 50

# Minimum working spare Tinker's Tools to maintain in backpack before trashing extras
MIN_TINKER_TOOLS = 2

# Delays in seconds
CRAFT_DELAY = 1.3
TOOL_CRAFT_DELAY = 1.2

# Server Craft Gump button IDs (standard ServUO / RunUO)
GUMP_BTN_MAKE_LAST = 21  # Universal "Make Last" button

# Enable verbose debug messages in client console
DEBUG = False


# ==============================================================================
# Item & Graphic Definitions
# ==============================================================================

# Ingot graphics & hues
INGOT_GRAPHIC = 0x1BF2
IRON_INGOT_HUE = 0  # Regular iron ingots (plain / unhued)

# Tinkering tools
TINKER_TOOL_GRAPHICS = {0x1EB8, 0x1EB9, 0x1EBC, 0x1EBD}

# Stackable items
LOCKPICK_GRAPHIC = 0x14FB

# Trash barrel graphics
TRASH_BARREL_GRAPHICS = {0x0E77}

# Special / colored ore and ingot names to strictly protect
SPECIAL_INGOT_NAMES = (
    "dull", "shadow", "copper", "bronze", "gold", "agapite", "verite", "valorite"
)

# Optimal Tinkering Progression Ladder: (min_skill, max_skill, item_name, ingot_cost)
PROGRESSION_LADDER: List[Tuple[float, float, str, int]] = [
    (0.0, 45.0, "Tinker's Tools", 2),
    (45.0, 60.0, "Tongs", 1),
    (60.0, 95.0, "Lockpick", 1),
    (95.0, 100.0, "Heating Stand", 4),
]


# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_recipe = None
lbl_counts = None
lbl_ingots = None
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

last_tinkering_skill: Optional[float] = None
current_recipe_name: str = "Tinker's Tools"
recommended_recipe_name: str = "Tinker's Tools"


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
    global last_tinkering_skill, recommended_recipe_name
    global lbl_skill, lbl_recipe, lbl_counts, lbl_ingots, lbl_tools

    # 1. Tinkering Skill
    t_skill = API.GetSkill("Tinkering")
    if t_skill:
        val = float(t_skill.Value)
        cap = float(t_skill.Cap)
        if lbl_skill:
            lbl_skill.Text = f"Tinkering: {val:.1f} / {cap:.1f}"

        if last_tinkering_skill is not None and val > last_tinkering_skill:
            gain = val - last_tinkering_skill
            API.SysMsg(f"[Tinkering] Skill gained +{gain:.1f}! New skill: {val:.1f}")

            # Blacksmithing synergy announcements
            if last_tinkering_skill < 40.0 <= val:
                API.SysMsg("[Tinkering] *** Milestone: You can now craft Smith's Hammers (40.0)! ***")
            if last_tinkering_skill < 45.0 <= val:
                API.SysMsg("[Tinkering] *** Milestone: You can now craft Tongs (45.0)! ***")

            # Check for progression milestone
            old_rec, _ = get_recommended_item(last_tinkering_skill)
            new_rec, cost = get_recommended_item(val)
            if new_rec != old_rec:
                API.SysMsg(f"[Tinkering] *** Progression Tier reached ({val:.1f})! ***")
                API.SysMsg(f"[Tinkering] Recommended next item: '{new_rec}' ({cost} ingots).")
                API.SysMsg(f"[Tinkering] Click 'Set Recipe' on the Gump to switch to '{new_rec}', or continue current recipe.")
                recommended_recipe_name = new_rec
                if lbl_recipe:
                    lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {new_rec})"

        last_tinkering_skill = val

    # 2. Recipe
    if lbl_recipe:
        if current_recipe_name != recommended_recipe_name:
            lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {recommended_recipe_name})"
        else:
            lbl_recipe.Text = f"Recipe: {current_recipe_name}"

    # 3. Counts
    if lbl_counts:
        lbl_counts.Text = f"Crafted: {total_crafted} | Trashed: {total_trashed} | Failed: {total_failed}"

    # 4. Ingot Counts
    bp_ingots = count_backpack_ingots()
    satchel_ingots = count_satchel_ingots() if satchel_serial else 0
    satchel_label = f"{satchel_ingots:,}" if satchel_serial else "N/A"
    if lbl_ingots:
        lbl_ingots.Text = f"Satchel: {satchel_label} | Backpack: {bp_ingots}"

    # 5. Tool & Trash Status
    tool_cnt = count_tinker_tools()
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
    API.SysMsg("[Tinkering] Script paused." if is_paused else "[Tinkering] Script resumed.")


def on_stop_clicked() -> None:
    """Stops the script execution."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_satchel_clicked() -> None:
    """Allows player to target their ingot/resource satchel or container."""
    global satchel_serial
    API.SysMsg("[Tinkering] Target your Resource Satchel / Ingot Container (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial:
        satchel_serial = new_serial
        API.SysMsg(f"[Tinkering] Satchel updated: 0x{satchel_serial:X}")
        update_stats()
        if count_backpack_ingots() < MIN_BACKPACK_INGOTS:
            restock_ingots_from_satchel()
    else:
        API.SysMsg("[Tinkering] Satchel targeting cancelled.")
    update_stats()


def on_trash_clicked() -> None:
    """Allows player to target a trash barrel / container."""
    global trash_barrel_serial
    API.SysMsg("[Tinkering] Target your Trash Barrel (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial:
        trash_barrel_serial = new_serial
        API.SysMsg(f"[Tinkering] Trash barrel updated: 0x{trash_barrel_serial:X}")
    else:
        API.SysMsg("[Tinkering] Trash barrel targeting cancelled.")
    update_stats()


def on_recipe_clicked() -> None:
    """Opens the Tinkering craft gump to allow manually selecting an item recipe."""
    global is_paused, btn_pause
    tool = get_tinker_tool()
    if tool:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused (Set Recipe)")
        API.SysMsg("[Tinkering] Opening craft menu. Click your desired item once to craft it, then click 'Resume' on the Gump.")
        API.UseObject(tool)
    else:
        API.SysMsg("[Tinkering] No Tinker's Tool available to open craft menu!")


def on_gump_disposed() -> None:
    """Handles Gump closure by user."""
    global is_stopped
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


def create_control_gump() -> None:
    """Renders the FesterUO Tinkering Trainer Gump."""
    global gump, lbl_status, lbl_skill, lbl_recipe, lbl_counts, lbl_ingots, lbl_tools
    global btn_pause, btn_recipe, btn_satchel, btn_trash, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 310, 220)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 310, 220)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Train Tinkering", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skill
    lbl_skill = API.Gumps.CreateGumpLabel("Tinkering: -- / --", 996)
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

    # Ingot counts
    lbl_ingots = API.Gumps.CreateGumpLabel("Satchel: 0 | Backpack: 0", 996)
    lbl_ingots.SetPos(10, 108)
    gump.Add(lbl_ingots)

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
    """Disposes the Gump safely."""
    global gump
    if gump and not getattr(gump, "IsDisposed", False):
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes UI events and maintains the pause wait loop."""
    global is_paused, is_stopped
    API.ProcessCallbacks()
    update_stats()

    if is_stopped or API.StopRequested:
        return False

    while is_paused and not API.StopRequested and not is_stopped:
        API.Pause(0.2)
        API.ProcessCallbacks()
        update_stats()

    return not (is_stopped or API.StopRequested)


def wait_with_ui(seconds: float) -> bool:
    """Time-sliced delay that continues processing UI callbacks."""
    elapsed = 0.0
    step = 0.15
    while elapsed < seconds:
        if not check_ui_events():
            return False
        API.Pause(step)
        elapsed += step
    return check_ui_events()


# ==============================================================================
# Helper Functions - Tool & Ingot Management
# ==============================================================================

def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def get_tinker_tool():
    """Finds a Tinker's Tool in the backpack."""
    global active_tool_serial
    if active_tool_serial:
        item = API.FindItem(active_tool_serial)
        if item and item.Container == API.Backpack:
            return item
        active_tool_serial = None

    for g in TINKER_TOOL_GRAPHICS:
        item = API.FindType(g, API.Backpack)
        if item:
            active_tool_serial = item.Serial
            return item

    items = API.ItemsInContainer(API.Backpack)
    if items:
        for item in items:
            name = str(getattr(item, "Name", "")).lower()
            if "tinker" in name and "tool" in name:
                active_tool_serial = item.Serial
                return item

    return None


def count_tinker_tools() -> int:
    """Counts available Tinker's Tools in the main backpack."""
    count = 0
    for g in TINKER_TOOL_GRAPHICS:
        items = API.FindTypeAll(g, API.Backpack)
        if items:
            count += len(items)
    return count


def is_regular_iron_ingot(item) -> bool:
    """Strictly checks if an item is a regular, unhued iron ingot."""
    if not item:
        return False
    if item.Graphic != INGOT_GRAPHIC:
        return False
    if item.Hue != IRON_INGOT_HUE:
        return False

    name = str(getattr(item, "Name", "") or "").lower()
    for special in SPECIAL_INGOT_NAMES:
        if special in name:
            return False

    return True


def count_backpack_ingots() -> int:
    """Counts plain iron ingots in the main backpack."""
    total = 0
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not items:
        return 0
    for item in items:
        if item.Serial != satchel_serial and is_regular_iron_ingot(item):
            total += getattr(item, "Amount", 1) or 1
    return total


def count_satchel_ingots() -> int:
    """Counts plain iron ingots inside the resource satchel."""
    if not satchel_serial:
        return 0
    total = 0
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if not items:
        return 0
    for item in items:
        if is_regular_iron_ingot(item):
            total += getattr(item, "Amount", 1) or 1
    return total


def get_satchel_ingots():
    """Returns the largest stack of plain iron ingots in the satchel."""
    if not satchel_serial:
        return None
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if not items:
        return None
    best_item = None
    best_amt = 0
    for item in items:
        if is_regular_iron_ingot(item):
            amt = getattr(item, "Amount", 1) or 1
            if amt > best_amt:
                best_amt = amt
                best_item = item
    return best_item


def restock_ingots_from_satchel() -> bool:
    """Pulls a batch of iron ingots from the satchel into the main backpack."""
    if not satchel_serial:
        return False

    current_bp = count_backpack_ingots()
    if current_bp >= MIN_BACKPACK_INGOTS:
        return True

    satchel_stack = get_satchel_ingots()
    if not satchel_stack:
        return False

    amt_available = getattr(satchel_stack, "Amount", 1) or 1
    amt_needed = max(RESTOCK_BATCH_SIZE, TARGET_BACKPACK_INGOTS - current_bp)
    amt_to_move = min(amt_available, amt_needed)

    if amt_to_move <= 0:
        return False

    update_status(f"Restocking {amt_to_move} ingots...")
    API.MoveItem(satchel_stack.Serial, API.Backpack, amt=amt_to_move)
    API.Pause(0.6)
    update_stats()
    return count_backpack_ingots() >= 2


def deposit_excess_ingots_to_satchel() -> None:
    """Moves loose iron ingots from the main backpack into the satchel."""
    if not satchel_serial:
        return

    current_bp = count_backpack_ingots()
    target_bp = 0 if DIRECT_SATCHEL_CRAFTING else TARGET_BACKPACK_INGOTS
    if current_bp <= target_bp:
        return

    excess = current_bp - target_bp
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not items:
        return

    for item in items:
        if item.Serial != satchel_serial and is_regular_iron_ingot(item):
            amt = getattr(item, "Amount", 1) or 1
            amt_to_move = min(amt, excess)
            if amt_to_move > 0:
                API.MoveItem(item.Serial, satchel_serial, amt=amt_to_move)
                API.Pause(0.5)
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
    """Returns the optimal item name and ingot cost for the current skill level."""
    for min_sk, max_sk, name, cost in PROGRESSION_LADDER:
        if min_sk <= skill < max_sk:
            return name, cost
    return "Heating Stand", 4


def ensure_tinker_tools() -> bool:
    """Ensures player maintains an adequate reserve of Tinker's Tools."""
    global tools_crafted
    tool_count = count_tinker_tools()
    if tool_count >= MIN_TINKER_TOOLS:
        return True

    tool = get_tinker_tool()
    if not tool:
        return False

    # If already training Tinker's Tools, the main craft cycle will replenish tools naturally
    if current_recipe_name == "Tinker's Tools":
        return True

    total_ingots = count_backpack_ingots() + (count_satchel_ingots() if satchel_serial else 0)
    if total_ingots < 2:
        return True

    update_status("Crafting spare tool...")
    API.SysMsg("[Tinkering] Tool supply low. Crafting spare Tinker's Tool...")

    count_before = count_tinker_tools()
    API.UseObject(tool)
    if API.WaitForGump(delay=2.5):
        API.ReplyGump(GUMP_BTN_MAKE_LAST)
        wait_with_ui(CRAFT_DELAY)

    count_after = count_tinker_tools()
    if count_after > count_before:
        tools_crafted += 1
        API.SysMsg("[Tinkering] Successfully crafted a spare Tinker's Tool!")
        update_stats()
        return True

    return True


# ==============================================================================
# Main Craft Cycle
# ==============================================================================

def craft_cycle() -> bool:
    """Executes a single craft attempt and manages newly crafted items."""
    global total_crafted, total_trashed, total_failed, current_recipe_name, recommended_recipe_name
    global is_paused, btn_pause

    # 1. Check Skill & Target Skill Cap
    skill_obj = API.GetSkill("Tinkering")
    if not skill_obj:
        update_status("Skill not found")
        return False

    val = float(skill_obj.Value)
    cap = float(skill_obj.Cap)
    if val >= TARGET_SKILL or val >= cap:
        update_status(f"Target Reached ({val:.1f})")
        API.SysMsg(f"[Tinkering] Target skill reached: {val:.1f} / {cap:.1f}!")
        return False

    # 2. Check Tool & Tool Replenishment
    tool = get_tinker_tool()
    if not tool:
        update_status("No Tool")
        API.SysMsg("[Tinkering] Out of Tinker's Tools! Please carry a Tinker's Tool to start.")
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        return True

    ensure_tinker_tools()

    # 3. Check & Restock Ingots
    rec_item, ingot_cost = get_recommended_item(val)
    total_ingots = count_backpack_ingots() + (count_satchel_ingots() if satchel_serial else 0)
    if total_ingots < ingot_cost:
        update_status("Out of Ingots")
        API.SysMsg("[Tinkering] Out of iron ingots in satchel and backpack! Please refill and click Resume.")
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        return True

    if not DIRECT_SATCHEL_CRAFTING and count_backpack_ingots() < ingot_cost:
        if not restock_ingots_from_satchel():
            update_status("Out of Ingots")
            API.SysMsg("[Tinkering] Out of iron ingots in satchel! Please refill satchel and click Resume.")
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            return True

    # 4. Snapshot backpack items before crafting
    bp_before_items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    bp_before_serials: Set[int] = {item.Serial for item in bp_before_items}

    # 5. Open craft gump if not already present
    if not API.HasGump():
        API.UseObject(tool)
        if not API.WaitForGump(delay=2.5):
            debug_msg("Craft gump timed out on tool use.")
            return True

    # 6. Click Make Last
    API.ClearJournal()
    API.ReplyGump(GUMP_BTN_MAKE_LAST)
    if not wait_with_ui(CRAFT_DELAY):
        return False

    # 7. Analyze result from journal & backpack
    entries = API.GetJournalEntries(CRAFT_DELAY + 0.8)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    # Check if Make Last is uninitialized
    if any("haven't made anything" in t or "have not made" in t for t in j_text) or API.GumpContains("haven't made anything") or API.GumpContains("not made anything"):
        API.SysMsg(f"[Tinkering] 'Make Last' is not set yet.")
        API.SysMsg(f"[Tinkering] In the open Tinkering menu: Click '{rec_item}' once to craft it, then click Resume on the Gump.")
        update_status(f"Prime '{rec_item}'")
        on_pause_clicked()
        return True

    # Check if server complained about missing resources despite satchel having ingots
    if any("sufficient metal" in t or "enough metal" in t or "lack the metal" in t or "sufficient ingots" in t for t in j_text) or API.InJournal("sufficient metal"):
        if satchel_serial and count_satchel_ingots() >= ingot_cost:
            API.SysMsg("[Tinkering] Server requires ingots in root backpack. Restocking from satchel...")
            restock_ingots_from_satchel()
            return True

    # Check craft success or failure from journal
    success = any("you create" in t or "placed in your backpack" in t or "put the" in t for t in j_text) or API.InJournal("you create")
    failed = any("you fail" in t or "failed" in t or "lack the skill" in t for t in j_text) or API.InJournal("you fail")

    # Detect newly crafted item via backpack serial diff
    bp_after_items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    new_item = None
    for it in bp_after_items:
        if it.Serial not in bp_before_serials:
            if it.Serial != satchel_serial and it.Serial != trash_barrel_serial:
                if it.Graphic != INGOT_GRAPHIC:
                    new_item = it
                    break

    if new_item:
        success = True

    if success:
        total_crafted += 1
        update_status("Crafted")
        update_stats()

        # Handle trashing or keeping newly crafted item
        if new_item:
            is_tool = new_item.Graphic in TINKER_TOOL_GRAPHICS
            is_lockpick = new_item.Graphic == LOCKPICK_GRAPHIC

            if is_tool:
                # Keep up to MIN_TINKER_TOOLS, trash extras if trash barrel available
                if count_tinker_tools() > MIN_TINKER_TOOLS and trash_barrel_serial:
                    API.MoveItem(new_item.Serial, trash_barrel_serial)
                    API.Pause(0.4)
                    total_trashed += 1
                    update_stats()
            elif is_lockpick:
                # Lockpicks stack and weigh 0.1; keep them unless user wants them trashed
                pass
            else:
                # Other non-stackable items (Tongs, Heating Stands, Scissors, etc.)
                if trash_barrel_serial:
                    update_status(f"Trashing {new_item.Name or 'item'}...")
                    API.MoveItem(new_item.Serial, trash_barrel_serial)
                    API.Pause(0.4)
                    total_trashed += 1
                    update_stats()

    elif failed:
        total_failed += 1
        update_status("Failed attempt")
        update_stats()

    elif any("worn out" in t or "broke" in t for t in j_text):
        API.SysMsg("[Tinkering] Tool broke during crafting.")
        global active_tool_serial
        active_tool_serial = None

    # Deposit excess ingots back into satchel
    deposit_excess_ingots_to_satchel()

    return True


# ==============================================================================
# Main Orchestration Loop
# ==============================================================================

def main():
    global satchel_serial, trash_barrel_serial, current_recipe_name, recommended_recipe_name

    API.SysMsg("=== FesterUO Tinkering Trainer ===")

    # 1. Initial skill and recipe recommendation
    t_skill_obj = API.GetSkill("Tinkering")
    current_skill = float(t_skill_obj.Value) if t_skill_obj else 0.0
    recommended_recipe_name, cost = get_recommended_item(current_skill)
    current_recipe_name = recommended_recipe_name

    # 2. Trash Barrel Setup
    auto_barrel = find_nearby_trash_barrel()
    if auto_barrel:
        trash_barrel_serial = auto_barrel.Serial
        API.SysMsg(f"[Tinkering] Auto-detected nearby Trash Barrel: 0x{trash_barrel_serial:X}")
    else:
        API.SysMsg("[Tinkering] Target your Trash Barrel (or press ESC / target yourself to skip auto-trashing)...")
        t_serial = API.RequestTarget(timeout=6.0)
        if t_serial and t_serial != API.Player.Serial:
            trash_barrel_serial = t_serial
            API.SysMsg(f"[Tinkering] Trash barrel set: 0x{trash_barrel_serial:X}")
        else:
            trash_barrel_serial = None
            API.SysMsg("[Tinkering] No trash barrel selected. Crafted items will remain in your backpack.")

    # 3. Satchel Setup
    API.SysMsg("[Tinkering] Target your Ingot / Resource Satchel (or press ESC / target yourself for backpack only)...")
    s_serial = API.RequestTarget(timeout=6.0)
    if s_serial and s_serial != API.Player.Serial:
        satchel_serial = s_serial
        API.SysMsg(f"[Tinkering] Satchel set: 0x{satchel_serial:X}")
    else:
        satchel_serial = None
        API.SysMsg("[Tinkering] Using backpack ingots only.")

    # 4. Check initial tool
    tool = get_tinker_tool()
    if not tool:
        API.SysMsg("[Tinkering] No Tinker's Tool found! Please carry at least one Tinker's Tool to start.")
        update_status("No Tool")

    # 5. Render Gump & initial stats
    create_control_gump()
    update_stats()

    # Initial check and restock of ingots only if not using direct satchel crafting
    if not DIRECT_SATCHEL_CRAFTING and count_backpack_ingots() < MIN_BACKPACK_INGOTS:
        restock_ingots_from_satchel()

    update_status("Running")
    API.SysMsg(f"[Tinkering] Training started. Current skill: {current_skill:.1f} | Recommended: {recommended_recipe_name}")

    # 6. Main Training Loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        success = craft_cycle()
        if not success:
            break

        API.Pause(0.2)

    update_status("Finished")
    API.SysMsg("[Tinkering] Training finished.")
    dispose_gump()


main()
