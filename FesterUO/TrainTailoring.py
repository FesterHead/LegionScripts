"""
TrainTailoring.py - Automated Resource-Efficient Tailoring Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Fully automated Tailoring skill training script for TazUO featuring:
    - Optimal resource-efficient progression ladder from 0.0 to 120.0 Tailoring:
        * 0.0 - 29.0:   Short Pants / Skirt (1-2 cloth)
        * 29.0 - 41.5:  Skullcap / Bandana (2 cloth)
        * 41.5 - 54.0:  Body Sash / Cap (4-11 cloth)
        * 54.0 - 74.0:  Cloak / Robe (14-16 cloth)
        * 74.0 - 99.6:  Oil Cloth (1 cloth - ultra-resource efficient!)
        * 99.6 - 120.0: Elven Shirt / Studded Armor (12 cloth / 14 leather)
    - Milestone Announcements & "Set Recipe" Manual Override:
        * Proactively notifies the player when reaching a skill threshold to recommend the next item.
        * Includes an interactive "Set Recipe" button allowing players to manually prime any craft recipe.
    - Automated Cutting & Recycling via Scissors:
        * Detects Scissors in backpack and automatically cuts newly crafted cloth/leather items
          back into raw cut cloth and leather, recovering substantial materials.
    - Automated Crafted Item Disposal (Trash Barrel Fallback):
        * Auto-detects nearby Trash Barrels or allows targeting one on startup or via the Gump.
        * Automatically deposits items that cannot be cut (e.g. certain hats/shoes) into the trash barrel.
        * Includes an interactive "Trash Can" button on the Gump to change/set trash barrels at any time.
    - Resource Satchel Integration:
        * Prompts player on startup to target a Cloth / Leather Resource Satchel (or secure container).
        * Supports direct satchel crafting or maintains a lightweight buffer of cloth/leather in the backpack.
        * Automatically restocks materials from the satchel when supplies run low.
    - Tool Upkeep via Tinkering:
        * Detects Sewing Kits in hands or backpack.
        * If kits break and Tinkering tools + iron ingots are available, attempts to auto-craft replacement
          Sewing Kits (1 iron ingot) on the fly.
    - Interactive Control Gump:
        * Real-time training status, live Tailoring skill level and cap with gain tracking,
          Crafted / Cut / Trashed / Failed counters, Satchel & Backpack material counts, and tool/trash indicators.
        * Interactive Pause / Resume, Set Recipe, Satchel, Trash Can, and Stop buttons.
"""

from typing import List, Tuple, Optional, Set
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Target Tailoring skill to stop training (e.g. 100.0 for GM, 120.0 for Legendary)
TARGET_SKILL: float = 120.0

# Direct Satchel Crafting (crafts directly from resource satchel without pulling to backpack)
DIRECT_SATCHEL_CRAFTING: bool = True

# Fallback limits if direct satchel crafting is disabled or server requires backpack items
MIN_BACKPACK_MATERIALS: int = 0 if DIRECT_SATCHEL_CRAFTING else 20
TARGET_BACKPACK_MATERIALS: int = 50
RESTOCK_BATCH_SIZE: int = 50

# Delays in seconds
CRAFT_DELAY: float = 1.3
TOOL_CRAFT_DELAY: float = 1.2

# Server Craft Gump button IDs (standard ServUO / RunUO)
GUMP_BTN_MAKE_LAST: int = 21  # Universal "Make Last" button

# Automatically cut crafted items with Scissors to recycle cloth and leather
AUTO_CUT_WITH_SCISSORS: bool = True

# Tool upkeep via Tinkering
AUTO_CRAFT_SEWING_KIT: bool = True
MAX_TOOL_CRAFT_ATTEMPTS: int = 8

# Enable verbose debug messages in client console
DEBUG: bool = False

# ==============================================================================
# Material & Tool Definitions
# ==============================================================================

# Tailoring materials (Cloth, Cut Cloth, Bolts of Cloth, Leather, Hides)
CLOTH_GRAPHICS: Set[int] = {
    0x1766, 0x1767,  # Cut cloth piles
    0x0F95,          # Bolt of cloth
}

LEATHER_GRAPHICS: Set[int] = {
    0x1067, 0x1081,  # Cut leather
    0x1078, 0x1079,  # Hides
}

ALL_TAILOR_MATERIALS: Set[int] = CLOTH_GRAPHICS | LEATHER_GRAPHICS

