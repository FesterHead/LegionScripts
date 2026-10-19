"""
TrainImbuing.py - Automated Resource-Efficient Imbuing Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Fully automated, resource-efficient Imbuing skill training script for TazUO featuring:
    - Dual Training Modes (Toggleable via Gump or Configuration):
        * Reimbue Loop Training (Primary Workhorse, 45.0 - 120.0):
            - Automatically invokes "Imbue Last Property" (`10008`) with target cursor cycling at a Soulforge.
            - ServUO Publish 57 20-Imbue Architecture: Repeatedly re-imbues the same item until it achieves
              20 successful imbuements (matching ServUO's `TimesImbued(item) < 20` skill gain limit).
            - Failed attempts continue rolling for skill gains without counting toward the 20-success cap.
            - Automatically detects and confirms property replacement sub-gumps immediately.
            - Automatically draws fresh items (daggers, caps, jingasas, etc.) from an Item Supply
              Container or backpack when an active item reaches 20 successes or capacity.
        * Mass Unraveling / Recycler Mode (0.0 - 50.0+ / Material Farming):
            - Automates bulk item or container unraveling at a Soulforge to gain early skill
              and stock up on Magical Residues, Enchanted Essences, and Relic Fragments.
            - Supports both backpack subcontainers (bulk container unraveling) and external house
              supply chests (draws items into backpack one-by-one to meet server proximity rules).
            - Skill-Threshold Auto-Return & Session Blacklist: If the server reports your Imbuing
              skill is too low to unravel an item, automatically returns the item back into the
              house supply chest and blacklists its serial so it is skipped for the rest of the
              session, pausing cleanly with "Supply Depleted" once all eligible items are done.
    - Automated Item Recycling via Soulforge Unraveling:
        * Once an item reaches 20 successes (or maximum server capacity), the script automatically
          unravels it at the Soulforge, reclaiming substantial Magical Residue and Enchanted Essence
          from the fully imbued, high-intensity item.
        * Alternative Trash Barrel / Discard Bag support for items that cannot be unraveled.
    - Resource Satchel & Chest Restocking / Stashing:
        * Prompts player to target a Resource Chest / Satchel containing Magical Residues,
          Enchanted Essences, and Gems (Citrine, Amber, Tourmaline, etc.).
        * Automatically stashes unraveled materials (Magical Residue, Enchanted Essence, Relic
          Fragments) from the root backpack into the resource satchel/chest.
        * Automatically restocks working buffers into the main backpack when reserves run low.
    - Milestone Guidance & Success Rate Optimization:
        * Dynamic progression ladder recommending optimal properties (Reflect Physical Damage,
          Hit Dispel, Damage Increase, Lower Reagent Cost, etc.) to maintain the ~50-70% success
          rate sweet spot for maximum skill gains.
        * Interactive "Setup Imbue" button allowing manual calibration of properties and intensity.
    - Interactive Control Gump:
        * Real-time training status, live Imbuing skill level and cap with gain announcements.
        * Dual success and fail attempt counters (e.g., "Item: Dagger | Success: 14/20 | Fails: 3"),
          Imbued / Unraveled / Failed counters.
        * Live Resource counts (Residue, Essence, Gems) and container binding indicators.
        * Interactive Pause / Resume, Mode Toggle, Setup Imbue, Item Supply, Resources, Trash,
          and Stop buttons.
    - Loop Safety & Exception Handling:
        * Strict adherence to API.StopRequested checks, API.Pause delays, and API.OnStop hooks.
"""

import time
from typing import List, Tuple, Optional, Set, Dict, Any
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Script version
SCRIPT_VERSION: str = "1.1.1"

# Target Imbuing skill to stop training (e.g. 100.0 for GM, 120.0 for Legendary)
TARGET_SKILL: float = 120.0

# Initial Training Mode: "REIMBUE" (Active Imbuing) or "UNRAVEL" (Mass Unraveling)
TRAINING_MODE: str = "REIMBUE"

# Target successful imbuements on a single item before retiring/recycling it.
# In ServUO (Publish 57 / Stygian Abyss Imbuing.cs), skill gains are granted up to 20 successful imbuements
# on the same item (TimesImbued < 20). Repeated imbuements are not penalized, and fails still grant rolls.
MAX_SUCCESSES_PER_ITEM: int = 20

# Maximum fail attempts allowed on a single item before retiring it as a safety precaution.
MAX_FAILS_PER_ITEM: int = 30

# Automatically unravel items at the Soulforge after retiring them
# to reclaim valuable Magical Residue and Enchanted Essence.
AUTO_UNRAVEL_AFTER_MAX: bool = True

# Action delays in seconds
IMBUE_DELAY: float = 1.6          # Delay after sending an imbue command
UNRAVEL_DELAY: float = 1.2        # Delay after sending an unravel command
MOVE_DELAY: float = 0.85          # Container drag/drop delay (satisfies ServUO 750ms-1000ms NextActionTime)
RESTOCK_DELAY: float = 0.8        # Restock pause delay

# Working buffer of Magical Residue and Gems maintained in main backpack
MIN_BACKPACK_RESIDUE: int = 15
RESTOCK_BATCH_RESIDUE: int = 60

MIN_BACKPACK_GEMS: int = 10
RESTOCK_BATCH_GEMS: int = 30

# Proximity check for Soulforge (set False to skip proximity scan if using custom multi/static)
REQUIRE_SOULFORGE_CHECK: bool = False

# Server Imbuing Gump button IDs (matched to native client Imbuing Menu)
GUMP_BTN_CANCEL: int = 1             # "CANCEL"
GUMP_BTN_IMBUE_ITEM: int = 10005     # "Imbue Item"
GUMP_BTN_REIMBUE_LAST: int = 10006   # "Reimbue Last"
GUMP_BTN_IMBUE_LAST_ITEM: int = 10007  # "Imbue Last Item"
GUMP_BTN_IMBUE_LAST_PROP: int = 10008  # "Imbue Last Property"
GUMP_BTN_UNRAVEL_ITEM: int = 10010   # "Unravel Item"
GUMP_BTN_UNRAVEL_CONTAINER: int = 10011  # "Unravel Container"
GUMP_BTN_CONFIRM: int = 1            # Default confirmation sub-gump button

# Enable verbose debug messages in client console
DEBUG: bool = True

# System message colors (hues)
HUE_INFO: int = 68     # Cyan / Light Green
HUE_WARN: int = 53     # Yellow
HUE_ERROR: int = 32    # Red
HUE_SUCCESS: int = 63   # Bright Green


# ==============================================================================
# Item & Graphic Definitions
# ==============================================================================

# Soulforge structures (house add-ons, Queen's Soulforge, gargish forges)
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
ALL_IMBUING_INGREDIENTS: Set[int] = (
    MAGICAL_RESIDUE_GRAPHICS | ENCHANTED_ESSENCE_GRAPHICS | RELIC_FRAGMENT_GRAPHICS
)

# Standard Gems
STANDARD_GEM_GRAPHICS: Set[int] = {
    0x0F15, 0x0F23, 0x0F24,  # Citrine
    0x0F25,                  # Amber
    0x0F18, 0x0F20,          # Tourmaline
    0x0F13, 0x0F19, 0x0F1A, 0x0F1B,  # Ruby
    0x0F10, 0x0F14,          # Emerald
    0x0F11, 0x0F12,          # Sapphire
    0x0F0F, 0x0F21, 0x0F22,  # Star Sapphire
    0x0F16, 0x0F17,          # Amethyst
    0x0F26, 0x0F27, 0x0F28, 0x0F29, 0x0F30,  # Diamond
}

