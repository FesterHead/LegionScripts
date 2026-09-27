"""
MiningAndLumberjackAuto.py - Combined Roaming Miner & Lumberjack Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Combines automated roaming mining and lumberjacking into a unified, alternating
    resource harvesting engine with an integrated control Gump:
    - Configurable Harvest Ratio Loop:
        1. Mines ore deposit(s) (default: 1 spot) until depleted.
        2. Switches to lumberjack gear and chops tree(s) (default: 4 trees) until depleted.
        3. Repeats seamlessly with custom tree-to-ore ratios (e.g. 4 trees per 1 mining spot).
    - Equipment & Dress Switching:
        * Automatically switches to the "Mining" dress profile and equips a pickaxe/shovel.
        * Automatically switches to the "Lumberjack" dress profile and equips a woodcutting axe.
    - Pathfinding & Spatial Scanning:
        * Scans nearby cave floors, mountain ridges, rock outcroppings, and world ore nodes.
        * Scans nearby static trees using TazUO's native vegetation detection.
        * Pathfinds directly to nodes within reach (distance <= 2).
        * Remembers recent deposits and trees to prevent immediate re-harvesting.
    - Integrated Control Gump:
        * Real-time activity status (Mining, Chopping, Moving, Paused, Overweight).
        * Live Mining and Lumberjacking skill tracking with automatic gain announcements.
        * Running statistics: Veins mined, Total ore, Trees chopped, Total logs/wood.
        * Character Strength, Dexterity, and Weight capacity monitoring.
        * Interactive Pause / Resume and Stop buttons.
"""

from collections import deque
import re
from typing import List, Tuple, Optional
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Delay in seconds between harvesting swings (1.0s on fast shards, 4.5s on OSI)
SWING_DELAY: float = 1.0

# Harvesting ratio: trees to chop per mining spot (e.g. 4 trees to 1 mining spot)
TREES_PER_MINING_SPOT: int = 8
MINING_SPOTS_PER_CYCLE: int = 1

# Dress configuration profiles configured in TazUO
DRESS_PROFILE_MINING: str = "Mining"
DRESS_PROFILE_LUMBERJACK: str = "Lumberjack"

# Search radius in tiles around the player to locate deposits and trees
SEARCH_RADIUS: int = 25

# Maximum number of recent deposits and trees to remember and avoid revisiting
DEPOSIT_HISTORY_LIMIT: int = 150
TREE_HISTORY_LIMIT: int = 50

# Radius in tiles to mark as depleted when a vein is exhausted
VEIN_DEPLETION_RADIUS: int = 6

# Backpack weight protection
MAX_WEIGHT_CHECK: bool = True
WEIGHT_BUFFER: int = 15  # Stop when Weight >= WeightMax - WEIGHT_BUFFER

# Maximum seconds allowed to pathfind before skipping node
PATHFIND_TIMEOUT: float = 12.0

# Enable verbose logging in client console
DEBUG: bool = False

# ==============================================================================
# Item & Graphic Definitions
# ==============================================================================

# Mining tools
PICKAXE_GRAPHIC: int = 0x0E86
SHOVEL_GRAPHICS: List[int] = [0x0F39, 0x0F3A]

# Woodcutting axes
AXE_GRAPHICS: List[int] = [
    0x0F43, 0x0F44,  # Hatchet
    0x0F45, 0x0F46,  # Executioner's Axe
    0x0F47, 0x0F48,  # Battle Axe
    0x0F49, 0x0F4A,  # Axe
    0x0F4B, 0x0F4C,  # Double Axe
    0x0F4D, 0x0F4E,  # Bardiche
    0x13AF, 0x13B0,  # War Axe
    0x13FA, 0x13FB,  # Large Battle Axe
    0x1442, 0x1443,  # Two Handed Axe
]

# Ore graphics
ORE_GRAPHICS: List[int] = [
    0x19B7,  # Single small ore
    0x19B8,  # Medium ore pile
    0x19B9,  # Large ore pile
    0x19BA,  # Small ore pile
]

# Log and wood graphics
LOG_GRAPHICS: List[int] = [
    0x1BDD,  # Standard wood log
    0x1BE0,  # Alternate log pile
]