# Tailoring tools
SEWING_KIT_GRAPHICS: Set[int] = {0x0F9D}
SCISSORS_GRAPHICS: Set[int] = {0x0F9E, 0x0F9F}

# Tinkering tools & materials for auto-crafting sewing kits
TINKER_TOOL_GRAPHICS: Set[int] = {0x1EB8, 0x1EB9, 0x1EBC, 0x1EBD}
INGOT_GRAPHIC: int = 0x1BF2
IRON_INGOT_HUE: int = 0

# Trash barrel graphics
TRASH_BARREL_GRAPHICS: Set[int] = {0x0E77}

# Optimal Tailoring Progression Ladder: (min_skill, max_skill, item_name, material_cost)
PROGRESSION_LADDER: List[Tuple[float, float, str, str]] = [
    (0.0, 29.0, "Short Pants / Skirt", "Cloth (1-2)"),
    (29.0, 41.5, "Skullcap / Bandana", "Cloth (2)"),
    (41.5, 54.0, "Body Sash / Cap", "Cloth (4-11)"),
    (54.0, 74.0, "Cloak / Robe", "Cloth (14-16)"),
    (74.0, 99.6, "Oil Cloth", "Cloth (1)"),
    (99.6, 120.0, "Elven Shirt / Studded Suit", "Cloth (12) / Leather (14)"),
]

# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_recipe = None
lbl_counts = None
lbl_materials = None
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
total_cut: int = 0
total_trashed: int = 0
total_failed: int = 0
tools_crafted: int = 0

last_tailoring_skill: Optional[float] = None
current_recipe_name: str = "Make Last"
recommended_recipe_name: str = "Short Pants"

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
    global last_tailoring_skill, recommended_recipe_name
    global lbl_skill, lbl_recipe, lbl_counts, lbl_materials, lbl_tools

    # 1. Tailoring Skill
    t_skill = API.GetSkill("Tailoring")
    if t_skill:
        val = float(t_skill.Value)
        cap = float(t_skill.Cap)
        if lbl_skill:
            lbl_skill.Text = f"Tailoring: {val:.1f} / {cap:.1f}"

        if last_tailoring_skill is not None and val > last_tailoring_skill:
            gain = val - last_tailoring_skill
            API.SysMsg(f"[Tailoring] Skill gained +{gain:.1f}! New skill: {val:.1f}")

            # Check for progression milestone
            old_rec, _ = get_recommended_item(last_tailoring_skill)
            new_rec, cost = get_recommended_item(val)
            if new_rec != old_rec:
                API.SysMsg(f"[Tailoring] *** Milestone reached ({val:.1f})! ***")
                API.SysMsg(f"[Tailoring] Recommended next item: '{new_rec}' ({cost}).")
                API.SysMsg(f"[Tailoring] Click 'Set Recipe' on the Gump to switch to '{new_rec}', or continue current recipe.")
                recommended_recipe_name = new_rec
                if lbl_recipe:
                    lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {new_rec})"

        last_tailoring_skill = val

    # 2. Recipe Label
    if lbl_recipe:
        if current_recipe_name != recommended_recipe_name:
            lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {recommended_recipe_name})"
        else:
            lbl_recipe.Text = f"Recipe: {current_recipe_name}"

    # 3. Running Counters
    if lbl_counts:
        lbl_counts.Text = f"Crafted: {total_crafted} | Cut: {total_cut} | Trashed: {total_trashed} | Failed: {total_failed}"

    # 4. Material Counts
    bp_mat = count_backpack_materials()
    satchel_mat = count_satchel_materials() if satchel_serial else 0
    satchel_label = f"{satchel_mat:,}" if satchel_serial else "N/A"
    if lbl_materials:
        lbl_materials.Text = f"Satchel: {satchel_label} | Backpack: {bp_mat:,}"

    # 5. Tool, Scissors & Trash status
    num_kits = count_sewing_kits()
    has_scissors = "Yes" if get_scissors() is not None else "No"
    trash_str = f"0x{trash_barrel_serial:X}" if trash_barrel_serial else "None"
    if lbl_tools:
        lbl_tools.Text = f"Kits: {num_kits} | Scissors: {has_scissors} | Trash: {trash_str}"


