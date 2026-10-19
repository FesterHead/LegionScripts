"""
TrainImbuingCraftUnravel.py - Intermediate Imbuing Trainer (Craft Oak Staves & Unravel)

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    An intermediate Imbuing training engine designed to bridge the gap when low on
    Magical Residue or when direct imbuing success rates are inefficient:
    1. Crafts Oak Quarterstaves using saws via "Make Last" from the Carpentry menu.
       - Saws are automatically selected and cycled from the backpack when they break.
       - Automatically restocks Oak boards from a designated resource satchel inside
         the player's backpack whenever the root backpack reserve drops below threshold.
    2. Immediately unravels each crafted oak staff at a nearby Soulforge.
       - Extracts Magical Residue and Enchanted Essence while training Imbuing skill.
       - Confirms unravel confirmation dialogs automatically.
       - Automatically stashes newly reclaimed residue and essence back into the satchel.
    3. Repeats seamlessly until target Imbuing skill is reached or resources are exhausted.

Features:
    - Interactive Control Gump:
        * Live Imbuing and Carpentry skill tracking with automatic gain announcements.
        * Staves Crafted, Staves Unraveled, and Failed attempt counters.
        * Live Oak Board, Saw, Magical Residue, and Enchanted Essence counts.
        * Interactive Pause / Resume, Set Satchel, Set Trash, and Stop buttons.
    - Automatic Satchel Detection & Interactive Retargeting.
    - Multi-Saw Rotation: detects broken saws and smoothly transitions to the next saw.
    - Loop Safety: strict API.StopRequested checks, UI event pump, and OnStop callback.
"""

from typing import List, Optional, Set, Dict, Any
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Script version
SCRIPT_VERSION: str = "1.1.0"

# Target Imbuing skill to stop training (e.g. 120.0 for Legendary, 100.0 for GM, 50.0 for early bracket)
TARGET_IMBUING_SKILL: float = 120.0

# Action pacing delays in seconds
CRAFT_DELAY: float = 1.6          # Delay after sending "Make Last"
UNRAVEL_DELAY: float = 1.2        # Delay after targeting item for unraveling
MOVE_DELAY: float = 0.65          # Container drag/drop delay
RESTOCK_DELAY: float = 0.8        # Satchel restock pause delay

# Working buffer of Oak Boards in root backpack
MIN_BACKPACK_BOARDS: int = 12     # Restock when backpack boards drop below this (Quarterstaff takes 6 boards)
RESTOCK_BATCH_BOARDS: int = 50    # Amount of oak boards to pull from satchel per restock batch

# Periodic maintenance & backpack unravel sweep interval (in crafts/cycles)
SWEEP_INTERVAL: int = 10          # Every 10 imbues, re-synchronize containers and unravel all lingering staves in backpack

# Stash harvested ingredients (Magical Residue & Enchanted Essence) into satchel
AUTO_STASH_INGREDIENTS: bool = True

# Discard items that cannot be unraveled into a trash barrel if available
AUTO_TRASH_UNUNRAVELABLE: bool = True

# Colors for SysMsg announcements
HUE_INFO: int = 88
HUE_SUCCESS: int = 68
HUE_WARN: int = 53
HUE_ALERT: int = 38

# Enable detailed debug messages in client console
DEBUG: bool = False

# ==============================================================================
# Graphic & Gump Definitions
# ==============================================================================

# Carpentry Saws
SAW_GRAPHICS: List[int] = [
    0x1034, 0x1035,  # Standard Saw
    0x1028, 0x1029,  # Dovetail Saw
]

# Alternate carpentry tools fallback
CARPENTRY_TOOL_GRAPHICS: List[int] = [
    0x1034, 0x1035,  # Saw
    0x1028, 0x1029,  # Dovetail Saw
    0x102C, 0x102D,  # Moulding Plane
    0x1032, 0x1033,  # Smoothing Plane
    0x102E, 0x102F,  # Jointing Plane
    0x10E4, 0x10E5,  # Froe / Draw Knife
    0x10E7, 0x10E8,  # Scorp
    0x102A, 0x102B,  # Hammer
]

# Wood Boards & Logs
BOARD_GRAPHICS: List[int] = [0x1BD7, 0x1BDD]
OAK_WOOD_HUE: int = 0x07DA  # 2010 (Standard Oak Wood hue in ServUO / ModernUO / RunUO / OSI)

# Quarter Staff graphics
QUARTER_STAFF_GRAPHICS: List[int] = [0x0E8A, 0x0E89]
ALL_STAFF_GRAPHICS: List[int] = [
    0x0E8A, 0x0E89,  # Quarter Staff
    0x13F8, 0x13F9,  # Gnarled Staff
    0x0DF0, 0x0DF1,  # Black Staff
    0x0E81, 0x0E82,  # Shepherd's Crook
    0x26C1, 0x26CB,  # Wild Staff
]

