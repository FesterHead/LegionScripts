"""
TrainInscription.py - Automated Resource-Efficient Inscription Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Fully automated Inscription skill training script for TazUO featuring:
    - Optimal resource-efficient progression ladder from 0.0 to 120.0 Inscription:
        * 0.0 - 30.0:   Reactive Armor (Circle 1, 4 Mana, Garlic / Silk / Ash)
        * 30.0 - 45.0:  Poison (Circle 3, 9 Mana, Nightshade - single reagent)
        * 45.0 - 65.0:  Lightning (Circle 4, 11 Mana, Mandrake / Ash)
        * 65.0 - 75.0:  Magic Reflection (Circle 5, 14 Mana, Garlic / Mandrake / Silk)
        * 75.0 - 90.0:  Energy Bolt (Circle 6, 20 Mana, Pearl / Nightshade)
        * 90.0 - 120.0: Flamestrike (Circle 7, 40 Mana, Silk / Ash)
    - Milestone Announcements & "Set Recipe" Manual Override:
        * Proactively notifies the player when reaching a skill threshold to recommend the next spell.
        * Includes an interactive "Set Recipe" button allowing players to manually prime any craft recipe.
    - Dual Crafted Scroll Management (Storage & Trash Disposal):
        * Storage Container: Prompts player to target a scroll book, chest, or pouch to preserve crafted scrolls.
        * Trash Barrel: Auto-detects nearby Trash Barrels or allows targeting a trash barrel on startup / UI.
        * Automatically deposits newly crafted scrolls into storage or trash via backpack serial diff.
        * Interactive "Storage" and "Trash Can" buttons on the Gump allow switching destinations at any time.
    - Automated Mana Management & Meditation:
        * Continuously monitors player mana against the active spell cost.
        * Automatically uses the Meditation skill when mana drops below threshold until fully restored.
    - Resource Satchel Integration & LRC Support:
        * Detects 100% Lower Reagent Cost (LRC) suits and bypasses reagent requirements automatically.
        * If LRC < 100%, monitors and restocks required reagents from the resource satchel.
        * Automatically restocks blank scrolls from the satchel when backpack reserves run low.
    - Tool Upkeep via Tinkering:
        * Detects Scribe's Pens in backpack or hands.
        * If pens break and Tinkering tools + iron ingots are available, attempts to auto-craft replacement
          Scribe's Pens (1 iron ingot) on the fly.
    - Interactive Control Gump:
        * Real-time training status, live Inscription skill level and cap with gain tracking,
          Mana and LRC indicators, Crafted / Stored / Trashed / Failed counters, and blank scroll counts.
        * Interactive Pause / Resume, Set Recipe, Satchel, Storage, Trash Can, and Stop buttons.
"""

from typing import List, Tuple, Optional, Set
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Target Inscription skill to stop training (e.g. 100.0 for GM, 120.0 for Legendary)
TARGET_SKILL = 120.0

# Direct Satchel Crafting (crafts directly from resource satchel without pulling to backpack)
DIRECT_SATCHEL_CRAFTING = True

# Working buffer of blank scrolls maintained in main backpack if direct crafting is not supported
MIN_BACKPACK_SCROLLS = 0 if DIRECT_SATCHEL_CRAFTING else 20
TARGET_BACKPACK_SCROLLS = 50
RESTOCK_BATCH_SIZE = 50

# Delays in seconds
CRAFT_DELAY = 1.3
TOOL_CRAFT_DELAY = 1.2
MEDITATE_DELAY = 2.0

# Meditation settings
USE_MEDITATION = True
MEDITATE_UPTO_MAX = True  # Meditate until full mana for longer uninterrupted crafting bursts

# Server Craft Gump button IDs (standard ServUO / RunUO)
GUMP_BTN_MAKE_LAST = 21  # Universal "Make Last" button

# Tool upkeep via Tinkering
AUTO_CRAFT_PEN = True
MAX_TOOL_CRAFT_ATTEMPTS = 8

# Dress configuration profile to load on startup (e.g., "Sorcery", "LRC", "Mage")
DRESS_PROFILE: str = "Sorcery"

# Enable verbose debug messages in client console
DEBUG = False


# ==============================================================================
# Item & Graphic Definitions
# ==============================================================================

# Scribe tools
PEN_GRAPHICS = {0x0FBF, 0x0FC0}

# Blank scroll graphics
BLANK_SCROLL_GRAPHICS = {0x0EF3, 0x0E34}

# Standard 1st through 8th circle spell scroll graphics (0x1F2D through 0x1F6C)
SPELL_SCROLL_GRAPHICS = set(range(0x1F2D, 0x1F6D))