# Standard UO mountain land and static tile IDs (ServUO engine)
SERVUO_MINEABLE_TILES: List[int] = [
    220, 221, 222, 223, 224, 225, 226, 227, 228, 229,
    230, 231, 236, 237, 238, 239, 240, 241, 242, 243,
    244, 245, 246, 247, 252, 253, 254, 255, 256, 257,
    258, 259, 260, 261, 262, 263, 268, 269, 270, 271,
    272, 273, 274, 275, 276, 277, 282, 283, 284, 285,
    286, 287, 288, 289, 290, 291, 296, 297, 298, 299,
    300, 301, 467, 468, 469, 470, 471, 472, 473, 474,
    476, 477, 478, 479, 480, 481, 482, 483, 484, 485,
    486, 487, 492, 493, 494, 495, 543, 544, 545, 546,
    547, 548, 549, 550, 551, 552, 553, 554, 555, 556,
    557, 558, 559, 560, 561, 562, 563, 564, 565, 566,
    567, 568, 569, 570, 571, 572, 573, 574, 575, 576,
    577, 578, 579, 581, 582, 583, 584, 585, 586, 587,
    588, 589, 590, 591, 592, 593, 594, 595, 596, 597,
    598, 599, 600, 601, 1339, 1340, 1341, 1342, 1343,
    1351, 1352, 1353, 1354, 1355, 1356, 1357, 1358, 1359,
    1361, 1362, 1363, 1386,
]

BOULDER_GRAPHICS: List[int] = [
    0x1363, 0x1364, 0x1365, 0x1366, 0x1367, 0x1368, 0x1369, 0x136A,
    0x136B, 0x136C, 0x136D, 0x134F, 0x1350, 0x1351, 0x1352,
]

MINEABLE_GRAPHICS: set = set(SERVUO_MINEABLE_TILES) | set(BOULDER_GRAPHICS)

# Journal keywords for depletion
MINING_DEPLETED_KEYWORDS = [
    "no metal here",
    "there is no metal",
    "you have depleted",
    "cannot be mined",
    "try mining elsewhere",
    "nothing here to mine",
    "cannot see that",
    "can't reach",
    "no line of sight",
    "too far away",
    "target cannot be seen",
    "have no line of sight",
    "someone has already",
    "mine that",
    "use a shovel",
]

CHOP_DEPLETED_KEYWORDS = [
    "no wood here",
    "not enough wood",
    "nothing here to chop",
    "cannot see that",
    "can't reach",
    "no line of sight",
    "too far away",
    "target cannot be seen",
    "have no line of sight",
    "try chopping elsewhere",
    "you have depleted",
    "someone has already",
    "it appears immune to your blow",
    "cannot be chopped",
    "use an axe on that",
]

TOOL_BROKEN_KEYWORDS = [
    "worn out",
    "broke",
    "destroyed",
    "no longer functions",
]

# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_mine_skill = None
lbl_lumber_skill = None
lbl_mine_stats = None
lbl_lumber_stats = None
lbl_char_stats = None
lbl_weight = None
btn_pause = None
btn_stop = None

is_paused: bool = False
is_stopped: bool = False

last_mining_skill: Optional[float] = None
last_lumber_skill: Optional[float] = None
last_str: Optional[int] = None
last_dex: Optional[int] = None

veins_mined: int = 0
total_ores: int = 0
trees_chopped: int = 0
total_wood: int = 0

depleted_veins: deque = deque(maxlen=DEPOSIT_HISTORY_LIMIT)
depleted_trees: deque = deque(maxlen=TREE_HISTORY_LIMIT)
unreachable_coords: set = set()

# ==============================================================================
# Gump & UI Updates
# ==============================================================================