# Soulforge structures
SOULFORGE_GRAPHICS: Set[int] = {
    0x2DD8,  # Elven / Soul Forge
    0x4263, 0x4264, 0x4265, 0x4266, 0x4267, 0x4268, 0x4269, 0x426A,  # Gargish / Queen's Soulforge
    0x426B, 0x426C, 0x426D, 0x426E, 0x426F, 0x4270, 0x4271, 0x4272,
    0x4277, 0x4278, 0x4279, 0x427A, 0x427B, 0x427C, 0x427D, 0x427E,
    0x427F, 0x4280, 0x4281, 0x4282, 0x4283, 0x4284, 0x4285, 0x4286,
    0x398C, 0x3996,  # Alternate Gargish forges
}

# Imbuing Ingredients
MAGICAL_RESIDUE_GRAPHICS: Set[int] = {0x2DB1, 0x2DB2}
ENCHANTED_ESSENCE_GRAPHICS: Set[int] = {0x2DB2, 0x2DB3}
RELIC_FRAGMENT_GRAPHICS: Set[int] = {0x2DB3, 0x2DB4}
ALL_INGREDIENT_GRAPHICS: Set[int] = (
    MAGICAL_RESIDUE_GRAPHICS | ENCHANTED_ESSENCE_GRAPHICS | RELIC_FRAGMENT_GRAPHICS
)

# Common satchel / container graphics in backpack
CONTAINER_GRAPHICS: List[int] = [
    0x0E75,  # Backpack
    0x0E76,  # Bag
    0x0E79,  # Pouch
    0x2DD6,  # Elven Satchel / Small Bag
    0x09B0,  # Belt Pouch
    0x0E7D,  # Wooden Box
]

# Trash barrel graphics
TRASH_BARREL_GRAPHICS: Set[int] = {0x0E77}

# Gump button IDs
GUMP_BTN_MAKE_LAST: int = 21         # Universal "Make Last" button on crafting menus
GUMP_BTN_UNRAVEL_ITEM: int = 10010   # "Unravel Item" on Imbuing menu
GUMP_BTN_CONFIRM: int = 1            # Universal confirmation button

# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_imbue_skill = None
lbl_carp_skill = None
lbl_counts = None
lbl_resources = None
lbl_ingredients = None
lbl_satchel = None
btn_pause = None
btn_satchel = None
btn_trash = None
btn_stop = None

satchel_serial: Optional[int] = None
trash_barrel_serial: Optional[int] = None
active_saw_serial: Optional[int] = None
wood_hue_override: Optional[int] = None

is_paused: bool = False
is_stopped: bool = False

staves_crafted: int = 0
staves_unraveled: int = 0
craft_failures: int = 0
unravel_failures: int = 0
residue_gained: int = 0
essence_gained: int = 0

last_imbue_skill: Optional[float] = None
last_carp_skill: Optional[float] = None

# ==============================================================================
# Helper & Logging Functions
# ==============================================================================

def debug_msg(msg: str) -> None:
    if DEBUG:
        API.SysMsg(f"[Debug] {msg}", HUE_INFO)


def update_status(text: str) -> None:
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def is_in_backpack(serial: Optional[int]) -> bool:
    """Checks whether a given serial resides inside the player's root backpack."""
    if not serial or serial == API.Backpack:
        return True
    item = API.FindItem(serial)
    if not item:
        return False
    return item.Container == API.Backpack or getattr(item, "RootContainer", 0) == API.Player.Serial


def is_near_soulforge() -> bool:
    """Checks whether the player is standing within 4 tiles of a Soulforge."""
    ground_items = API.GetItemsOnGround(4)
    if ground_items:
        for it in ground_items:
            g = getattr(it, "Graphic", 0)
            name = str(getattr(it, "Name", "") or "").lower()
            if g in SOULFORGE_GRAPHICS or "soulforge" in name or "forge" in name:
                return True
    return True  # Fallback gracefully to allow player to proceed


def find_nearby_trash_barrel() -> Optional[Any]:
    """Scans ground within 3 tiles for an existing Trash Barrel."""
    ground_items = API.GetItemsOnGround(3)
    if ground_items:
        for item in ground_items:
            g = getattr(item, "Graphic", 0)
            name = str(getattr(item, "Name", "") or "").lower()
            if "trash" in name or g in TRASH_BARREL_GRAPHICS:
                return item
    return None

# ==============================================================================
# Satchel & Board Management
# ==============================================================================