# Reagent definitions
REAGENT_DEFS = {
    "Black Pearl": {
        "graphics": {0x0F7A},
    },
    "Bloodmoss": {
        "graphics": {0x0F7B},
    },
    "Garlic": {
        "graphics": {0x0F84},
    },
    "Ginseng": {
        "graphics": {0x0F85},
    },
    "Mandrake Root": {
        "graphics": {0x0F86},
    },
    "Nightshade": {
        "graphics": {0x0F88},
    },
    "Sulfurous Ash": {
        "graphics": {0x0F8C},
    },
    "Spiders' Silk": {
        "graphics": {0x0F8D},
    },
}

# Tinkering tools & materials for auto-crafting scribe's pens
TINKER_TOOL_GRAPHICS = {0x1EB8, 0x1EB9, 0x1EBC, 0x1EBD}
INGOT_GRAPHIC = 0x1BF2
IRON_INGOT_HUE = 0

# Trash barrel graphics
TRASH_BARREL_GRAPHICS = {0x0E77}

# Reagent map by spell name for custom recipe support
SPELL_REAGENT_MAP: Dict[str, List[str]] = {
    "Reactive Armor": ["Garlic", "Spiders' Silk", "Sulfurous Ash"],
    "Poison": ["Nightshade"],
    "Lightning": ["Mandrake Root", "Sulfurous Ash"],
    "Magic Reflection": ["Garlic", "Mandrake Root", "Spiders' Silk"],
    "Energy Bolt": ["Black Pearl", "Nightshade"],
    "Flamestrike": ["Spiders' Silk", "Sulfurous Ash"],
    "Recall": ["Black Pearl", "Bloodmoss", "Mandrake Root"],
    "Fireball": ["Black Pearl"],
    "Blade Spirits": ["Black Pearl", "Mandrake Root", "Nightshade"],
    "Greater Heal": ["Garlic", "Ginseng", "Mandrake Root", "Spiders' Silk"],
}

# Optimal Inscription Progression Ladder: (min_skill, max_skill, spell_name, circle, mana_cost, [reagents])
PROGRESSION_LADDER: List[Tuple[float, float, str, int, int, List[str]]] = [
    (0.0, 30.0, "Reactive Armor", 1, 4, ["Garlic", "Spiders' Silk", "Sulfurous Ash"]),
    (30.0, 45.0, "Poison", 3, 9, ["Nightshade"]),
    (45.0, 70.0, "Lightning", 4, 11, ["Mandrake Root", "Sulfurous Ash"]),
    (70.0, 75.0, "Magic Reflection", 5, 14, ["Garlic", "Mandrake Root", "Spiders' Silk"]),
    (75.0, 90.0, "Energy Bolt", 6, 20, ["Black Pearl", "Nightshade"]),
    (90.0, 120.0, "Flamestrike", 7, 40, ["Spiders' Silk", "Sulfurous Ash"]),
]


# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_mana = None
lbl_recipe = None
lbl_counts = None
lbl_scrolls = None
lbl_tools = None
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
armor_blocks_meditation: bool = False

total_crafted: int = 0
total_stored: int = 0
total_trashed: int = 0
total_failed: int = 0
tools_crafted: int = 0

last_inscription_skill: Optional[float] = None
current_recipe_name: str = "Make Last"
recommended_recipe_name: str = "Reactive Armor"


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
    global last_inscription_skill, recommended_recipe_name
    global lbl_skill, lbl_mana, lbl_recipe, lbl_counts, lbl_scrolls, lbl_tools

    # 1. Inscription Skill
    i_skill = API.GetSkill("Inscription")
    if i_skill:
        val = float(i_skill.Value)
        cap = float(i_skill.Cap)
        if lbl_skill:
            lbl_skill.Text = f"Inscription: {val:.1f} / {cap:.1f}"

        if last_inscription_skill is not None and val > last_inscription_skill:
            gain = val - last_inscription_skill
            API.SysMsg(f"[Inscription] Skill gained +{gain:.1f}! New skill: {val:.1f}")

            # Check for progression milestone
            old_rec, _, _, _ = get_recommended_item(last_inscription_skill)
            new_rec, circle, mana_cost, _ = get_recommended_item(val)
            if new_rec != old_rec:
                API.SysMsg(f"[Inscription] *** Progression Milestone reached ({val:.1f})! ***")
                API.SysMsg(f"[Inscription] Recommended next spell: '{new_rec}' (Circle {circle}, {mana_cost} Mana).")
                API.SysMsg(f"[Inscription] Click 'Set Recipe' on the Gump to switch to '{new_rec}', or continue current recipe.")
                recommended_recipe_name = new_rec
                if lbl_recipe:
                    lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {new_rec})"

        last_inscription_skill = val

    # 2. Mana & LRC
    if lbl_mana:
        cur_mana = API.Player.Mana if API.Player and API.Player.Mana is not None else 0
        max_mana = API.Player.ManaMax if API.Player and API.Player.ManaMax is not None else 0
        lrc = getattr(API.Player, "LowerReagentCost", 0) or 0
        lbl_mana.Text = f"Mana: {cur_mana}/{max_mana} | LRC: {lrc}%"

    # 3. Recipe
    if lbl_recipe:
        if current_recipe_name != recommended_recipe_name:
            lbl_recipe.Text = f"Recipe: {current_recipe_name} (Rec: {recommended_recipe_name})"
        else:
            lbl_recipe.Text = f"Recipe: {current_recipe_name}"

    # 4. Counts
    if lbl_counts:
        lbl_counts.Text = f"Crafted: {total_crafted} | Stored: {total_stored} | Trashed: {total_trashed} | Failed: {total_failed}"

    # 5. Scroll Counts
    bp_scrolls = count_backpack_scrolls()
    satchel_scrolls = count_satchel_scrolls() if satchel_serial else 0
    satchel_label = f"{satchel_scrolls:,}" if satchel_serial else "N/A"
    if lbl_scrolls:
        lbl_scrolls.Text = f"Satchel: {satchel_label} | Backpack: {bp_scrolls}"

    # 6. Tool & Destination Status
    pens_cnt = count_scribe_pens()
    pens_str = f"Pens: {pens_cnt}"

    if storage_serial:
        dest_str = "Dest: Storage"
    elif trash_barrel_serial:
        dest_str = "Dest: Trash"
    else:
        dest_str = "Dest: Backpack"

    if lbl_tools:
        lbl_tools.Text = f"{pens_str} | {dest_str}"


