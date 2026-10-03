"""
TrainCooking.py - Automated Resource-Efficient Cooking Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Fully automated Cooking skill training script for TazUO featuring:
    - Optimal resource-efficient progression ladder from 0.0 to 100.0 Cooking:
        * 0.0 - 50.0:   Fish Steak / Cooked Ribs (1 raw fish steak / cut of ribs)
        * 50.0 - 65.0:  Dough / Bread Loaf (flour + water)
        * 65.0 - 80.0:  Pan of Cookies / Meat Pie (sweet dough / ribs)
        * 80.0 - 100.0: Baked Fruit Pie / Miso Soup / Apple Pie
    - Universal Crafting Engine with Dual Mode Support:
        * Craft Gump Mode (Default): Uses standard Cooking tools (Skillet, Flour Sifter, Rolling Pin)
          with high-speed "Make Last" crafting.
        * Direct Heat Source Mode: Automatically cooks raw food directly onto a targeted or auto-detected
          heat source (Campfire, Oven, Stove, Forge, Heating Stand).
    - Milestone Announcements & "Set Recipe" Manual Override:
        * Proactively notifies the player when reaching a skill threshold to recommend the next recipe.
        * Includes an interactive "Set Recipe" button allowing players to manually select and prime any
          recipe (Fish Steaks, Ribs, Pies, Bread, Miso Soup, etc.) from the open craft menu.
    - Dual Crafted Food Management (Storage & Trash Disposal):
        * Storage Container: Prompts player to target a food chest, cooler, or pouch to preserve cooked food.
        * Trash Barrel: Auto-detects nearby Trash Barrels or allows targeting one to discard cooked food,
          preventing overweight and backpack clutter.
        * Automatically deposits cooked food via backpack serial diff and graphic detection.
    - Resource Satchel Integration:
        * Direct Satchel Crafting support (if server allows crafting directly from satchels).
        * Restock support: Maintains a lightweight buffer of raw ingredients in backpack, pulling fresh
          batches from the satchel as needed.
    - Tool Upkeep via Tinkering:
        * Detects Skillets in backpack or hands.
        * If skillets break and Tinkering tools + iron ingots are available, attempts to auto-craft replacement
          Skillets (2 iron ingots) on the fly.
    - Heat Source Awareness:
        * Auto-detects nearby Campfires, Ovens, Stoves, Hearths, Forges, or Heating Stands.
    - Interactive Control Gump:
        * Real-time training status, live Cooking skill level and cap with gain tracking,
          Crafted / Stored / Trashed / Failed counters, Satchel & Backpack ingredient counts,
          Tool & Destination indicators, and live Weight indicator.
        * Interactive Pause / Resume, Set Recipe, Satchel, Storage, Trash Can, and Stop buttons.
"""

from typing import List, Tuple, Optional, Set
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Target Cooking skill to stop training (e.g. 100.0 for GM)
TARGET_SKILL = 100.0

# Direct Satchel Crafting (crafts directly from resource satchel without pulling to backpack)
DIRECT_SATCHEL_CRAFTING = True

# Working buffer of raw ingredients maintained in main backpack if direct crafting is not supported
MIN_BACKPACK_INGREDIENTS = 0 if DIRECT_SATCHEL_CRAFTING else 20
TARGET_BACKPACK_INGREDIENTS = 50
RESTOCK_BATCH_SIZE = 50

# Delays in seconds
CRAFT_DELAY = 1.3
TOOL_CRAFT_DELAY = 1.2
DIRECT_COOK_DELAY = 1.5

# Server Craft Gump button IDs (standard ServUO / RunUO)
GUMP_BTN_MAKE_LAST = 21  # Universal "Make Last" button

# Tool upkeep via Tinkering
AUTO_CRAFT_TOOL = True
MAX_TOOL_CRAFT_ATTEMPTS = 8

# Enable verbose debug messages in client console
DEBUG = False


# ==============================================================================
# Item & Graphic Definitions
# ==============================================================================

# Cooking tools (Skillet, Flour Sifter, Rolling Pin)
SKILLET_GRAPHICS = {0x097F}
FLOUR_SIFTER_GRAPHICS = {0x103E}
ROLLING_PIN_GRAPHICS = {0x1043}
ALL_COOKING_TOOLS = SKILLET_GRAPHICS | FLOUR_SIFTER_GRAPHICS | ROLLING_PIN_GRAPHICS