def auto_detect_satchel() -> Optional[int]:
    """Scans root backpack subcontainers to automatically detect the satchel holding boards."""
    global wood_hue_override
    bp_items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not bp_items:
        return None

    # First priority: container with boards
    for item in bp_items:
        if item.Graphic in CONTAINER_GRAPHICS or getattr(item, "IsContainer", False):
            sub_items = API.ItemsInContainer(item.Serial, recursive=True)
            if sub_items:
                for sub in sub_items:
                    if sub.Graphic in BOARD_GRAPHICS:
                        hue = getattr(sub, "Hue", 0) or 0
                        wood_hue_override = hue
                        return item.Serial

    # Second priority: elven satchel or bag
    for item in bp_items:
        if item.Graphic in [0x2DD6, 0x0E76]:
            return item.Serial

    return None


def is_target_board(item: Any) -> bool:
    """Determines if an item matches the desired oak/wood board criteria."""
    if not item or item.Graphic not in BOARD_GRAPHICS:
        return False
    hue = getattr(item, "Hue", 0) or 0
    if wood_hue_override is not None:
        return hue == wood_hue_override
    if hue == OAK_WOOD_HUE:
        return True
    # If no hue matched yet and board has any non-zero hue, treat as special/oak
    return hue != 0 or hue == 0


def count_backpack_boards() -> int:
    """Counts matching boards in the player's root backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    total = 0
    for item in items:
        if item.Serial != satchel_serial and is_target_board(item):
            total += getattr(item, "Amount", 1) or 1
    return total


def count_satchel_boards() -> int:
    """Counts matching boards inside the designated satchel."""
    if not satchel_serial:
        return 0
    items = API.ItemsInContainer(satchel_serial, recursive=True) or []
    total = 0
    for item in items:
        if is_target_board(item):
            total += getattr(item, "Amount", 1) or 1
    return total


def get_satchel_board_stack() -> Optional[Any]:
    """Finds the largest stack of matching boards inside the satchel."""
    if not satchel_serial:
        return None
    items = API.ItemsInContainer(satchel_serial, recursive=True) or []
    best_item = None
    best_amt = 0
    for item in items:
        if is_target_board(item):
            amt = getattr(item, "Amount", 1) or 1
            if amt > best_amt:
                best_amt = amt
                best_item = item
    return best_item


def count_total_boards() -> int:
    """Counts matching boards across both root backpack and satchel."""
    return count_backpack_boards() + count_satchel_boards()


def restock_boards_from_satchel(amount: int = RESTOCK_BATCH_BOARDS) -> bool:
    """Pulls a batch of oak boards from the satchel into the root backpack."""
    if not satchel_serial:
        return False

    # Pre-open satchel so the server registers container access
    API.UseObject(satchel_serial)
    API.Pause(0.4)

    stack = get_satchel_board_stack()
    if not stack:
        return False

    avail = getattr(stack, "Amount", 1) or 1
    amt_to_move = min(avail, amount)
    if amt_to_move <= 0:
        return False

    dest = API.Player.Backpack.Serial if (API.Player and API.Player.Backpack) else API.Backpack
    update_status(f"Restocking {amt_to_move} boards...")
    API.MoveItem(stack.Serial, dest, amt_to_move)

    # Wait for arrival in root backpack
    for _ in range(6):
        API.Pause(0.2)
        if count_backpack_boards() >= 6:
            update_stats()
            return True

    update_stats()
    return count_backpack_boards() >= 6

# ==============================================================================
# Saws & Tools Management
# ==============================================================================

def get_available_saws() -> List[Any]:
    """Returns all saws currently in the player's root backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    return [it for it in items if it.Graphic in SAW_GRAPHICS]


