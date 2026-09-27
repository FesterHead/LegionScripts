"""
TrainBlacksmith.py - Automated Blacksmithing Training Engine for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Fully automated, resource-efficient Blacksmithing skill training script with
    interactive control Gump. Progresses through the mathematically optimal,
    lowest-ingot items from 0 to 120 (GM / Legendary):
      - 30.0 to 45.0: Mace (6 ingots)
      - 45.0 to 50.0: Maul (6 ingots)
      - 50.0 to 95.0: Short Spear (6 ingots - primary training workhorse)
      - 95.0 to 106.4: Platemail Gorget (10 ingots - cheapest plate)
      - 106.4 to 108.9: Platemail Gloves (12 ingots)
      - 108.9 to 116.3: Platemail Arms (18 ingots)
      - 116.3 to 118.8: Platemail Legs (20 ingots)
      - 118.8 to 120.0: Platemail Tunic (25 ingots)

Features:
    - Resource Satchel Management:
        * Prompts player to target their resource satchel / bag containing ingots on startup.
        * Maintains a lightweight working buffer of ingots in the main backpack (default 40-80).
        * Moves smelted/recycled ingots back into the satchel to prevent weight overloads.
    - Automated Ingot Recycling (Smelting):
        * Automatically smelts crafted items at the forge to recover 50%-90% of raw ingots.
    - Tool Upkeep via Tinkering:
        * Detects equipped or backpack Smith's Hammers, Sledgehammers, and Tongs.
        * If out of hammers, automatically crafts replacement Smith's Hammers using
          Tinker's Tools and ingots from the satchel.
    - Tier Progression & Recipe Control:
        * Dynamically monitors Blacksmith skill and announces tier transitions.
        * Uses high-speed "Make Last" crafting with interactive "Set Recipe" button fallback.
    - Interactive Control Gump:
        * Displays status, live Blacksmith skill & cap with gain announcements.
        * Running counters: Crafted, Smelted, Failed, and Estimated Ingots Saved.
        * Live Satchel and Backpack ingot counts.
        * Interactive Pause/Resume, Set Recipe, Set Satchel, and Stop buttons.
"""

from collections import deque
import re
from typing import Optional, List, Tuple
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Target Blacksmith skill to stop training (e.g. 100.0 for GM, 120.0 for Legendary)
TARGET_SKILL = 120.0

# Direct Satchel Crafting (crafts directly from resource satchel without pulling to backpack)
DIRECT_SATCHEL_CRAFTING = True

# Working ingot buffer maintained in main backpack (prevents becoming overweight)
MIN_BACKPACK_INGOTS = 0 if DIRECT_SATCHEL_CRAFTING else 20
TARGET_BACKPACK_INGOTS = 50
RESTOCK_BATCH_SIZE = 50

# Crafting action delays in seconds
CRAFT_DELAY = 1.3
SMELT_DELAY = 0.8
TOOL_CRAFT_DELAY = 1.5
MAX_TOOL_CRAFT_ATTEMPTS = 8  # Maximum retry attempts to craft a replacement smithing tool via Tinkering

# Server Craft Gump button IDs (standard ServUO / RunUO)
GUMP_BTN_MAKE_LAST = 21  # Universal "Make Last" button
GUMP_BTN_SMELT = 14      # "Smelt Item" button on Blacksmith craft menu

# Enable verbose debug messages in client console
DEBUG = False


# ==============================================================================
# Item & Graphic Definitions
# ==============================================================================

INGOT_GRAPHIC = 0x1BF2
IRON_INGOT_HUE = 0  # Regular iron ingots (plain / unhued)

# Smithing tools
SMITH_HAMMER_GRAPHICS = {0x13E3, 0x13E4}
TONGS_GRAPHICS = {0x0FBB}
SLEDGEHAMMER_GRAPHICS = {0x0FB4, 0x0FB5}
ALL_SMITH_TOOLS = SMITH_HAMMER_GRAPHICS | TONGS_GRAPHICS | SLEDGEHAMMER_GRAPHICS

# Tinkering tools
TINKER_TOOL_GRAPHICS = {0x1EB8, 0x1EB9, 0x1EBC, 0x1EBD}