# Raw food graphics (for direct cooking and inventory counting)
RAW_FOOD_GRAPHICS = {
    0x097A,  # Raw Fish Steak
    0x09F1,  # Cut of Raw Ribs
    0x09B9,  # Raw Bird
    0x1607,  # Raw Chicken Leg
    0x1609,  # Raw Leg of Lamb
    0x09B5,  # Eggs
    0x103D,  # Dough
    0x103C,  # Sweet Dough
    0x1042,  # Unbaked Pie / Cobbler
}

# Cooked food graphics
COOKED_FOOD_GRAPHICS = {
    0x097B,  # Cooked Fish Steak
    0x09F2,  # Cooked Cut of Ribs
    0x09BA,  # Cooked Bird
    0x1608,  # Cooked Chicken Leg
    0x160A,  # Cooked Leg of Lamb
    0x09B6,  # Fried Eggs
    0x103B, 0x098C,  # Bread Loaf
    0x09E9,  # Cake
    0x160C,  # Pan of Cookies
    0x1041,  # Baked Pie / Cobbler
    0x284C,  # Miso Soup
}

# Heat source graphics (Ovens, Campfires, Forges, Heating Stands, Hearths)
HEAT_SOURCE_GRAPHICS = {
    # Campfires & fires
    0x0DE3, 0x0DE9, 0x0FAC,
    # Ovens, stoves, hearths
    0x0461, 0x0462, 0x0463, 0x0464, 0x0465, 0x0466,
    0x092B, 0x092C, 0x092D, 0x092E, 0x092F, 0x0930,
    0x0DE7, 0x0DE8,
    # Heating stands
    0x1849, 0x184A, 0x184B, 0x184C, 0x184D, 0x184E, 0x184F, 0x1850,
    # Fireplaces / Firepits
    0x0475, 0x047B, 0x0482, 0x0489,
    # Braziers
    0x0E31, 0x0E32, 0x0E33,
    # Forges
    0x0FB1, 0x197A, 0x197B, 0x197C, 0x197D, 0x197E, 0x197F,
    0x1980, 0x1981, 0x1982, 0x1983, 0x1984, 0x1985,
    0x1986, 0x1987, 0x1988, 0x1989, 0x198A, 0x198B,
}

# Tinkering tools & materials for auto-crafting skillets
TINKER_TOOL_GRAPHICS = {0x1EB8, 0x1EB9, 0x1EBC, 0x1EBD}
INGOT_GRAPHIC = 0x1BF2
IRON_INGOT_HUE = 0

# Trash barrel graphics
TRASH_BARREL_GRAPHICS = {0x0E77}

# Optimal Cooking Progression Ladder: (min_skill, max_skill, item_name, raw_ingredient)
PROGRESSION_LADDER: List[Tuple[float, float, str, str]] = [
    (0.0, 50.0, "Fish Steak", "Raw Fish Steak / Raw Ribs"),
    (50.0, 65.0, "Dough / Bread Loaf", "Flour + Water"),
    (65.0, 80.0, "Pan of Cookies / Meat Pie", "Sweet Dough / Ribs"),
    (80.0, 100.0, "Baked Fruit Pie / Miso Soup", "Fruit / Miso / Dough"),
]


# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_recipe = None
lbl_counts = None
lbl_ingredients = None
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
heat_source_serial: Optional[int] = None

is_paused: bool = False
is_stopped: bool = False
use_direct_mode: bool = False

total_crafted: int = 0
total_stored: int = 0
total_trashed: int = 0
total_failed: int = 0
tools_crafted: int = 0