def get_carpentry_tools() -> List[Any]:
    """Returns any carpentry tool in the player's root backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    return [it for it in items if it.Graphic in CARPENTRY_TOOL_GRAPHICS]


def get_active_saw() -> Optional[Any]:
    """Returns a valid saw to use, cycling to the next saw if active one is broken."""
    global active_saw_serial
    if active_saw_serial:
        saw = API.FindItem(active_saw_serial)
        if saw and (saw.Graphic in SAW_GRAPHICS or saw.Graphic in CARPENTRY_TOOL_GRAPHICS):
            return saw
        active_saw_serial = None

    saws = get_available_saws()
    if saws:
        active_saw_serial = saws[0].Serial
        return saws[0]

    tools = get_carpentry_tools()
    if tools:
        active_saw_serial = tools[0].Serial
        return tools[0]

    return None

# ==============================================================================
# Ingredients & Stashing
# ==============================================================================

def count_backpack_residue() -> int:
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    return sum(it.Amount for it in items if it.Graphic in MAGICAL_RESIDUE_GRAPHICS)


def count_backpack_essence() -> int:
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    return sum(it.Amount for it in items if it.Graphic in ENCHANTED_ESSENCE_GRAPHICS)


def count_total_residue() -> int:
    items = API.ItemsInContainer(API.Backpack, recursive=True) or []
    return sum(it.Amount for it in items if it.Graphic in MAGICAL_RESIDUE_GRAPHICS)


def count_total_essence() -> int:
    items = API.ItemsInContainer(API.Backpack, recursive=True) or []
    return sum(it.Amount for it in items if it.Graphic in ENCHANTED_ESSENCE_GRAPHICS)


def stash_unraveled_ingredients() -> None:
    """Moves newly unraveled residue and essence from root backpack into satchel."""
    if not AUTO_STASH_INGREDIENTS or not satchel_serial:
        return
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    for it in items:
        if it.Serial != satchel_serial and it.Graphic in ALL_INGREDIENT_GRAPHICS:
            API.MoveItem(it.Serial, satchel_serial)
            API.Pause(0.4)

# ==============================================================================
# UI & Gump Management
# ==============================================================================

def update_stats() -> None:
    """Refreshes all Gump labels, counts, and announces skill gains."""
    global last_imbue_skill, last_carp_skill
    global lbl_imbue_skill, lbl_carp_skill, lbl_counts, lbl_resources, lbl_ingredients, lbl_satchel

    # 1. Imbuing skill
    i_skill = API.GetSkill("Imbuing")
    if i_skill and lbl_imbue_skill:
        val = float(i_skill.Value)
        cap = float(i_skill.Cap)
        lbl_imbue_skill.Text = f"Imbuing: {val:.1f} / {cap:.1f}"
        if last_imbue_skill is not None and val > last_imbue_skill:
            gain = val - last_imbue_skill
            API.SysMsg(f"[Imbuing] Gain +{gain:.1f}! Skill is now {val:.1f}", HUE_SUCCESS)
        last_imbue_skill = val

    # 2. Carpentry skill
    c_skill = API.GetSkill("Carpentry")
    if c_skill and lbl_carp_skill:
        val = float(c_skill.Value)
        cap = float(c_skill.Cap)
        lbl_carp_skill.Text = f"Carpentry: {val:.1f} / {cap:.1f}"
        if last_carp_skill is not None and val > last_carp_skill:
            gain = val - last_carp_skill
            API.SysMsg(f"[Carpentry] Gain +{gain:.1f}! Skill is now {val:.1f}", HUE_INFO)
        last_carp_skill = val

    # 3. Counters
    if lbl_counts:
        lbl_counts.Text = f"Crafted: {staves_crafted} | Unraveled: {staves_unraveled} | Fail: {craft_failures}"

    # 4. Resources
    bp_b = count_backpack_boards()
    sat_b = count_satchel_boards()
    saws_c = len(get_available_saws())
    if lbl_resources:
        lbl_resources.Text = f"Boards: {bp_b} (Pack) + {sat_b} (Satchel) | Saws: {saws_c}"

    # 5. Ingredients
    res_tot = count_total_residue()
    ess_tot = count_total_essence()
    if lbl_ingredients:
        lbl_ingredients.Text = f"Residue: {res_tot} (+{residue_gained}) | Essence: {ess_tot} (+{essence_gained})"

    # 6. Satchel
    if lbl_satchel:
        lbl_satchel.Text = f"Satchel: 0x{satchel_serial:X}" if satchel_serial else "Satchel: Not Set"


def on_pause_clicked() -> None:
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Trainer paused." if is_paused else "Trainer resumed.", HUE_WARN if is_paused else HUE_INFO)


def on_satchel_clicked() -> None:
    global satchel_serial, wood_hue_override
    API.SysMsg("[Trainer] Target your Oak Board Satchel (or ESC to cancel)...", HUE_INFO)
    s = API.RequestTarget(timeout=6.0)
    if s and s != API.Player.Serial:
        satchel_serial = s
        API.UseObject(satchel_serial)
        API.Pause(0.4)
        # Auto-detect wood hue in satchel
        items = API.ItemsInContainer(satchel_serial, recursive=True) or []
        for it in items:
            if it.Graphic in BOARD_GRAPHICS:
                wood_hue_override = getattr(it, "Hue", 0) or 0
                break
        API.SysMsg(f"[Trainer] Satchel set to 0x{satchel_serial:X} (Boards: {count_satchel_boards()})", HUE_SUCCESS)
    update_stats()


def on_trash_clicked() -> None:
    global trash_barrel_serial
    API.SysMsg("[Trainer] Target your Trash Barrel (or ESC to clear)...", HUE_INFO)
    t = API.RequestTarget(timeout=6.0)
    if t and t != API.Player.Serial:
        trash_barrel_serial = t
        API.SysMsg(f"[Trainer] Trash barrel set: 0x{trash_barrel_serial:X}", HUE_SUCCESS)
    else:
        trash_barrel_serial = None
        API.SysMsg("[Trainer] Trash barrel cleared.", HUE_INFO)


def on_stop_clicked() -> None:
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.SysMsg("[Trainer] Stop requested.", HUE_WARN)
    API.Stop()


def on_gump_disposed() -> None:
    global is_stopped
    if not is_stopped and not API.StopRequested:
        is_stopped = True
        API.Stop()


def create_control_gump() -> None:
    """Initializes and renders the combined Craft & Unravel Control Gump."""
    global gump, lbl_status, lbl_imbue_skill, lbl_carp_skill, lbl_counts
    global lbl_resources, lbl_ingredients, lbl_satchel, btn_pause, btn_satchel, btn_trash, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(520, 80, 360, 245)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 360, 245)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("Imbuing: Craft & Unravel", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    lbl_author = API.Gumps.CreateGumpLabel(f"by FesterHead v{SCRIPT_VERSION}", 996)
    lbl_author.SetPos(225, 8)
    gump.Add(lbl_author)

    # Status
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skills: Imbuing & Carpentry
    lbl_imbue_skill = API.Gumps.CreateGumpLabel("Imbuing: -- / --", 68)
    lbl_imbue_skill.SetPos(10, 48)
    gump.Add(lbl_imbue_skill)

    lbl_carp_skill = API.Gumps.CreateGumpLabel("Carpentry: -- / --", 996)
    lbl_carp_skill.SetPos(190, 48)
    gump.Add(lbl_carp_skill)

    # Counters
    lbl_counts = API.Gumps.CreateGumpLabel("Crafted: 0 | Unraveled: 0 | Fail: 0", 53)
    lbl_counts.SetPos(10, 70)
    gump.Add(lbl_counts)

    # Resources (Boards & Saws)
    lbl_resources = API.Gumps.CreateGumpLabel("Boards: -- | Saws: --", 996)
    lbl_resources.SetPos(10, 92)
    gump.Add(lbl_resources)

    # Ingredients (Residue & Essence)
    lbl_ingredients = API.Gumps.CreateGumpLabel("Residue: 0 (+0) | Essence: 0 (+0)", 88)
    lbl_ingredients.SetPos(10, 114)
    gump.Add(lbl_ingredients)

    # Satchel status
    lbl_satchel = API.Gumps.CreateGumpLabel("Satchel: Auto-detecting...", 996)
    lbl_satchel.SetPos(10, 136)
    gump.Add(lbl_satchel)

    # Buttons Row 1: Set Satchel / Set Trash
    btn_satchel = API.Gumps.CreateSimpleButton("Set Satchel", 165, 24)
    btn_satchel.SetPos(10, 166)
    API.Gumps.AddControlOnClick(btn_satchel, on_satchel_clicked)
    gump.Add(btn_satchel)

    btn_trash = API.Gumps.CreateSimpleButton("Set Trash", 165, 24)
    btn_trash.SetPos(185, 166)
    API.Gumps.AddControlOnClick(btn_trash, on_trash_clicked)
    gump.Add(btn_trash)

    # Buttons Row 2: Pause / Stop
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 165, 26)
    btn_pause.SetPos(10, 198)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 165, 26)
    btn_stop.SetPos(185, 198)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)
    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    global gump
    if gump and not getattr(gump, "IsDisposed", False):
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes UI callbacks, pauses, and checks for stop requests."""
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
    """Pauses for a duration while keeping the UI and stop callbacks responsive."""
    elapsed = 0.0
    step = 0.2
    while elapsed < seconds:
        if not check_ui_events():
            return False
        API.Pause(step)
        elapsed += step
    return check_ui_events()

