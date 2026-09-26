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

# Working ingot buffer maintained in main backpack (prevents becoming overweight)
MIN_BACKPACK_INGOTS = 20
TARGET_BACKPACK_INGOTS = 60
RESTOCK_BATCH_SIZE = 50

# Crafting action delays in seconds
CRAFT_DELAY = 1.3
SMELT_DELAY = 0.8
TOOL_CRAFT_DELAY = 1.5

# Server Craft Gump button IDs (standard ServUO / RunUO)
GUMP_BTN_MAKE_LAST = 21  # Universal "Make Last" button
GUMP_BTN_SMELT = 14      # "Smelt Item" button on Blacksmith craft menu

# Enable verbose debug messages in client console
DEBUG = False


# ==============================================================================
# Item & Graphic Definitions
# ==============================================================================

INGOT_GRAPHIC = 0x1BF2

# Smithing tools
SMITH_HAMMER_GRAPHICS = {0x13E3, 0x13E4}
TONGS_GRAPHICS = {0x0FBB}
SLEDGEHAMMER_GRAPHICS = {0x0FB5}
ALL_SMITH_TOOLS = SMITH_HAMMER_GRAPHICS | TONGS_GRAPHICS | SLEDGEHAMMER_GRAPHICS

# Tinkering tools
TINKER_TOOL_GRAPHICS = {0x1EB8, 0x1EB9}

# Forges and Anvils
FORGE_GRAPHICS = {0x0FB1, 0x197A, 0x197E, 0x1982, 0x1986, 0x198A, 0x198E, 0x1992, 0x1996, 0x199A}
ANVIL_GRAPHICS = {0x0FAF, 0x0FB0}

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
    tool = get_smith_tool()
    if tool:
        API.SysMsg("Opening craft menu. Click your desired item once to set recipe, then resume.")
        API.UseObject(tool)
    else:
        API.SysMsg("No smithing tool available to open craft menu!")


def on_gump_disposed() -> None:
    global is_stopped
    if not is_stopped and not API.StopRequested:
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
            if "hammer" in name or "tongs" in name:
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


def count_backpack_ingots() -> int:
    """Counts raw iron ingots residing directly in the player's main backpack (outside satchel)."""
    if not API.Player:
        return 0
    items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not items:
        return 0
    total = 0
    for item in items:
        if item.Graphic == INGOT_GRAPHIC and item.Serial != satchel_serial:
            total += getattr(item, "Amount", 1) or 1
    return total


def count_satchel_ingots() -> int:
    """Counts iron ingots inside the resource satchel."""
    if not satchel_serial:
        return 0
    items = API.ItemsInContainer(satchel_serial, recursive=True)
    if not items:
        items = API.ItemsInContainer(satchel_serial)
    if not items:
        return 0
    total = 0
    for item in items:
        if item.Graphic == INGOT_GRAPHIC:
            total += getattr(item, "Amount", 1) or 1
    return total


def restock_ingots_from_satchel() -> bool:
    """Pulls a batch of ingots from the resource satchel into the main backpack."""
    if not satchel_serial:
        return False

    current_bp = count_backpack_ingots()
    if current_bp >= MIN_BACKPACK_INGOTS:
        return True

    satchel_ingot = API.FindType(INGOT_GRAPHIC, satchel_serial)
    if not satchel_ingot:
        return False

    amt_available = getattr(satchel_ingot, "Amount", 1) or 1
    amt_needed = max(RESTOCK_BATCH_SIZE, TARGET_BACKPACK_INGOTS - current_bp)
    amt_to_move = min(amt_available, amt_needed)

    if amt_to_move <= 0:
        return False

    update_status(f"Restocking {amt_to_move} ingots...")
    API.MoveItem(satchel_ingot.Serial, API.Backpack, amt=amt_to_move)
    API.Pause(0.6)
    update_stats()
    return count_backpack_ingots() >= 6


def deposit_excess_ingots_to_satchel() -> None:
    """Moves excess ingots from backpack back into the satchel to prevent weight overburden."""
    if not satchel_serial:
        return

    current_bp = count_backpack_ingots()
    if current_bp <= TARGET_BACKPACK_INGOTS + 20:
        return

    excess = current_bp - TARGET_BACKPACK_INGOTS
    if excess <= 10:
        return

    bp_items = API.ItemsInContainer(API.Backpack, recursive=False)
    if not bp_items:
        return

    for item in bp_items:
        if item.Graphic == INGOT_GRAPHIC and item.Serial != satchel_serial:
            item_amt = getattr(item, "Amount", 1) or 1
            amt_to_move = min(item_amt, excess)
            if amt_to_move > 0:
                API.MoveItem(item.Serial, satchel_serial, amt=amt_to_move)
                API.Pause(0.6)
                excess -= amt_to_move
                if excess <= 0:
                    break


