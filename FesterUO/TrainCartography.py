"""
TrainCartography.py - Automated Resource-Efficient Cartography Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Fully automated Cartography skill training script for TazUO featuring:
    - Optimal resource-efficient progression ladder from 0.0 to 100.0 (or 120.0) Cartography:
        * 0.0 - 50.0:   Local Map (1 blank scroll)
        * 50.0 - 65.0:  City Map (1 blank scroll)
        * 65.0 - 70.0:  Sea Chart (1 blank scroll)
        * 70.0 - 120.0: World Map (1 blank scroll)
    - Milestone Announcements & "Set Recipe" Manual Override:
        * Proactively notifies the player when reaching a skill threshold to recommend the next map.
        * Includes an interactive "Set Recipe" button allowing players to manually prime any craft recipe.
    - Dual Crafted Map Management (Storage & Trash Disposal):
        * Storage Container: Prompts player to target a chest, bag, or pouch to preserve crafted maps.
        * Trash Barrel: Auto-detects nearby Trash Barrels or allows targeting a trash barrel on startup / UI.
        * Automatically deposits newly crafted maps into storage or trash via backpack serial diff,
          preventing overweight and backpack clutter.
        * Interactive "Storage" and "Trash Can" buttons on the Gump allow switching destinations at any time.
    - Resource Satchel Integration:
        * Direct Satchel Crafting support (if server allows crafting directly from satchels).
        * Restock support: Maintains a lightweight buffer of blank scrolls in backpack, pulling fresh batches as needed.
        * Uses standard Blank Scrolls (0x0EF3, 0x0E34) while also supporting Blank Maps (0x14EB, 0x14EC).
    - Tool Upkeep via Tinkering & Smart Pen Discrimination:
        * Detects Mapmaker's Pens in backpack or hands with active OPL tooltip verification.
        * Strictly discriminates between Mapmaker's Pens and Scribe's Pens, never accidentally using
          a Scribe's Pen for Cartography.
        * Automatically tracks active pen serials and detects when tools break.
        * Closes stale craft menus and automatically crafts replacement Mapmaker's Pens (1 ingot + 1 blank scroll)
          via Tinkering on the fly using serial diff detection.
    - Interactive Control Gump:
        * Real-time training status, live Cartography skill level and cap with gain tracking,
          Crafted / Stored / Trashed / Failed counters, Satchel & Backpack blank scroll counts,
          Tool & Destination indicators, and live Weight indicator.
        * Interactive Pause / Resume, Set Recipe, Satchel, Storage, Trash Can, and Stop buttons.
"""

from typing import List, Tuple, Optional, Set
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Target Cartography skill to stop training (e.g. 100.0 for GM, 120.0 for Legendary)
TARGET_SKILL = 100.0

# Direct Satchel Crafting (crafts directly from resource satchel without pulling to backpack)
DIRECT_SATCHEL_CRAFTING = True

# Working buffer of blank scrolls maintained in main backpack if direct crafting is not supported
MIN_BACKPACK_SCROLLS = 0 if DIRECT_SATCHEL_CRAFTING else 20
TARGET_BACKPACK_SCROLLS = 50
RESTOCK_BATCH_SIZE = 50

# Delays in seconds
CRAFT_DELAY = 1.3
TOOL_CRAFT_DELAY = 1.2

# Server Craft Gump button IDs (standard ServUO / RunUO)
GUMP_BTN_MAKE_LAST = 21  # Universal "Make Last" button

# Tool upkeep via Tinkering
AUTO_CRAFT_PEN = True
MAX_TOOL_CRAFT_ATTEMPTS = 8

# Enable verbose debug messages in client console
DEBUG = False


# ==============================================================================
# Item & Graphic Definitions
# ==============================================================================

# Mapmaker / Scribe pen graphics
PEN_GRAPHICS = {0x0FBF, 0x0FC0}

# Blank scrolls (primary material for mapmaking) and blank rolled maps
BLANK_SCROLL_GRAPHICS = {0x0EF3, 0x0E34}
BLANK_MAP_GRAPHICS = {0x14EB, 0x14EC}
ALL_BLANK_MATERIALS = BLANK_SCROLL_GRAPHICS | BLANK_MAP_GRAPHICS

# Crafted map graphics (rolled and unrolled maps)
CRAFTED_MAP_GRAPHICS = {0x14EB, 0x14EC, 0x14ED, 0x14EE}

# Tinkering tools & materials for auto-crafting mapmaker's pens
TINKER_TOOL_GRAPHICS = {0x1EB8, 0x1EB9, 0x1EBC, 0x1EBD}
INGOT_GRAPHIC = 0x1BF2
IRON_INGOT_HUE = 0

# Trash barrel graphics
TRASH_BARREL_GRAPHICS = {0x0E77}