def on_pause_clicked() -> None:
    """Callback triggered when the Pause/Resume button is clicked."""
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("[Tailoring] Paused." if is_paused else "[Tailoring] Resumed.")


def on_stop_clicked() -> None:
    """Callback triggered when the Stop button is clicked."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_satchel_clicked() -> None:
    """Allows player to target a Cloth / Leather Satchel container."""
    global satchel_serial
    API.SysMsg("[Tailoring] Target your Resource Satchel / Material Box (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial:
        satchel_serial = new_serial
        API.SysMsg(f"[Tailoring] Satchel updated: 0x{satchel_serial:X}")
        API.UseObject(satchel_serial)
        API.Pause(0.5)
    else:
        API.SysMsg("[Tailoring] Satchel targeting cancelled.")
    update_stats()


def on_trash_clicked() -> None:
    """Allows player to target a trash barrel / container."""
    global trash_barrel_serial
    API.SysMsg("[Tailoring] Target your Trash Barrel (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial:
        trash_barrel_serial = new_serial
        API.SysMsg(f"[Tailoring] Trash barrel updated: 0x{trash_barrel_serial:X}")
    else:
        API.SysMsg("[Tailoring] Trash barrel targeting cancelled.")
    update_stats()


def on_recipe_clicked() -> None:
    """Opens the Tailoring craft gump to allow manually selecting an item recipe."""
    global is_paused, btn_pause
    tool = get_sewing_kit()
    if tool:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused (Set Recipe)")
        API.SysMsg("[Tailoring] Opening craft menu. Click your desired item once to craft it, then click 'Resume' on the Gump.")
        API.UseObject(tool.Serial)
    else:
        API.SysMsg("[Tailoring] No sewing kit available to open craft menu!")


def on_gump_disposed() -> None:
    global is_stopped
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


def create_control_gump() -> None:
    """Renders the FesterUO Tailoring Trainer Gump."""
    global gump, lbl_status, lbl_skill, lbl_recipe, lbl_counts, lbl_materials, lbl_tools
    global btn_pause, btn_recipe, btn_satchel, btn_trash, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 310, 220)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 310, 220)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Train Tailoring", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skill
    lbl_skill = API.Gumps.CreateGumpLabel("Tailoring: -- / --", 996)
    lbl_skill.SetPos(10, 48)
    gump.Add(lbl_skill)

    # Recipe
    lbl_recipe = API.Gumps.CreateGumpLabel("Recipe: Initializing...", 53)
    lbl_recipe.SetPos(10, 68)
    gump.Add(lbl_recipe)

    # Counts
    lbl_counts = API.Gumps.CreateGumpLabel("Crafted: 0 | Cut: 0 | Trashed: 0 | Failed: 0", 996)
    lbl_counts.SetPos(10, 88)
    gump.Add(lbl_counts)

    # Material counts
    lbl_materials = API.Gumps.CreateGumpLabel("Satchel: 0 | Backpack: 0", 996)
    lbl_materials.SetPos(10, 108)
    gump.Add(lbl_materials)

    # Tool status
    lbl_tools = API.Gumps.CreateGumpLabel("Kits: 0 | Scissors: No | Trash: None", 996)
    lbl_tools.SetPos(10, 128)
    gump.Add(lbl_tools)

    # Row 1 Buttons: Pause, Set Recipe
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 72, 22)
    btn_pause.SetPos(10, 155)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_recipe = API.Gumps.CreateSimpleButton("Set Recipe", 88, 22)
    btn_recipe.SetPos(90, 155)
    API.Gumps.AddControlOnClick(btn_recipe, on_recipe_clicked)
    gump.Add(btn_recipe)

    # Row 1 Buttons: Satchel, Trash Can
    btn_satchel = API.Gumps.CreateSimpleButton("Satchel", 72, 22)
    btn_satchel.SetPos(10, 185)
    API.Gumps.AddControlOnClick(btn_satchel, on_satchel_clicked)
    gump.Add(btn_satchel)

    btn_trash = API.Gumps.CreateSimpleButton("Trash Can", 88, 22)
    btn_trash.SetPos(90, 185)
    API.Gumps.AddControlOnClick(btn_trash, on_trash_clicked)
    gump.Add(btn_trash)

    # Stop Button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 60, 52)
    btn_stop.SetPos(240, 155)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Handle right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely removes the Gump window."""
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

    while is_paused and not API.StopRequested and not is_stopped:
        API.ProcessCallbacks()
        API.Pause(0.1)
        update_stats()
        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            on_pause_clicked()
            break

    return not is_stopped and not API.StopRequested