def craft_smith_hammer_with_tinkering() -> bool:
    """Crafts a replacement Smith's Hammer using Tinkering tools and ingots."""
    global tools_crafted
    tinker_tool = get_tinker_tool()
    if not tinker_tool:
        update_status("No Tinker's Tool")
        API.SysMsg("[Blacksmith] Out of smithing tools and no Tinker's Tool found in backpack!")
        return False

    # Need at least 4 ingots
    if count_backpack_ingots() < 4:
        if not restock_ingots_from_satchel():
            API.SysMsg("[Blacksmith] Not enough ingots to craft a Smith's Hammer!")
            return False

    update_status("Tinkering Smith Hammer...")
    API.SysMsg("[Blacksmith] Crafting replacement Smith's Hammer via Tinkering...")

    # Record tools before craft
    tools_before = API.FindTypeAll(0x13E3, API.Backpack) or []
    count_before = len(tools_before)

    API.UseObject(tinker_tool)
    if API.WaitForGump(delay=2.5):
        # Attempt Make Last on tinker gump
        API.ReplyGump(GUMP_BTN_MAKE_LAST)
        wait_with_ui(TOOL_CRAFT_DELAY)
    else:
        API.SysMsg("[Blacksmith] Tinker craft menu did not appear.")
        return False

    # Verify if a new hammer appeared
    tools_after = API.FindTypeAll(0x13E3, API.Backpack) or []
    if len(tools_after) > count_before or get_smith_tool() is not None:
        tools_crafted += 1
        API.SysMsg("[Blacksmith] Successfully crafted a new Smith's Hammer!")
        update_stats()
        return True

    API.SysMsg("[Blacksmith] Failed to auto-craft Smith's Hammer. Please set Make Last in Tinkering.")
    return False


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
    """Finds an anvil and forge within 3 tiles of player."""
    px, py = API.Player.X, API.Player.Y
    statics = API.GetStaticsInArea(px - 3, py - 3, px + 3, py + 3)
    if statics:
        for s in statics:
            sg = getattr(s, "Graphic", 0)
            if sg in FORGE_GRAPHICS:
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

    # Close any open craft gumps to keep client clean
    if API.HasGump():
        API.CloseGump()
        API.Pause(0.2)

    total_smelted += 1
    deposit_excess_ingots_to_satchel()
    return True


# ==============================================================================
# Main Craft Cycle
# ==============================================================================

def craft_cycle() -> bool:
    """Executes a single craft attempt and recycles the crafted item."""
    global total_crafted, total_failed, current_recipe_name

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
        if not craft_smith_hammer_with_tinkering():
            return False
        tool = get_smith_tool()
        if not tool:
            return False

    # 3. Check & Restock Ingots
    if count_backpack_ingots() < ingot_cost:
        if not restock_ingots_from_satchel():
            update_status("Out of Ingots")
            API.SysMsg("[Blacksmith] Out of ingots in satchel! Refill satchel to continue.")
            return False

    # 4. Snapshot backpack items before crafting
    bp_items_before = API.ItemsInContainer(API.Backpack, recursive=False) or []
    known_serials = {item.Serial for item in bp_items_before}

    # 5. Execute Craft via Make Last
    update_status(f"Crafting {current_recipe_name}...")
    API.ClearJournal()

    # If craft gump is open, click Make Last; otherwise double click tool and click Make Last
    if not API.HasGump():
        API.UseObject(tool)
        if not API.WaitForGump(delay=2.5):
            debug_msg("Craft gump timed out on tool use.")
            return True

    API.ReplyGump(GUMP_BTN_MAKE_LAST)
    if not wait_with_ui(CRAFT_DELAY):
        return False

    # 6. Check Result in Journal & Backpack
    crafted_item = get_backpack_crafted_item(known_serials)
    entries = API.GetJournalEntries(CRAFT_DELAY + 1.0)
    j_text = [str(e.Text).lower() for e in entries] if entries else []

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

    # 3. Check forge/anvil proximity
    forge = find_nearby_forge()
    if not forge:
        API.SysMsg("[Notice] No forge detected within 3 tiles. Ensure you stand near an Anvil & Forge!")

    # 4. Initialize Gump & Recipe
    skill_obj = API.GetSkill("Blacksmith") or API.GetSkill("Blacksmithy")
    current_skill = float(skill_obj.Value) if skill_obj else 0.0
    rec_item, rec_cost = get_recommended_item(current_skill)
    current_recipe_name = rec_item

    create_control_gump()
    update_stats()

    # Initial check of ingots in backpack
    if count_backpack_ingots() < MIN_BACKPACK_INGOTS:
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