def on_pause_clicked() -> None:
    """Toggles pause/resume state."""
    global is_paused, btn_pause, armor_blocks_meditation
    is_paused = not is_paused
    if not is_paused:
        armor_blocks_meditation = False  # Allow re-testing meditation if player changed gear
        equip_dress_profile()
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Running")
    API.SysMsg("[Inscription] Script paused." if is_paused else "[Inscription] Script resumed.")


def on_stop_clicked() -> None:
    """Stops the script execution."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_satchel_clicked() -> None:
    """Allows player to target their resource satchel or container."""
    global satchel_serial
    API.SysMsg("[Inscription] Target your Resource Satchel / Supplies Container (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial and new_serial != API.Player.Serial:
        satchel_serial = new_serial
        API.SysMsg(f"[Inscription] Satchel updated: 0x{satchel_serial:X}")
        API.UseObject(satchel_serial)
        API.Pause(0.4)
        update_stats()
        if count_backpack_scrolls() < MIN_BACKPACK_SCROLLS:
            restock_scrolls_from_satchel()
    else:
        API.SysMsg("[Inscription] Satchel targeting cleared.")
        satchel_serial = None
    update_stats()


def on_storage_clicked() -> None:
    """Allows player to target a container / scroll book for completed scrolls."""
    global storage_serial
    API.SysMsg("[Inscription] Target your Scroll Storage Container / Book (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial and new_serial != API.Player.Serial:
        storage_serial = new_serial
        API.SysMsg(f"[Inscription] Storage container updated: 0x{storage_serial:X}")
    else:
        API.SysMsg("[Inscription] Storage container cleared.")
        storage_serial = None
    update_stats()


def on_trash_clicked() -> None:
    """Allows player to target a trash barrel / container."""
    global trash_barrel_serial
    API.SysMsg("[Inscription] Target your Trash Barrel (or press ESC to clear)...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial and new_serial != API.Player.Serial:
        trash_barrel_serial = new_serial
        API.SysMsg(f"[Inscription] Trash barrel updated: 0x{trash_barrel_serial:X}")
    else:
        API.SysMsg("[Inscription] Trash barrel cleared.")
        trash_barrel_serial = None
    update_stats()


def on_recipe_clicked() -> None:
    """Opens the Inscription craft gump to allow manually selecting a spell recipe."""
    global is_paused, btn_pause
    pen = get_scribe_pen()
    if pen:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused (Set Recipe)")
        API.SysMsg("[Inscription] Opening Inscription menu. Click your desired spell once to craft it, then click 'Resume' on the Gump.")
        API.UseObject(pen)
    else:
        API.SysMsg("[Inscription] No Scribe's Pen available to open craft menu!")


def on_gump_disposed() -> None:
    global is_stopped
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


def create_control_gump() -> None:
    """Renders the FesterUO Inscription Trainer Gump."""
    global gump, lbl_status, lbl_skill, lbl_mana, lbl_recipe, lbl_counts, lbl_scrolls, lbl_tools
    global btn_pause, btn_recipe, btn_satchel, btn_storage, btn_trash, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 320, 245)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 320, 245)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Train Inscription", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skill
    lbl_skill = API.Gumps.CreateGumpLabel("Inscription: -- / --", 996)
    lbl_skill.SetPos(10, 48)
    gump.Add(lbl_skill)

    # Mana & LRC
    lbl_mana = API.Gumps.CreateGumpLabel("Mana: --/-- | LRC: --%", 996)
    lbl_mana.SetPos(10, 68)
    gump.Add(lbl_mana)

    # Recipe
    lbl_recipe = API.Gumps.CreateGumpLabel("Recipe: Initializing...", 53)
    lbl_recipe.SetPos(10, 88)
    gump.Add(lbl_recipe)

    # Counts
    lbl_counts = API.Gumps.CreateGumpLabel("Crafted: 0 | Stored: 0 | Trashed: 0 | Failed: 0", 996)
    lbl_counts.SetPos(10, 108)
    gump.Add(lbl_counts)

    # Scroll counts
    lbl_scrolls = API.Gumps.CreateGumpLabel("Satchel: 0 | Backpack: 0", 996)
    lbl_scrolls.SetPos(10, 128)
    gump.Add(lbl_scrolls)

    # Tools & Destination
    lbl_tools = API.Gumps.CreateGumpLabel("Pens: -- | Dest: --", 996)
    lbl_tools.SetPos(10, 148)
    gump.Add(lbl_tools)

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
    weight = API.Player.Weight
    weight_max = API.Player.WeightMax
    if weight is not None and weight_max is not None and weight_max > 0:
        return weight >= (weight_max - 15)
    return False


def get_pen_info(item) -> Tuple[bool, str]:
    """
    Analyzes an item and returns (is_pen, pen_type).
    pen_type is 'scribe', 'mapmaker', or 'unknown'.
    Queries tooltip properties from the server if name is not yet cached.
    """
    if not item or item.Graphic not in PEN_GRAPHICS:
        return False, "none"

    name = str(getattr(item, "Name", "") or "").lower()

    if not any(kw in name for kw in ["map", "cartograph", "scribe", "inscript"]):
        props = str(API.ItemNameAndProps(item.Serial, wait=True, timeout=2) or "").lower()
        if props:
            name = f"{name} {props}"

    if "scribe" in name or "inscript" in name:
        return True, "scribe"
    if "map" in name or "cartograph" in name:
        return True, "mapmaker"

    return True, "unknown"


def is_valid_scribe_pen(item) -> bool:
    """
    Returns True ONLY if the pen is verified to be a Scribe's Pen and NEVER a Mapmaker's Pen.
    """
    global active_pen_serial
    if not item or item.Graphic not in PEN_GRAPHICS:
        return False

    # If this is our known active scribe pen, accept it
    if active_pen_serial and item.Serial == active_pen_serial:
        return True

    is_pen, p_type = get_pen_info(item)
    if not is_pen:
        return False

    # Strictly reject any Mapmaker's Pen!
    if p_type == "mapmaker":
        return False

    # Validated Scribe's Pen
    if p_type == "scribe":
        return True

    return False


def get_scribe_pen():
    """Finds a verified Scribe's Pen in player hands or backpack."""
    global active_pen_serial

    # 1. If active pen is known and still in player possession, use it
    if active_pen_serial:
        item = API.FindItem(active_pen_serial)
        if item and item.Graphic in PEN_GRAPHICS:
            is_pen, p_type = get_pen_info(item)
            if p_type != "mapmaker":
                return item
        active_pen_serial = None

    # 2. Check hands
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and is_valid_scribe_pen(item):
            active_pen_serial = item.Serial
            return item

    # 3. Check main backpack
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if is_valid_scribe_pen(item):
                active_pen_serial = item.Serial
                return item

    return None