def wait_with_ui(seconds: float) -> bool:
    """Waits for specified seconds in small slices while processing UI events."""
    elapsed = 0.0
    step = 0.1
    while elapsed < seconds:
        if not check_ui_events():
            return False
        API.Pause(step)
        elapsed += step
    return check_ui_events()


# ==============================================================================
# Helper Functions - Materials, Tools & Detection
# ==============================================================================

def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def is_overburdened() -> bool:
    """Returns True if player is near maximum weight capacity."""
    if not API.Player:
        return False
    weight = API.Player.Weight
    weight_max = API.Player.WeightMax
    if weight is not None and weight_max is not None and weight_max > 0:
        return weight >= (weight_max - 15)
    return False


def get_sewing_kit():
    """Finds a usable Sewing Kit in hands or backpack."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in SEWING_KIT_GRAPHICS:
            return item

    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Graphic in SEWING_KIT_GRAPHICS:
                return item
    return None


def count_sewing_kits() -> int:
    """Counts usable sewing kits in hands and backpack."""
    cnt = 0
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in SEWING_KIT_GRAPHICS:
            cnt += 1

    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Graphic in SEWING_KIT_GRAPHICS:
                cnt += 1
    return cnt


def get_scissors():
    """Finds a pair of scissors in the backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Graphic in SCISSORS_GRAPHICS:
                return item
    return None


def get_tinker_tool():
    """Finds a usable Tinker's Tool in hands, backpack, or satchel."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in TINKER_TOOL_GRAPHICS:
            return item

    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Graphic in TINKER_TOOL_GRAPHICS:
                return item

    if satchel_serial:
        satchel_items = API.ItemsInContainer(satchel_serial, recursive=False)
        if satchel_items:
            for item in satchel_items:
                if item.Graphic in TINKER_TOOL_GRAPHICS:
                    return item

    return None


def count_backpack_materials() -> int:
    """Counts cloth and leather pieces in the main backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not items:
        return 0

    total = 0
    for item in items:
        if item.Serial != satchel_serial and item.Graphic in ALL_TAILOR_MATERIALS:
            amt = getattr(item, "Amount", 1) or 1
            # A bolt of cloth is worth 50 cut cloth
            if item.Graphic == 0x0F95:
                total += amt * 50
            else:
                total += amt
    return total


def count_satchel_materials() -> int:
    """Counts cloth and leather pieces in the resource satchel."""
    if not satchel_serial:
        return 0
    items = API.ItemsInContainer(satchel_serial, recursive=False)
    if not items:
        return 0

    total = 0
    for item in items:
        if item.Graphic in ALL_TAILOR_MATERIALS:
            amt = getattr(item, "Amount", 1) or 1
            if item.Graphic == 0x0F95:
                total += amt * 50
            else:
                total += amt
    return total


def get_satchel_materials_stack():
    """Finds the largest stack of cloth or leather in the satchel."""
    if not satchel_serial:
        return None
    items = API.ItemsInContainer(satchel_serial, recursive=False)
    if not items:
        return None

    best_item = None
    best_amt = 0
    for item in items:
        if item.Graphic in ALL_TAILOR_MATERIALS:
            amt = getattr(item, "Amount", 1) or 1
            if amt > best_amt:
                best_amt = amt
                best_item = item
    return best_item


def restock_materials_from_satchel() -> bool:
    """Pulls a batch of cloth or leather from the satchel into the backpack."""
    if not satchel_serial:
        return False

    current_bp = count_backpack_materials()
    if current_bp >= MIN_BACKPACK_MATERIALS:
        return True

    mat_stack = get_satchel_materials_stack()
    if not mat_stack:
        return False

    amt_available = getattr(mat_stack, "Amount", 1) or 1
    amt_needed = max(RESTOCK_BATCH_SIZE, TARGET_BACKPACK_MATERIALS - current_bp)
    amt_to_move = min(amt_available, amt_needed)

    if amt_to_move <= 0:
        return False

    update_status(f"Restocking {amt_to_move} materials...")
    API.MoveItem(mat_stack.Serial, API.Backpack, amt=amt_to_move)
    API.Pause(0.6)
    update_stats()
    return count_backpack_materials() >= 2