# Special Mondain's Legacy / Stygian Abyss Gems
SPECIAL_GEM_GRAPHICS: Set[int] = {
    0x3192,  # Perfect Emerald
    0x3193,  # Dark Sapphire
    0x3194,  # Turquoise
    0x3195,  # Ecru Citrine
    0x3196,  # White Pearl
    0x3197,  # Fire Ruby
    0x3198,  # Blue Diamond
    0x3199,  # Brilliant Amber
}

ALL_GEM_GRAPHICS: Set[int] = STANDARD_GEM_GRAPHICS | SPECIAL_GEM_GRAPHICS

# Container graphics to exclude when searching for equipment to imbue
CONTAINER_GRAPHICS: Set[int] = {
    0x0E75, 0x0E76, 0x0E79, 0x0E7A, 0x0E7D, 0x0E7C,  # Backpack, Bag, Pouches, Wooden Boxes
    0x09B0, 0x0E3F, 0x0E77, 0x0E7F, 0x0E40, 0x0E41,  # Pouches, Crates, Barrels, Kegs, Chests
    0x0E42, 0x0E43, 0x2FB7,                          # Metal chests, strongboxes
}

# Currency, Reagent, Ingot & Craft Resource graphics to strictly exclude from imbuing targets
EXCLUDED_GRAPHICS: Set[int] = (
    ALL_IMBUING_INGREDIENTS | ALL_GEM_GRAPHICS | CONTAINER_GRAPHICS | {
        0x0EED, 0x0EF0,          # Gold, Silver coins
        0x1BEF, 0x1BF2,          # Ingots
        0x1BDD, 0x1BE0,          # Logs
        0x1BD7, 0x1BD8, 0x1BD9,  # Boards
        0x1067, 0x1081,          # Leather
        0x1766, 0x1767, 0x0F95,  # Cloth
        0x0E34, 0x0EF3,          # Blank scrolls
        0x0E21, 0x0E20,          # Bandages
        0x0F0E,                  # Empty bottles
        0x1EB8, 0x1EB9, 0x1EBC, 0x1EBD,  # Tinker tools
        0x13E3, 0x13E4, 0x0FBB, 0x0FB4,  # Smith hammers, tongs
        0x0F9D, 0x0F9E, 0x0F9F,          # Sewing kits, scissors
        0x0FBF, 0x0FC0,                  # Scribe pens
        0x1084, 0x1085,                  # Key rings, keys
        0x0EFA, 0x2252, 0x2253, 0x2D50,  # Spellbooks, runebooks, BOD books
    }
)

# Trash barrel graphics
TRASH_BARREL_GRAPHICS: Set[int] = {0x0E77}

# Optimal Progression Ladder: (min_skill, max_skill, recommended_property, required_materials, recommendation_notes)
PROGRESSION_LADDER: List[Tuple[float, float, str, str, str]] = [
    (0.0, 45.0, "Unravel Magic Loot / Items", "Magical items (loot/crafted)", "0-45: Mass unravel at Soulforge for free skill & residue"),
    (45.0, 55.0, "Hit Dispel (Weapons) or Luck (Armor/Weapons)", "Amber / Citrine + Residue", "Daggers: Hit Dispel (Amber + Residue) | Armor/Weapons: Luck (Citrine + Residue, ~50-70% success)"),
    (55.0, 70.0, "Hit Dispel or Luck (Higher Intensity)", "Amber / Citrine + Residue", "Daggers / Butcher Knives / Jingasas (~50-70% success)"),
    (70.0, 90.0, "Hit Dispel / LRC", "Amber/Tourmaline + Residue", "Weapons: Hit Dispel | Armor: Lower Reagent Cost (~50-70% success)"),
    (90.0, 105.0, "Damage Increase / High Intensity", "Citrine/Gems + Essence", "Weapons / Armor (mid-high intensity, ~50-70% success)"),
    (105.0, 120.0, "High Intensity Imbues", "Gems + Essence/Relics", "Weapons / Armor (high intensity, ~50-70% success)"),
]


# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_mode = None
lbl_item = None
lbl_counts = None
lbl_resources = None
lbl_containers = None

btn_pause = None
btn_mode = None
btn_setup = None
btn_supply = None
btn_resource = None
btn_trash = None
btn_stop = None

# Containers & Serials
supply_container_serial: Optional[int] = None
resource_chest_serial: Optional[int] = None
trash_barrel_serial: Optional[int] = None
custom_soulforge_serial: Optional[int] = None

# Active Item State
current_item_serial: Optional[int] = None
current_item_name: str = "None"
current_item_successes: int = 0
current_item_fails: int = 0
target_training_graphic: Optional[int] = None

# Runtime flags
is_paused: bool = False
is_stopped: bool = False

# Counters
total_imbued: int = 0
total_unraveled: int = 0
total_failed: int = 0

# Session-level cache of items that cannot be unraveled due to insufficient skill or low magic
skipped_unravel_serials: Set[int] = set()
# Items that have finished their training cycle (prevent re-selecting failed/plain or unraveled items)
retired_item_serials: Set[int] = set()

last_imbuing_skill: Optional[float] = None
recommended_prop_name: str = "Initializing..."


# ==============================================================================
# Helpers & Logging
# ==============================================================================

def debug_msg(text: str) -> None:
    """Prints debug messages if DEBUG mode is enabled."""
    if DEBUG:
        API.SysMsg(f"[DEBUG-Imbuing] {text}", HUE_INFO)