# Optimal Cartography Progression Ladder: (min_skill, max_skill, map_name, scroll_cost)
PROGRESSION_LADDER: List[Tuple[float, float, str, int]] = [
    (0.0, 50.0, "Local Map", 1),
    (50.0, 65.0, "City Map", 1),
    (65.0, 70.0, "Sea Chart", 1),
    (70.0, 120.0, "World Map", 1),
]


# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_recipe = None
lbl_counts = None
lbl_scrolls = None
lbl_tools = None
lbl_weight = None

btn_pause = None
btn_recipe = None
btn_satchel = None
btn_storage = None
btn_trash = None
btn_stop = None

satchel_serial: Optional[int] = None
storage_serial: Optional[int] = None
trash_barrel_serial: Optional[int] = None
active_pen_serial: Optional[int] = None

is_paused: bool = False
is_stopped: bool = False

total_crafted: int = 0
total_stored: int = 0
total_trashed: int = 0
total_failed: int = 0
tools_crafted: int = 0

last_cartography_skill: Optional[float] = None
current_recipe_name: str = "Make Last"
recommended_recipe_name: str = "Local Map"


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
    global last_cartography_skill, recommended_recipe_name
    global lbl_skill, lbl_recipe, lbl_counts, lbl_scrolls, lbl_tools, lbl_weight

    # 1. Cartography Skill
    c_skill = API.GetSkill("Cartography")
    if c_skill:
        val = float(c_skill.Value)
        cap = float(c_skill.Cap)
        if lbl_skill:
            lbl_skill.Text = f"Cartography: {val:.1f} / {cap:.1f}"

        if last_cartography_skill is not None and val > last_cartography_skill:
            gain = val - last_cartography_skill
            API.SysMsg(f"[Cartography] Skill gained +{gain:.1f}! New skill: {val:.1f}")

            # Check for progression milestone
            old_rec, _ = get_recommended_item(last_cartography_skill)
            new_rec, _ = get_recommended_item(val)
            if new_rec != old_rec:
                API.SysMsg(f"[Cartography] *** Progression Milestone reached ({val:.1f})! ***")
                API.SysMsg(f"[Cartography] Recommended next map: '{new_rec}'.")
                API.SysMsg(f"[Cartography] Click 'Set Recipe' on the Gump to switch to '{new_rec}', or continue current recipe.")
                recommended_recipe_name = new_rec
                if lbl_recipe:
                    lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {new_rec})"

        last_cartography_skill = val

    # 2. Recipe
    if lbl_recipe:
        if current_recipe_name != recommended_recipe_name:
            lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {recommended_recipe_name})"
        else:
            lbl_recipe.Text = f"Recipe: {current_recipe_name}"

    # 3. Counts
    if lbl_counts:
        lbl_counts.Text = f"Crafted: {total_crafted} | Stored: {total_stored} | Trashed: {total_trashed} | Failed: {total_failed}"

    # 4. Blank Scroll Counts
    bp_scrolls = count_backpack_blank_scrolls()
    satchel_scrolls = count_satchel_blank_scrolls() if satchel_serial else 0
    satchel_label = f"{satchel_scrolls:,}" if satchel_serial else "N/A"
    if lbl_scrolls:
        lbl_scrolls.Text = f"Satchel: {satchel_label} | Backpack: {bp_scrolls}"

    # 5. Tool & Destination Status
    pens_cnt = count_mapmaker_pens()
    pens_str = f"Pens: {pens_cnt}"

    if storage_serial:
        dest_str = "Dest: Storage"
    elif trash_barrel_serial:
        dest_str = "Dest: Trash"
    else:
        dest_str = "Dest: Backpack"

    if lbl_tools:
        lbl_tools.Text = f"{pens_str} | {dest_str}"

    # 6. Weight
    if lbl_weight:
        cur_w = API.Player.Weight if API.Player and API.Player.Weight is not None else 0
        max_w = API.Player.WeightMax if API.Player and API.Player.WeightMax is not None else 0
        lbl_weight.Text = f"Weight: {cur_w} / {max_w}"


def on_pause_clicked() -> None:
    """Toggles pause/resume state."""
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Running")
    API.SysMsg("[Cartography] Script paused." if is_paused else "[Cartography] Script resumed.")