last_cooking_skill: Optional[float] = None
current_recipe_name: str = "Make Last"
recommended_recipe_name: str = "Fish Steak"


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
    global last_cooking_skill, recommended_recipe_name
    global lbl_skill, lbl_recipe, lbl_counts, lbl_ingredients, lbl_tools, lbl_weight

    # 1. Cooking Skill
    c_skill = API.GetSkill("Cooking")
    if c_skill:
        val = float(c_skill.Value)
        cap = float(c_skill.Cap)
        if lbl_skill:
            lbl_skill.Text = f"Cooking: {val:.1f} / {cap:.1f}"

        if last_cooking_skill is not None and val > last_cooking_skill:
            gain = val - last_cooking_skill
            API.SysMsg(f"[Cooking] Skill gained +{gain:.1f}! New skill: {val:.1f}")

            # Check for progression milestone
            old_rec, _ = get_recommended_item(last_cooking_skill)
            new_rec, _ = get_recommended_item(val)
            if new_rec != old_rec:
                API.SysMsg(f"[Cooking] *** Progression Milestone reached ({val:.1f})! ***")
                API.SysMsg(f"[Cooking] Recommended next recipe: '{new_rec}'.")
                API.SysMsg(f"[Cooking] Click 'Set Recipe' on the Gump to switch to '{new_rec}', or continue current recipe.")
                recommended_recipe_name = new_rec
                if lbl_recipe:
                    lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {new_rec})"

        last_cooking_skill = val

    # 2. Recipe
    if lbl_recipe:
        if current_recipe_name != recommended_recipe_name:
            lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {recommended_recipe_name})"
        else:
            lbl_recipe.Text = f"Recipe: {current_recipe_name}"

    # 3. Counts
    if lbl_counts:
        lbl_counts.Text = f"Crafted: {total_crafted} | Stored: {total_stored} | Trashed: {total_trashed} | Failed: {total_failed}"

    # 4. Ingredients Counts
    bp_ing = count_backpack_raw_food()
    satchel_ing = count_satchel_raw_food() if satchel_serial else 0
    satchel_label = f"{satchel_ing:,}" if satchel_serial else "N/A"
    if lbl_ingredients:
        lbl_ingredients.Text = f"Satchel: {satchel_label} | Backpack: {bp_ing}"

    # 5. Tool & Destination Status
    tools_cnt = count_cooking_tools()
    mode_str = "Direct" if use_direct_mode else f"Tools: {tools_cnt}"

    if storage_serial:
        dest_str = "Dest: Storage"
    elif trash_barrel_serial:
        dest_str = "Dest: Trash"
    else:
        dest_str = "Dest: Backpack"

    if lbl_tools:
        lbl_tools.Text = f"{mode_str} | {dest_str}"

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
    API.SysMsg("[Cooking] Script paused." if is_paused else "[Cooking] Script resumed.")


def on_stop_clicked() -> None:
    """Stops the script execution."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_satchel_clicked() -> None:
    """Allows player to target their resource satchel or container."""
    global satchel_serial
    API.SysMsg("[Cooking] Target your Resource Satchel / Ingredients Container (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial and new_serial != API.Player.Serial:
        satchel_serial = new_serial
        API.SysMsg(f"[Cooking] Satchel updated: 0x{satchel_serial:X}")
        update_stats()
        if count_backpack_raw_food() < MIN_BACKPACK_INGREDIENTS:
            restock_raw_food_from_satchel()
    else:
        API.SysMsg("[Cooking] Satchel targeting cleared.")
        satchel_serial = None
    update_stats()


def on_storage_clicked() -> None:
    """Allows player to target a container for completed cooked food."""
    global storage_serial
    API.SysMsg("[Cooking] Target your Cooked Food Storage Container (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial and new_serial != API.Player.Serial:
        storage_serial = new_serial
        API.SysMsg(f"[Cooking] Storage container updated: 0x{storage_serial:X}")
    else:
        API.SysMsg("[Cooking] Storage container cleared.")
        storage_serial = None
    update_stats()


def on_trash_clicked() -> None:
    """Allows player to target a trash barrel / container."""
    global trash_barrel_serial
    API.SysMsg("[Cooking] Target your Trash Barrel (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial and new_serial != API.Player.Serial:
        trash_barrel_serial = new_serial
        API.SysMsg(f"[Cooking] Trash barrel updated: 0x{trash_barrel_serial:X}")
    else:
        API.SysMsg("[Cooking] Trash barrel cleared.")
        trash_barrel_serial = None
    update_stats()


def on_recipe_clicked() -> None:
    """Opens the Cooking craft gump to allow manually selecting a recipe."""
    global is_paused, btn_pause
    tool = get_cooking_tool()
    if tool:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused (Set Recipe)")
        API.SysMsg("[Cooking] Opening Cooking menu. Click your desired recipe once to craft it, then click 'Resume' on the Gump.")
        API.UseObject(tool)
    else:
        API.SysMsg("[Cooking] No Cooking Tool (Skillet, Flour Sifter, Rolling Pin) available to open craft menu!")


def on_gump_disposed() -> None:
    global is_stopped
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


def create_control_gump() -> None:
    """Renders the FesterUO Cooking Trainer Gump."""
    global gump, lbl_status, lbl_skill, lbl_recipe, lbl_counts, lbl_ingredients, lbl_tools, lbl_weight
    global btn_pause, btn_recipe, btn_satchel, btn_storage, btn_trash, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 320, 245)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 320, 245)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Train Cooking", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status (hue 996)
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skill
    lbl_skill = API.Gumps.CreateGumpLabel("Cooking: -- / --", 996)
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

    # Ingredients counts
    lbl_ingredients = API.Gumps.CreateGumpLabel("Satchel: 0 | Backpack: 0", 996)
    lbl_ingredients.SetPos(10, 108)
    gump.Add(lbl_ingredients)

    # Tools & Destination
    lbl_tools = API.Gumps.CreateGumpLabel("Tools: -- | Dest: --", 996)
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


def get_cooking_tool():
    """Finds a usable Cooking Tool (Skillet, Flour Sifter, Rolling Pin) in hands or backpack."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in ALL_COOKING_TOOLS:
            return item

    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        # Prefer Skillet
        for item in items:
            if item.Graphic in SKILLET_GRAPHICS:
                return item
        for item in items:
            if item.Graphic in ALL_COOKING_TOOLS:
                return item
    return None