def update_status(text: str) -> None:
    """Updates the Gump status label."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def get_recommended_tier(skill_val: float) -> Tuple[str, str, str]:
    """Returns (property_name, required_materials, notes) for current skill level."""
    for min_s, max_s, prop_name, mats, notes in PROGRESSION_LADDER:
        if min_s <= skill_val < max_s:
            return prop_name, mats, notes
    last = PROGRESSION_LADDER[-1]
    return last[2], last[3], last[4]


def update_stats() -> None:
    """Refreshes all Gump labels with real-time statistics."""
    global last_imbuing_skill, lbl_skill, lbl_mode, lbl_item, lbl_counts, lbl_resources, lbl_containers
    global recommended_prop_name

    # 1. Skill tracking
    skill_obj = API.GetSkill("Imbuing")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        gain_str = ""
        if last_imbuing_skill is not None and val > last_imbuing_skill:
            gain = val - last_imbuing_skill
            gain_str = f" (+{gain:.1f})"
            API.SysMsg(f"[Imbuing] Skill gained +{gain:.1f}! Current skill: {val:.1f}", HUE_SUCCESS)

        rec_prop, rec_mats, _ = get_recommended_tier(val)
        if rec_prop != recommended_prop_name and last_imbuing_skill is not None:
            API.SysMsg(f"[Imbuing] Milestone! Recommended Property: {rec_prop} ({rec_mats})", HUE_WARN)
        recommended_prop_name = rec_prop

        last_imbuing_skill = val
        lbl_skill.Text = f"Imbuing: {val:.1f} / {cap:.1f}{gain_str}"

    # 2. Mode label
    if lbl_mode:
        lbl_mode.Text = f"Mode: {TRAINING_MODE} | Rec: {recommended_prop_name}"

    # 3. Item & Attempts label
    if lbl_item:
        lbl_item.Text = f"Item: {current_item_name} | Success: {current_item_successes}/{MAX_SUCCESSES_PER_ITEM} | Fails: {current_item_fails}"

    # 4. Counters label
    if lbl_counts:
        lbl_counts.Text = f"Imbued: {total_imbued} | Unraveled: {total_unraveled} | Failed: {total_failed}"

    # 5. Resources label
    if lbl_resources:
        res_cnt = count_total_residue()
        ess_cnt = count_total_essence()
        gem_cnt = count_total_gems()
        lbl_resources.Text = f"Residue: {res_cnt} | Essence: {ess_cnt} | Gems: {gem_cnt}"

    # 6. Containers label
    if lbl_containers:
        sup_str = "Set" if supply_container_serial else "Backpack"
        res_str = "Set" if resource_chest_serial else "None"
        trash_str = "Set" if trash_barrel_serial else ("Unravel" if AUTO_UNRAVEL_AFTER_MAX else "None")
        lbl_containers.Text = f"Supply: {sup_str} | Res: {res_str} | Trash: {trash_str}"


def wait_with_ui(duration: float, step: float = 0.1) -> bool:
    """Waits for duration seconds in small increments while checking for stop or pause."""
    elapsed = 0.0
    while elapsed < duration:
        API.ProcessCallbacks()
        if API.StopRequested or is_stopped:
            return False
        while is_paused and not API.StopRequested and not is_stopped:
            API.ProcessCallbacks()
            API.Pause(0.2)
        API.Pause(step)
        elapsed += step
    return True


def pause_trainer(reason: str = "Paused") -> None:
    """Pauses the trainer and updates UI button state."""
    global is_paused, btn_pause
    is_paused = True
    if btn_pause:
        btn_pause.SetText("Resume")
    update_status(f"Paused ({reason})")


# ==============================================================================
# Soulforge & Proximity Checking
# ==============================================================================

def is_near_soulforge() -> bool:
    """Checks whether the player is currently near a valid Soulforge structure."""
    if not REQUIRE_SOULFORGE_CHECK:
        return True

    # 1. Custom targeted Soulforge
    if custom_soulforge_serial:
        sf_obj = API.FindItem(custom_soulforge_serial)
        if sf_obj and sf_obj.Distance <= 4:
            return True

    # 2. Dynamic ground items
    ground_items = API.GetItemsOnGround(4)
    if ground_items:
        for it in ground_items:
            g = getattr(it, "Graphic", 0)
            name = str(getattr(it, "Name", "") or "").lower()
            if g in SOULFORGE_GRAPHICS or "soulforge" in name:
                return True

    return True  # Fallback gracefully to allow player to proceed


def find_nearby_trash_barrel() -> Optional[Any]:
    """Scans ground within 3 tiles for an existing Trash Barrel."""
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


def wait_for_imbuing_menu(timeout: float = 4.0) -> bool:
    """
    Waits specifically for the server-side Imbuing Menu to open and be parsed.
    Strictly verifies phrases that only appear on the server's Imbuing Menu
    to prevent false positives from client-side script gumps.
    """
    start = time.time()
    while (time.time() - start) < timeout:
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


# ==============================================================================
# Inventory & Resource Management
# ==============================================================================

def is_in_backpack(serial: Optional[int]) -> bool:
    """Checks whether a given serial resides inside the player's root backpack."""
    if not serial or serial == API.Backpack:
        return True
    item = API.FindItem(serial)
    if not item:
        return False
    return item.Container == API.Backpack or getattr(item, "RootContainer", 0) == API.Player.Serial


def count_backpack_residue() -> int:
    """Counts total Magical Residue in the player's root backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    return sum(item.Amount for item in items if item.Graphic in MAGICAL_RESIDUE_GRAPHICS)


def count_backpack_essence() -> int:
    """Counts total Enchanted Essence in the player's root backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    return sum(item.Amount for item in items if item.Graphic in ENCHANTED_ESSENCE_GRAPHICS)