# ==============================================================================
# Crafting Engine (Make Last from Saw)
# ==============================================================================

def craft_oak_quarterstaff() -> Optional[int]:
    """
    Executes a 'Make Last' craft from an available saw in the backpack.
    Returns the serial of the newly crafted staff if successful, or None on failure.
    """
    global craft_failures, staves_crafted, active_saw_serial

    # 1. Ensure we have sufficient oak boards (backpack or satchel)
    total_boards = count_total_boards()
    if total_boards < 6:
        API.SysMsg(f"[Trainer] Out of oak boards! (Total available: {total_boards}). Pausing.", HUE_ALERT)
        update_status("Out of boards")
        on_pause_clicked()
        return None

    # 2. If root backpack is low on boards, pull a batch from satchel
    if count_backpack_boards() < 6 and count_satchel_boards() >= 6:
        restock_boards_from_satchel()

    # 2. Find an active saw
    saw = get_active_saw()
    if not saw:
        API.SysMsg("[Trainer] No saws found in backpack! Please restock saws and click Resume.", HUE_ALERT)
        update_status("No saws")
        on_pause_clicked()
        return None

    # 3. Snapshot backpack items before crafting for serial diff
    bp_before = {item.Serial for item in (API.ItemsInContainer(API.Backpack, recursive=False) or [])}

    # 4. Open carpentry craft menu if not open
    if not API.HasGump():
        API.ClearJournal()
        API.UseObject(saw.Serial)
        if not API.WaitForGump(delay=2.5):
            debug_msg("Carpentry menu did not appear.")
            return None

    # 5. Click Make Last (Button 21)
    update_status("Crafting staff...")
    API.ClearJournal()
    API.ReplyGump(GUMP_BTN_MAKE_LAST)
    wait_with_ui(CRAFT_DELAY)

    # 6. Analyze journal entries
    entries = API.GetJournalEntries(CRAFT_DELAY + 0.8)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    # Check if Make Last is uninitialized
    if any("haven't made anything" in t or "have not made" in t for t in j_text) or API.GumpContains("haven't made anything"):
        API.SysMsg("[Trainer] 'Make Last' is not primed yet!", HUE_WARN)
        API.SysMsg("[Trainer] In the Carpentry menu: Click 'Weapons' -> 'Quarter Staff' once to craft it, then click Resume on the Gump.", HUE_ALERT)
        update_status("Prime Quarter Staff")
        on_pause_clicked()
        return None

    # Check tool wear / breakage
    if any("worn out" in t or "broke" in t or "destroyed" in t for t in j_text):
        API.SysMsg("[Trainer] Saw broke! Cycling to the next saw in backpack...", HUE_INFO)
        active_saw_serial = None

    # Check resource depletion
    if any("sufficient wood" in t or "enough wood" in t for t in j_text) or API.InJournal("sufficient wood"):
        restock_boards_from_satchel()
        return None

    # Check craft failure
    failed = any("you fail" in t or "failed" in t or "destroy" in t for t in j_text) or API.InJournal("you fail")
    if failed:
        craft_failures += 1
        debug_msg("Craft attempt failed.")
        return None

    # 7. Identify newly crafted item via backpack serial diff
    bp_after = API.ItemsInContainer(API.Backpack, recursive=False) or []
    new_item = None
    for item in bp_after:
        if item.Serial not in bp_before:
            new_item = item
            break

    # Fallback: scan for any staff in backpack
    if not new_item:
        for item in bp_after:
            if item.Graphic in ALL_STAFF_GRAPHICS:
                new_item = item
                break

    if new_item:
        staves_crafted += 1
        debug_msg(f"Crafted staff 0x{new_item.Serial:X} (Graphic 0x{new_item.Graphic:X})")
        return new_item.Serial

    return None