def update_status(text: str) -> None:
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def update_stats() -> None:
    global last_mining_skill, last_lumber_skill, last_str, last_dex
    global lbl_mine_skill, lbl_lumber_skill, lbl_mine_stats, lbl_lumber_stats, lbl_char_stats, lbl_weight

    # 1. Mining Skill
    m_skill = API.GetSkill("Mining")
    if m_skill and lbl_mine_skill:
        val = float(m_skill.Value)
        cap = float(m_skill.Cap)
        lbl_mine_skill.Text = f"Mining: {val:.1f} / {cap:.1f}"
        if last_mining_skill is not None and val > last_mining_skill:
            gain = val - last_mining_skill
            API.SysMsg(f"[Mining] Skill gained +{gain:.1f}! New skill: {val:.1f}")
        last_mining_skill = val

    # 2. Lumberjacking Skill
    l_skill = API.GetSkill("Lumberjacking")
    if l_skill and lbl_lumber_skill:
        val = float(l_skill.Value)
        cap = float(l_skill.Cap)
        lbl_lumber_skill.Text = f"Lumberjacking: {val:.1f} / {cap:.1f}"
        if last_lumber_skill is not None and val > last_lumber_skill:
            gain = val - last_lumber_skill
            API.SysMsg(f"[Lumberjack] Skill gained +{gain:.1f}! New skill: {val:.1f}")
        last_lumber_skill = val

    # 3. Counters
    if lbl_mine_stats:
        lbl_mine_stats.Text = f"Mined: {veins_mined} veins | {total_ores} ore"

    if lbl_lumber_stats:
        lbl_lumber_stats.Text = f"Chopped: {trees_chopped} trees | {total_wood} logs"

    # 4. Strength & Dexterity
    cur_str = API.Player.Strength
    cur_dex = API.Player.Dexterity
    if cur_str is not None and cur_dex is not None and lbl_char_stats:
        lbl_char_stats.Text = f"Str: {cur_str} | Dex: {cur_dex}"
        if last_str is not None and cur_str > last_str:
            API.SysMsg(f"[Stats] Strength increased by {cur_str - last_str}! Total: {cur_str}")
        if last_dex is not None and cur_dex > last_dex:
            API.SysMsg(f"[Stats] Dexterity increased by {cur_dex - last_dex}! Total: {cur_dex}")
        last_str = cur_str
        last_dex = cur_dex

    # 5. Weight
    w = API.Player.Weight or 0
    w_max = API.Player.WeightMax or 0
    if lbl_weight:
        lbl_weight.Text = f"Weight: {w} / {w_max}"


def on_pause_clicked() -> None:
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Miner & Lumberjack paused." if is_paused else "Miner & Lumberjack resumed.")


def on_stop_clicked() -> None:
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    if API.Pathfinding():
        API.CancelPathfinding()
    API.Stop()


def on_gump_disposed() -> None:
    global is_stopped
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


def create_control_gump() -> None:
    """Initializes and renders the combined Miner & Lumberjack Gump."""
    global gump, lbl_status, lbl_mine_skill, lbl_lumber_skill, lbl_mine_stats, lbl_lumber_stats
    global lbl_char_stats, lbl_weight, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 310, 220)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 310, 220)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Miner & Lumberjack", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skills: Mining & Lumberjack
    lbl_mine_skill = API.Gumps.CreateGumpLabel("Mining: -- / --", 996)
    lbl_mine_skill.SetPos(10, 48)
    gump.Add(lbl_mine_skill)

    lbl_lumber_skill = API.Gumps.CreateGumpLabel("Lumberjack: -- / --", 996)
    lbl_lumber_skill.SetPos(10, 68)
    gump.Add(lbl_lumber_skill)

    # Harvesting stats
    lbl_mine_stats = API.Gumps.CreateGumpLabel("Mined: 0 veins | 0 ore", 53)
    lbl_mine_stats.SetPos(10, 88)
    gump.Add(lbl_mine_stats)

    lbl_lumber_stats = API.Gumps.CreateGumpLabel("Chopped: 0 trees | 0 logs", 53)
    lbl_lumber_stats.SetPos(10, 108)
    gump.Add(lbl_lumber_stats)

    # Char stats and Weight
    lbl_char_stats = API.Gumps.CreateGumpLabel("Str: -- | Dex: --", 996)
    lbl_char_stats.SetPos(10, 128)
    gump.Add(lbl_char_stats)

    lbl_weight = API.Gumps.CreateGumpLabel("Weight: -- / --", 996)
    lbl_weight.SetPos(10, 148)
    gump.Add(lbl_weight)

    # Buttons: Pause / Stop
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 130, 24)
    btn_pause.SetPos(15, 175)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 135, 24)
    btn_stop.SetPos(160, 175)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)
    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    global gump
    if gump and not getattr(gump, "IsDisposed", False):
        gump.Dispose()