def count_backpack_gems() -> int:
    """Counts total qualifying gems in the player's root backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    return sum(item.Amount for item in items if item.Graphic in ALL_GEM_GRAPHICS)


def count_total_residue() -> int:
    """Counts total Magical Residue across backpack and resource satchel/chest."""
    items = API.ItemsInContainer(API.Backpack, recursive=True) or []
    total = sum(item.Amount for item in items if item.Graphic in MAGICAL_RESIDUE_GRAPHICS)
    if resource_chest_serial and not is_in_backpack(resource_chest_serial):
        ext_items = API.ItemsInContainer(resource_chest_serial, recursive=True) or []
        total += sum(item.Amount for item in ext_items if item.Graphic in MAGICAL_RESIDUE_GRAPHICS)
    return total


def count_total_essence() -> int:
    """Counts total Enchanted Essence across backpack and resource satchel/chest."""
    items = API.ItemsInContainer(API.Backpack, recursive=True) or []
    total = sum(item.Amount for item in items if item.Graphic in ENCHANTED_ESSENCE_GRAPHICS)
    if resource_chest_serial and not is_in_backpack(resource_chest_serial):
        ext_items = API.ItemsInContainer(resource_chest_serial, recursive=True) or []
        total += sum(item.Amount for item in ext_items if item.Graphic in ENCHANTED_ESSENCE_GRAPHICS)
    return total


def count_total_gems() -> int:
    """Counts total qualifying gems across backpack and resource satchel/chest."""
    items = API.ItemsInContainer(API.Backpack, recursive=True) or []
    total = sum(item.Amount for item in items if item.Graphic in ALL_GEM_GRAPHICS)
    if resource_chest_serial and not is_in_backpack(resource_chest_serial):
        ext_items = API.ItemsInContainer(resource_chest_serial, recursive=True) or []
        total += sum(item.Amount for item in ext_items if item.Graphic in ALL_GEM_GRAPHICS)
    return total


def stash_unraveled_ingredients() -> None:
    """Moves newly unraveled ingredients (Magical Residue, Enchanted Essence, Relic Fragments) from root backpack into resource satchel/chest."""
    if not resource_chest_serial:
        return

    bp_items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    for it in bp_items:
        if it.Serial == resource_chest_serial:
            continue

        is_ingredient = (
            it.Graphic in ALL_IMBUING_INGREDIENTS or
            any(w in (getattr(it, "Name", "") or "").lower() for w in ["residue", "essence", "relic"])
        )
        if is_ingredient:
            name = getattr(it, "Name", "") or f"Item (0x{it.Graphic:X})"
            API.SysMsg(f"[Imbuing] Stashing {it.Amount}x {name} into resource satchel...", HUE_INFO)
            API.MoveItem(it.Serial, resource_chest_serial)
            API.Pause(MOVE_DELAY)


def restock_resources_from_chest() -> bool:
    """Restocks Magical Residues and Gems from an external resource chest into the backpack."""
    if not resource_chest_serial:
        return False

    # If the resource container is already inside the player's backpack (e.g. a satchel or pouch),
    # the UO server automatically consumes gems and residue directly from it. No restocking needed!
    if is_in_backpack(resource_chest_serial):
        return True

    chest_items = API.ItemsInContainer(resource_chest_serial, recursive=True) or []
    if not chest_items:
        # Attempt to open chest to load contents
        API.UseObject(resource_chest_serial)
        API.Pause(0.5)
        chest_items = API.ItemsInContainer(resource_chest_serial, recursive=True) or []

    # 1. Restock Magical Residue
    if count_backpack_residue() < MIN_BACKPACK_RESIDUE:
        res_stacks = [it for it in chest_items if it.Graphic in MAGICAL_RESIDUE_GRAPHICS and it.Amount > 0]
        if res_stacks:
            stack = res_stacks[0]
            amt = min(RESTOCK_BATCH_RESIDUE, stack.Amount)
            API.SysMsg(f"[Imbuing] Restocking {amt} Magical Residue from resource chest...", HUE_INFO)
            API.MoveItem(stack.Serial, API.Backpack, amt=amt)
            API.Pause(MOVE_DELAY)

    # 2. Restock Gems
    if count_backpack_gems() < MIN_BACKPACK_GEMS:
        gem_stacks = [it for it in chest_items if it.Graphic in ALL_GEM_GRAPHICS and it.Amount > 0]
        if gem_stacks:
            stack = gem_stacks[0]
            amt = min(RESTOCK_BATCH_GEMS, stack.Amount)
            API.SysMsg(f"[Imbuing] Restocking {amt} Gems from resource chest...", HUE_INFO)
            API.MoveItem(stack.Serial, API.Backpack, amt=amt)
            API.Pause(MOVE_DELAY)

    update_stats()
    return True


# ==============================================================================
# Item Selection & Disposal
# ==============================================================================

def is_imbuable_item(item: Any) -> bool:
    """Validates if an item qualifies as a training target (excluding resources/tools/containers/scrolls)."""
    if not item:
        return False
    g = getattr(item, "Graphic", 0)
    if g in EXCLUDED_GRAPHICS or (0x1F2D <= g <= 0x1F72):  # All Magery/Spell scrolls
        return False
    if item.IsContainer:
        return False
    name = str(getattr(item, "Name", "") or "").lower()
    if any(w in name for w in ["scroll", "reagent", "ingot", "board", "log", "cloth", "leather", "potion", "gem"]):
        return False
    return True


def get_or_fetch_target_item() -> Optional[Any]:
    """
    Returns the active item to imbue.
    If the current item reached max successes (20) or fails (30), handles disposal
    and fetches a fresh item from the supply container or backpack.
    """
    global current_item_serial, current_item_name, current_item_successes, current_item_fails, target_training_graphic

    # 1. Check if current active item is still valid and below max successes and fails
    if current_item_serial:
        item = API.FindItem(current_item_serial)
        if item and item.Container == API.Backpack and current_item_successes < MAX_SUCCESSES_PER_ITEM and current_item_fails < MAX_FAILS_PER_ITEM:
            return item

        # Item reached max successes, fail limit, or is missing -> Dispose / Recycle it
        if item and (current_item_successes >= MAX_SUCCESSES_PER_ITEM or current_item_fails >= MAX_FAILS_PER_ITEM):
            API.SysMsg(f"[Imbuing] Item '{current_item_name}' completed {current_item_successes} successes ({current_item_fails} fails).", HUE_INFO)
            retire_finished_item(item)

        current_item_serial = None
        current_item_name = "None"
        current_item_successes = 0
        current_item_fails = 0

    # 2. Check backpack for an existing imbuable item
    if not supply_container_serial:
        eligible_bp = [
            it for it in (API.ItemsInContainer(API.Backpack, recursive=False) or [])
            if is_imbuable_item(it) and it.Serial not in retired_item_serials and it.Serial not in skipped_unravel_serials
        ]
        if eligible_bp:
            match = None
            if target_training_graphic is not None:
                for it in eligible_bp:
                    if it.Graphic == target_training_graphic:
                        match = it
                        break
            if not match:
                first_g = eligible_bp[0].Graphic
                if all(it.Graphic == first_g for it in eligible_bp) or len(eligible_bp) == 1:
                    match = eligible_bp[0]
                    target_training_graphic = match.Graphic
                else:
                    API.SysMsg("[Imbuing] Multiple item types in backpack! Target the item type you want to train on (e.g. Dagger)...", HUE_INFO)
                    t_serial = API.RequestTarget(timeout=8.0)
                    if t_serial and t_serial != API.Player.Serial:
                        t_obj = API.FindItem(t_serial)
                        if t_obj and is_imbuable_item(t_obj):
                            match = t_obj
                            target_training_graphic = t_obj.Graphic

            if match:
                current_item_serial = match.Serial
                current_item_name = match.Name or f"Item (0x{match.Graphic:X})"
                current_item_successes = 0
                current_item_fails = 0
                API.SysMsg(f"[Imbuing] Active target set to backpack item: {current_item_name}", HUE_INFO)
                update_stats()
                return match

    # 3. Check Supply Container for fresh items
    if supply_container_serial and supply_container_serial != API.Backpack:
        supply_items = API.ItemsInContainer(supply_container_serial, recursive=False) or []
        if not supply_items:
            API.UseObject(supply_container_serial)
            API.Pause(0.5)
            supply_items = API.ItemsInContainer(supply_container_serial, recursive=False) or []

        for it in supply_items:
            if is_imbuable_item(it) and it.Serial not in retired_item_serials and it.Serial not in skipped_unravel_serials:
                name = it.Name or f"Item (0x{it.Graphic:X})"
                if it.Container != API.Backpack:
                    API.SysMsg(f"[Imbuing] Drawing fresh item '{name}' from supply container...", HUE_INFO)
                    API.MoveItem(it.Serial, API.Backpack)
                    start_m = time.time()
                    while (time.time() - start_m) < 1.2:
                        bp_it = API.FindItem(it.Serial)
                        if bp_it and (bp_it.Container == API.Backpack or getattr(bp_it, "RootContainer", 0) == API.Player.Serial):
                            break
                        API.Pause(0.1)

                    bp_it = API.FindItem(it.Serial)
                    if not bp_it or (bp_it.Container != API.Backpack and getattr(bp_it, "RootContainer", 0) != API.Player.Serial):
                        debug_msg(f"Retrying move for '{name}' after cooldown...")
                        API.Pause(0.6)
                        API.MoveItem(it.Serial, API.Backpack)
                        start_m2 = time.time()
                        while (time.time() - start_m2) < 1.2:
                            bp_it2 = API.FindItem(it.Serial)
                            if bp_it2 and (bp_it2.Container == API.Backpack or getattr(bp_it2, "RootContainer", 0) == API.Player.Serial):
                                break
                            API.Pause(0.1)

                    bp_it = API.FindItem(it.Serial)
                    if not bp_it or (bp_it.Container != API.Backpack and getattr(bp_it, "RootContainer", 0) != API.Player.Serial):
                        API.SysMsg(f"[Imbuing] Could not move '{name}' into backpack (unmovable/full). Skipping item.", HUE_WARN)
                        retired_item_serials.add(it.Serial)
                        continue
                    API.Pause(MOVE_DELAY)

                current_item_serial = it.Serial
                current_item_name = name
                current_item_successes = 0
                current_item_fails = 0
                update_stats()
                return it

        # Supply container exhausted
        API.SysMsg("[Imbuing] Supply container has no more qualifying items!", HUE_WARN)
        pause_trainer("Supply Empty")
        return None

    # No items found and no supply container configured
    API.SysMsg("[Imbuing] No items to imbue found in backpack! Please add items or set a Supply Bag.", HUE_WARN)
    pause_trainer("No Items")
    return None


def retire_finished_item(item: Any) -> None:
    """Disposes or recycles a finished item via Soulforge Unraveling or returns to supply."""
    global total_unraveled, retired_item_serials

    if not item:
        return

    retired_item_serials.add(item.Serial)

    # Option A: Auto-Unravel at Soulforge
    if AUTO_UNRAVEL_AFTER_MAX:
        API.SysMsg(f"[Imbuing] Unraveling finished item '{item.Name or 'item'}' at Soulforge...", HUE_INFO)
        if execute_unravel_item(item.Serial):
            return

    # If unraveling failed (e.g. skill too low) or disabled, safely return to supply container
    if supply_container_serial and not is_in_backpack(supply_container_serial):
        API.SysMsg(f"[Imbuing] Returning finished item to supply chest...", HUE_INFO)
        API.MoveItem(item.Serial, supply_container_serial)
        API.Pause(MOVE_DELAY)
    elif trash_barrel_serial:
        API.SysMsg(f"[Imbuing] Depositing finished item into trash barrel / discard bag...", HUE_INFO)
        API.MoveItem(item.Serial, trash_barrel_serial)
        API.Pause(MOVE_DELAY)
    else:
        API.SysMsg("[Imbuing] Item completed max imbues. Left in backpack.", HUE_WARN)


# ==============================================================================
# Imbuing & Unraveling Execution
# ==============================================================================

def execute_reimbue_cycle(target_item: Any) -> bool:
    """Executes a single Reimbue Last attempt on the specified item."""
    global total_imbued, total_failed, current_item_successes, current_item_fails, current_item_serial, current_item_name

    # Check Soulforge proximity
    if not is_near_soulforge():
        API.SysMsg("[Imbuing] Warning: Must be standing near a Soulforge to imbue!", HUE_WARN)
        update_status("Need Soulforge")
        API.Pause(1.0)
        return True

    # Check total available resources across backpack and satchel/chest
    if count_total_residue() < 1:
        API.SysMsg("[Imbuing] Out of Magical Residue! Please refill supplies.", HUE_ERROR)
        pause_trainer("Out of Residue")
        return True

    if count_total_gems() < 1:
        API.SysMsg("[Imbuing] Out of Gems! Please refill supplies.", HUE_ERROR)
        pause_trainer("Out of Gems")
        return True

    # If using an external chest (outside backpack), restock working buffer into backpack
    if resource_chest_serial and not is_in_backpack(resource_chest_serial):
        if count_backpack_residue() < 1 or count_backpack_gems() < 1:
            restock_resources_from_chest()

    update_status(f"Imbuing {current_item_name}...")
    API.ClearJournal()

    # Pacing pause to ensure no action delay collision
    API.Pause(0.4)

    # Invoke Imbuing Skill
    API.UseSkill("Imbuing")

    # Wait specifically for the Soulforge Imbuing Menu
    if not wait_for_imbuing_menu(timeout=4.0):
        debug_msg("Timed out waiting for Imbuing menu.")
        return True

    # Check if server reports no previous imbue configured
    if (API.GumpContains("haven't") or
            API.GumpContains("not made") or
            API.GumpContains("previous")):
        API.SysMsg("[Imbuing] No previous property primed for 'Reimbue Last'!", HUE_WARN)
        API.SysMsg("[Imbuing] Click 'Setup Imbue' on the Gump to choose property & intensity, then click Resume.", HUE_INFO)
        pause_trainer("Setup Required")
        return True

    # Send "Imbue Last Property" (10008) so the server prompts for a target cursor
    API.ReplyGump(GUMP_BTN_IMBUE_LAST_PROP)

    # Target our active item
    if API.WaitForTarget(timeout=2.5):
        API.Target(target_item.Serial)
    else:
        # Fallback if server expected Reimbue Last directly
        debug_msg("Imbue target cursor did not appear, trying Reimbue Last...")
        API.ReplyGump(GUMP_BTN_REIMBUE_LAST)

    # Check immediately for confirmation sub-gump (ServUO prompt when replacing/re-imbuing an existing property)
    start_c = time.time()
    while (time.time() - start_c) < 1.0:
        if API.HasGump():
            curr_gump = API.GetGump()
            gump_text = API.GetGumpContents().lower() if API.GetGumpContents() else ""
            if any(w in gump_text for w in ["replace", "overwrite", "continue", "proceed", "confirm", "warning"]):
                conf_buttons = []
                if curr_gump and hasattr(curr_gump, "Children"):
                    for child in curr_gump.Children:
                        if hasattr(child, "ButtonID") and child.ButtonID is not None and child.ButtonID > 0:
                            conf_buttons.append(child.ButtonID)
                btn = conf_buttons[0] if conf_buttons else GUMP_BTN_CONFIRM
                API.ReplyGump(btn)
                API.Pause(0.3)
                break
        API.Pause(0.1)

    # Action delay for server response
    if not wait_with_ui(IMBUE_DELAY):
        return False

    # Evaluate results via Journal
    entries = API.GetJournalEntries(IMBUE_DELAY + 1.2)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    # Check for max capacity / cannot be imbued further (ServUO 20-imbue cap reached)
    if any("cannot be imbued" in t or "reached its" in t or "limit" in t or "capacity" in t for t in j_text):
        API.SysMsg(f"[Imbuing] Item reached server imbuing capacity! Retiring '{current_item_name}'.", HUE_WARN)
        retire_finished_item(target_item)
        current_item_serial = None
        current_item_name = "None"
        current_item_successes = 0
        current_item_fails = 0
        update_stats()
        return True

    # Check for missing ingredients
    if any("insufficient" in t or "lack" in t or "do not have enough" in t for t in j_text):
        API.SysMsg("[Imbuing] Insufficient materials reported by server.", HUE_WARN)
        if resource_chest_serial:
            restock_resources_from_chest()
        else:
            pause_trainer("Need Resources")
        return True

    # Check for success
    if any("successfully" in t or "you imbue" in t or "you infuse" in t for t in j_text):
        total_imbued += 1
        current_item_successes += 1
        debug_msg(f"Imbue success! Item successes: {current_item_successes}/{MAX_SUCCESSES_PER_ITEM}")

        if current_item_successes >= MAX_SUCCESSES_PER_ITEM:
            API.SysMsg(f"[Imbuing] '{current_item_name}' reached {MAX_SUCCESSES_PER_ITEM} successes! Retiring item for unraveling.", HUE_SUCCESS)
            retire_finished_item(target_item)
            current_item_serial = None
            current_item_name = "None"
            current_item_successes = 0
            current_item_fails = 0
            update_stats()
            return True

    elif any("fail" in t for t in j_text):
        total_failed += 1
        current_item_fails += 1
        debug_msg(f"Imbue failed. Item fails: {current_item_fails}/{MAX_FAILS_PER_ITEM} (Successes: {current_item_successes}/{MAX_SUCCESSES_PER_ITEM})")
        if current_item_fails >= MAX_FAILS_PER_ITEM:
            API.SysMsg(f"[Imbuing] Item reached fail safety limit ({MAX_FAILS_PER_ITEM}). Retiring item.", HUE_WARN)
            retire_finished_item(target_item)
            current_item_serial = None
            current_item_name = "None"
            current_item_successes = 0
            current_item_fails = 0
            update_stats()
            return True

    update_stats()
    return True


def execute_unravel_item(item_serial: int, fallback_name: str = "") -> bool:
    """Unravels a single item at the Soulforge, returning it to supply if skill is too low."""
    global total_unraveled, skipped_unravel_serials

    if not is_near_soulforge():
        API.SysMsg("[Imbuing] Must be standing near a Soulforge to unravel!", HUE_WARN)
        return False

    item_obj = API.FindItem(item_serial)
    if not item_obj:
        debug_msg(f"Item 0x{item_serial:X} not found to unravel.")
        return False

    item_name = getattr(item_obj, "Name", "") or fallback_name or f"Item (0x{getattr(item_obj, 'Graphic', 0):X})"

    API.ClearJournal()
    API.Pause(0.4)
    API.UseSkill("Imbuing")

    # Wait specifically for the Imbuing Menu
    if not wait_for_imbuing_menu(timeout=4.0):
        return False

    active_id = API.HasGump()
    reply_ok = API.ReplyGump(GUMP_BTN_UNRAVEL_ITEM, active_id)
    if not reply_ok:
        API.ReplyGump(GUMP_BTN_UNRAVEL_ITEM)

    if API.WaitForTarget(timeout=3.0):
        API.Pause(0.2)
        API.Target(item_serial)
        API.Pause(0.2)
        if API.HasTarget():
            debug_msg("Unravel target cursor still active; repeating target...")
            API.Target(item_serial)
    else:
        return False

    API.Pause(UNRAVEL_DELAY)

    # Check for confirmation sub-gump (handle any confirmation dialog flexibly)
    start_c = time.time()
    while (time.time() - start_c) < 1.2:
        if API.HasGump():
            curr_gump = API.GetGump()
            gump_text = API.GetGumpContents().lower() if API.GetGumpContents() else ""
            if any(w in gump_text for w in ["unravel", "destroy", "special", "confirmation", "continue", "magic item", "sure"]):
                conf_buttons = []
                if curr_gump and hasattr(curr_gump, "Children"):
                    for child in curr_gump.Children:
                        if hasattr(child, "ButtonID") and child.ButtonID is not None and child.ButtonID > 0:
                            conf_buttons.append(child.ButtonID)
                btn = conf_buttons[0] if conf_buttons else GUMP_BTN_CONFIRM
                API.SysMsg(f"[Imbuing] Confirming unravel dialog with button {btn}...", HUE_INFO)
                API.ReplyGump(btn)
                API.Pause(0.4)
                break
        API.Pause(0.1)

    # Inspect journal results for failure / insufficient skill / non-magical item
    entries = API.GetJournalEntries(UNRAVEL_DELAY + 1.2)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    # Check if skill was not high enough or item cannot be unraveled
    if any("not skilled enough" in t or "not high enough" in t or "lack the skill" in t for t in j_text):
        API.SysMsg(f"[Imbuing] Skill too low to unravel '{item_name}'. Skipping.", HUE_WARN)
        skipped_unravel_serials.add(item_serial)

        # Return item to house supply container if external
        if supply_container_serial and not is_in_backpack(supply_container_serial):
            API.SysMsg(f"[Imbuing] Returning '{item_name}' to supply container...", HUE_INFO)
            API.MoveItem(item_serial, supply_container_serial)
            API.Pause(MOVE_DELAY)
        return False

    if any("not a magical" in t or "cannot be unraveled" in t or "cannot unravel" in t or "not enough magical" in t for t in j_text):
        API.SysMsg(f"[Imbuing] Cannot unravel '{item_name}' (plain/non-magical or low intensity).", HUE_WARN)
        skipped_unravel_serials.add(item_serial)
        return False

    # Check if item was successfully destroyed/unraveled
    item_gone = not API.FindItem(item_serial)
    journal_success = any(
        w in t for t in j_text for w in ["extract", "obtain", "residue", "essence", "relic", "destroyed"]
    )
    if item_gone or journal_success:
        total_unraveled += 1
        API.SysMsg(f"[Imbuing] Successfully unraveled '{item_name}'.", HUE_SUCCESS)
        stash_unraveled_ingredients()
        update_stats()
        return True

    return False


def execute_unravel_container_cycle() -> bool:
    """Executes an unravel cycle at the Soulforge (supporting backpack bags and external supply chests)."""
    global total_unraveled, skipped_unravel_serials

    if not is_near_soulforge():
        API.SysMsg("[Imbuing] Must be standing near a Soulforge to unravel!", HUE_WARN)
        update_status("Need Soulforge")
        API.Pause(1.0)
        return True

    # Mode A: If supply container is external (in house / on ground), pull items into backpack
    if supply_container_serial and not is_in_backpack(supply_container_serial):
        # Stash any loose unraveled ingredients in root backpack into satchel
        stash_unraveled_ingredients()

        # 1. Check if an item to unravel is already in backpack (excluding skipped items)
        bp_items = API.ItemsInContainer(API.Backpack, recursive=False) or []
        bp_unravel = next((it for it in bp_items if is_imbuable_item(it) and it.Serial not in skipped_unravel_serials), None)

        if not bp_unravel:
            # 2. Draw fresh item from external supply container (excluding skipped items)
            supply_items = API.ItemsInContainer(supply_container_serial, recursive=False) or []
            if not supply_items:
                API.UseObject(supply_container_serial)
                API.Pause(0.5)
                supply_items = API.ItemsInContainer(supply_container_serial, recursive=False) or []

            eligible_items = [it for it in supply_items if is_imbuable_item(it) and it.Serial not in skipped_unravel_serials]
            if not eligible_items:
                API.SysMsg("[Imbuing] Supply container has no more items you have the skill to unravel.", HUE_WARN)
                pause_trainer("Supply Depleted")
                return True

            item_to_pull = eligible_items[0]
            API.SysMsg(f"[Imbuing] Drawing '{name}' from supply container into backpack...", HUE_INFO)
            API.MoveItem(item_to_pull.Serial, API.Backpack)

            # Wait for item to physically arrive in backpack
            start_m = time.time()
            while (time.time() - start_m) < 1.2:
                bp_it = API.FindItem(item_to_pull.Serial)
                if bp_it and (bp_it.Container == API.Backpack or getattr(bp_it, "RootContainer", 0) == API.Player.Serial):
                    break
                API.Pause(0.1)

            bp_unravel = API.FindItem(item_to_pull.Serial)
            # If not in backpack after initial attempt, retry once after a drag delay buffer
            if not bp_unravel or (bp_unravel.Container != API.Backpack and getattr(bp_unravel, "RootContainer", 0) != API.Player.Serial):
                debug_msg(f"First move attempt for '{name}' did not land. Retrying move after cooldown...")
                API.Pause(0.6)
                API.MoveItem(item_to_pull.Serial, API.Backpack)
                start_m2 = time.time()
                while (time.time() - start_m2) < 1.2:
                    bp_it = API.FindItem(item_to_pull.Serial)
                    if bp_it and (bp_it.Container == API.Backpack or getattr(bp_it, "RootContainer", 0) == API.Player.Serial):
                        break
                    API.Pause(0.1)

            bp_unravel = API.FindItem(item_to_pull.Serial)
            if not bp_unravel or (bp_unravel.Container != API.Backpack and getattr(bp_unravel, "RootContainer", 0) != API.Player.Serial):
                API.SysMsg(f"[Imbuing] Could not move '{name}' into backpack (unmovable, locked down, or backpack full). Skipping item.", HUE_WARN)
                skipped_unravel_serials.add(item_to_pull.Serial)
                API.Pause(0.4)
                return True

        update_status(f"Unraveling {bp_unravel.Name or name}...")
        return execute_unravel_item(bp_unravel.Serial, fallback_name=getattr(bp_unravel, "Name", "") or name)

    # Mode B: Target container is in the backpack (or is the backpack itself)
    target_cont = supply_container_serial or API.Backpack
    update_status("Unraveling Container...")
    API.ClearJournal()

    # Step 1: Invoke Imbuing Skill
    API.SysMsg("[Imbuing] [1/5] Using skill Imbuing near Soulforge...", HUE_INFO)
    API.Pause(0.5)
    API.UseSkill("Imbuing")

    # Step 2: Wait specifically for the Imbuing Menu to open and be parsed
    API.SysMsg("[Imbuing] [2/5] Waiting for server Imbuing menu...", HUE_INFO)
    if not wait_for_imbuing_menu(timeout=4.0):
        API.SysMsg("[Imbuing] Timed out waiting for Imbuing menu!", HUE_WARN)
        pause_trainer("Menu Timeout")
        return False

    # Step 3: Send "Unravel Container" (Button 10011)
    active_id = API.HasGump()
    API.SysMsg(f"[Imbuing] [3/5] Replying Button {GUMP_BTN_UNRAVEL_CONTAINER} to Gump 0x{active_id:X}...", HUE_INFO)
    API.Pause(0.2)
    reply_ok = API.ReplyGump(GUMP_BTN_UNRAVEL_CONTAINER, active_id)
    if not reply_ok:
        API.ReplyGump(GUMP_BTN_UNRAVEL_CONTAINER)

    # Step 4: Wait for target cursor to select the container
    API.SysMsg("[Imbuing] [4/5] Waiting for target cursor from server...", HUE_INFO)
    if not API.WaitForTarget(timeout=4.0):
        API.SysMsg("[Imbuing] Target cursor did not appear! Pausing trainer to prevent desync.", HUE_WARN)
        if API.HasGump():
            API.CloseGump()
        pause_trainer("Target Timeout")
        return False

    API.SysMsg(f"[Imbuing] [4b/5] Target cursor active! Targeting backpack container 0x{target_cont:X}...", HUE_INFO)
    API.Target(target_cont)
    API.Pause(UNRAVEL_DELAY)

    # Step 5: Check for confirmation dialog (only reply if genuine confirmation dialog is present!)
    API.SysMsg("[Imbuing] [5/5] Checking for special material confirmation dialog...", HUE_INFO)
    start_c = time.time()
    while (time.time() - start_c) < 1.0:
        if API.HasGump():
            if (API.GumpContains("special material") or
                    API.GumpContains("DESTROYED") or
                    API.GumpContains("UNRAVEL MAGIC ITEM CONFIRMATION")):
                conf_gump = API.GetGump()
                conf_buttons = []
                if conf_gump and hasattr(conf_gump, "Children"):
                    for child in conf_gump.Children:
                        if hasattr(child, "ButtonID") and child.ButtonID is not None:
                            conf_buttons.append(child.ButtonID)
                API.SysMsg(f"[Imbuing] [5b/5] Special material dialog detected! Buttons: {conf_buttons}", HUE_WARN)
                btn = conf_buttons[0] if conf_buttons and conf_buttons[0] != 0 else GUMP_BTN_CONFIRM
                API.ReplyGump(btn)
                API.Pause(0.5)
                break
        API.Pause(0.1)

    # Inspect journal results
    entries = API.GetJournalEntries(UNRAVEL_DELAY + 1.0)
    j_text = [str(e.Text).lower() for e in entries] if entries else []
    if any("must be in your backpack" in t for t in j_text):
        API.SysMsg("[Imbuing] Server requires container to be in your backpack!", HUE_WARN)
        pause_trainer("Not In Backpack")
        return True

    if any("no magical" in t or "nothing" in t or "cannot be unraveled" in t for t in j_text):
        API.SysMsg("[Imbuing] Container has no more unraveled items.", HUE_WARN)
        pause_trainer("Container Empty")
        return True

    total_unraveled += 1
    stash_unraveled_ingredients()
    update_stats()
    API.SysMsg("[Imbuing] Container unraveling processed.", HUE_SUCCESS)
    API.Pause(1.5)
    return True


# ==============================================================================
# UI Callbacks & Gump Setup
# ==============================================================================

def on_pause_clicked() -> None:
    """Toggles trainer pause state."""
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg(f"[Imbuing] Trainer {'paused' if is_paused else 'resumed'}.", HUE_INFO)


def on_mode_clicked() -> None:
    """Toggles between REIMBUE and UNRAVEL modes."""
    global TRAINING_MODE, btn_mode
    if TRAINING_MODE == "REIMBUE":
        TRAINING_MODE = "UNRAVEL"
    else:
        TRAINING_MODE = "REIMBUE"

    if btn_mode:
        btn_mode.SetText(f"Mode: {TRAINING_MODE}")
    API.SysMsg(f"[Imbuing] Switched mode to: {TRAINING_MODE}", HUE_INFO)
    update_stats()


def on_setup_clicked() -> None:
    """Pauses the trainer and opens the Imbuing menu on the working item for initial setup."""
    global is_paused, btn_pause, current_item_serial, current_item_name, current_item_successes, current_item_fails
    pause_trainer("Setup Imbue")

    API.SysMsg("=== Imbuing Setup Mode ===", HUE_INFO)
    API.SysMsg("[Imbuing] Target the item you want to train on (e.g. Dagger in backpack)...", HUE_INFO)
    tar = API.RequestTarget(timeout=6.0)
    if tar and tar != API.Player.Serial:
        tar_obj = API.FindItem(tar)
        if tar_obj and is_imbuable_item(tar_obj):
            current_item_serial = tar_obj.Serial
            current_item_name = getattr(tar_obj, "Name", "") or f"Item (0x{getattr(tar_obj, 'Graphic', 0):X})"
            current_item_successes = 0
            current_item_fails = 0
            API.SysMsg(f"[Imbuing] Target item locked to: {current_item_name}", HUE_SUCCESS)
            update_stats()

    API.SysMsg("1. In the menu, select your property once (aim for ~50-70% success chance).", HUE_INFO)
    API.SysMsg("2. Re-imbues on the same item grant skill up to 20 successes in ServUO!", HUE_INFO)
    API.SysMsg("3. Click 'Resume' on the Gump to begin automated training!", HUE_SUCCESS)

    API.UseSkill("Imbuing")


def on_supply_clicked() -> None:
    """Prompts the player to target the Item Supply Container."""
    global supply_container_serial
    API.SysMsg("[Imbuing] Target your Item Supply Container (or press ESC / self for backpack only)...", HUE_INFO)
    target = API.RequestTarget(timeout=8.0)
    if target and target != API.Player.Serial:
        supply_container_serial = target
        API.SysMsg(f"[Imbuing] Item Supply Container updated: 0x{supply_container_serial:X}", HUE_SUCCESS)
        API.UseObject(supply_container_serial)
        API.Pause(0.4)
    else:
        supply_container_serial = None
        API.SysMsg("[Imbuing] Supply Container cleared. Using backpack items only.", HUE_WARN)
    update_stats()


def on_resource_clicked() -> None:
    """Prompts the player to target the Resource Chest / Satchel."""
    global resource_chest_serial
    API.SysMsg("[Imbuing] Target your Resource Chest / Satchel for Residue/Essence/Gems...", HUE_INFO)
    target = API.RequestTarget(timeout=8.0)
    if target and target != API.Player.Serial:
        resource_chest_serial = target
        API.SysMsg(f"[Imbuing] Resource Chest set: 0x{resource_chest_serial:X}", HUE_SUCCESS)
        API.UseObject(resource_chest_serial)
        API.Pause(0.4)
    else:
        resource_chest_serial = None
        API.SysMsg("[Imbuing] Resource Chest cleared. Using backpack resources only.", HUE_WARN)
    update_stats()


def on_trash_clicked() -> None:
    """Prompts the player to target a Trash Barrel or Discard Container."""
    global trash_barrel_serial
    API.SysMsg("[Imbuing] Target your Trash Barrel / Discard Bag (or press ESC to auto-unravel at Soulforge)...", HUE_INFO)
    target = API.RequestTarget(timeout=8.0)
    if target and target != API.Player.Serial:
        trash_barrel_serial = target
        API.SysMsg(f"[Imbuing] Trash Barrel / Discard Bag set: 0x{trash_barrel_serial:X}", HUE_SUCCESS)
    else:
        trash_barrel_serial = None
        API.SysMsg(f"[Imbuing] Trash Container cleared. Finished items will {'auto-unravel at Soulforge' if AUTO_UNRAVEL_AFTER_MAX else 'remain in backpack'}.", HUE_INFO)
    update_stats()


def on_stop_clicked() -> None:
    """Stops the script execution."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_gump_disposed() -> None:
    """Handles right-click close on the Gump."""
    global is_stopped
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