# ==============================================================================
# Unraveling Engine (Soulforge Unravel)
# ==============================================================================

def wait_for_imbuing_menu(timeout: float = 4.0) -> bool:
    """Waits specifically for the server-side Imbuing Menu to open."""
    start = API.GetTime() if hasattr(API, "GetTime") else 0
    import time
    start_t = time.time()
    while (time.time() - start_t) < timeout:
        if API.StopRequested or is_stopped:
            return False
        if API.HasGump():
            if (API.GumpContains("Adds or modifies") or
                    API.GumpContains("Repeats the last") or
                    API.GumpContains("IMBUING MENU") or
                    API.GumpContains("Unravels all items")):
                return True
        API.Pause(0.1)
    return False


def execute_unravel_item(item_serial: int) -> bool:
    """
    Unravels a single item at the nearby Soulforge.
    Returns True if the item was successfully unraveled/destroyed.
    """
    global staves_unraveled, unravel_failures, residue_gained, essence_gained

    if not is_near_soulforge():
        API.SysMsg("[Trainer] Must be standing near a Soulforge to unravel!", HUE_WARN)
        update_status("Need Soulforge")
        on_pause_clicked()
        return False

    item_obj = API.FindItem(item_serial)
    if not item_obj:
        debug_msg(f"Staff 0x{item_serial:X} not found to unravel.")
        return False

    item_name = getattr(item_obj, "Name", "") or "Oak Quarterstaff"

    # Pre-unravel ingredient snapshot
    before_res = count_total_residue()
    before_ess = count_total_essence()

    update_status("Unraveling...")
    API.ClearJournal()
    API.Pause(0.3)

    # If a non-imbuing gump is currently open (e.g. lingering craft menu), close it
    if API.HasGump():
        if not (API.GumpContains("Adds or modifies") or
                API.GumpContains("Repeats the last") or
                API.GumpContains("IMBUING MENU") or
                API.GumpContains("Unravels all items")):
            API.CloseGump()
            API.Pause(0.2)

    API.UseSkill("Imbuing")

    if not wait_for_imbuing_menu(timeout=4.0):
        debug_msg("Imbuing menu did not appear.")
        return False

    # Reply with Unravel Item button
    active_id = API.HasGump()
    reply_ok = API.ReplyGump(GUMP_BTN_UNRAVEL_ITEM, active_id)
    if not reply_ok:
        API.ReplyGump(GUMP_BTN_UNRAVEL_ITEM)

    if API.WaitForTarget(timeout=3.0):
        API.Target(item_serial)
    else:
        debug_msg("Unravel target cursor timed out.")
        return False

    wait_with_ui(UNRAVEL_DELAY)

    # Handle confirmation sub-gump if it appears
    import time
    start_c = time.time()
    while (time.time() - start_c) < 2.0:
        if API.HasGump():
            if (API.GumpContains("special material") or
                    API.GumpContains("DESTROYED") or
                    API.GumpContains("UNRAVEL MAGIC ITEM CONFIRMATION") or
                    API.GumpContains("unravel")):
                conf_gump = API.GetGump()
                conf_buttons = []
                if conf_gump and hasattr(conf_gump, "Children"):
                    for child in conf_gump.Children:
                        if hasattr(child, "ButtonID") and child.ButtonID is not None:
                            conf_buttons.append(child.ButtonID)
                btn = conf_buttons[0] if conf_buttons and conf_buttons[0] != 0 else GUMP_BTN_CONFIRM
                API.ReplyGump(btn)
                API.Pause(0.4)
                break
        API.Pause(0.1)

    # Inspect journal results
    entries = API.GetJournalEntries(UNRAVEL_DELAY + 1.2)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    # Check if item cannot be unraveled
    if any("cannot be unraveled" in t or "cannot unravel" in t or "not skilled enough" in t for t in j_text):
        API.SysMsg(f"[Trainer] Item '{item_name}' cannot be unraveled.", HUE_WARN)
        unravel_failures += 1
        if AUTO_TRASH_UNUNRAVELABLE and trash_barrel_serial:
            API.SysMsg("[Trainer] Discarding into trash barrel...", HUE_INFO)
            API.MoveItem(item_serial, trash_barrel_serial)
            API.Pause(MOVE_DELAY)
        return False

    # Check if item was successfully destroyed/unraveled
    item_gone = not API.FindItem(item_serial)
    journal_success = any(
        w in t for t in j_text for w in ["extract", "obtain", "residue", "essence", "relic", "destroyed"]
    )

    if item_gone or journal_success:
        staves_unraveled += 1

        # Calculate gained ingredients
        after_res = count_total_residue()
        after_ess = count_total_essence()
        delta_res = max(0, after_res - before_res)
        delta_ess = max(0, after_ess - before_ess)
        residue_gained += delta_res
        essence_gained += delta_ess

        res_str = f" (+{delta_res} residue)" if delta_res > 0 else ""
        ess_str = f" (+{delta_ess} essence)" if delta_ess > 0 else ""
        API.SysMsg(f"[Trainer] Unraveled '{item_name}'{res_str}{ess_str}.", HUE_SUCCESS)

        stash_unraveled_ingredients()
        update_stats()
        return True

    return False