def count_scribe_pens() -> int:
    """Counts usable Scribe's Pens, strictly excluding Mapmaker's Pens."""
    cnt = 0
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and is_valid_scribe_pen(item):
            cnt += 1
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if is_valid_scribe_pen(item):
                cnt += 1
    return cnt


def count_backpack_scrolls() -> int:
    """Counts blank scrolls currently in the main backpack."""
    total = 0
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if items:
        for item in items:
            if item.Serial != satchel_serial and item.Graphic in BLANK_SCROLL_GRAPHICS:
                total += getattr(item, "Amount", 1) or 1
    return total


def count_satchel_scrolls() -> int:
    """Counts blank scrolls inside the designated resource satchel."""
    if not satchel_serial:
        return 0
    total = 0
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if items:
        for item in items:
            if item.Graphic in BLANK_SCROLL_GRAPHICS:
                total += getattr(item, "Amount", 1) or 1
    return total


def get_satchel_scrolls():
    """Finds the largest stack of blank scrolls inside the satchel."""
    if not satchel_serial:
        return None
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if not items:
        return None
    best_item = None
    best_amt = 0
    for item in items:
        if item.Graphic in BLANK_SCROLL_GRAPHICS:
            amt = getattr(item, "Amount", 1) or 1
            if amt > best_amt:
                best_amt = amt
                best_item = item
    return best_item