# Forges and Anvils
FORGE_GRAPHICS = {
    0x0FB1,  # Small stone/round forge (classic circular hearth)
    0x197A, 0x197B, 0x197C, 0x197D, 0x197E, 0x197F,
    0x1980, 0x1981, 0x1982, 0x1983, 0x1984, 0x1985,
    0x1986, 0x1987, 0x1988, 0x1989, 0x198A, 0x198B,
    0x198C, 0x198D, 0x198E, 0x198F, 0x1990, 0x1991,
    0x1992, 0x1993, 0x1994, 0x1995, 0x1996, 0x1997,
    0x1998, 0x1999, 0x199A, 0x199B, 0x199C, 0x199D,
    0x199E, 0x199F, 0x19A0, 0x19A1, 0x19A2,
    0x2DD8,  # Elven / Soul Forge
    0x398C, 0x3996,  # Gargish forges
    0x4017,  # Alternate stone forge ID
}
ANVIL_GRAPHICS = {
    0x0FAF, 0x0FB0,  # Standard anvils
    0x2DD5, 0x2DD6,  # Elven anvils
    0x4015, 0x4016,  # Alternate anvil IDs
}

# Optimal Progression Ladder: (min_skill, max_skill, item_name, ingot_cost)
PROGRESSION_LADDER = [
    (0.0, 45.0, "Mace", 6),
    (45.0, 50.0, "Maul", 6),
    (50.0, 95.0, "Short Spear", 6),
    (95.0, 106.4, "Platemail Gorget", 10),
    (106.4, 108.9, "Platemail Gloves", 12),
    (108.9, 116.3, "Platemail Arms", 18),
    (116.3, 118.8, "Platemail Legs", 20),
    (118.8, 120.0, "Platemail Tunic", 25),
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
lbl_tool = None
btn_pause = None
btn_recipe = None
btn_satchel = None
btn_stop = None

is_paused = False
is_stopped = False

satchel_serial: Optional[int] = None
last_skill: Optional[float] = None
current_recipe_name: str = "Initializing..."
active_tool_serial: Optional[int] = None

total_crafted = 0
total_smelted = 0
total_failed = 0
tools_crafted = 0


# ==============================================================================
# Gump & UI Updates
# ==============================================================================

def update_status(text: str) -> None:
    """Updates the status display on the Gump."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def update_stats() -> None:
    """Updates live skill, recipe, counters, and ingot counts on the Gump."""
    global last_skill, lbl_skill, lbl_recipe, lbl_counts, lbl_ingots, lbl_tool

    # Skill tracking
    skill_obj = API.GetSkill("Blacksmith") or API.GetSkill("Blacksmithy")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        lbl_skill.Text = f"Blacksmith: {val:.1f} / {cap:.1f}"
        if last_skill is not None and val > last_skill:
            gain = val - last_skill
            API.SysMsg(f"[Blacksmith] Skill gained +{gain:.1f}! New skill: {val:.1f}")
        last_skill = val

    # Recipe label
    if lbl_recipe:
        lbl_recipe.Text = f"Recipe: {current_recipe_name}"

    # Counts
    if lbl_counts:
        lbl_counts.Text = f"Crafted: {total_crafted} | Smelted: {total_smelted} | Failed: {total_failed}"

    # Ingot counts
    if lbl_ingots:
        s_count = count_satchel_ingots()
        bp_count = count_backpack_ingots()
        lbl_ingots.Text = f"Satchel: {s_count:,} | Backpack: {bp_count}"

    # Tool status
    if lbl_tool:
        tool = get_smith_tool()
        if tool:
            lbl_tool.Text = f"Tool: Ready (Tinkered: {tools_crafted})"
        else:
            lbl_tool.Text = "Tool: None (Tinkering required)"


def on_pause_clicked() -> None:
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Blacksmith trainer paused." if is_paused else "Blacksmith trainer resumed.")


def on_stop_clicked() -> None:
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_satchel_clicked() -> None:
    """Prompts the player to re-target their resource satchel."""
    global satchel_serial
    API.SysMsg("Target your resource satchel containing ingots...")
    new_serial = API.RequestTarget(timeout=10.0)
    if new_serial:
        satchel_serial = new_serial
        API.SysMsg(f"Satchel updated: 0x{satchel_serial:X}")
        update_stats()


def on_recipe_clicked() -> None:
    """Opens the Blacksmith craft gump to allow manually selecting an item recipe."""
    global is_paused, btn_pause
    tool = get_smith_tool()
    if tool:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused (Set Recipe)")
        API.SysMsg("Opening craft menu. Click your desired item once to craft it, then click 'Resume' on the Gump.")
        API.UseObject(tool)
    else:
        API.SysMsg("No smithing tool available to open craft menu!")


def on_gump_disposed() -> None:
    global is_stopped
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


def create_control_gump() -> None:
    """Initializes and renders the interactive Blacksmith Trainer Gump."""
    global gump, lbl_status, lbl_skill, lbl_recipe, lbl_counts, lbl_ingots, lbl_tool
    global btn_pause, btn_recipe, btn_satchel, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 310, 220)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 310, 220)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Blacksmith Trainer", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skill
    lbl_skill = API.Gumps.CreateGumpLabel("Blacksmith: -- / --", 996)
    lbl_skill.SetPos(10, 48)
    gump.Add(lbl_skill)

    # Active Recipe
    lbl_recipe = API.Gumps.CreateGumpLabel("Recipe: Initializing...", 53)
    lbl_recipe.SetPos(10, 68)
    gump.Add(lbl_recipe)

    # Stats: Crafted / Smelted / Failed
    lbl_counts = API.Gumps.CreateGumpLabel("Crafted: 0 | Smelted: 0 | Failed: 0", 996)
    lbl_counts.SetPos(10, 88)
    gump.Add(lbl_counts)

    # Ingot Counts
    lbl_ingots = API.Gumps.CreateGumpLabel("Satchel: 0 | Backpack: 0", 996)
    lbl_ingots.SetPos(10, 108)
    gump.Add(lbl_ingots)

    # Tool status
    lbl_tool = API.Gumps.CreateGumpLabel("Tool: Checking...", 996)
    lbl_tool.SetPos(10, 128)
    gump.Add(lbl_tool)

    # Buttons Row 1: Pause & Set Recipe
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

    # Buttons Row 2: Stop
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 270, 22)
    btn_stop.SetPos(15, 184)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)
    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    global gump
    if gump and not gump.IsDisposed:
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

    return not (is_stopped or API.StopRequested)


def wait_with_ui(seconds: float) -> bool:
    """Time-sliced pause that processes UI callbacks."""
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


def get_smith_tool():
    """Finds an equipped smith hammer or tongs, or one in the main backpack."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in ALL_SMITH_TOOLS:
            return item

    for g in ALL_SMITH_TOOLS:
        item = API.FindType(g, API.Backpack)
        if item:
            return item

    items = API.ItemsInContainer(API.Backpack)
    if items:
        for item in items:
            name = str(getattr(item, "Name", "")).lower()
            if ("smith" in name and "hammer" in name) or ("sledge" in name and "hammer" in name) or "tongs" in name:
                return item

    return None


def get_tinker_tool():
    """Finds a Tinker's Tool in the backpack."""
    for g in TINKER_TOOL_GRAPHICS:
        item = API.FindType(g, API.Backpack)
        if item:
            return item

    items = API.ItemsInContainer(API.Backpack)
    if items:
        for item in items:
            name = str(getattr(item, "Name", "")).lower()
            if "tinker" in name and "tool" in name:
                return item

    return None


def count_smith_tools() -> int:
    """Counts all smithing tools (hammers, sledgehammers, and tongs) in the backpack."""
    total = 0
    for g in ALL_SMITH_TOOLS:
        items = API.FindTypeAll(g, API.Backpack)
        if items:
            total += len(items)
    return total


# Special / colored ore and ingot names to strictly protect
SPECIAL_INGOT_NAMES = (
    "dull", "shadow", "copper", "bronze", "gold", "agapite", "verite", "valorite"
)


def is_regular_iron_ingot(item) -> bool:
    """Checks if an item is a regular (plain/unhued) iron ingot, filtering out colored/special ingots."""
    if not item:
        return False
    if getattr(item, "Graphic", 0) != INGOT_GRAPHIC:
        return False
    # In Ultima Online, standard iron ingots strictly have Hue 0 (0x0000)
    hue = getattr(item, "Hue", 0) or 0
    if hue != IRON_INGOT_HUE:
        return False
    # Secondary check on name to prevent any custom special ingots
    name = str(getattr(item, "Name", "") or "").lower()
    if name:
        for special in SPECIAL_INGOT_NAMES:
            if special in name:
                return False
    return True


def count_backpack_ingots() -> int:
    """Counts raw regular iron ingots (Hue 0) residing directly in the player's main backpack (outside satchel)."""
    if not API.Player:
        return 0
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not items:
        return 0
    total = 0
    for item in items:
        if item.Serial != satchel_serial and is_regular_iron_ingot(item):
            total += getattr(item, "Amount", 1) or 1
    return total


def count_satchel_ingots() -> int:
    """Counts regular iron ingots (Hue 0) inside the resource satchel."""
    if not satchel_serial:
        return 0
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if not items:
        items = API.ItemsInContainer(satchel_serial)
    if not items:
        return 0
    total = 0
    for item in items:
        if is_regular_iron_ingot(item):
            total += getattr(item, "Amount", 1) or 1
    return total


def get_satchel_iron_ingot():
    """Finds the stack of regular iron ingots (Hue 0) in the resource satchel."""
    if not satchel_serial:
        return None
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if not items:
        items = API.ItemsInContainer(satchel_serial)
    if items:
        for item in items:
            if is_regular_iron_ingot(item):
                return item
    return None


def restock_ingots_from_satchel() -> bool:
    """Pulls a batch of regular iron ingots (Hue 0) from the resource satchel into the main backpack."""
    if not satchel_serial:
        return False

    current_bp = count_backpack_ingots()
    if current_bp >= MIN_BACKPACK_INGOTS:
        return True

    satchel_ingot = get_satchel_iron_ingot()
    if not satchel_ingot:
        return False

    amt_available = getattr(satchel_ingot, "Amount", 1) or 1
    amt_needed = max(RESTOCK_BATCH_SIZE, TARGET_BACKPACK_INGOTS - current_bp)
    amt_to_move = min(amt_available, amt_needed)

    if amt_to_move <= 0:
        return False

    update_status(f"Restocking {amt_to_move} iron ingots...")
    API.MoveItem(satchel_ingot.Serial, API.Backpack, amt=amt_to_move)
    API.Pause(0.6)
    update_stats()
    return count_backpack_ingots() >= 6


def deposit_excess_ingots_to_satchel() -> None:
    """Moves excess regular iron ingots from backpack back into the satchel to prevent weight overburden."""
    if not satchel_serial:
        return

    current_bp = count_backpack_ingots()
    target_bp = 0 if DIRECT_SATCHEL_CRAFTING else TARGET_BACKPACK_INGOTS
    if current_bp <= target_bp:
        return

    excess = current_bp - target_bp
    if excess <= 0:
        return

    bp_items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not bp_items:
        return

    for item in bp_items:
        if item.Serial != satchel_serial and is_regular_iron_ingot(item):
            item_amt = getattr(item, "Amount", 1) or 1
            amt_to_move = min(item_amt, excess)
            if amt_to_move > 0:
                API.MoveItem(item.Serial, satchel_serial, amt=amt_to_move)
                API.Pause(0.5)
                excess -= amt_to_move
                if excess <= 0:
                    break


def craft_smith_tool_with_tinkering() -> bool:
    """Crafts a replacement smithing tool (Tongs if Tinkering >= 45.0, else Smith's Hammer) using Tinkering tools and ingots."""
    global tools_crafted, active_tool_serial
    tinker_tool = get_tinker_tool()
    if not tinker_tool:
        update_status("No Tinker's Tool")
        API.SysMsg("[Blacksmith] Out of smithing tools and no Tinker's Tool found in backpack! Please carry a Tinker's Tool.")
        return False

    tinker_skill_obj = API.GetSkill("Tinkering")
    tinker_skill = float(tinker_skill_obj.Value) if tinker_skill_obj else 0.0

    # Prefer Tongs (1 ingot, 45.0 skill) over Smith's Hammer (4 ingots, 40.0 skill)
    prefer_tongs = tinker_skill >= 45.0
    tool_name = "Tongs" if prefer_tongs else "Smith's Hammer"
    ingots_needed = 1 if prefer_tongs else 4

    # Need enough ingots
    if count_backpack_ingots() < ingots_needed:
        if not restock_ingots_from_satchel():
            API.SysMsg(f"[Blacksmith] Not enough ingots in backpack or satchel to craft {tool_name} (need {ingots_needed})!")
            update_status("Out of Ingots")
            return False

    update_status(f"Tinkering {tool_name}...")
    API.SysMsg(f"[Blacksmith] Crafting replacement {tool_name} via Tinkering ({ingots_needed} ingot)...")

    # Record tools before craft
    count_before = count_smith_tools()

    # Retry up to MAX_TOOL_CRAFT_ATTEMPTS in case of skill failure
    for attempt in range(1, MAX_TOOL_CRAFT_ATTEMPTS + 1):
        if API.StopRequested or is_stopped:
            return False

        # Ensure enough ingots remain in backpack across multiple attempts
        if count_backpack_ingots() < ingots_needed:
            if not restock_ingots_from_satchel():
                API.SysMsg(f"[Blacksmith] Not enough ingots in backpack or satchel to craft {tool_name} (need {ingots_needed})!")
                update_status("Out of Ingots")
                return False

        if not API.HasGump():
            API.UseObject(tinker_tool)
            if not API.WaitForGump(delay=2.5):
                API.SysMsg("[Blacksmith] Tinker craft menu did not appear.")
                return False

        # Check if Make Last is uninitialized in Tinkering
        if API.GumpContains("haven't made anything") or API.GumpContains("not made anything"):
            API.SysMsg(f"[Blacksmith] Tinkering 'Make Last' is not set to {tool_name}.")
            API.SysMsg(f"[Blacksmith] In the open Tinkering menu: Click 'Tools' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
            update_status(f"Craft 1 {tool_name} in Tinkering")
            return False

        # Clear journal to detect results
        API.ClearJournal()
        API.ReplyGump(GUMP_BTN_MAKE_LAST)
        wait_with_ui(TOOL_CRAFT_DELAY)

        # Check journal for success or fail
        entries = API.GetJournalEntries(TOOL_CRAFT_DELAY + 0.5)
        j_text = [str(e.Text).lower() for e in entries] if entries else []

        if any("haven't made anything" in t or "have not made" in t for t in j_text):
            API.SysMsg(f"[Blacksmith] Tinkering 'Make Last' is not set to {tool_name}.")
            API.SysMsg(f"[Blacksmith] In the open Tinkering menu: Click 'Tools' -> '{tool_name}' once to craft it, then click Resume on the Gump.")
            update_status(f"Craft 1 {tool_name} in Tinkering")
            return False

        # Check if a new tool appeared
        count_after = count_smith_tools()
        if count_after > count_before or get_smith_tool() is not None:
            tools_crafted += 1
            API.SysMsg(f"[Blacksmith] Successfully crafted new {tool_name}!")
            update_stats()

            # Close the Tinkering gump so it does not hijack the Blacksmith craft loop
            if API.HasGump():
                API.ReplyGump(0)
                API.Pause(0.3)

            # Invalidate active tool serial to force double-clicking the new tool
            active_tool_serial = None
            return True

        if any("fail" in t or "lack the skill" in t for t in j_text):
            debug_msg(f"Tinkering {tool_name} craft attempt {attempt}/{MAX_TOOL_CRAFT_ATTEMPTS} failed, retrying...")
            API.Pause(0.5)

    # If all attempts failed, close menu and prompt player
    if API.HasGump():
        API.ReplyGump(0)
        API.Pause(0.3)

    API.SysMsg(f"[Blacksmith] Failed to auto-craft {tool_name} after {MAX_TOOL_CRAFT_ATTEMPTS} attempts.")
    API.SysMsg(f"[Blacksmith] Please manually craft {tool_name} once via Tinkering to prime Make Last, then click Resume.")
    update_status(f"Paused (Need {tool_name})")
    return False


craft_smith_hammer_with_tinkering = craft_smith_tool_with_tinkering


# ==============================================================================
# Helper Functions - Skill Tiers & Smelting
# ==============================================================================

def get_recommended_item(skill: float) -> Tuple[str, int]:
    """Returns the most ingot-efficient item name and ingot cost for the current skill."""
    for min_sk, max_sk, name, cost in PROGRESSION_LADDER:
        if min_sk <= skill < max_sk:
            return name, cost
    return "Platemail Tunic", 25


def find_nearby_forge():
    """Finds a forge within reach (searching ground items and map statics)."""
    px, py = API.Player.X, API.Player.Y

    # 1. Search dynamic ground items (placed house addons, circular stone forges, world objects)
    ground_items = API.GetItemsOnGround(4)
    if ground_items:
        for item in ground_items:
            g = getattr(item, "Graphic", 0)
            name = str(getattr(item, "Name", "") or "").lower()
            if g in FORGE_GRAPHICS or "forge" in name:
                debug_msg(f"Forge detected on ground: 0x{item.Serial:X} (Graphic: 0x{g:04X}, Name: '{item.Name}') at ({item.X}, {item.Y})")
                return item

    # 2. Search map statics (town blacksmith shops)
    statics = API.GetStaticsInArea(px - 4, py - 4, px + 4, py + 4)
    if statics:
        for s in statics:
            sg = getattr(s, "Graphic", 0)
            if sg in FORGE_GRAPHICS:
                debug_msg(f"Forge detected as static: Graphic 0x{sg:04X} at ({s.X}, {s.Y})")
                return s

    return None


def find_nearby_anvil():
    """Finds an anvil within reach (searching ground items and map statics)."""
    px, py = API.Player.X, API.Player.Y

    # 1. Search dynamic ground items (placed anvils)
    ground_items = API.GetItemsOnGround(4)
    if ground_items:
        for item in ground_items:
            g = getattr(item, "Graphic", 0)
            name = str(getattr(item, "Name", "") or "").lower()
            if g in ANVIL_GRAPHICS or "anvil" in name:
                debug_msg(f"Anvil detected on ground: 0x{item.Serial:X} (Graphic: 0x{g:04X}, Name: '{item.Name}') at ({item.X}, {item.Y})")
                return item

    # 2. Search map statics
    statics = API.GetStaticsInArea(px - 4, py - 4, px + 4, py + 4)
    if statics:
        for s in statics:
            sg = getattr(s, "Graphic", 0)
            if sg in ANVIL_GRAPHICS:
                debug_msg(f"Anvil detected as static: Graphic 0x{sg:04X} at ({s.X}, {s.Y})")
                return s

    return None


def get_backpack_crafted_item(exclude_serials):
    """Finds a newly crafted weapon or armor piece in the main backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not items:
        return None
    for item in items:
        if item.Serial in exclude_serials:
            continue
        if item.Serial == satchel_serial:
            continue
        if item.Graphic == INGOT_GRAPHIC:
            continue
        if item.Graphic in ALL_SMITH_TOOLS or item.Graphic in TINKER_TOOL_GRAPHICS:
            continue
        # Candidate item found
        return item
    return None


def smelt_item(item) -> bool:
    """Smelts a crafted item at the forge using the Blacksmith craft gump or direct forge targeting."""
    global total_smelted
    update_status(f"Smelting {item.Name or 'item'}...")

    tool = get_smith_tool()
    if not tool:
        return False

    # Attempt 1: Click Smelt button on existing open craft gump
    smelted = False
    if API.HasGump():
        API.ReplyGump(GUMP_BTN_SMELT)
        if API.WaitForTarget(timeout=2.0):
            API.Target(item.Serial)
            API.Pause(SMELT_DELAY)
            smelted = True

    # Attempt 2: If gump wasn't open or target timed out, use tool to open gump and smelt
    if not smelted:
        API.UseObject(tool)
        if API.WaitForGump(delay=2.0):
            API.ReplyGump(GUMP_BTN_SMELT)
            if API.WaitForTarget(timeout=2.0):
                API.Target(item.Serial)
                API.Pause(SMELT_DELAY)
                smelted = True

    total_smelted += 1
    deposit_excess_ingots_to_satchel()
    return True


# ==============================================================================
# Main Craft Cycle
# ==============================================================================

def craft_cycle() -> bool:
    """Executes a single craft attempt and recycles the crafted item."""
    global total_crafted, total_failed, current_recipe_name, is_paused, active_tool_serial

    # 1. Check Skill
    skill_obj = API.GetSkill("Blacksmith") or API.GetSkill("Blacksmithy")
    if not skill_obj:
        update_status("Skill not found")
        return False

    val = float(skill_obj.Value)
    cap = float(skill_obj.Cap)
    if val >= TARGET_SKILL or val >= cap:
        update_status(f"Target Reached ({val:.1f})")
        API.SysMsg(f"[Blacksmith] Congratulations! Target skill reached: {val:.1f} / {cap:.1f}")
        return False

    rec_item, ingot_cost = get_recommended_item(val)
    if rec_item != current_recipe_name:
        API.SysMsg(f"[Blacksmith] Tier Change! Current skill: {val:.1f}. Optimal item: {rec_item} ({ingot_cost} ingots).")
        current_recipe_name = rec_item
        update_stats()

    # 2. Check Tool
    tool = get_smith_tool()
    if not tool:
        active_tool_serial = None
        if not craft_smith_tool_with_tinkering():
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            return True
        tool = get_smith_tool()
        if not tool:
            update_status("No Tool")
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            return True

    # 3. Check & Restock Ingots
    total_ingots = count_backpack_ingots() + (count_satchel_ingots() if satchel_serial else 0)
    if total_ingots < ingot_cost:
        update_status("Out of Ingots")
        API.SysMsg("[Blacksmith] Out of ingots in satchel and backpack! Please refill and click Resume.")
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        return True

    if not DIRECT_SATCHEL_CRAFTING and count_backpack_ingots() < ingot_cost:
        if not restock_ingots_from_satchel():
            update_status("Out of Ingots")
            API.SysMsg("[Blacksmith] Out of ingots in satchel! Please refill satchel and click Resume.")
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            return True

    # 4. Snapshot backpack items before crafting
    bp_items_before = API.ItemsInContainer(API.Backpack, recursive=False) or []
    known_serials = {item.Serial for item in bp_items_before}

    # 5. Execute Craft via Make Last
    update_status(f"Crafting {current_recipe_name}...")
    API.ClearJournal()

    # Check if tool changed or active gump is invalid
    tool_changed = (active_tool_serial is None or active_tool_serial != tool.Serial)
    active_gump = API.HasGump()

    # If a non-blacksmith gump (such as Tinkering) is currently open, close it
    if active_gump:
        if API.GumpContains("Tinkering") or API.GumpContains("TINKERING") or tool_changed:
            API.ReplyGump(0, active_gump)
            API.Pause(0.3)
            if API.HasGump(active_gump):
                API.CloseGump(active_gump)
            active_gump = API.HasGump()

    # If no craft gump is open or tool changed, use the smithing tool
    if not active_gump or tool_changed:
        API.UseObject(tool)
        active_tool_serial = tool.Serial
        if not API.WaitForGump(delay=2.5):
            debug_msg("Craft gump timed out on tool use.")
            return True

    # Check if gump displays "haven't made anything yet"
    if API.GumpContains("haven't made anything") or API.GumpContains("not made anything"):
        category_hint = "Bashing" if current_recipe_name in ["Mace", "Maul"] else "Metal Armor / Weapons"
        API.SysMsg(f"[Blacksmith] Notice: 'You haven't made anything yet.'")
        API.SysMsg(f"[Blacksmith] In the menu on screen, click '{category_hint}' -> '{current_recipe_name}' once to craft it.")
        API.SysMsg("[Blacksmith] Once crafted, click 'Resume' on the Gump and the trainer will loop automatically!")
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status(f"Click {current_recipe_name} in menu")
        return True

    API.ReplyGump(GUMP_BTN_MAKE_LAST)
    if not wait_with_ui(CRAFT_DELAY):
        return False

    # Check if server responded with "haven't made anything yet"
    if API.GumpContains("haven't made anything") or API.GumpContains("not made anything"):
        category_hint = "Bashing" if current_recipe_name in ["Mace", "Maul"] else "Metal Armor / Weapons"
        API.SysMsg(f"[Blacksmith] Notice: 'You haven't made anything yet.'")
        API.SysMsg(f"[Blacksmith] In the menu on screen, click '{category_hint}' -> '{current_recipe_name}' once to craft it.")
        API.SysMsg("[Blacksmith] Once crafted, click 'Resume' on the Gump and the trainer will loop automatically!")
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status(f"Click {current_recipe_name} in menu")
        return True

    # 6. Check Result in Journal & Backpack
    crafted_item = get_backpack_crafted_item(known_serials)
    entries = API.GetJournalEntries(CRAFT_DELAY + 1.0)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

    # Check if Make Last is uninitialized in journal
    if any("haven't made anything" in t or "have not made" in t for t in j_text):
        API.SysMsg(f"[Blacksmith] Make Last is not set yet. Opening craft menu - please click '{current_recipe_name}' once, then click Resume on the Gump.")
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused (Set Recipe)")
        API.UseObject(tool)
        return True

    # Check if server complained about missing resources despite satchel having ingots
    if any("sufficient metal" in t or "enough metal" in t or "lack the metal" in t for t in j_text) or API.InJournal("sufficient metal"):
        if satchel_serial and count_satchel_ingots() >= ingot_cost:
            API.SysMsg("[Blacksmith] Server requires ingots in root backpack. Restocking from satchel...")
            restock_ingots_from_satchel()
            return True

    # Check for success
    if crafted_item or any("you create" in t or "placed in your backpack" in t for t in j_text):
        total_crafted += 1
        debug_msg(f"Crafted successfully: {crafted_item.Name if crafted_item else 'item'}")

        # Smelt immediately
        if crafted_item:
            smelt_item(crafted_item)
    elif any("you fail" in t or "lack the skill" in t for t in j_text):
        total_failed += 1
        debug_msg("Craft failed.")
    elif any("worn out" in t or "broke" in t for t in j_text):
        API.SysMsg("[Blacksmith] Tool broke during crafting.")
        active_tool_serial = None

    update_stats()
    return True


# ==============================================================================
# Script Initialization & Stop Hooks
# ==============================================================================

def on_stop() -> None:
    dispose_gump()
    API.SysMsg("Blacksmith trainer stopped.")

API.OnStop(on_stop)


def main() -> None:
    global satchel_serial, current_recipe_name

    API.SysMsg("=== FesterUO Blacksmith Trainer ===")

    # 1. Verify / Acquire Resource Satchel
    if not satchel_serial:
        API.SysMsg("Please target your Resource Satchel containing ingots...")
        target_serial = API.RequestTarget(timeout=15.0)
        if not target_serial:
            API.SysMsg("No satchel targeted. Stopping.")
            return
        satchel_serial = target_serial

    # 2. Open satchel container so items inside are known to client
    satchel_item = API.FindItem(satchel_serial)
    if satchel_item:
        API.UseObject(satchel_serial)
        API.Pause(0.5)

    # Check for any colored/special ingots in the backpack to alert the user
    bp_items = API.ItemsInContainer(API.Backpack, recursive=False)
    if bp_items:
        for item in bp_items:
            if item.Serial != satchel_serial and getattr(item, "Graphic", 0) == INGOT_GRAPHIC and not is_regular_iron_ingot(item):
                c_name = getattr(item, "Name", "") or f"Colored (Hue {item.Hue})"
                API.SysMsg(f"[Blacksmith] Notice: {c_name} detected in backpack. Training strictly uses regular Iron ingots (Hue 0).")

    # 3. Check forge and anvil proximity
    forge = find_nearby_forge()
    if forge:
        f_name = getattr(forge, "Name", "Forge") or "Forge"
        API.SysMsg(f"[Blacksmith] {f_name} detected at ({forge.X}, {forge.Y}).")
    else:
        API.SysMsg("[Notice] No forge detected within 4 tiles. Ensure you stand near an Anvil & Forge!")

    anvil = find_nearby_anvil()
    if anvil:
        a_name = getattr(anvil, "Name", "Anvil") or "Anvil"
        API.SysMsg(f"[Blacksmith] {a_name} detected at ({anvil.X}, {anvil.Y}).")
    else:
        API.SysMsg("[Notice] No anvil detected within 4 tiles.")

    # 4. Initialize Gump & Recipe
    skill_obj = API.GetSkill("Blacksmith") or API.GetSkill("Blacksmithy")
    current_skill = float(skill_obj.Value) if skill_obj else 0.0
    rec_item, rec_cost = get_recommended_item(current_skill)
    current_recipe_name = rec_item

    create_control_gump()
    update_stats()

    # Initial check of ingots in backpack only if not using direct satchel crafting
    if not DIRECT_SATCHEL_CRAFTING and count_backpack_ingots() < MIN_BACKPACK_INGOTS:
        restock_ingots_from_satchel()

    update_status("Running")
    API.SysMsg(f"Blacksmith training started. Current skill: {current_skill:.1f} | Recipe: {current_recipe_name}")

    # 5. Main Training Loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        success = craft_cycle()
        if not success:
            break

        API.Pause(0.2)

    update_status("Finished")
    API.SysMsg("Blacksmith training finished.")
    dispose_gump()


main()