def count_cooking_tools() -> int:
    """Counts usable cooking tools."""
    cnt = 0
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in ALL_COOKING_TOOLS:
            cnt += 1

    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Graphic in ALL_COOKING_TOOLS:
                cnt += 1
    return cnt


def find_nearby_heat_source():
    """Finds a heat source (Oven, Campfire, Forge, Heating Stand) within 3 tiles."""
    ground_items = API.GetItemsOnGround(3)
    if ground_items:
        for item in ground_items:
            if item.Graphic in HEAT_SOURCE_GRAPHICS:
                return item
            name = str(getattr(item, "Name", "") or "").lower()
            if any(kw in name for kw in ["fire", "oven", "stove", "forge", "hearth", "heating stand", "brazier"]):
                return item
    return None


def find_backpack_heat_source():
    """Checks if player is carrying a portable Heating Stand in their backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=True)
    if items:
        for item in items:
            if item.Graphic in {0x1849, 0x184A, 0x184B, 0x184C, 0x184D, 0x184E, 0x184F, 0x1850}:
                return item
    return None


def count_backpack_raw_food() -> int:
    """Counts raw food items currently in the main backpack."""
    total = 0
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Serial != satchel_serial and item.Graphic in RAW_FOOD_GRAPHICS:
                total += getattr(item, "Amount", 1) or 1
    return total


def count_satchel_raw_food() -> int:
    """Counts raw food items inside the designated resource satchel."""
    if not satchel_serial:
        return 0
    total = 0
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if items:
        for item in items:
            if item.Graphic in RAW_FOOD_GRAPHICS:
                total += getattr(item, "Amount", 1) or 1
    return total


def get_satchel_raw_food():
    """Finds the largest stack of raw food inside the satchel."""
    if not satchel_serial:
        return None
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if not items:
        return None
    best_item = None
    best_amt = 0
    for item in items:
        if item.Graphic in RAW_FOOD_GRAPHICS:
            amt = getattr(item, "Amount", 1) or 1
            if amt > best_amt:
                best_amt = amt
                best_item = item
    return best_item


def get_backpack_raw_food():
    """Finds a stack of raw food in the main backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Serial != satchel_serial and item.Graphic in RAW_FOOD_GRAPHICS:
                return item
    return None


def restock_raw_food_from_satchel() -> bool:
    """Pulls a batch of raw food from the satchel into the main backpack."""
    if not satchel_serial:
        return False

    current_bp = count_backpack_raw_food()
    if current_bp >= MIN_BACKPACK_INGREDIENTS and current_bp > 0:
        return True

    satchel_food = get_satchel_raw_food()
    if not satchel_food:
        return False

    amt_available = getattr(satchel_food, "Amount", 1) or 1
    amt_needed = max(RESTOCK_BATCH_SIZE, TARGET_BACKPACK_INGREDIENTS - current_bp)
    amt_to_move = min(amt_available, amt_needed)

    if amt_to_move <= 0:
        return False

    update_status(f"Restocking {amt_to_move} ingredients...")
    API.MoveItem(satchel_food.Serial, API.Backpack, amt=amt_to_move)
    API.Pause(0.6)
    update_stats()
    return count_backpack_raw_food() >= 1


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