def restock_scrolls_from_satchel() -> bool:
    """Pulls a batch of blank scrolls from the satchel into the main backpack."""
    if not satchel_serial:
        return False

    current_bp = count_backpack_scrolls()
    if current_bp >= MIN_BACKPACK_SCROLLS and current_bp > 0:
        return True

    satchel_scroll_stack = get_satchel_scrolls()
    if not satchel_scroll_stack:
        return False

    amt_available = getattr(satchel_scroll_stack, "Amount", 1) or 1
    amt_needed = max(RESTOCK_BATCH_SIZE, TARGET_BACKPACK_SCROLLS - current_bp)
    amt_to_move = min(amt_available, amt_needed)

    if amt_to_move <= 0:
        return False

    update_status(f"Restocking {amt_to_move} scrolls...")
    API.MoveItem(satchel_scroll_stack.Serial, API.Backpack, amt=amt_to_move)
    API.Pause(0.6)
    update_stats()
    return count_backpack_scrolls() >= 1


def count_items_by_graphics(container_serial: int, graphics: Set[int], recursive: bool = True) -> int:
    """Counts total amount of items matching graphics in a container."""
    total = 0
    items = API.ItemsInContainer(container_serial, recursive=recursive)
    if items:
        for item in items:
            if item.Graphic in graphics:
                total += getattr(item, "Amount", 1) or 1
    return total


def check_reagent_availability(reagents: List[str]) -> Tuple[bool, str]:
    """
    Verifies that required reagents are present in the backpack or satchel.
    Players with 100% Lower Reagent Cost (LRC) bypass reagent requirements.
    When LRC < 100%, checks across backpack and satchel without moving reagents into the root backpack.
    """
    if not API.Player:
        return True, ""

    lrc = getattr(API.Player, "LowerReagentCost", 0) or 0
    if lrc >= 100:
        return True, ""

    for reg_name in reagents:
        if reg_name not in REAGENT_DEFS:
            continue
        g_set = REAGENT_DEFS[reg_name]["graphics"]
        # Search recursively throughout backpack (including any satchels/pouches inside it)
        amt = count_items_by_graphics(API.Backpack, g_set, recursive=True)
        # If satchel is an external container (e.g. chest/secure), also check satchel
        if amt < 1 and satchel_serial:
            amt += count_items_by_graphics(satchel_serial, g_set, recursive=True)
        if amt < 1:
            return False, reg_name

    return True, ""


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


def get_recommended_item(skill: float) -> Tuple[str, int, int, List[str]]:
    """Returns optimal (spell_name, circle, mana_cost, [reagents]) for current skill level."""
    for min_sk, max_sk, name, circle, mana, regs in PROGRESSION_LADDER:
        if min_sk <= skill < max_sk:
            return name, circle, mana, regs
    return "Flamestrike", 7, 40, ["Spiders' Silk", "Sulfurous Ash"]


# ==============================================================================
# Mana Recovery & Meditation
# ==============================================================================

def equip_dress_profile() -> None:
    """Equips the configured dress profile (e.g. 'Sorcery') if specified."""
    if not DRESS_PROFILE:
        return
    available = API.GetAvailableDressOutfits()
    if available and DRESS_PROFILE not in available:
        API.SysMsg(f"[Inscription] Note: Dress profile '{DRESS_PROFILE}' not found in TazUO. Available: {', '.join(available)}")
        return
    API.SysMsg(f"[Inscription] Equipping dress profile '{DRESS_PROFILE}'...")
    API.Dress(DRESS_PROFILE)
    API.Pause(0.6)