def check_ui_events() -> bool:
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
    elapsed = 0.0
    step = 0.2
    while elapsed < seconds:
        if not check_ui_events():
            return False
        API.Pause(step)
        elapsed += step
    return check_ui_events()


# ==============================================================================
# Helper Functions - Tool & Weight Management
# ==============================================================================

def on_stop() -> None:
    if API.Pathfinding():
        API.CancelPathfinding()
    dispose_gump()
    API.SysMsg("Miner & Lumberjack stopped.")

API.OnStop(on_stop)


def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    return max(abs(x1 - x2), abs(y1 - y2))


def is_overburdened() -> bool:
    if not MAX_WEIGHT_CHECK:
        return False
    weight = API.Player.Weight
    weight_max = API.Player.WeightMax
    if weight is not None and weight_max is not None and weight_max > 0:
        return weight >= (weight_max - WEIGHT_BUFFER)
    return False


def is_mining_tool(item) -> bool:
    if not item:
        return False
    g = getattr(item, "Graphic", 0)
    if g == PICKAXE_GRAPHIC or g in SHOVEL_GRAPHICS:
        return True
    item_data = getattr(item, "ItemData", None)
    if item_data:
        name = str(getattr(item_data, "Name", "")).lower()
        if "pickaxe" in name or "shovel" in name:
            return True
    return False


def get_equipped_mining_tool():
    """Finds an equipped pickaxe or shovel."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and is_mining_tool(item):
            return item
    return None


def get_backpack_mining_tool():
    """Finds a pickaxe or shovel in the backpack."""
    pickaxe = API.FindType(PICKAXE_GRAPHIC, API.Backpack)
    if pickaxe:
        return pickaxe
    for sg in SHOVEL_GRAPHICS:
        shovel = API.FindType(sg, API.Backpack)
        if shovel:
            return shovel
    items = API.GetItems(API.Backpack)
    if items:
        for item in items:
            if is_mining_tool(item):
                return item
    return None


def get_mining_tool():
    """Finds an equipped pickaxe/shovel or one in the backpack."""
    return get_equipped_mining_tool() or get_backpack_mining_tool()


def is_axe_item(item) -> bool:
    if not item:
        return False
    g = getattr(item, "Graphic", 0)
    if g in AXE_GRAPHICS:
        return True
    item_data = getattr(item, "ItemData", None)
    if item_data:
        name = str(getattr(item_data, "Name", "")).lower()
        if "axe" in name or "hatchet" in name:
            return True
    return False


def get_equipped_axe():
    """Finds an axe equipped in either weapon hand."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and is_axe_item(item):
            return item
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and not is_mining_tool(item):
            return item
    return None


def get_backpack_axe():
    """Finds an axe in player backpack."""
    for g in AXE_GRAPHICS:
        item = API.FindType(g, API.Backpack)
        if item:
            return item
    items = API.GetItems(API.Backpack)
    if items:
        for item in items:
            if is_axe_item(item):
                return item
    return None


def get_axe():
    """Finds an axe equipped or in backpack."""
    return get_equipped_axe() or get_backpack_axe()