def create_control_gump() -> None:
    """Renders the FesterUO Imbuing Trainer interactive Gump."""
    global gump, lbl_status, lbl_skill, lbl_mode, lbl_item, lbl_counts, lbl_resources, lbl_containers
    global btn_pause, btn_mode, btn_setup, btn_supply, btn_resource, btn_trash, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(520, 80, 330, 240)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 330, 240)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("Imbuing Trainer", 53)
    title.SetPos(10, 8)
    gump.Add(title)
    lbl_author = API.Gumps.CreateGumpLabel(f"by FesterHead v{SCRIPT_VERSION}", 996)
    lbl_author.SetPos(195, 8)
    gump.Add(lbl_author)

    # Status
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skill
    lbl_skill = API.Gumps.CreateGumpLabel("Imbuing: -- / --", 996)
    lbl_skill.SetPos(10, 48)
    gump.Add(lbl_skill)

    # Mode & Recommendation
    lbl_mode = API.Gumps.CreateGumpLabel("Mode: Reimbue Loop | Rec: Initializing...", 53)
    lbl_mode.SetPos(10, 68)
    gump.Add(lbl_mode)

    # Item & Attempts
    lbl_item = API.Gumps.CreateGumpLabel(f"Item: None | Success: 0/{MAX_SUCCESSES_PER_ITEM} | Fails: 0", 996)
    lbl_item.SetPos(10, 88)
    gump.Add(lbl_item)

    # Counters
    lbl_counts = API.Gumps.CreateGumpLabel("Imbued: 0 | Unraveled: 0 | Failed: 0", 996)
    lbl_counts.SetPos(10, 108)
    gump.Add(lbl_counts)

    # Resources
    lbl_resources = API.Gumps.CreateGumpLabel("Residue: 0 | Essence: 0 | Gems: 0", 996)
    lbl_resources.SetPos(10, 128)
    gump.Add(lbl_resources)

    # Containers
    lbl_containers = API.Gumps.CreateGumpLabel("Supply: None | Res: None | Trash: Auto", 996)
    lbl_containers.SetPos(10, 148)
    gump.Add(lbl_containers)

    # Row 1 Buttons: Pause, Mode, Setup Imbue
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 68, 24)
    btn_pause.SetPos(10, 172)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_mode = API.Gumps.CreateSimpleButton(f"Mode: {TRAINING_MODE}", 110, 24)
    btn_mode.SetPos(84, 172)
    API.Gumps.AddControlOnClick(btn_mode, on_mode_clicked)
    gump.Add(btn_mode)

    btn_setup = API.Gumps.CreateSimpleButton("Setup Imbue", 122, 24)
    btn_setup.SetPos(198, 172)
    API.Gumps.AddControlOnClick(btn_setup, on_setup_clicked)
    gump.Add(btn_setup)

    # Row 2 Buttons: Supply Bag, Resources, Trash Can, Stop
    btn_supply = API.Gumps.CreateSimpleButton("Supply Bag", 76, 24)
    btn_supply.SetPos(10, 202)
    API.Gumps.AddControlOnClick(btn_supply, on_supply_clicked)
    gump.Add(btn_supply)

    btn_resource = API.Gumps.CreateSimpleButton("Resources", 72, 24)
    btn_resource.SetPos(90, 202)
    API.Gumps.AddControlOnClick(btn_resource, on_resource_clicked)
    gump.Add(btn_resource)

    btn_trash = API.Gumps.CreateSimpleButton("Trash Can", 72, 24)
    btn_trash.SetPos(166, 202)
    API.Gumps.AddControlOnClick(btn_trash, on_trash_clicked)
    gump.Add(btn_trash)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 78, 24)
    btn_stop.SetPos(242, 202)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Handle right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    # Render Gump to screen
    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Disposes the Gump safely."""
    global gump
    if gump and not getattr(gump, "IsDisposed", False):
        try:
            gump.Dispose()
        except Exception:
            pass
        gump = None


# ==============================================================================
# Script Initialization & Stop Hooks
# ==============================================================================

def on_stop() -> None:
    """Cleanup hook when script terminates."""
    dispose_gump()
    API.SysMsg("[Imbuing] Trainer stopped.", HUE_INFO)

API.OnStop(on_stop)


def main() -> None:
    """Main script entry point."""
    global supply_container_serial, resource_chest_serial, trash_barrel_serial
    global recommended_prop_name

    API.SysMsg(f"=== FesterUO Imbuing Trainer v{SCRIPT_VERSION} ===", HUE_INFO)

    # 1. Initial skill evaluation
    skill_obj = API.GetSkill("Imbuing")
    curr_skill = float(skill_obj.Value) if skill_obj else 0.0
    rec_prop, rec_mats, rec_notes = get_recommended_tier(curr_skill)
    recommended_prop_name = rec_prop

    # 2. Render Gump UI immediately so user sees the interface upon double-clicking
    create_control_gump()
    update_stats()

    # 3. Trash Barrel (set via Gump "Trash Can" button if explicitly desired)
    trash_barrel_serial = None

    # 4. Prompt for Item Supply Container
    bp_serial = API.Backpack
    API.SysMsg("[Imbuing] Target your Item Supply Container (or click your backpack / press ESC for backpack only)...", HUE_INFO)
    s_serial = API.RequestTarget(timeout=6.0)
    if s_serial and s_serial != API.Player.Serial and s_serial != bp_serial:
        supply_container_serial = s_serial
        API.SysMsg(f"[Imbuing] Supply Container set: 0x{supply_container_serial:X}", HUE_SUCCESS)
        API.UseObject(supply_container_serial)
        API.Pause(0.4)
    else:
        supply_container_serial = None
        API.SysMsg("[Imbuing] Backpack mode: Training directly on items in backpack.", HUE_SUCCESS)

    # 5. Prompt for Resource Chest / Satchel
    API.SysMsg("[Imbuing] Target your Resource Chest / Satchel with Residue/Essence/Gems (or press ESC / self for backpack only)...", HUE_INFO)
    r_serial = API.RequestTarget(timeout=6.0)
    if r_serial and r_serial != API.Player.Serial and r_serial != bp_serial:
        resource_chest_serial = r_serial
        API.SysMsg(f"[Imbuing] Resource Chest set: 0x{resource_chest_serial:X}", HUE_SUCCESS)
        API.UseObject(resource_chest_serial)
        API.Pause(0.4)
    else:
        resource_chest_serial = None
        API.SysMsg("[Imbuing] Using resources in backpack.", HUE_INFO)

    update_stats()

    # Initial restock check
    if resource_chest_serial:
        restock_resources_from_chest()
        API.Pause(0.8)

    update_status("Running")
    API.SysMsg(f"[Imbuing] Training started. Current skill: {curr_skill:.1f} | Recommendation: {rec_notes}", HUE_SUCCESS)

    # Cooldown pause to ensure no action delay collision before using skill
    API.Pause(0.8)

    # 6. Main Training Loop
    while not API.StopRequested and not is_stopped:
        API.ProcessCallbacks()
        while is_paused and not API.StopRequested and not is_stopped:
            API.ProcessCallbacks()
            API.Pause(0.2)

        if API.StopRequested or is_stopped:
            break

        # Check target skill reached
        skill_obj = API.GetSkill("Imbuing")
        if skill_obj and float(skill_obj.Value) >= TARGET_SKILL:
            API.SysMsg(f"[Imbuing] Target skill {TARGET_SKILL:.1f} reached! Congratulations!", HUE_SUCCESS)
            break

        # Execute according to active mode
        if TRAINING_MODE == "REIMBUE":
            target_item = get_or_fetch_target_item()
            if target_item:
                execute_reimbue_cycle(target_item)
            else:
                API.Pause(0.5)
        elif TRAINING_MODE == "UNRAVEL":
            execute_unravel_container_cycle()

        API.Pause(0.2)

    update_status("Finished")
    API.SysMsg("[Imbuing] Trainer finished.", HUE_INFO)
    dispose_gump()


main()