def handle_mana_recovery(target_mana: Optional[int] = None) -> bool:
    """
    Restores mana by meditating or pausing until mana reaches target_mana (or max mana).
    Returns False if stopped or cancelled.
    """
    global armor_blocks_meditation
    if not API.Player:
        return True

    cur_mana = API.Player.Mana if API.Player.Mana is not None else 0
    max_mana = API.Player.ManaMax if API.Player.ManaMax is not None else 0

    target = target_mana if target_mana is not None else max_mana
    if cur_mana >= target:
        return True

    display_max = max_mana if max_mana > 0 else target
    update_status(f"Regenerating Mana ({cur_mana}/{display_max})...")
    API.SysMsg(f"[Inscription] Low mana ({cur_mana}/{target}). Regenerating mana...")

    in_trance = False

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return False

        if not API.Player:
            return True

        cur_mana = API.Player.Mana if API.Player.Mana is not None else 0
        max_mana = API.Player.ManaMax if API.Player.ManaMax is not None else 0
        display_max = max_mana if max_mana > 0 else target
        update_status(f"Regenerating Mana ({cur_mana}/{display_max})...")
        update_stats()

        # 1. Check if server indicates mana is full ("You are at peace.")
        if API.InJournal("at peace") or API.InJournal("you are at peace"):
            API.SysMsg("[Inscription] Mana fully restored (at peace).")
            break

        # 2. Check if mana reached target or max threshold (with 1 mana tolerance for bonus stat desync)
        effective_threshold = (max_mana - 1) if (MEDITATE_UPTO_MAX and max_mana > 0) else target
        if cur_mana >= effective_threshold:
            API.SysMsg(f"[Inscription] Mana restored ({cur_mana}/{display_max}).")
            break

        # 3. Handle active meditation or passive regen
        if USE_MEDITATION and not armor_blocks_meditation:
            # Check journal for active meditation trance state
            if API.InJournal("meditative trance") or API.InJournal("enter a meditative trance"):
                in_trance = True

            if API.InJournal("lost your concentration") or API.InJournal("lose your concentration"):
                in_trance = False

            if API.InJournal("regenerative forces") or API.InJournal("cannot penetrate your armor"):
                armor_blocks_meditation = True
                in_trance = False
                API.SysMsg("[Inscription] Armor blocks Meditation ('Regenerative forces cannot penetrate your armor').")
                API.SysMsg("[Inscription] Switched to passive mana regen. (Tip: Wear all-leather, cloth, or Mage Armor to meditate faster).")

            # Only activate Meditation skill if not already meditating in trance
            if not in_trance and not API.BuffExists("Meditation"):
                API.ClearJournal()
                API.UseSkill("Meditation")
                # Wait for server response to Meditation attempt
                if not wait_with_ui(1.5):
                    return False
                if API.InJournal("at peace") or API.InJournal("you are at peace"):
                    API.SysMsg("[Inscription] Mana fully restored (at peace).")
                    break
                if API.InJournal("meditative trance") or API.InJournal("enter a meditative trance"):
                    in_trance = True
                elif API.InJournal("must wait") or API.InJournal("cannot focus"):
                    if not wait_with_ui(2.0):
                        return False
            else:
                # In active trance or passive regen: wait while monitoring mana and journal
                if not wait_with_ui(0.8):
                    return False
        else:
            # Passive mana regen
            if not wait_with_ui(1.0):
                return False

    update_stats()

    # Re-equip dress profile upon exiting meditation
    if DRESS_PROFILE and not is_stopped and not API.StopRequested:
        equip_dress_profile()

    return not (is_stopped or API.StopRequested)