def count_backpack_ingots() -> int:
    """Counts iron ingots in the backpack for Tinkering tool upkeep."""
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not items:
        return 0
    total = 0
    for item in items:
        if item.Graphic == INGOT_GRAPHIC and item.Hue == IRON_INGOT_HUE:
            total += getattr(item, "Amount", 1) or 1
    return total


def count_satchel_ingots() -> int:
    """Counts iron ingots in the satchel."""
    if not satchel_serial:
        return 0
    items = API.ItemsInContainer(satchel_serial, recursive=False)
    if not items:
        return 0
    total = 0
    for item in items:
        if item.Graphic == INGOT_GRAPHIC and item.Hue == IRON_INGOT_HUE:
            total += getattr(item, "Amount", 1) or 1
    return total


def restock_ingots_from_satchel(amount: int = 4) -> bool:
    """Pulls iron ingots from satchel for auto-crafting sewing kits."""
    if not satchel_serial:
        return False
    items = API.ItemsInContainer(satchel_serial, recursive=False)
    if not items:
        return False
    for item in items:
        if item.Graphic == INGOT_GRAPHIC and item.Hue == IRON_INGOT_HUE:
            avail = getattr(item, "Amount", 1) or 1
            move_amt = min(avail, amount)
            if move_amt > 0:
                API.MoveItem(item.Serial, API.Backpack, amt=move_amt)
                API.Pause(0.6)
                return True
    return False


def find_nearby_trash_barrel():
    """Finds a trash barrel within 3 tiles."""
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


def get_recommended_item(skill: float) -> Tuple[str, str]:
    """Returns the recommended item name and material requirement for current skill."""
    for min_sk, max_sk, name, cost in PROGRESSION_LADDER:
        if min_sk <= skill < max_sk:
            return name, cost
    return "Elven Shirt / Studded Suit", "Cloth (12) / Leather (14)"


def craft_sewing_kit_with_tinkering() -> bool:
    """Crafts a replacement Sewing Kit using Tinkering tools and iron ingots."""
    global tools_crafted, is_paused, btn_pause
    if not AUTO_CRAFT_SEWING_KIT:
        return False

    tinker_tool = get_tinker_tool()
    if not tinker_tool:
        update_status("Need Tinker Tool")
        API.SysMsg("[Tailoring] No Tinker's Tool found to craft a replacement sewing kit!")
        return False

    tinker_skill_obj = API.GetSkill("Tinkering")
    tinker_skill = float(tinker_skill_obj.Value) if tinker_skill_obj else 0.0
    if tinker_skill < 10.0:
        update_status("Low Tinker Skill")
        API.SysMsg(f"[Tailoring] Tinkering skill ({tinker_skill:.1f}) is too low to craft sewing kits.")
        return False

    # Check total ingots in backpack and satchel
    total_ingots = count_backpack_ingots() + count_satchel_ingots()
    if total_ingots < 2:
        update_status("Out of Ingots")
        API.SysMsg("[Tailoring] Not enough iron ingots in backpack or satchel to craft sewing kit (need 1 ingot)!")
        return False

    # Pull ingots from satchel if needed
    if count_backpack_ingots() < 2:
        restock_ingots_from_satchel(4)

    update_status("Tinkering Sewing Kit...")
    API.SysMsg("[Tailoring] Crafting replacement Sewing Kit via Tinkering (1 ingot)...")

    count_before = count_sewing_kits()

    for attempt in range(1, MAX_TOOL_CRAFT_ATTEMPTS + 1):
        if API.StopRequested or is_stopped:
            return False

        if count_backpack_ingots() < 2:
            restock_ingots_from_satchel(4)

        if not API.HasGump():
            API.UseObject(tinker_tool.Serial)
            if not API.WaitForGump(delay=2.5):
                API.SysMsg("[Tailoring] Tinkering craft menu did not appear.")
                return False

        # Check if Make Last is uninitialized
        if API.GumpContains("haven't made anything") or API.GumpContains("not made anything"):
            API.SysMsg("[Tailoring] Tinkering 'Make Last' is not set to Sewing Kit.")
            API.SysMsg("[Tailoring] In the open Tinkering menu: Click 'Tools' -> 'Sewing Kit' once, then click Resume on the Gump.")
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            update_status("Craft 1 Sewing Kit")
            return True

        API.ClearJournal()
        API.ReplyGump(GUMP_BTN_MAKE_LAST)
        wait_with_ui(TOOL_CRAFT_DELAY)

        # Check if a new kit appeared
        count_after = count_sewing_kits()
        if count_after > count_before or get_sewing_kit() is not None:
            tools_crafted += 1
            API.SysMsg("[Tailoring] Successfully crafted new Sewing Kit!")
            update_stats()
            if API.HasGump():
                API.ReplyGump(0)
                API.Pause(0.3)
            return True

        API.Pause(0.4)

    if API.HasGump():
        API.ReplyGump(0)
        API.Pause(0.3)

    API.SysMsg(f"[Tailoring] Failed to auto-craft Sewing Kit after {MAX_TOOL_CRAFT_ATTEMPTS} attempts.")
    is_paused = True
    if btn_pause:
        btn_pause.SetText("Resume")
    update_status("Craft 1 Sewing Kit")
    return True