def on_stop_clicked() -> None:
    """Stops the script execution."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_satchel_clicked() -> None:
    """Allows player to target their resource satchel or container."""
    global satchel_serial
    API.SysMsg("[Cartography] Target your Resource Satchel / Supplies Container (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial and new_serial != API.Player.Serial:
        satchel_serial = new_serial
        API.SysMsg(f"[Cartography] Satchel updated: 0x{satchel_serial:X}")
        update_stats()
        if count_backpack_blank_scrolls() < MIN_BACKPACK_SCROLLS:
            restock_scrolls_from_satchel()
    else:
        API.SysMsg("[Cartography] Satchel targeting cleared.")
        satchel_serial = None
    update_stats()


def on_storage_clicked() -> None:
    """Allows player to target a container for completed maps."""
    global storage_serial
    API.SysMsg("[Cartography] Target your Map Storage Container / Box (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial and new_serial != API.Player.Serial:
        storage_serial = new_serial
        API.SysMsg(f"[Cartography] Storage container updated: 0x{storage_serial:X}")
    else:
        API.SysMsg("[Cartography] Storage container cleared.")
        storage_serial = None
    update_stats()


def on_trash_clicked() -> None:
    """Allows player to target a trash barrel / container."""
    global trash_barrel_serial
    API.SysMsg("[Cartography] Target your Trash Barrel (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial and new_serial != API.Player.Serial:
        trash_barrel_serial = new_serial
        API.SysMsg(f"[Cartography] Trash barrel updated: 0x{trash_barrel_serial:X}")
    else:
        API.SysMsg("[Cartography] Trash barrel cleared.")
        trash_barrel_serial = None
    update_stats()


def on_recipe_clicked() -> None:
    """Opens the Cartography craft gump to allow manually selecting a map recipe."""
    global is_paused, btn_pause
    pen = get_mapmaker_pen()
    if not pen:
        if not craft_pen_with_tinkering():
            API.SysMsg("[Cartography] No Mapmaker's Pen available to open craft menu!")
            return
        pen = get_mapmaker_pen()

    if pen:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused (Set Recipe)")
        API.SysMsg("[Cartography] Opening Cartography menu. Click your desired map once to craft it, then click 'Resume' on the Gump.")
        if API.HasGump():
            API.CloseGump()
            API.Pause(0.3)
        API.UseObject(pen)
    else:
        API.SysMsg("[Cartography] No Mapmaker's Pen available to open craft menu!")


def on_gump_disposed() -> None:
    global is_stopped
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


def create_control_gump() -> None:
    """Renders the FesterUO Cartography Trainer Gump."""
    global gump, lbl_status, lbl_skill, lbl_recipe, lbl_counts, lbl_scrolls, lbl_tools, lbl_weight
    global btn_pause, btn_recipe, btn_satchel, btn_storage, btn_trash, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 320, 245)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 320, 245)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Train Cartography", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status (hue 996)
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skill
    lbl_skill = API.Gumps.CreateGumpLabel("Cartography: -- / --", 996)
    lbl_skill.SetPos(10, 48)
    gump.Add(lbl_skill)

    # Recipe (gold hue 53)
    lbl_recipe = API.Gumps.CreateGumpLabel("Recipe: Initializing...", 53)
    lbl_recipe.SetPos(10, 68)
    gump.Add(lbl_recipe)

    # Counts
    lbl_counts = API.Gumps.CreateGumpLabel("Crafted: 0 | Stored: 0 | Trashed: 0 | Failed: 0", 996)
    lbl_counts.SetPos(10, 88)
    gump.Add(lbl_counts)

    # Blank scroll counts
    lbl_scrolls = API.Gumps.CreateGumpLabel("Satchel: 0 | Backpack: 0", 996)
    lbl_scrolls.SetPos(10, 108)
    gump.Add(lbl_scrolls)

    # Tools & Destination
    lbl_tools = API.Gumps.CreateGumpLabel("Pens: -- | Dest: --", 996)
    lbl_tools.SetPos(10, 128)
    gump.Add(lbl_tools)

    # Weight
    lbl_weight = API.Gumps.CreateGumpLabel("Weight: -- / --", 996)
    lbl_weight.SetPos(10, 148)
    gump.Add(lbl_weight)

    # Buttons Row 1: Pause, Set Recipe, Satchel
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 85, 22)
    btn_pause.SetPos(15, 175)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_recipe = API.Gumps.CreateSimpleButton("Set Recipe", 95, 22)
    btn_recipe.SetPos(110, 175)
    API.Gumps.AddControlOnClick(btn_recipe, on_recipe_clicked)
    gump.Add(btn_recipe)

    btn_satchel = API.Gumps.CreateSimpleButton("Satchel", 85, 22)
    btn_satchel.SetPos(215, 175)
    API.Gumps.AddControlOnClick(btn_satchel, on_satchel_clicked)
    gump.Add(btn_satchel)

    # Buttons Row 2: Storage, Trash Can, Stop
    btn_storage = API.Gumps.CreateSimpleButton("Storage", 85, 22)
    btn_storage.SetPos(15, 205)
    API.Gumps.AddControlOnClick(btn_storage, on_storage_clicked)
    gump.Add(btn_storage)

    btn_trash = API.Gumps.CreateSimpleButton("Trash Can", 95, 22)
    btn_trash.SetPos(110, 205)
    API.Gumps.AddControlOnClick(btn_trash, on_trash_clicked)
    gump.Add(btn_trash)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 85, 22)
    btn_stop.SetPos(215, 205)
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
# Helper Functions - Tools, Materials & Detection
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


def is_blank_scroll(item) -> bool:
    """Returns True if item is a blank scroll or blank map, not a completed/crafted map."""
    if not item or item.Graphic not in ALL_BLANK_MATERIALS:
        return False

    # Standard blank scrolls are always blank
    if item.Graphic in BLANK_SCROLL_GRAPHICS:
        return True

    # For 0x14EB / 0x14EC rolled maps
    name = str(getattr(item, "Name", "") or "").lower()
    if "blank" in name:
        return True

    if any(kw in name for kw in ["local", "city", "sea chart", "world", "detail", "map of"]):
        return False

    # In UO, blank items stack together; crafted maps never stack
    if (getattr(item, "Amount", 1) or 1) > 1:
        return True

    return True


def is_crafted_map(item) -> bool:
    """Returns True if item is a completed crafted map."""
    if not item:
        return False

    # Unrolled maps are always crafted
    if item.Graphic in {0x14ED, 0x14EE}:
        return True

    if item.Graphic in {0x14EB, 0x14EC}:
        name = str(getattr(item, "Name", "") or "").lower()
        if any(kw in name for kw in ["local", "city", "sea chart", "world", "detail", "map of"]):
            return True
        if "blank" in name:
            return False

    return False


def get_pen_info(item) -> Tuple[bool, str]:
    """
    Analyzes an item and returns (is_pen, pen_type).
    pen_type is 'mapmaker', 'scribe', or 'unknown'.
    Queries tooltip properties from the server if name is not yet cached.
    """
    if not item or item.Graphic not in PEN_GRAPHICS:
        return False, "none"

    name = str(getattr(item, "Name", "") or "").lower()

    if not any(kw in name for kw in ["map", "cartograph", "scribe", "inscript"]):
        props = str(API.ItemNameAndProps(item.Serial, wait=True, timeout=2) or "").lower()
        if props:
            name = f"{name} {props}"

    if "map" in name or "cartograph" in name:
        return True, "mapmaker"
    if "scribe" in name or "inscript" in name:
        return True, "scribe"

    return True, "unknown"


def is_valid_mapmaker_pen(item) -> bool:
    """
    Returns True ONLY if the pen is verified to be a Mapmaker's Pen and NEVER a Scribe's Pen.
    """
    global active_pen_serial
    if not item or item.Graphic not in PEN_GRAPHICS:
        return False

    # If this is our known active mapmaker pen, accept it
    if active_pen_serial and item.Serial == active_pen_serial:
        return True

    is_pen, p_type = get_pen_info(item)
    if not is_pen:
        return False

    # Strictly reject any Scribe's Pen!
    if p_type == "scribe":
        return False

    # Validated Mapmaker's Pen
    if p_type == "mapmaker":
        return True

    return False


def get_mapmaker_pen():
    """Finds a verified Mapmaker's Pen in player hands or backpack."""
    global active_pen_serial

    # 1. If active pen is known and still in player possession, use it
    if active_pen_serial:
        item = API.FindItem(active_pen_serial)
        if item and item.Graphic in PEN_GRAPHICS:
            is_pen, p_type = get_pen_info(item)
            if p_type != "scribe":
                return item
        active_pen_serial = None

    # 2. Check hands
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and is_valid_mapmaker_pen(item):
            active_pen_serial = item.Serial
            return item

    # 3. Check main backpack
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if is_valid_mapmaker_pen(item):
                active_pen_serial = item.Serial
                return item

    return None