# ==============================================================================
# Tinkering Upkeep - Scribe's Pen Crafting
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
    """Crafts a replacement Scribe's Pen using Tinkering tools and iron ingots."""
    global tools_crafted, is_paused, btn_pause, active_pen_serial
    if not AUTO_CRAFT_PEN:
        return False

    tinker_tool = get_tinker_tool()
    if not tinker_tool:
        update_status("Need Tinker's Tool")
        API.SysMsg("[Inscription] No Tinker's Tool found in backpack or satchel to craft a new scribe's pen!")
        return False

    tool_name = "Scribe's Pen"

    total_ingots = count_backpack_ingots() + count_satchel_ingots()
    if total_ingots < 1:
        update_status("Out of Ingots")
        API.SysMsg(f"[Inscription] Not enough iron ingots in backpack or satchel to craft {tool_name} (need 1 ingot)!")
        return False

    if count_backpack_ingots() < 1:
        restock_ingots_from_satchel(4)

    update_status(f"Tinkering {tool_name}...")
    API.SysMsg(f"[Inscription] Crafting replacement {tool_name} via Tinkering (1 ingot)...")

    # Close any currently open craft gump (e.g. stale Inscription gump from previous pen)
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
                API.SysMsg("[Inscription] Tinkering craft menu did not appear.")
                return False

        if API.GumpContains("haven't made anything") or API.GumpContains("not made anything"):
            API.SysMsg(f"[Inscription] Tinkering 'Make Last' is not set to {tool_name}.")
            API.SysMsg(f"[Inscription] In the open Tinkering menu: Click 'Tools' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
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
            API.SysMsg(f"[Inscription] Tinkering 'Make Last' is not set to {tool_name}.")
            API.SysMsg(f"[Inscription] In the open Tinkering menu: Click 'Tools' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
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
            API.SysMsg(f"[Inscription] Successfully crafted new {tool_name} (0x{new_serial:X})!")
            update_stats()
            if API.HasGump():
                API.CloseGump()
                API.Pause(0.3)
            deposit_ingots_to_satchel()
            return True

        if any("you create" in t for t in j_text) and not new_pens:
            API.SysMsg(f"[Inscription] Tinkering 'Make Last' is currently set to a different item, not {tool_name}.")
            API.SysMsg(f"[Inscription] In the open Tinkering menu: Click 'Tools' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
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
    API.SysMsg(f"[Inscription] Failed to auto-craft {tool_name} after {MAX_TOOL_CRAFT_ATTEMPTS} attempts.")
    API.SysMsg(f"[Inscription] In the Tinkering menu: Click 'Tools' -> '{tool_name}' once to prime Make Last, then click Resume on the Gump.")
    is_paused = True
    if btn_pause:
        btn_pause.SetText("Resume")
    update_status(f"Craft 1 {tool_name}")
    return False



# ==============================================================================
# Crafting Cycle
# ==============================================================================

def craft_cycle() -> bool:
    """Executes a single craft attempt, recovers mana, restocks materials, and stores/trashes scrolls."""
    global total_crafted, total_failed, total_stored, total_trashed, current_recipe_name

    # 1. Check weight before crafting
    if is_overburdened():
        update_status("Overweight")
        API.SysMsg("[Inscription] Weight limit reached! Please lighten your backpack, then click Resume on the Gump.")
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        return True

    # 2. Get current skill and recipe info
    i_skill_obj = API.GetSkill("Inscription")
    current_skill = float(i_skill_obj.Value) if i_skill_obj else 0.0
    rec_name, circle, mana_cost, reagents = get_recommended_item(current_skill)

    # Stop if target skill reached
    if current_skill >= TARGET_SKILL:
        update_status("Target Skill Reached!")
        API.SysMsg(f"[Inscription] Congratulations! Target skill {TARGET_SKILL:.1f} reached!")
        return False

    # 3. Check and recover mana
    if API.Player and (API.Player.Mana or 0) < mana_cost:
        if not handle_mana_recovery(target_mana=mana_cost):
            return False

    # 4. Check total blank scrolls available
    total_scrolls = count_backpack_scrolls() + (count_satchel_scrolls() if satchel_serial else 0)
    if total_scrolls < 1:
        update_status("Out of Scrolls")
        API.SysMsg("[Inscription] Out of blank scrolls in backpack and satchel! Add scrolls, then click Resume on the Gump.")
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        return True

    # Maintain backpack scroll buffer if needed
    if not DIRECT_SATCHEL_CRAFTING and count_backpack_scrolls() < MIN_BACKPACK_SCROLLS:
        restock_scrolls_from_satchel()

    # 5. Check reagents (if LRC < 100)
    active_reagents = SPELL_REAGENT_MAP.get(current_recipe_name, reagents)
    has_regs, missing_reg = check_reagent_availability(active_reagents)
    if not has_regs:
        update_status(f"Need {missing_reg}")
        API.SysMsg(f"[Inscription] Missing required reagent: {missing_reg} (and LRC < 100%)!")
        API.SysMsg(f"[Inscription] Add {missing_reg} to your backpack/satchel and click Resume, or click 'Set Recipe' to choose a different spell.")
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        return True

    # 6. Ensure Scribe's Pen is available
    pen = get_scribe_pen()
    if not pen:
        if not craft_pen_with_tinkering():
            update_status("No Pen")
            API.SysMsg("[Inscription] Out of Scribe's Pens! Please equip or carry a scribe's pen, then click Resume on the Gump.")
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            return True
        pen = get_scribe_pen()
        if not pen:
            return True

    # 7. Record pre-craft backpack state for serial diff detection
    bp_before = {item.Serial for item in (API.ItemsInContainer(API.Backpack, recursive=False) or [])}

    # 8. Open craft menu if needed
    if not API.HasGump():
        API.ClearJournal()
        API.UseObject(pen)
        if not API.WaitForGump(delay=2.5):
            debug_msg("Inscription craft menu did not appear.")
            return True

    # 9. Click Make Last
    API.ClearJournal()
    API.ReplyGump(GUMP_BTN_MAKE_LAST)
    wait_with_ui(CRAFT_DELAY)

    # 10. Analyze result from journal
    entries = API.GetJournalEntries(CRAFT_DELAY + 0.8)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    # Check if Make Last is uninitialized
    if any("haven't made anything" in t or "have not made" in t for t in j_text) or API.GumpContains("haven't made anything"):
        API.SysMsg("[Inscription] 'Make Last' is not set yet.")
        API.SysMsg(f"[Inscription] In the open Inscription menu: Click '{rec_name}' (Circle {circle}) once to craft it, then click Resume on the Gump.")
        update_status(f"Prime '{rec_name}'")
        on_pause_clicked()
        return True

    # Check if missing blank scrolls
    if any("sufficient blank" in t or "enough blank" in t or "more scrolls" in t for t in j_text) or API.InJournal("blank scroll"):
        if satchel_serial and count_satchel_scrolls() >= 1:
            API.SysMsg("[Inscription] Server requires blank scrolls in root backpack. Restocking from satchel...")
            restock_scrolls_from_satchel()
            return True

    # Check craft success or failure
    success = any("you create" in t or "put the" in t or "put it into" in t or "inscribe" in t for t in j_text) or API.InJournal("you create")
    failed = any("you fail" in t or "failed" in t or "destroy" in t for t in j_text) or API.InJournal("you fail")

    # Detect newly crafted item via backpack serial diff
    bp_after = API.ItemsInContainer(API.Backpack, recursive=False) or []
    new_item = None
    for it in bp_after:
        if it.Serial not in bp_before:
            if it.Serial != satchel_serial and it.Serial != trash_barrel_serial and it.Serial != storage_serial:
                if it.Graphic not in BLANK_SCROLL_GRAPHICS and it.Graphic not in PEN_GRAPHICS and it.Graphic not in TINKER_TOOL_GRAPHICS:
                    new_item = it
                    break

    # Also detect if any spell scroll exists in backpack that can be moved
    if not new_item:
        for it in bp_after:
            if it.Serial != satchel_serial and it.Serial != trash_barrel_serial and it.Serial != storage_serial:
                if it.Graphic in SPELL_SCROLL_GRAPHICS:
                    new_item = it
                    break

    if new_item:
        success = True

    if success:
        total_crafted += 1
        update_status("Crafted")
        update_stats()

        # Handle storage or trashing of crafted scroll
        if new_item:
            if getattr(new_item, "Name", None):
                clean_name = str(new_item.Name).lower().replace("a spell scroll of ", "").replace("a scroll of ", "").strip()
                if clean_name:
                    current_recipe_name = clean_name.title()
            if storage_serial:
                update_status(f"Storing {new_item.Name or 'scroll'}...")
                API.MoveItem(new_item.Serial, storage_serial)
                API.Pause(0.4)
                total_stored += 1
                update_stats()
            elif trash_barrel_serial:
                update_status(f"Trashing {new_item.Name or 'scroll'}...")
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
    API.SysMsg("[Inscription] Inscription trainer stopped.")

API.OnStop(on_stop)


def main():
    global satchel_serial, storage_serial, trash_barrel_serial, current_recipe_name, recommended_recipe_name

    API.SysMsg("=== FesterUO Inscription Trainer ===")

    # 0. Load Dress Profile
    equip_dress_profile()

    # 1. Initial skill and recipe recommendation
    i_skill_obj = API.GetSkill("Inscription")
    current_skill = float(i_skill_obj.Value) if i_skill_obj else 0.0
    recommended_recipe_name, circle, mana, _ = get_recommended_item(current_skill)
    current_recipe_name = recommended_recipe_name

    # 2. Storage Setup (Container / Scroll Book)
    API.SysMsg("[Inscription] Target your Scroll Storage Container / Book (or press ESC / target yourself to skip)...")
    s_serial = API.RequestTarget(timeout=6.0)
    if s_serial and s_serial != API.Player.Serial:
        storage_serial = s_serial
        API.SysMsg(f"[Inscription] Storage container set: 0x{storage_serial:X}")
    else:
        storage_serial = None
        API.SysMsg("[Inscription] No storage container selected.")

    # 3. Trash Barrel Setup (if storage not set, or for backup disposal)
    auto_barrel = find_nearby_trash_barrel()
    if auto_barrel:
        trash_barrel_serial = auto_barrel.Serial
        API.SysMsg(f"[Inscription] Auto-detected nearby Trash Barrel: 0x{trash_barrel_serial:X}")
    elif not storage_serial:
        API.SysMsg("[Inscription] Target your Trash Barrel (or press ESC / target yourself to keep scrolls in backpack)...")
        t_serial = API.RequestTarget(timeout=6.0)
        if t_serial and t_serial != API.Player.Serial:
            trash_barrel_serial = t_serial
            API.SysMsg(f"[Inscription] Trash barrel set: 0x{trash_barrel_serial:X}")
        else:
            trash_barrel_serial = None
            API.SysMsg("[Inscription] No trash barrel selected. Crafted scrolls will remain in backpack.")

    # 4. Satchel Setup
    API.SysMsg("[Inscription] Target your Resource Satchel for Blank Scrolls/Reagents/Ingots (or press ESC for backpack only)...")
    sat_serial = API.RequestTarget(timeout=6.0)
    if sat_serial and sat_serial != API.Player.Serial:
        satchel_serial = sat_serial
        API.SysMsg(f"[Inscription] Satchel set: 0x{satchel_serial:X}")
        API.UseObject(satchel_serial)
        API.Pause(0.4)
    else:
        satchel_serial = None
        API.SysMsg("[Inscription] Using backpack resources only.")

    # 5. Check initial tool
    pen = get_scribe_pen()
    if not pen:
        API.SysMsg("[Inscription] No Scribe's Pen found! Please equip or carry a scribe's pen.")
        update_status("No Pen")

    # 6. Render Gump & initial stats
    create_control_gump()
    update_stats()

    # Initial check and restock of scrolls if needed
    if not DIRECT_SATCHEL_CRAFTING and count_backpack_scrolls() < MIN_BACKPACK_SCROLLS:
        restock_scrolls_from_satchel()

    update_status("Running")
    API.SysMsg(f"[Inscription] Training started. Current skill: {current_skill:.1f} | Recommended: {recommended_recipe_name} (Circle {circle})")

    # 7. Main Training Loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        success = craft_cycle()
        if not success:
            break

        API.Pause(0.2)

    update_status("Finished")
    API.SysMsg("[Inscription] Training finished.")
    dispose_gump()


main()