# ==============================================================================
# Crafting Cycle
# ==============================================================================

def craft_cycle() -> bool:
    """Executes a single craft attempt, cuts/recycles or trashes crafted items."""
    global total_crafted, total_failed, total_cut, total_trashed, current_recipe_name

    # 1. Weight protection
    if is_overburdened():
        update_status("Overweight")
        API.SysMsg("[Tailoring] Weight limit reached! Please lighten your backpack.")
        return False

    # 2. Check total materials available
    total_mat = count_backpack_materials() + (count_satchel_materials() if satchel_serial else 0)
    if total_mat < 1:
        update_status("Out of Materials")
        API.SysMsg("[Tailoring] Out of cloth / leather in backpack and satchel!")
        return False

    # If direct satchel crafting is disabled, maintain backpack buffer
    if not DIRECT_SATCHEL_CRAFTING and count_backpack_materials() < MIN_BACKPACK_MATERIALS:
        restock_materials_from_satchel()

    # 3. Ensure sewing kit is available
    tool = get_sewing_kit()
    if not tool:
        if not craft_sewing_kit_with_tinkering():
            update_status("No Sewing Kit")
            API.SysMsg("[Tailoring] Out of sewing kits! Please equip or carry a sewing kit.")
            return False
        tool = get_sewing_kit()
        if not tool:
            return True

    # 4. Record pre-craft backpack state for serial diff detection
    bp_before = {item.Serial for item in (API.ItemsInContainer(API.Backpack, recursive=False) or [])}

    # 5. Open craft menu if needed
    if not API.HasGump():
        API.ClearJournal()
        API.UseObject(tool.Serial)
        if not API.WaitForGump(delay=2.5):
            debug_msg("Tailoring menu did not appear.")
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
        t_skill_obj = API.GetSkill("Tailoring")
        current_skill = float(t_skill_obj.Value) if t_skill_obj else 0.0
        rec_name, _ = get_recommended_item(current_skill)
        API.SysMsg("[Tailoring] 'Make Last' is not set yet.")
        API.SysMsg(f"[Tailoring] In the open Tailoring menu: Click '{rec_name}' once to craft it, then click Resume on the Gump.")
        update_status(f"Prime '{rec_name}'")
        on_pause_clicked()
        return True

    # Check if server complained about missing resources despite satchel having cloth
    if any("sufficient" in t or "enough" in t for t in j_text) or API.InJournal("sufficient"):
        if satchel_serial and count_satchel_materials() >= 2:
            API.SysMsg("[Tailoring] Server requires materials in backpack. Restocking from satchel...")
            restock_materials_from_satchel()
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
                if it.Graphic not in ALL_TAILOR_MATERIALS and it.Graphic not in SEWING_KIT_GRAPHICS and it.Graphic not in SCISSORS_GRAPHICS:
                    new_item = it
                    break

    if new_item:
        success = True

    if success:
        total_crafted += 1
        update_status("Crafted")
        update_stats()

        # Handle cutting with scissors or trashing
        if new_item:
            item_handled = False

            # Option A: Cut with scissors to recycle materials
            if AUTO_CUT_WITH_SCISSORS:
                scissors = get_scissors()
                if scissors:
                    update_status("Cutting item...")
                    API.ClearJournal()
                    API.UseObject(scissors.Serial)
                    if API.WaitForTarget(timeout=2.0):
                        API.Target(new_item.Serial)
                        API.Pause(0.5)

                        # Check if item serial was destroyed/cut
                        bp_now = {it.Serial for it in (API.ItemsInContainer(API.Backpack, recursive=False) or [])}
                        if new_item.Serial not in bp_now:
                            total_cut += 1
                            item_handled = True
                            debug_msg(f"Recycled item 0x{new_item.Serial:X} with scissors.")

            # Option B: Discard in trash barrel if not cut
            if not item_handled:
                # Find nearby trash barrel if not set
                target_barrel = trash_barrel_serial
                if not target_barrel:
                    nearby = find_nearby_trash_barrel()
                    if nearby:
                        target_barrel = nearby.Serial

                if target_barrel:
                    update_status("Trashing...")
                    API.MoveItem(new_item.Serial, target_barrel, 0)
                    total_trashed += 1
                    API.Pause(0.4)
                else:
                    debug_msg(f"Crafted item 0x{new_item.Serial:X} left in backpack (no scissors / trash barrel).")

        update_stats()
        return True

    elif failed:
        total_failed += 1
        update_status("Failed")
        update_stats()
        return True

    return True