def count_mapmaker_pens() -> int:
    """Counts usable Mapmaker's Pens, strictly excluding Scribe's Pens."""
    cnt = 0
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and is_valid_mapmaker_pen(item):
            cnt += 1

    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if is_valid_mapmaker_pen(item):
                cnt += 1
    return cnt


def count_backpack_blank_scrolls() -> int:
    """Counts blank scrolls / blank maps currently in the main backpack."""
    total = 0
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Serial != satchel_serial and is_blank_scroll(item):
                total += getattr(item, "Amount", 1) or 1
    return total


def count_satchel_blank_scrolls() -> int:
    """Counts blank scrolls / blank maps inside the designated resource satchel."""
    if not satchel_serial:
        return 0
    total = 0
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if items:
        for item in items:
            if is_blank_scroll(item):
                total += getattr(item, "Amount", 1) or 1
    return total


def get_satchel_blank_scrolls():
    """Finds the largest stack of blank scrolls inside the satchel."""
    if not satchel_serial:
        return None
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if not items:
        return None
    best_item = None
    best_amt = 0
    for item in items:
        if is_blank_scroll(item):
            amt = getattr(item, "Amount", 1) or 1
            if amt > best_amt:
                best_amt = amt
                best_item = item
    return best_item


def restock_scrolls_from_satchel() -> bool:
    """Pulls a batch of blank scrolls from the satchel into the main backpack."""
    if not satchel_serial:
        return False

    current_bp = count_backpack_blank_scrolls()
    if current_bp >= MIN_BACKPACK_SCROLLS and current_bp > 0:
        return True

    satchel_scroll_stack = get_satchel_blank_scrolls()
    if not satchel_scroll_stack:
        return False

    amt_available = getattr(satchel_scroll_stack, "Amount", 1) or 1
    amt_needed = max(RESTOCK_BATCH_SIZE, TARGET_BACKPACK_SCROLLS - current_bp)
    amt_to_move = min(amt_available, amt_needed)

    if amt_to_move <= 0:
        return False

    update_status(f"Restocking {amt_to_move} blank scrolls...")
    API.MoveItem(satchel_scroll_stack.Serial, API.Backpack, amt=amt_to_move)
    API.Pause(0.6)
    update_stats()
    return count_backpack_blank_scrolls() >= 1