def is_quarter_staff(item: Any) -> bool:
    """Checks if an item is a quarterstaff or crafted training staff."""
    if not item:
        return False
    g = getattr(item, "Graphic", 0)
    name = str(getattr(item, "Name", "") or "").lower()
    return g in ALL_STAFF_GRAPHICS or "staff" in name or "quarter" in name


def get_backpack_staves() -> List[Any]:
    """Finds all quarterstaves or crafted staves currently in the root backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    return [it for it in items if is_quarter_staff(it)]


def sweep_and_unravel_all_staves(reason: str = "Backpack Sweep") -> int:
    """
    Scans the root backpack and unravels all quarterstaves currently present.
    Returns the number of staves unraveled during this sweep.
    """
    staves = get_backpack_staves()
    if not staves:
        return 0

    API.SysMsg(f"[Trainer] [{reason}] Found {len(staves)} quarterstaff/staves in backpack. Unraveling all...", HUE_INFO)
    update_status(f"Unraveling ({len(staves)} staves)")

    unraveled_count = 0
    for staff in staves:
        if API.StopRequested or is_stopped:
            break
        # Verify item still exists in backpack before attempting unravel
        if API.FindItem(staff.Serial):
            if execute_unravel_item(staff.Serial):
                unraveled_count += 1
            wait_with_ui(0.4)

    return unraveled_count


def perform_periodic_reset(cycle_num: int) -> None:
    """
    Executes a periodic refresh ('starting again' maintenance cycle):
    1. Pre-opens / touches satchel to keep server container window synchronized.
    2. Verifies active saw and Soulforge proximity.
    3. Unravels ALL quarterstaves accumulated in the backpack.
    4. Stashes any reclaimed residue and essence into the satchel.
    """
    API.SysMsg(f"[Trainer] [10-Imbue Reset] Cycle {cycle_num}: Re-synchronizing containers & sweeping backpack staves...", HUE_INFO)

    # 1. Resynchronize satchel container
    if satchel_serial:
        API.UseObject(satchel_serial)
        API.Pause(0.3)

    # 2. Check saw health
    get_active_saw()

    # 3. Unravel any and all staves in backpack
    sweep_and_unravel_all_staves("10-Imbue Reset")

    # 4. Stash all accumulated ingredients
    stash_unraveled_ingredients()


# ==============================================================================
# Main Orchestration Loop
# ==============================================================================

def main():
    global satchel_serial, trash_barrel_serial

    API.SysMsg(f"=== FesterUO Intermediate Imbuing Trainer v{SCRIPT_VERSION} ===", HUE_INFO)

    # 1. Verify Soulforge proximity
    if not is_near_soulforge():
        API.SysMsg("[Trainer] WARNING: Please stand adjacent to a Soulforge before starting!", HUE_ALERT)

    # 2. Check saws
    saws = get_available_saws()
    if not saws:
        API.SysMsg("[Trainer] No saws detected in backpack! Please place saws in your backpack.", HUE_ALERT)

    # 3. Detect or prompt for Satchel
    detected = auto_detect_satchel()
    if detected:
        satchel_serial = detected
        API.UseObject(satchel_serial)
        API.Pause(0.4)
        API.SysMsg(f"[Trainer] Auto-detected oak board satchel: 0x{satchel_serial:X} (Boards: {count_satchel_boards()})", HUE_SUCCESS)
    else:
        API.SysMsg("[Trainer] Target your Oak Board Satchel (or press ESC to use backpack boards only)...", HUE_INFO)
        target_s = API.RequestTarget(timeout=6.0)
        if target_s and target_s != API.Player.Serial:
            satchel_serial = target_s
            API.UseObject(satchel_serial)
            API.Pause(0.4)
            API.SysMsg(f"[Trainer] Satchel set: 0x{satchel_serial:X} (Boards: {count_satchel_boards()})", HUE_SUCCESS)
        else:
            satchel_serial = None
            API.SysMsg("[Trainer] Using backpack boards only.", HUE_WARN)

    # 4. Check for nearby Trash Barrel
    nearby_trash = find_nearby_trash_barrel()
    if nearby_trash:
        trash_barrel_serial = nearby_trash.Serial
        API.SysMsg(f"[Trainer] Auto-detected nearby trash barrel: 0x{trash_barrel_serial:X}", HUE_INFO)

    # 5. Initialize Gump & stats
    create_control_gump()
    update_stats()
    update_status("Running")

    API.SysMsg(f"[Trainer] Ready! Saws: {len(saws)} | Boards: {count_backpack_boards()} pack, {count_satchel_boards()} satchel.", HUE_SUCCESS)

    # Clean up any leftover quarterstaves in backpack first
    sweep_and_unravel_all_staves("Startup")

    cycle_count: int = 0

    # 6. Core Craft & Unravel Loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Check target skill
        cur_skill = API.GetSkill("Imbuing")
        if cur_skill and float(cur_skill.Value) >= TARGET_IMBUING_SKILL:
            API.SysMsg(f"[Trainer] Target Imbuing skill ({TARGET_IMBUING_SKILL:.1f}) reached! Congratulations!", HUE_SUCCESS)
            update_status("Target Reached")
            break

        # Periodic 10-imbue reset routine ("think it's starting again")
        if cycle_count > 0 and (cycle_count % SWEEP_INTERVAL) == 0:
            perform_periodic_reset(cycle_count)

        # Step 1: Craft an Oak Quarterstaff via Make Last
        staff_serial = craft_oak_quarterstaff()

        # Step 2: Unravel the crafted staff if created
        if staff_serial:
            wait_with_ui(0.3)
            execute_unravel_item(staff_serial)

        # Safety sweep: If lingering staves were missed and are accumulating in backpack, sweep them immediately
        lingering = get_backpack_staves()
        if len(lingering) >= 2:
            sweep_and_unravel_all_staves("Lingering Staves")

        cycle_count += 1

        # Brief cycle breather
        wait_with_ui(0.4)

    update_status("Stopped")
    dispose_gump()
    API.SysMsg(f"[Trainer] Finished. Total crafted: {staves_crafted}, unraveled: {staves_unraveled}.", HUE_INFO)


def on_stop_hook():
    """Cleanup hook registered with API.OnStop."""
    global is_stopped
    is_stopped = True
    dispose_gump()


API.OnStop(on_stop_hook)

main()