# ==============================================================================
# Lifecycle Callbacks
# ==============================================================================

def on_stop() -> None:
    """Invoked when the script is stopped from the client UI."""
    dispose_gump()
    API.SysMsg("[Tailoring] Script stopped.")

API.OnStop(on_stop)

# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    global satchel_serial, trash_barrel_serial, last_tailoring_skill, recommended_recipe_name

    skill_obj = API.GetSkill("Tailoring")
    if not skill_obj:
        API.SysMsg("[Tailoring] Error: Could not retrieve Tailoring skill information.")
        return

    cap = TARGET_SKILL if TARGET_SKILL is not None else float(skill_obj.Cap)
    current_val = float(skill_obj.Value)

    if current_val >= cap:
        API.SysMsg(f"[Tailoring] Skill already at or above goal ({current_val:.1f} / {cap:.1f}). Nothing to train!")
        return

    last_tailoring_skill = current_val
    rec_name, cost = get_recommended_item(current_val)
    recommended_recipe_name = rec_name

    create_control_gump()
    update_stats()
    update_status("Starting...")

    # 1. Look for nearby trash barrel
    nearby_trash = find_nearby_trash_barrel()
    if nearby_trash:
        trash_barrel_serial = nearby_trash.Serial
        API.SysMsg(f"[Tailoring] Auto-detected nearby Trash Barrel: 0x{trash_barrel_serial:X}")

    # 2. Check for scissors
    scissors = get_scissors()
    if scissors:
        API.SysMsg("[Tailoring] Scissors detected in backpack. Automated material recycling enabled!")
    else:
        API.SysMsg("[Tailoring] Tip: Carry a pair of Scissors in your backpack to automatically recycle crafted clothes back into cloth!")

    # 3. Prompt for Satchel if not set and backpack materials low
    if count_backpack_materials() < 20 and not satchel_serial:
        API.SysMsg("[Tailoring] Target your Cloth / Leather Resource Satchel (or press ESC to skip)...")
        satchel_target = API.RequestTarget(timeout=8.0)
        if satchel_target and satchel_target != API.Player.Serial and satchel_target != API.Backpack:
            satchel_serial = satchel_target
            API.SysMsg(f"[Tailoring] Satchel linked: 0x{satchel_serial:X}")
            API.UseObject(satchel_serial)
            API.Pause(0.5)

    update_stats()
    API.SysMsg(f"[Tailoring] Training started (Skill: {current_val:.1f} / {cap:.1f}). Recommended: '{rec_name}' ({cost}).")

    # Main training loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Check skill goal completion
        skill_obj = API.GetSkill("Tailoring")
        if not skill_obj:
            API.SysMsg("[Tailoring] Lost skill reference.")
            break

        current_val = float(skill_obj.Value)
        if current_val >= cap:
            update_status("Complete!")
            update_stats()
            API.SysMsg(f"[Tailoring] *** Training complete! Reached {current_val:.1f} / {cap:.1f} ***")
            break

        if not craft_cycle():
            API.Pause(1.0)

    update_status("Finished")
    update_stats()
    API.SysMsg(f"[Tailoring] Training ended. Total Crafted: {total_crafted} | Cut: {total_cut} | Trashed: {total_trashed} | Failed: {total_failed}.")


main()