def find_nearby_trash_barrel():
    """Finds a trash barrel within 3 tiles (searching ground items)."""
    ground_items = API.GetItemsOnGround(3)
    if ground_items:
        for item in ground_items:
            name = str(getattr(item, "Name", "") or "").lower()
            if "trash" in name:
                return item
            g = getattr(item, "Graphic", 0)
            if g in TRASH_BARREL_GRAPHICS:
                props = str(item.NameAndProps() if hasattr(item, "NameAndProps") else "").lower()
                if "trash" in props or "barrel" in props:
                    return item
    return None


def get_recommended_item(skill: float) -> Tuple[str, int]:
    """Returns optimal (map_name, blank_scroll_cost) for current skill level."""
    for min_sk, max_sk, name, cost in PROGRESSION_LADDER:
        if min_sk <= skill < max_sk:
            return name, cost
    return "World Map", 1


# ==============================================================================
# Tinkering Upkeep - Mapmaker's Pen Crafting
# ==============================================================================

def get_tinker_tool():
    """Finds a Tinker's Tool in player hands, backpack, or satchel."""
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
        items = API.ItemsInContainer(satchel_serial, recursive=True)
        if items:
            for item in items:
                if item.Graphic in TINKER_TOOL_GRAPHICS:
                    API.MoveItem(item.Serial, API.Backpack)
                    API.Pause(0.5)
                    return item
    return None


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


def count_satchel_ingots() -> int:
    """Counts regular iron ingots inside the resource satchel."""
    if not satchel_serial:
        return 0
    total = 0
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if items:
        for item in items:
            if item.Graphic == INGOT_GRAPHIC:
                hue = getattr(item, "Hue", 0) or 0
                if hue == IRON_INGOT_HUE:
                    total += getattr(item, "Amount", 1) or 1
    return total


def restock_ingots_from_satchel(amount: int = 4) -> bool:
    """Pulls iron ingots from the satchel to craft replacement pens."""
    if not satchel_serial:
        return False
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if not items:
        return False
    for item in items:
        if item.Graphic == INGOT_GRAPHIC and (getattr(item, "Hue", 0) or 0) == IRON_INGOT_HUE:
            amt_available = getattr(item, "Amount", 1) or 1
            amt_to_move = min(amt_available, amount)
            if amt_to_move > 0:
                API.MoveItem(item.Serial, API.Backpack, amt=amt_to_move)
                API.Pause(0.5)
                return count_backpack_ingots() >= 1
    return False


def deposit_ingots_to_satchel() -> None:
    """Deposits any leftover iron ingots from backpack back into the satchel."""
    if not satchel_serial:
        return
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not items:
        return
    for item in items:
        if item.Serial != satchel_serial and item.Graphic == INGOT_GRAPHIC:
            if (getattr(item, "Hue", 0) or 0) == IRON_INGOT_HUE:
                API.MoveItem(item.Serial, satchel_serial)
                API.Pause(0.5)