def clear_hands() -> None:
    """Unequips items in OneHanded and TwoHanded layers into the backpack."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item:
            API.MoveItem(item.Serial, API.Backpack)
            API.Pause(0.4)


def switch_to_mining(force: bool = False):
    """Switches gear to mining using dress profile or direct equip."""
    if not force and get_equipped_mining_tool():
        return
    available = []
    try:
        available = API.GetAvailableDressOutfits() or []
    except Exception:
        pass
    if DRESS_PROFILE_MINING and DRESS_PROFILE_MINING in available:
        update_status("Dress: Mining gear...")
        API.Dress(DRESS_PROFILE_MINING)
        API.Pause(0.8)
    else:
        equipped = get_equipped_mining_tool()
        if not equipped:
            tool = get_backpack_mining_tool()
            if tool:
                clear_hands()
                update_status("Equipping pickaxe/shovel...")
                API.EquipItem(tool.Serial)
                API.Pause(0.8)


def switch_to_lumberjack(force: bool = False):
    """Switches gear to lumberjack using dress profile or direct equip."""
    if not force and get_equipped_axe():
        return
    available = []
    try:
        available = API.GetAvailableDressOutfits() or []
    except Exception:
        pass
    if DRESS_PROFILE_LUMBERJACK and DRESS_PROFILE_LUMBERJACK in available:
        update_status("Dress: Lumberjack gear...")
        API.Dress(DRESS_PROFILE_LUMBERJACK)
        API.Pause(0.8)
    else:
        equipped = get_equipped_axe()
        if not equipped:
            axe = get_backpack_axe()
            if axe:
                clear_hands()
                update_status("Equipping axe...")
                API.EquipItem(axe.Serial)
                API.Pause(0.8)


def get_backpack_ore_count() -> int:
    total = 0
    for og in ORE_GRAPHICS:
        items = API.FindTypeAll(og, API.Backpack)
        if items:
            for item in items:
                total += getattr(item, "Amount", 1) or 1
    return total


def get_backpack_log_count() -> int:
    total = 0
    for lg in LOG_GRAPHICS:
        items = API.FindTypeAll(lg, API.Backpack)
        if items:
            for item in items:
                total += getattr(item, "Amount", 1) or 1
    return total


# ==============================================================================
# Mining Engine
# ==============================================================================

def is_vein_depleted(x: int, y: int) -> bool:
    for dx, dy in depleted_veins:
        if chebyshev_distance(x, y, dx, dy) <= VEIN_DEPLETION_RADIUS:
            return True
    return False


def mark_vein_depleted(x: int, y: int) -> None:
    depleted_veins.append((x, y))
    debug_msg(f"Marked vein at ({x}, {y}) depleted. Total in history: {len(depleted_veins)}")


def find_mineable_stand_tile(tx: int, ty: int) -> Optional[Tuple[int, int]]:
    px = API.Player.X
    py = API.Player.Y

    stand_candidates = []
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx == 0 and dy == 0:
                continue
            if max(abs(dx), abs(dy)) > 2:
                continue
            sx = tx + dx
            sy = ty + dy

            tile = API.GetTile(sx, sy)
            if not tile or getattr(tile, "Impassible", False):
                continue

            statics = API.GetStaticsAt(sx, sy)
            if statics and any(getattr(s, "IsImpassible", False) for s in statics):
                continue

            dist = chebyshev_distance(px, py, sx, sy)
            stand_candidates.append((dist, (sx, sy)))

    if not stand_candidates:
        return None

    stand_candidates.sort(key=lambda item: item[0])
    return stand_candidates[0][1]


def find_nearby_deposits():
    """Scans for nearby mineable statics and terrain tiles."""
    px = API.Player.X
    py = API.Player.Y
    candidates = {}

    statics = API.GetStaticsInArea(px - SEARCH_RADIUS, py - SEARCH_RADIUS, px + SEARCH_RADIUS, py + SEARCH_RADIUS)
    if statics:
        for s in statics:
            coord = (int(s.X), int(s.Y))
            if coord in unreachable_coords or is_vein_depleted(coord[0], coord[1]):
                continue

            is_mineable = getattr(s, "IsCave", False) or (s.Graphic in MINEABLE_GRAPHICS)
            if not is_mineable and s.Name:
                name = str(s.Name).lower()
                if any(k in name for k in ["ore", "deposit", "cave", "mountain", "stone", "boulder"]):
                    is_mineable = True

            if is_mineable and coord not in candidates:
                candidates[coord] = s

    # Scan terrain land tiles
    for dy in range(-SEARCH_RADIUS, SEARCH_RADIUS + 1):
        for dx in range(-SEARCH_RADIUS, SEARCH_RADIUS + 1):
            tx = px + dx
            ty = py + dy
            coord = (tx, ty)
            if coord in unreachable_coords or coord in candidates or is_vein_depleted(tx, ty):
                continue
            tile = API.GetTile(tx, ty)
            if tile and tile.Graphic in MINEABLE_GRAPHICS:
                candidates[coord] = tile

    dep_list = list(candidates.values())
    dep_list.sort(key=lambda d: chebyshev_distance(px, py, int(d.X), int(d.Y)))
    return dep_list


def navigate_to_deposit(deposit, spot_index: int = 1, total_spots: int = 1) -> bool:
    tx = int(deposit.X)
    ty = int(deposit.Y)

    if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
        return True

    stand_tile = find_mineable_stand_tile(tx, ty)
    if not stand_tile:
        unreachable_coords.add((tx, ty))
        return False

    sx, sy = stand_tile
    if total_spots > 1:
        update_status(f"Moving to deposit {spot_index}/{total_spots} ({sx}, {sy})")
    else:
        update_status(f"Moving to deposit ({sx}, {sy})")
    API.Pathfind(sx, sy, distance=0, run=True)

    elapsed = 0.0
    while API.Pathfinding() and not API.StopRequested and not is_stopped:
        if not check_ui_events():
            API.CancelPathfinding()
            return False
        API.Pause(0.2)
        elapsed += 0.2
        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
            API.CancelPathfinding()
            return True
        if elapsed >= PATHFIND_TIMEOUT:
            API.CancelPathfinding()
            unreachable_coords.add((tx, ty))
            return False

    return chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2


def mine_deposit(deposit, spot_index: int = 1, total_spots: int = 1) -> None:
    """Mines a single deposit continuously until it is depleted."""
    global veins_mined, total_ores

    tx = int(deposit.X)
    ty = int(deposit.Y)
    tz = int(getattr(deposit, "Z", 0))
    tg = int(getattr(deposit, "Graphic", 0)) if getattr(deposit, "Graphic", None) else 0

    # A tile is static if it has IsCave, is ApiStatic, or has graphic >= 0x4000
    is_static = hasattr(deposit, "IsCave") or getattr(deposit, "__class__", "") == "ApiStatic" or tg >= 0x4000

    veins_mined += 1
    swing = 0

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        if is_overburdened():
            update_status("Overweight")
            API.SysMsg("Weight limit reached! Pausing.")
            break

        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) > 2:
            break

        tool = get_equipped_mining_tool()
        if not tool:
            switch_to_mining()
            tool = get_equipped_mining_tool() or get_mining_tool()
            if not tool:
                update_status("No tool")
                API.SysMsg("Out of mining tools! Stopping.")
                return

        swing += 1
        if total_spots > 1:
            update_status(f"Mining {spot_index}/{total_spots} ({tx}, {ty}) #{swing}")
        else:
            update_status(f"Mining ({tx}, {ty}) #{swing}")

        # Attempt to get target cursor
        target_ready = False
        for attempt in range(3):
            if API.StopRequested or is_stopped:
                return

            API.ClearJournal()
            if API.HasTarget():
                API.CancelTarget()
                API.Pause(0.2)

            API.UseObject(tool)
            if API.WaitForTarget(timeout=2.0):
                target_ready = True
                break

            entries = API.GetJournalEntries(2.0)
            j_text = [str(e.Text).lower() for e in entries] if entries else []
            if any("must wait" in t or "wait to perform" in t for t in j_text) or API.InJournal("must wait"):
                update_status(f"Action delay ({attempt + 1}/3)...")
                API.Pause(1.2)
            else:
                API.Pause(0.5)

        if not target_ready:
            break

        before_ore = get_backpack_ore_count()

        # Send target with fallback mechanisms based on Static vs Land tile
        dx = tx - API.Player.X
        dy = ty - API.Player.Y
        target_accepted = False

        if is_static:
            # Static tile targeting
            API.Target(tx, ty, tz, tg)
            API.Pause(0.15)
            if not API.HasTarget():
                target_accepted = True
            else:
                API.TargetTileRel(dx, dy, tg)
                API.Pause(0.15)
                if not API.HasTarget():
                    target_accepted = True
                else:
                    API.TargetRel(dx, dy, tilesOnly=True)
                    API.Pause(0.15)
                    if not API.HasTarget():
                        target_accepted = True
        else:
            # Land tile targeting (mountain terrain, rock slopes, cave floor)
            API.TargetLandRel(dx, dy)
            API.Pause(0.15)
            if not API.HasTarget():
                target_accepted = True
            else:
                API.Target(tx, ty, tz)
                API.Pause(0.15)
                if not API.HasTarget():
                    target_accepted = True
                else:
                    API.TargetRel(dx, dy, tilesOnly=False)
                    API.Pause(0.15)
                    if not API.HasTarget():
                        target_accepted = True

        if not target_accepted and API.HasTarget():
            debug_msg(f"Target at ({tx}, {ty}) rel=({dx}, {dy}) not accepted, skipping deposit.")
            API.CancelTarget()
            break

        API.Pause(SWING_DELAY)
        update_stats()

        # Track ores gained
        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        after_ore = get_backpack_ore_count()
        delta = max(0, after_ore - before_ore)
        if delta > 0:
            total_ores += delta
        elif any("dig some" in t for t in recent_text) or API.InJournal("dig some"):
            total_ores += 1

        # Check tool broken
        if any(any(kw in t for kw in TOOL_BROKEN_KEYWORDS) for t in recent_text):
            API.SysMsg("Tool broke during mining.")
            tool = get_mining_tool()
            if not tool:
                update_status("No tool")
                API.SysMsg("Out of mining tools! Stopping.")
                return

        # Check depletion
        depleted = False
        for kw in MINING_DEPLETED_KEYWORDS:
            if any(kw in t for t in recent_text) or API.InJournal(kw):
                debug_msg(f"Deposit depleted: '{kw}'")
                depleted = True
                break

        if depleted:
            mark_vein_depleted(tx, ty)
            break


# ==============================================================================
# Lumberjacking Engine
# ==============================================================================

def find_nearby_trees():
    """Scans for nearby static trees within SEARCH_RADIUS."""
    px = API.Player.X
    py = API.Player.Y
    statics = API.GetStaticsInArea(px - SEARCH_RADIUS, py - SEARCH_RADIUS, px + SEARCH_RADIUS, py + SEARCH_RADIUS)
    if not statics:
        return []

    candidates = {}
    for s in statics:
        if not getattr(s, "IsTree", False):
            continue
        coord = (int(s.X), int(s.Y))
        if coord in depleted_trees:
            continue
        if coord not in candidates:
            candidates[coord] = s

    tree_list = list(candidates.values())
    tree_list.sort(key=lambda t: chebyshev_distance(px, py, int(t.X), int(t.Y)))
    return tree_list


def navigate_to_tree(tree, tree_index: int = 1, total_trees: int = 1) -> bool:
    tx = int(tree.X)
    ty = int(tree.Y)

    if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
        return True

    if total_trees > 1:
        update_status(f"Moving to tree {tree_index}/{total_trees} ({tx}, {ty})")
    else:
        update_status(f"Moving to tree ({tx}, {ty})")
    API.Pathfind(tx, ty, distance=1, run=True)

    elapsed = 0.0
    while API.Pathfinding() and not API.StopRequested and not is_stopped:
        if not check_ui_events():
            API.CancelPathfinding()
            return False
        API.Pause(0.2)
        elapsed += 0.2
        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
            API.CancelPathfinding()
            return True
        if elapsed >= PATHFIND_TIMEOUT:
            API.CancelPathfinding()
            depleted_trees.append((tx, ty))
            return False

    return chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2


def chop_tree(tree, tree_index: int = 1, total_trees: int = 1) -> None:
    """Chops a single tree continuously until it is depleted."""
    global trees_chopped, total_wood

    tx = int(tree.X)
    ty = int(tree.Y)
    tz = int(tree.Z)
    tg = int(tree.Graphic)

    trees_chopped += 1
    swing = 0

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        if is_overburdened():
            update_status("Overweight")
            API.SysMsg("Weight limit reached! Pausing.")
            break

        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) > 2:
            break

        axe = get_equipped_axe()
        if not axe:
            switch_to_lumberjack()
            axe = get_equipped_axe()
            if not axe:
                update_status("No axe")
                API.SysMsg("No axe found or equipped! Stopping.")
                return

        swing += 1
        if total_trees > 1:
            update_status(f"Chop {tree_index}/{total_trees} ({tx}, {ty}) #{swing}")
        else:
            update_status(f"Chopping ({tx}, {ty}) #{swing}")

        # Attempt to get target cursor
        target_ready = False
        for attempt in range(3):
            if API.StopRequested or is_stopped:
                return

            API.ClearJournal()
            if API.HasTarget():
                API.CancelTarget()
                API.Pause(0.2)

            API.UseObject(axe)
            if API.WaitForTarget(timeout=2.0):
                target_ready = True
                break

            entries = API.GetJournalEntries(2.0)
            j_text = [str(e.Text).lower() for e in entries] if entries else []
            if any("must wait" in t or "wait to perform" in t for t in j_text) or API.InJournal("must wait"):
                update_status(f"Action delay ({attempt + 1}/3)...")
                API.Pause(1.2)
            else:
                API.Pause(0.5)

        if not target_ready:
            break

        before_wood = get_backpack_log_count()

        # Send target to tree static with fallbacks
        API.Target(tx, ty, tz, tg)
        API.Pause(0.15)
        if API.HasTarget():
            dx = tx - API.Player.X
            dy = ty - API.Player.Y
            API.TargetTileRel(dx, dy, tg)
            API.Pause(0.15)
            if API.HasTarget():
                API.TargetRel(dx, dy, tilesOnly=True)
                API.Pause(0.15)
                if API.HasTarget():
                    debug_msg(f"Target at tree ({tx}, {ty}) not accepted, skipping tree.")
                    API.CancelTarget()
                    break

        API.Pause(SWING_DELAY)
        update_stats()

        # Track wood gained
        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        after_wood = get_backpack_log_count()
        delta = max(0, after_wood - before_wood)
        if delta > 0:
            total_wood += delta
        elif any("chop some" in t or "put some wood" in t for t in recent_text) or API.InJournal("chop some"):
            total_wood += 1

        # Check depletion
        depleted = False
        for kw in CHOP_DEPLETED_KEYWORDS:
            if any(kw in t for t in recent_text) or API.InJournal(kw):
                debug_msg(f"Tree depleted: '{kw}'")
                depleted = True
                break

        if depleted:
            depleted_trees.append((tx, ty))
            break


# ==============================================================================
# Main Orchestration Loop
# ==============================================================================

def main():
    API.SysMsg("=== FesterUO Combined Miner & Lumberjack ===")

    # Initial check of tools
    mining_tool = get_mining_tool()
    axe = get_axe()

    if not mining_tool or not axe:
        API.SysMsg("Combined Harvest: Please carry both a pickaxe/shovel and an axe in hands or backpack!")
        return

    # Equip initial mining gear
    switch_to_mining(force=True)

    create_control_gump()
    update_stats()
    update_status("Started")
    API.SysMsg(f"Harvest engine started (Radius: {SEARCH_RADIUS} tiles, Ratio: {TREES_PER_MINING_SPOT} trees / {MINING_SPOTS_PER_CYCLE} mining spot).")

    mining_spots_done = 0
    trees_done = 0
    current_mode = "mine"

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        if is_overburdened():
            update_status("Overweight")
            API.SysMsg("Weight limit reached! Stopping harvest loop.")
            break

        if current_mode == "mine":
            # Switch gear if needed
            switch_to_mining()

            deposits = find_nearby_deposits()
            if deposits:
                target_dep = deposits[0]
                if navigate_to_deposit(target_dep, mining_spots_done + 1, MINING_SPOTS_PER_CYCLE):
                    mine_deposit(target_dep, mining_spots_done + 1, MINING_SPOTS_PER_CYCLE)
                    mining_spots_done += 1
                else:
                    debug_msg(f"Could not reach deposit at ({target_dep.X}, {target_dep.Y})")
                    mining_spots_done += 1
            else:
                debug_msg("No unvisited ore deposits found in radius.")
                # Advance phase if no deposits in range
                mining_spots_done = MINING_SPOTS_PER_CYCLE

            if mining_spots_done >= MINING_SPOTS_PER_CYCLE:
                mining_spots_done = 0
                trees_done = 0
                current_mode = "chop"
                switch_to_lumberjack(force=True)

        else:
            # Switch gear if needed
            switch_to_lumberjack()

            trees = find_nearby_trees()
            if trees:
                target_tree = trees[0]
                if navigate_to_tree(target_tree, trees_done + 1, TREES_PER_MINING_SPOT):
                    chop_tree(target_tree, trees_done + 1, TREES_PER_MINING_SPOT)
                    trees_done += 1
                else:
                    debug_msg(f"Could not reach tree at ({target_tree.X}, {target_tree.Y})")
                    trees_done += 1
            else:
                debug_msg("No unvisited static trees found in radius.")
                # Advance phase if no trees in range
                trees_done = TREES_PER_MINING_SPOT

            if trees_done >= TREES_PER_MINING_SPOT:
                trees_done = 0
                mining_spots_done = 0
                current_mode = "mine"
                switch_to_mining(force=True)

        API.Pause(0.5)

    dispose_gump()
    API.SysMsg("Combined Miner & Lumberjack finished.")


main()