def get_recommended_item(skill: float) -> Tuple[str, str]:
    """Returns optimal (recipe_name, ingredient_info) for current skill level."""
    for min_sk, max_sk, name, ing in PROGRESSION_LADDER:
        if min_sk <= skill < max_sk:
            return name, ing
    return "Baked Fruit Pie / Miso Soup", "Fruit / Miso / Dough"


# ==============================================================================
# Tinkering Upkeep - Skillet Crafting
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
    """Pulls iron ingots from the satchel to craft replacement skillets."""
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


def craft_skillet_with_tinkering() -> bool:
    """Crafts a replacement Skillet using Tinkering tools and iron ingots."""
    global tools_crafted, is_paused, btn_pause
    if not AUTO_CRAFT_TOOL:
        return False

    tinker_tool = get_tinker_tool()
    if not tinker_tool:
        update_status("Need Tinker's Tool")
        API.SysMsg("[Cooking] No Tinker's Tool found in backpack or satchel to craft a new Skillet!")
        return False

    tool_name = "Skillet"

    total_ingots = count_backpack_ingots() + count_satchel_ingots()
    if total_ingots < 2:
        update_status("Out of Ingots")
        API.SysMsg(f"[Cooking] Not enough iron ingots in backpack or satchel to craft {tool_name} (need 2 ingots)!")
        return False

    if count_backpack_ingots() < 2:
        restock_ingots_from_satchel(4)

    update_status(f"Tinkering {tool_name}...")
    API.SysMsg(f"[Cooking] Crafting replacement {tool_name} via Tinkering (2 ingots)...")

    count_before = count_cooking_tools()

    for attempt in range(1, MAX_TOOL_CRAFT_ATTEMPTS + 1):
        if API.StopRequested or is_stopped:
            return False

        if count_backpack_ingots() < 2:
            restock_ingots_from_satchel(4)

        if not API.HasGump():
            API.ClearJournal()
            API.UseObject(tinker_tool)
            if not API.WaitForGump(delay=2.5):
                API.SysMsg("[Cooking] Tinkering craft menu did not appear.")
                return False

        if API.GumpContains("haven't made anything") or API.GumpContains("not made anything"):
            API.SysMsg(f"[Cooking] Tinkering 'Make Last' is not set to {tool_name}.")
            API.SysMsg(f"[Cooking] In the open Tinkering menu: Click 'Utensils' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
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
            API.SysMsg(f"[Cooking] Tinkering 'Make Last' is not set to {tool_name}.")
            API.SysMsg(f"[Cooking] In the open Tinkering menu: Click 'Utensils' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            update_status(f"Craft 1 {tool_name} in menu")
            return True

        count_after = count_cooking_tools()
        if count_after > count_before or get_cooking_tool() is not None:
            tools_crafted += 1
            API.SysMsg(f"[Cooking] Successfully crafted new {tool_name}!")
            update_stats()
            if API.HasGump():
                API.ReplyGump(0)
                API.Pause(0.3)
            deposit_ingots_to_satchel()
            return True

        if any("you create" in t for t in j_text) and count_after <= count_before:
            API.SysMsg(f"[Cooking] Tinkering 'Make Last' is currently set to a different item, not {tool_name}.")
            API.SysMsg(f"[Cooking] In the open Tinkering menu: Click 'Utensils' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            update_status(f"Craft 1 {tool_name} in menu")
            return True

        if any("fail" in t or "lack the skill" in t for t in j_text):
            debug_msg(f"Tinkering {tool_name} attempt {attempt}/{MAX_TOOL_CRAFT_ATTEMPTS} failed, retrying...")
            API.Pause(0.5)

    if API.HasGump():
        API.ReplyGump(0)
        API.Pause(0.3)

    deposit_ingots_to_satchel()
    API.SysMsg(f"[Cooking] Failed to auto-craft {tool_name} after {MAX_TOOL_CRAFT_ATTEMPTS} attempts.")
    API.SysMsg(f"[Cooking] In the Tinkering menu: Click 'Utensils' -> '{tool_name}' once to prime Make Last, then click Resume on the Gump.")
    is_paused = True
    if btn_pause:
        btn_pause.SetText("Resume")
    update_status(f"Craft 1 {tool_name}")
    return True


# ==============================================================================
# Crafting Cycle
# ==============================================================================

def craft_cycle() -> bool:
    """Executes a single craft attempt, restocks ingredients, and stores/trashes cooked food."""
    global total_crafted, total_failed, total_stored, total_trashed, current_recipe_name

    # 1. Check weight before crafting
    if is_overburdened():
        update_status("Overweight")
        API.SysMsg("[Cooking] Weight limit reached! Please lighten your backpack.")
        return False

    # 2. Get current skill and recipe info
    c_skill_obj = API.GetSkill("Cooking")
    current_skill = float(c_skill_obj.Value) if c_skill_obj else 0.0
    rec_name, ing_info = get_recommended_item(current_skill)

    # Stop if target skill reached
    if current_skill >= TARGET_SKILL:
        update_status("Target Skill Reached!")
        API.SysMsg(f"[Cooking] Congratulations! Target skill {TARGET_SKILL:.1f} reached!")
        return False

    # 3. Direct Heat Source Cooking Mode (if enabled or no craft gump tool available)
    if use_direct_mode:
        return direct_cook_cycle()

    # 4. Craft Gump Mode: Ensure Cooking Tool is available
    tool = get_cooking_tool()
    if not tool:
        if not craft_skillet_with_tinkering():
            # If cannot craft, check if direct mode is possible
            raw_food = get_backpack_raw_food()
            if raw_food and (heat_source_serial or find_nearby_heat_source() or find_backpack_heat_source()):
                API.SysMsg("[Cooking] No Cooking Tool found. Switching to Direct Heat Source cooking mode.")
                return direct_cook_cycle()
            update_status("No Cooking Tool")
            API.SysMsg("[Cooking] Out of Cooking Tools (Skillet, Flour Sifter, Rolling Pin)!")
            return False
        tool = get_cooking_tool()
        if not tool:
            return True

    # 5. Maintain backpack ingredient buffer if needed
    if not DIRECT_SATCHEL_CRAFTING and count_backpack_raw_food() < MIN_BACKPACK_INGREDIENTS:
        restock_raw_food_from_satchel()

    # 6. Record pre-craft backpack state for serial and amount diff detection
    bp_before = {item.Serial: getattr(item, "Amount", 1) or 1 for item in (API.ItemsInContainer(API.Backpack, recursive=False) or [])}

    # 7. Open craft menu if needed
    if not API.HasGump():
        API.ClearJournal()
        API.UseObject(tool)
        if not API.WaitForGump(delay=2.5):
            debug_msg("Cooking craft menu did not appear.")
            return True

    # 8. Click Make Last
    API.ClearJournal()
    API.ReplyGump(GUMP_BTN_MAKE_LAST)
    wait_with_ui(CRAFT_DELAY)

    # 9. Analyze result from journal
    entries = API.GetJournalEntries(CRAFT_DELAY + 0.8)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    # Check if Make Last is uninitialized
    if any("haven't made anything" in t or "have not made" in t for t in j_text) or API.GumpContains("haven't made anything"):
        API.SysMsg("[Cooking] 'Make Last' is not set yet.")
        API.SysMsg(f"[Cooking] In the open Cooking menu: Click '{rec_name}' once to craft it, then click Resume on the Gump.")
        update_status(f"Prime '{rec_name}'")
        on_pause_clicked()
        return True

    # Check if missing ingredients
    if any("insufficient" in t or "not enough" in t or "need more" in t for t in j_text):
        if satchel_serial and count_satchel_raw_food() >= 1:
            API.SysMsg("[Cooking] Server requires ingredients in root backpack. Restocking from satchel...")
            restock_raw_food_from_satchel()
            return True
        else:
            update_status("Out of Ingredients")
            API.SysMsg("[Cooking] Out of required ingredients in backpack and satchel!")
            return False

    # Check craft success or failure
    success = any("you create" in t or "put the" in t or "put it into" in t or "bake" in t or "cook" in t for t in j_text) or API.InJournal("you create")
    failed = any("you fail" in t or "failed" in t or "ruin" in t or "destroy" in t or "burn" in t for t in j_text) or API.InJournal("you fail")

    # Detect newly crafted food via backpack serial diff or stack increase
    bp_after = API.ItemsInContainer(API.Backpack, recursive=False) or []
    new_item = None
    for it in bp_after:
        if it.Serial not in bp_before:
            if it.Serial != satchel_serial and it.Serial != trash_barrel_serial and it.Serial != storage_serial:
                if it.Graphic not in ALL_COOKING_TOOLS and it.Graphic not in TINKER_TOOL_GRAPHICS:
                    new_item = it
                    break
        elif (getattr(it, "Amount", 1) or 1) > bp_before.get(it.Serial, 0):
            if it.Graphic in COOKED_FOOD_GRAPHICS:
                new_item = it
                break

    if new_item:
        success = True

    if success:
        total_crafted += 1
        update_status("Crafted")
        update_stats()

        # Handle storage or trashing of cooked food
        if new_item:
            if storage_serial:
                update_status(f"Storing {new_item.Name or 'food'}...")
                API.MoveItem(new_item.Serial, storage_serial)
                API.Pause(0.4)
                total_stored += 1
                update_stats()
            elif trash_barrel_serial:
                update_status(f"Trashing {new_item.Name or 'food'}...")
                API.MoveItem(new_item.Serial, trash_barrel_serial)
                API.Pause(0.4)
                total_trashed += 1
                update_stats()

    elif failed:
        total_failed += 1
        update_status("Failed attempt")
        update_stats()

    return True


def direct_cook_cycle() -> bool:
    """Executes a single direct cooking attempt by using raw food directly on a heat source."""
    global total_crafted, total_failed, total_stored, total_trashed, heat_source_serial

    raw_food = get_backpack_raw_food()
    if not raw_food:
        if satchel_serial and restock_raw_food_from_satchel():
            raw_food = get_backpack_raw_food()
        if not raw_food:
            update_status("Out of Raw Food")
            API.SysMsg("[Cooking] Out of raw food to cook in backpack and satchel!")
            return False

    # Find heat source
    heat_source = None
    if heat_source_serial:
        heat_source = API.FindItem(heat_source_serial)
    if not heat_source:
        heat_source = find_nearby_heat_source() or find_backpack_heat_source()
        if heat_source:
            heat_source_serial = heat_source.Serial

    if not heat_source:
        update_status("Need Heat Source")
        API.SysMsg("[Cooking] No heat source (Campfire, Oven, Stove, Forge, Heating Stand) nearby or targeted!")
        return False

    bp_before = {item.Serial: getattr(item, "Amount", 1) or 1 for item in (API.ItemsInContainer(API.Backpack, recursive=False) or [])}

    API.ClearJournal()
    API.UseObject(raw_food.Serial)
    if not API.WaitForTarget(delay=1.5):
        debug_msg("Direct cook targeting cursor did not appear.")
        return True

    API.Target(heat_source.Serial)
    wait_with_ui(DIRECT_COOK_DELAY)

    entries = API.GetJournalEntries(DIRECT_COOK_DELAY + 0.5)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    success = any("you cook" in t or "you create" in t or "taste delicious" in t or "put the" in t for t in j_text) or API.InJournal("cook")
    failed = any("you fail" in t or "failed" in t or "burn" in t or "ruin" in t for t in j_text) or API.InJournal("fail") or API.InJournal("burn")

    bp_after = API.ItemsInContainer(API.Backpack, recursive=False) or []
    new_item = None
    for it in bp_after:
        if it.Serial not in bp_before:
            if it.Serial != satchel_serial and it.Serial != trash_barrel_serial and it.Serial != storage_serial:
                new_item = it
                break
        elif (getattr(it, "Amount", 1) or 1) > bp_before.get(it.Serial, 0):
            if it.Graphic in COOKED_FOOD_GRAPHICS:
                new_item = it
                break

    if new_item:
        success = True

    if success:
        total_crafted += 1
        update_status("Cooked")
        update_stats()

        if new_item:
            if storage_serial:
                update_status(f"Storing {new_item.Name or 'food'}...")
                API.MoveItem(new_item.Serial, storage_serial)
                API.Pause(0.4)
                total_stored += 1
                update_stats()
            elif trash_barrel_serial:
                update_status(f"Trashing {new_item.Name or 'food'}...")
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
    API.SysMsg("[Cooking] Cooking trainer stopped.")

API.OnStop(on_stop)


def main():
    global satchel_serial, storage_serial, trash_barrel_serial, heat_source_serial
    global current_recipe_name, recommended_recipe_name, use_direct_mode

    API.SysMsg("=== FesterUO Cooking Trainer ===")

    # 1. Initial skill and recipe recommendation
    c_skill_obj = API.GetSkill("Cooking")
    current_skill = float(c_skill_obj.Value) if c_skill_obj else 0.0
    recommended_recipe_name, _ = get_recommended_item(current_skill)
    current_recipe_name = recommended_recipe_name

    # 2. Storage Setup (Container for Cooked Food)
    API.SysMsg("[Cooking] Target your Cooked Food Storage Container (or press ESC / target yourself to skip)...")
    s_serial = API.RequestTarget(timeout=6.0)
    if s_serial and s_serial != API.Player.Serial:
        storage_serial = s_serial
        API.SysMsg(f"[Cooking] Storage container set: 0x{storage_serial:X}")
    else:
        storage_serial = None
        API.SysMsg("[Cooking] No storage container selected.")

    # 3. Trash Barrel Setup (if storage not set, or for backup disposal)
    auto_barrel = find_nearby_trash_barrel()
    if auto_barrel:
        trash_barrel_serial = auto_barrel.Serial
        API.SysMsg(f"[Cooking] Auto-detected nearby Trash Barrel: 0x{trash_barrel_serial:X}")
    elif not storage_serial:
        API.SysMsg("[Cooking] Target your Trash Barrel (or press ESC / target yourself to keep food in backpack)...")
        t_serial = API.RequestTarget(timeout=6.0)
        if t_serial and t_serial != API.Player.Serial:
            trash_barrel_serial = t_serial
            API.SysMsg(f"[Cooking] Trash barrel set: 0x{trash_barrel_serial:X}")
        else:
            trash_barrel_serial = None
            API.SysMsg("[Cooking] No trash barrel selected. Cooked food will remain in backpack.")

    # 4. Satchel Setup
    API.SysMsg("[Cooking] Target your Resource Satchel for Raw Food/Ingredients (or press ESC for backpack only)...")
    sat_serial = API.RequestTarget(timeout=6.0)
    if sat_serial and sat_serial != API.Player.Serial:
        satchel_serial = sat_serial
        API.SysMsg(f"[Cooking] Satchel set: 0x{satchel_serial:X}")
    else:
        satchel_serial = None
        API.SysMsg("[Cooking] Using backpack resources only.")

    # 5. Heat Source Check
    heat_source = find_nearby_heat_source() or find_backpack_heat_source()
    if heat_source:
        heat_source_serial = heat_source.Serial
        h_name = str(getattr(heat_source, "Name", "") or "Heat Source")
        API.SysMsg(f"[Cooking] Auto-detected Heat Source: 0x{heat_source_serial:X} ({h_name}).")
    else:
        API.SysMsg("[Cooking] Note: Most recipes require being near a heat source (Oven, Stove, Campfire, Forge, or Heating Stand).")

    # 6. Check Cooking Tool / Mode
    tool = get_cooking_tool()
    if tool:
        use_direct_mode = False
        t_name = str(getattr(tool, "Name", "") or "Cooking Tool")
        API.SysMsg(f"[Cooking] Using Craft Gump with tool: {t_name}")
    else:
        raw_food = get_backpack_raw_food()
        if raw_food and heat_source:
            use_direct_mode = True
            API.SysMsg("[Cooking] No cooking tool found. Direct Heat Source cooking mode active.")
        else:
            use_direct_mode = False
            API.SysMsg("[Cooking] No Cooking Tool found. Will attempt to craft Skillet via Tinkering.")

    # 7. Render Gump & initial stats
    create_control_gump()
    update_stats()

    # Initial check and restock of raw food if needed
    if not DIRECT_SATCHEL_CRAFTING and count_backpack_raw_food() < MIN_BACKPACK_INGREDIENTS:
        restock_raw_food_from_satchel()

    update_status("Running")
    API.SysMsg(f"[Cooking] Training started. Current skill: {current_skill:.1f} | Recommended: {recommended_recipe_name}")

    # 8. Main Training Loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        success = craft_cycle()
        if not success:
            break

        API.Pause(0.2)

    update_status("Finished")
    API.SysMsg("[Cooking] Training finished.")
    dispose_gump()


main()