def craft_pen_with_tinkering() -> bool:
    """Crafts a replacement Mapmaker's Pen using Tinkering tools, iron ingots, and blank scrolls."""
    global tools_crafted, is_paused, btn_pause, active_pen_serial
    if not AUTO_CRAFT_PEN:
        return False

    tinker_tool = get_tinker_tool()
    if not tinker_tool:
        update_status("Need Tinker's Tool")
        API.SysMsg("[Cartography] No Tinker's Tool found in backpack or satchel to craft a new Mapmaker's Pen!")
        return False

    tool_name = "Mapmaker's Pen"

    total_ingots = count_backpack_ingots() + count_satchel_ingots()
    if total_ingots < 1:
        update_status("Out of Ingots")
        API.SysMsg(f"[Cartography] Not enough iron ingots in backpack or satchel to craft {tool_name} (need 1 ingot)!")
        return False

    if count_backpack_ingots() < 1:
        restock_ingots_from_satchel(4)

    # Mapmaker's pens require 1 blank scroll (or blank map) to tinker
    total_scrolls = count_backpack_blank_scrolls() + (count_satchel_blank_scrolls() if satchel_serial else 0)
    if total_scrolls < 1:
        update_status("Need Blank Scroll")
        API.SysMsg(f"[Cartography] Need at least 1 blank scroll to craft {tool_name}!")
        return False

    if count_backpack_blank_scrolls() < 1:
        restock_scrolls_from_satchel()

    update_status(f"Tinkering {tool_name}...")
    API.SysMsg(f"[Cartography] Crafting replacement {tool_name} via Tinkering (1 ingot + 1 scroll)...")

    # Close any currently open craft gump (e.g. stale Cartography gump from previous pen)
    if API.HasGump():
        API.CloseGump()
        API.Pause(0.3)

    bp_pens_before = {item.Serial for item in (API.ItemsInContainer(API.Backpack, recursive=False) or []) if item.Graphic in PEN_GRAPHICS}

    for attempt in range(1, MAX_TOOL_CRAFT_ATTEMPTS + 1):
        if API.StopRequested or is_stopped:
            return False

        if count_backpack_ingots() < 1:
            restock_ingots_from_satchel(4)

        if not API.HasGump():
            API.ClearJournal()
            API.UseObject(tinker_tool)
            if not API.WaitForGump(delay=2.5):
                API.SysMsg("[Cartography] Tinkering craft menu did not appear.")
                return False

        if API.GumpContains("haven't made anything") or API.GumpContains("not made anything"):
            API.SysMsg(f"[Cartography] Tinkering 'Make Last' is not set to {tool_name}.")
            API.SysMsg(f"[Cartography] In the open Tinkering menu: Click 'Tools' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            update_status(f"Craft 1 {tool_name} in menu")
            return True

        API.ClearJournal()
        API.ReplyGump(GUMP_BTN_MAKE_LAST)
        wait_with_ui(TOOL_CRAFT_DELAY)

        entries = API.GetJournalEntries(TOOL_CRAFT_DELAY + 0.5)
        j_text = [str(e.Text).lower() for e in entries] if entries else []

        if any("haven't made anything" in t or "have not made" in t for t in j_text):
            API.SysMsg(f"[Cartography] Tinkering 'Make Last' is not set to {tool_name}.")
            API.SysMsg(f"[Cartography] In the open Tinkering menu: Click 'Tools' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            update_status(f"Craft 1 {tool_name} in menu")
            return True

        bp_pens_after = {item.Serial for item in (API.ItemsInContainer(API.Backpack, recursive=False) or []) if item.Graphic in PEN_GRAPHICS}
        new_pens = bp_pens_after - bp_pens_before
        if new_pens:
            new_serial = list(new_pens)[0]
            active_pen_serial = new_serial
            tools_crafted += 1
            API.SysMsg(f"[Cartography] Successfully crafted new {tool_name} (0x{new_serial:X})!")
            update_stats()
            if API.HasGump():
                API.CloseGump()
                API.Pause(0.3)
            deposit_ingots_to_satchel()
            return True

        if any("you create" in t for t in j_text) and not new_pens:
            API.SysMsg(f"[Cartography] Tinkering 'Make Last' is currently set to a different item, not {tool_name}.")
            API.SysMsg(f"[Cartography] In the open Tinkering menu: Click 'Tools' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            update_status(f"Craft 1 {tool_name} in menu")
            return True

        if any("fail" in t or "lack the skill" in t for t in j_text):
            debug_msg(f"Tinkering {tool_name} attempt {attempt}/{MAX_TOOL_CRAFT_ATTEMPTS} failed, retrying...")
            API.Pause(0.5)

    if API.HasGump():
        API.CloseGump()
        API.Pause(0.3)

    deposit_ingots_to_satchel()
    API.SysMsg(f"[Cartography] Failed to auto-craft {tool_name} after {MAX_TOOL_CRAFT_ATTEMPTS} attempts.")
    API.SysMsg(f"[Cartography] In the Tinkering menu: Click 'Tools' -> '{tool_name}' once to prime Make Last, then click Resume on the Gump.")
    is_paused = True
    if btn_pause:
        btn_pause.SetText("Resume")
    update_status(f"Craft 1 {tool_name}")
    return True


# ==============================================================================
# Crafting Cycle
# ==============================================================================

def craft_cycle() -> bool:
    """Executes a single craft attempt, restocks blank scrolls, and stores/trashes crafted maps."""
    global total_crafted, total_failed, total_stored, total_trashed, current_recipe_name

    # 1. Check weight before crafting
    if is_overburdened():
        update_status("Overweight")
        API.SysMsg("[Cartography] Weight limit reached! Please lighten your backpack.")
        return False

    # 2. Get current skill and recipe info
    c_skill_obj = API.GetSkill("Cartography")
    current_skill = float(c_skill_obj.Value) if c_skill_obj else 0.0
    rec_name, scroll_cost = get_recommended_item(current_skill)

    # Stop if target skill reached
    if current_skill >= TARGET_SKILL:
        update_status("Target Skill Reached!")
        API.SysMsg(f"[Cartography] Congratulations! Target skill {TARGET_SKILL:.1f} reached!")
        return False

    # 3. Check total blank scrolls available
    total_scrolls = count_backpack_blank_scrolls() + (count_satchel_blank_scrolls() if satchel_serial else 0)
    if total_scrolls < 1:
        update_status("Out of Scrolls")
        API.SysMsg("[Cartography] Out of blank scrolls/maps in backpack and satchel!")
        return False

    # Maintain backpack blank scroll buffer if needed
    if not DIRECT_SATCHEL_CRAFTING and count_backpack_blank_scrolls() < MIN_BACKPACK_SCROLLS:
        restock_scrolls_from_satchel()

    # 4. Ensure Mapmaker's Pen is available
    pen = get_mapmaker_pen()
    if not pen:
        if not craft_pen_with_tinkering():
            update_status("No Pen")
            API.SysMsg("[Cartography] Out of Mapmaker's Pens! Please equip or carry a mapmaker's pen.")
            return False
        pen = get_mapmaker_pen()
        if not pen:
            return True

    # 5. Record pre-craft backpack state for serial diff detection
    bp_before = {item.Serial for item in (API.ItemsInContainer(API.Backpack, recursive=False) or [])}

    # 6. Open craft menu if needed
    if not API.HasGump():
        API.ClearJournal()
        API.UseObject(pen)
        if not API.WaitForGump(delay=2.5):
            debug_msg("Cartography craft menu did not appear.")
            return True

    # 7. Click Make Last
    API.ClearJournal()
    API.ReplyGump(GUMP_BTN_MAKE_LAST)
    wait_with_ui(CRAFT_DELAY)

    # 8. Analyze result from journal
    entries = API.GetJournalEntries(CRAFT_DELAY + 0.8)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    # Check if Make Last is uninitialized
    if any("haven't made anything" in t or "have not made" in t for t in j_text) or API.GumpContains("haven't made anything"):
        API.SysMsg("[Cartography] 'Make Last' is not set yet.")
        API.SysMsg(f"[Cartography] In the open Cartography menu: Click '{rec_name}' once to craft it, then click Resume on the Gump.")
        update_status(f"Prime '{rec_name}'")
        on_pause_clicked()
        return True

    # Check if missing blank scrolls
    if any("sufficient" in t or "enough" in t or "more scroll" in t or "more blank" in t for t in j_text) or API.InJournal("blank scroll") or API.InJournal("blank map") or API.InJournal("scroll"):
        if satchel_serial and count_satchel_blank_scrolls() >= 1:
            API.SysMsg("[Cartography] Server requires blank scrolls in root backpack. Restocking from satchel...")
            restock_scrolls_from_satchel()
            return True

    # Check craft success or failure
    success = any("you create" in t or "put the" in t or "put it into" in t or "draw" in t for t in j_text) or API.InJournal("you create")
    failed = any("you fail" in t or "failed" in t or "destroy" in t or "ruin" in t for t in j_text) or API.InJournal("you fail")

    # Detect newly crafted item via backpack serial diff
    bp_after = API.ItemsInContainer(API.Backpack, recursive=False) or []
    new_item = None
    for it in bp_after:
        if it.Serial not in bp_before:
            if it.Serial != satchel_serial and it.Serial != trash_barrel_serial and it.Serial != storage_serial:
                if it.Graphic not in PEN_GRAPHICS and it.Graphic not in TINKER_TOOL_GRAPHICS:
                    new_item = it
                    break

    # Also detect if any unstacked crafted map exists in backpack
    if not new_item:
        for it in bp_after:
            if it.Serial != satchel_serial and it.Serial != trash_barrel_serial and it.Serial != storage_serial:
                if is_crafted_map(it):
                    new_item = it
                    break

    if new_item:
        success = True

    if success:
        total_crafted += 1
        update_status("Crafted")
        update_stats()

        # Handle storage or trashing of crafted map
        if new_item:
            if storage_serial:
                update_status(f"Storing {new_item.Name or 'map'}...")
                API.MoveItem(new_item.Serial, storage_serial)
                API.Pause(0.4)
                total_stored += 1
                update_stats()
            elif trash_barrel_serial:
                update_status(f"Trashing {new_item.Name or 'map'}...")
                API.MoveItem(new_item.Serial, trash_barrel_serial)
                API.Pause(0.4)
                total_trashed += 1
                update_stats()

    elif failed:
        total_failed += 1
        update_status("Failed attempt")
        update_stats()

    return True


# ==============================================================================
# Script Initialization & Stop Hooks
# ==============================================================================

def on_stop() -> None:
    dispose_gump()
    API.SysMsg("[Cartography] Cartography trainer stopped.")

API.OnStop(on_stop)


def main():
    global satchel_serial, storage_serial, trash_barrel_serial, active_pen_serial
    global current_recipe_name, recommended_recipe_name

    API.SysMsg("=== FesterUO Cartography Trainer ===")

    # 1. Initial skill and recipe recommendation
    c_skill_obj = API.GetSkill("Cartography")
    current_skill = float(c_skill_obj.Value) if c_skill_obj else 0.0
    recommended_recipe_name, _ = get_recommended_item(current_skill)
    current_recipe_name = recommended_recipe_name

    # 2. Storage Setup (Container / Map Box)
    API.SysMsg("[Cartography] Target your Map Storage Container (or press ESC / target yourself to skip)...")
    s_serial = API.RequestTarget(timeout=6.0)
    if s_serial and s_serial != API.Player.Serial:
        storage_serial = s_serial
        API.SysMsg(f"[Cartography] Storage container set: 0x{storage_serial:X}")
    else:
        storage_serial = None
        API.SysMsg("[Cartography] No storage container selected.")

    # 3. Trash Barrel Setup (if storage not set, or for backup disposal)
    auto_barrel = find_nearby_trash_barrel()
    if auto_barrel:
        trash_barrel_serial = auto_barrel.Serial
        API.SysMsg(f"[Cartography] Auto-detected nearby Trash Barrel: 0x{trash_barrel_serial:X}")
    elif not storage_serial:
        API.SysMsg("[Cartography] Target your Trash Barrel (or press ESC / target yourself to keep maps in backpack)...")
        t_serial = API.RequestTarget(timeout=6.0)
        if t_serial and t_serial != API.Player.Serial:
            trash_barrel_serial = t_serial
            API.SysMsg(f"[Cartography] Trash barrel set: 0x{trash_barrel_serial:X}")
        else:
            trash_barrel_serial = None
            API.SysMsg("[Cartography] No trash barrel selected. Crafted maps will remain in backpack.")

    # 4. Satchel Setup
    API.SysMsg("[Cartography] Target your Resource Satchel for Blank Scrolls/Maps/Ingots (or press ESC for backpack only)...")
    sat_serial = API.RequestTarget(timeout=6.0)
    if sat_serial and sat_serial != API.Player.Serial:
        satchel_serial = sat_serial
        API.SysMsg(f"[Cartography] Satchel set: 0x{satchel_serial:X}")
    else:
        satchel_serial = None
        API.SysMsg("[Cartography] Using backpack resources only.")

    # 5. Check initial tool
    pen = get_mapmaker_pen()
    if not pen:
        API.SysMsg("[Cartography] No Mapmaker's Pen found. Attempting to auto-craft one via Tinkering...")
        if craft_pen_with_tinkering():
            pen = get_mapmaker_pen()

    if pen:
        active_pen_serial = pen.Serial
        API.SysMsg(f"[Cartography] Ready with Mapmaker's Pen: 0x{active_pen_serial:X}")
    else:
        API.SysMsg("[Cartography] No Mapmaker's Pen found! Please equip or carry a mapmaker's pen.")
        update_status("No Pen")

    # 6. Render Gump & initial stats
    create_control_gump()
    update_stats()

    # Initial check and restock of blank scrolls if needed
    if not DIRECT_SATCHEL_CRAFTING and count_backpack_blank_scrolls() < MIN_BACKPACK_SCROLLS:
        restock_scrolls_from_satchel()

    update_status("Running")
    API.SysMsg(f"[Cartography] Training started. Current skill: {current_skill:.1f} | Recommended: {recommended_recipe_name}")

    # 7. Main Training Loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        success = craft_cycle()
        if not success:
            break

        API.Pause(0.2)

    update_status("Finished")
    API.SysMsg("[Cartography] Training finished.")
    dispose_gump()


main()
