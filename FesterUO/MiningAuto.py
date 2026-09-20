"""
MiningAuto.py - Automated Roaming Mining Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Automates mining across caves, mountainsides, and ore deposits with an interactive control Gump:
    - Automatically loads the "Mining" dress profile at startup.
    - Scans for nearby mineable statics (cave floors, walls, rock outcroppings, boulders)
      and world ore deposits within SEARCH_RADIUS.
    - Filters deposits by the player's current Mining skill to only target deposits they can harvest.
    - Selects the nearest unvisited deposit and pathfinds to within mining reach (distance <= 2).
    - Repeatedly swings the equipped pickaxe or shovel until the deposit is depleted or tool breaks.
    - Remembers recent deposits to prevent revisiting depleted veins.
    - Tracks and displays:
        - Current mining activity status
        - Veins / deposits mined counter
        - Total ores mined counter
        - Live Mining skill (value and cap) with skill gain announcements
        - Player Strength and Dexterity stats with increase notifications
        - Interactive Pause / Resume and Stop controls.
    - Monitors player weight capacity and stops safely before becoming overburdened.

Usage:
    1. Equip a pickaxe or shovel (or carry spares in your backpack).
    2. Ensure you have the "Mining" dress profile configured in TazUO (optional).
    3. Stand near a cave, mountain ridge, or ore field.
    4. Start the script in TazUO.
    5. Monitor and control execution using the on-screen Gump.
"""

from collections import deque
import re
from typing import List, Tuple, Optional
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Enable verbose logging in the client console/journal
DEBUG: bool = False

# Delay in seconds between swings.
# FesterUO allows fast harvesting (1.0s). Set to 4.5s or 5.0s for standard UO shards.
SWING_DELAY: float = 1.0

# Dress configuration profile to load at startup (set to None or "" to disable)
DRESS_PROFILE: str = "Mining"

# Search radius in tiles around the player to locate ore deposits
SEARCH_RADIUS: int = 25

# Maximum number of recent deposits/vein tiles to remember and avoid revisiting
DEPOSIT_HISTORY_LIMIT: int = 250

# Radius in tiles to mark as depleted when a vein is exhausted (standard UO veins are 8x8 blocks)
VEIN_DEPLETION_RADIUS: int = 6

# Stop script if backpack weight is near capacity
MAX_WEIGHT_CHECK: bool = True
WEIGHT_BUFFER: int = 15  # Stop when Weight >= WeightMax - WEIGHT_BUFFER

# Maximum seconds allowed to pathfind to a deposit before skipping it
PATHFIND_TIMEOUT: float = 12.0

# Mining tool graphic IDs
PICKAXE_GRAPHIC: int = 0x0E86
SHOVEL_GRAPHICS: List[int] = [0x0F39, 0x0F3A]

# Ore item graphic IDs
ORE_GRAPHICS: List[int] = [
    0x19B7,  # Single small ore
    0x19B8,  # Medium ore pile
    0x19B9,  # Large ore pile
    0x19BA,  # Small ore pile
]

# Standard UO mining skill requirements by ore type
ORE_SKILL_REQUIREMENTS = {
    "valorite": 99.0,
    "verite": 95.0,
    "agapite": 90.0,
    "gold": 85.0,
    "golden": 85.0,
    "bronze": 80.0,
    "copper": 75.0,
    "shadow": 70.0,
    "shadow iron": 70.0,
    "dull copper": 65.0,
    "iron": 0.0,
}

# Standard UO mountain land and static tile IDs (from ServUO Mining engine)
SERVUO_MINEABLE_TILES: List[int] = [
    220, 221, 222, 223, 224, 225, 226, 227, 228, 229,
    230, 231, 236, 237, 238, 239, 240, 241, 242, 243,
    244, 245, 246, 247, 252, 253, 254, 255, 256, 257,
    258, 259, 260, 261, 262, 263, 268, 269, 270, 271,
    272, 273, 274, 275, 276, 277, 278, 279, 286, 287,
    288, 289, 290, 291, 292, 293, 294, 295, 296, 297,
    321, 322, 323, 324, 467, 468, 469, 470, 471, 472,
    473, 474, 476, 477, 478, 479, 480, 481, 482, 483,
    484, 485, 486, 487, 492, 493, 494, 495, 543, 544,
    545, 546, 547, 548, 549, 550, 551, 552, 553, 554,
    555, 556, 557, 558, 559, 560, 561, 562, 563, 564,
    565, 566, 567, 568, 569, 570, 571, 572, 573, 574,
    575, 576, 577, 578, 579, 581, 582, 583, 584, 585,
    586, 587, 588, 589, 590, 591, 592, 593, 594, 595,
    596, 597, 598, 599, 600, 601, 610, 611, 612, 613,
    1010, 1741, 1742, 1743, 1744, 1745, 1746, 1747, 1748, 1749,
    1750, 1751, 1752, 1753, 1754, 1755, 1756, 1757, 1771, 1772,
    1773, 1774, 1775, 1776, 1777, 1778, 1779, 1780, 1781, 1782,
    1783, 1784, 1785, 1786, 1787, 1788, 1789, 1790, 1801, 1802,
    1803, 1804, 1805, 1806, 1807, 1808, 1809, 1811, 1812, 1813,
    1814, 1815, 1816, 1817, 1818, 1819, 1820, 1821, 1822, 1823,
    1824, 1831, 1832, 1833, 1834, 1835, 1836, 1837, 1838, 1839,
    1840, 1841, 1842, 1843, 1844, 1845, 1846, 1847, 1848, 1849,
    1850, 1851, 1852, 1853, 1854, 1861, 1862, 1863, 1864, 1865,
    1866, 1867, 1868, 1869, 1870, 1871, 1872, 1873, 1874, 1875,
    1876, 1877, 1878, 1879, 1880, 1881, 1882, 1883, 1884, 1981,
    1982, 1983, 1984, 1985, 1986, 1987, 1988, 1989, 1990, 1991,
    1992, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2001,
    2002, 2003, 2004, 2028, 2029, 2030, 2031, 2032, 2033, 2100,
    2101, 2102, 2103, 2104, 2105,
    0x053B, 0x053C, 0x053D, 0x053E, 0x053F, 0x0540, 0x0541, 0x0542, 0x0543, 0x0544,
    0x0545, 0x0546, 0x0547, 0x0548, 0x0549, 0x054A, 0x054B, 0x054C, 0x054D, 0x054E,
    0x054F, 0x0551, 0x0552, 0x0553, 0x056A,
    0x453B, 0x453C, 0x453D, 0x453E, 0x453F, 0x4540, 0x4541,
    0x4542, 0x4543, 0x4544, 0x4545, 0x4546, 0x4547, 0x4548,
    0x4549, 0x454A, 0x454B, 0x454C, 0x454D, 0x454E, 0x454F
]

BOULDER_GRAPHICS: List[int] = [
    0x0E56, 0x0E57, 0x0E58, 0x0E59, 0x0E5A, 0x0E5B, 0x0E5C, 0x0E5D, 0x0E5E, 0x0E5F,
    0x1363, 0x1364, 0x1365, 0x1366, 0x1367, 0x1368, 0x1369, 0x136A, 0x136B, 0x136C, 0x136D
]

MINEABLE_GRAPHICS = set(SERVUO_MINEABLE_TILES + BOULDER_GRAPHICS)

# Journal keywords indicating an ore deposit has been exhausted or cannot be mined (matched case-insensitively)
DEPLETED_KEYWORDS: List[str] = [
    "no metal here to mine",
    "not enough metal here",
    "no ore here to mine",
    "not enough ore here",
    "nothing here to mine",
    "cannot see that",
    "can't reach",
    "too far away",
    "can't mine that",
    "cannot mine that",
    "can't mine there",
    "target cannot be seen",
]

# Journal keywords indicating a tool broke (matched case-insensitively)
TOOL_BROKEN_KEYWORDS: List[str] = [
    "worn out your tool",
    "destroyed the item : pickaxe",
    "destroyed the item : shovel",
    "tool has broken",
]

# ==============================================================================
# Global Gump & State Management
# ==============================================================================

gump = None
lbl_status = None
lbl_deposits = None
lbl_ores = None
lbl_skill = None
lbl_stats = None
btn_pause = None
btn_stop = None

is_paused: bool = False
is_stopped: bool = False
deposits_mined_count: int = 0
ores_mined_count: int = 0

last_skill: Optional[float] = None
last_str: Optional[int] = None
last_dex: Optional[int] = None

# FIFO history tracking depleted vein centers (x, y)
depleted_veins: deque = deque(maxlen=DEPOSIT_HISTORY_LIMIT)
# FIFO history tracking unreachable coordinates
unreachable_coords: deque = deque(maxlen=200)


def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def is_vein_depleted(tx: int, ty: int) -> bool:
    """Checks if (tx, ty) falls within the depletion radius of any recently depleted vein."""
    for vx, vy in depleted_veins:
        if chebyshev_distance(tx, ty, vx, vy) <= VEIN_DEPLETION_RADIUS:
            return True
    return False


def mark_vein_depleted(center_x: int, center_y: int) -> None:
    """Marks a vein center coordinate as depleted to avoid revisiting any tiles in this vein."""
    coord = (center_x, center_y)
    if coord not in depleted_veins:
        depleted_veins.append(coord)
    debug_msg(f"Marked vein at {coord} as depleted (Total depleted veins tracked: {len(depleted_veins)}).")


def update_status(text: str) -> None:
    """Updates the status display on the Gump and prints to debug if enabled."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"
    debug_msg(text)


def increment_deposits_mined() -> None:
    """Increments the deposits mined counter and updates the Gump label."""
    global deposits_mined_count, lbl_deposits
    deposits_mined_count += 1
    if lbl_deposits:
        lbl_deposits.Text = f"Veins Mined: {deposits_mined_count}"


def increment_ores_mined(amount: int = 1) -> None:
    """Increments the ores mined counter and updates the Gump label."""
    global ores_mined_count, lbl_ores
    ores_mined_count += amount
    if lbl_ores:
        lbl_ores.Text = f"Ores Mined: {ores_mined_count}"


def update_stats() -> None:
    """Updates Mining skill, Strength, and Dexterity on the Gump and announces increases."""
    global last_skill, last_str, last_dex, lbl_skill, lbl_stats

    # Update Mining skill
    skill_obj = API.GetSkill("Mining")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        lbl_skill.Text = f"Mining: {val:.1f} / {cap:.1f}"
        if last_skill is not None and val > last_skill:
            gain = val - last_skill
            API.SysMsg(f"Mining gained +{gain:.1f}! New skill: {val:.1f}")
        last_skill = val

    # Update STR and DEX
    cur_str = API.Player.Strength
    cur_dex = API.Player.Dexterity
    if lbl_stats and cur_str is not None and cur_dex is not None:
        lbl_stats.Text = f"STR: {cur_str} | DEX: {cur_dex}"
        if last_str is not None and cur_str > last_str:
            API.SysMsg(f"Strength increased to {cur_str}!")
        if last_dex is not None and cur_dex > last_dex:
            API.SysMsg(f"Dexterity increased to {cur_dex}!")
        last_str = cur_str
        last_dex = cur_dex


def on_pause_clicked() -> None:
    """Callback triggered when the Pause/Resume button is clicked."""
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Auto miner paused." if is_paused else "Auto miner resumed.")


def on_stop_clicked() -> None:
    """Callback triggered when the Stop button is clicked."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_gump_disposed() -> None:
    """Callback triggered if the Gump window is closed by right-click."""
    global is_stopped
    if not is_stopped and not API.StopRequested:
        is_stopped = True
        API.Stop()


def create_control_gump() -> None:
    """Initializes and renders the interactive FesterUO Auto Miner Gump."""
    global gump, lbl_status, lbl_deposits, lbl_ores, lbl_skill, lbl_stats, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 240, 170)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 240, 170)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Auto Miner", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 30)
    gump.Add(lbl_status)

    # Veins / deposits mined counter
    lbl_deposits = API.Gumps.CreateGumpLabel("Veins Mined: 0", 996)
    lbl_deposits.SetPos(10, 50)
    gump.Add(lbl_deposits)

    # Ores mined counter
    lbl_ores = API.Gumps.CreateGumpLabel("Ores Mined: 0", 996)
    lbl_ores.SetPos(10, 70)
    gump.Add(lbl_ores)

    # Mining skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Mining: --", 996)
    lbl_skill.SetPos(10, 90)
    gump.Add(lbl_skill)

    # Stats label
    lbl_stats = API.Gumps.CreateGumpLabel("STR: -- | DEX: --", 996)
    lbl_stats.SetPos(10, 110)
    gump.Add(lbl_stats)

    # Pause button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 70, 22)
    btn_pause.SetPos(15, 136)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 70, 22)
    btn_stop.SetPos(155, 136)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Handle gump right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely removes the Gump window from the screen."""
    global gump
    if gump and not gump.IsDisposed:
        gump.Dispose()


def check_ui_events() -> bool:
    """
    Processes Gump callbacks, updates stats, and handles pause states.
    Returns False if execution should stop, True to continue.
    """
    global is_paused, is_stopped
    API.ProcessCallbacks()
    update_stats()

    if is_stopped or API.StopRequested:
        return False

    # Check button clicks directly in case callbacks were batched
    if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
        on_stop_clicked()
        return False

    if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
        on_pause_clicked()

    # If paused, hold in loop while continuing to process UI events
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


# ==============================================================================
# Helper Functions: Equipment, Inventory & Target Filtering
# ==============================================================================

def on_stop() -> None:
    """Callback when script execution is stopped."""
    if API.Pathfinding():
        API.CancelPathfinding()
    dispose_gump()
    API.SysMsg("Auto miner stopped.")


API.OnStop(on_stop)


def get_mining_tool():
    """Finds an equipped pickaxe or shovel, or one in the backpack."""
    # Check equipped weapon layers
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item:
            g = item.Graphic
            name = str(item.Name).lower() if item.Name else ""
            if g == PICKAXE_GRAPHIC or g in SHOVEL_GRAPHICS or "pick" in name or "shovel" in name:
                return item

    # Check backpack for pickaxe
    pick = API.FindType(PICKAXE_GRAPHIC, API.Backpack)
    if pick:
        return pick

    # Check backpack for shovels
    for sg in SHOVEL_GRAPHICS:
        shovel = API.FindType(sg, API.Backpack)
        if shovel:
            return shovel

    # Fallback search by item name in backpack
    items = API.ItemsInContainer(API.Backpack)
    if items:
        for item in items:
            name = str(item.Name).lower() if item.Name else ""
            if "pick" in name or "shovel" in name:
                return item

    return None


def get_backpack_ore_count() -> int:
    """Returns the total count of ore in the player's backpack."""
    items = API.ItemsInContainer(API.Backpack)
    if not items:
        return 0

    total = 0
    for item in items:
        g = item.Graphic
        amt = item.Amount if item.Amount else 1
        name = str(item.Name).lower() if item.Name else ""
        if g in ORE_GRAPHICS or "ore" in name:
            total += amt

    return total


def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Calculates tile distance between two coordinates."""
    return max(abs(x1 - x2), abs(y1 - y2))


def is_overburdened() -> bool:
    """Checks if the player's weight has reached the safe threshold."""
    if not MAX_WEIGHT_CHECK:
        return False
    weight = API.Player.Weight
    weight_max = API.Player.WeightMax
    if weight is not None and weight_max is not None and weight_max > 0:
        return weight >= (weight_max - WEIGHT_BUFFER)
    return False


def get_deposit_skill_requirement(name: str) -> float:
    """Returns the minimum mining skill required to harvest the named deposit."""
    name_lower = name.lower()
    for metal, req in ORE_SKILL_REQUIREMENTS.items():
        if metal in name_lower:
            return req
    return 0.0


def can_mine_deposit(deposit, player_mining: float) -> bool:
    """Checks if the player's mining skill is sufficient for this deposit."""
    name = getattr(deposit, "Name", None) or ""
    req = get_deposit_skill_requirement(name)
    return player_mining >= req


def get_walkable_mining_stand(tx: int, ty: int) -> Optional[Tuple[int, int]]:
    """
    Finds a walkable position (grass, dirt, road, cave floor) within mining reach (distance <= 2)
    of the mountain tile (tx, ty).
    """
    px = API.Player.X
    py = API.Player.Y

    stand_candidates = []
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx == 0 and dy == 0:
                continue
            dist_to_mountain = max(abs(dx), abs(dy))
            if dist_to_mountain > 2:
                continue
            sx = tx + dx
            sy = ty + dy

            # Check if this stand tile is walkable
            tile = API.GetTile(sx, sy)
            if not tile or getattr(tile, "Impassible", False):
                continue

            # Check if there is an impassable static here
            statics = API.GetStaticsAt(sx, sy)
            if statics and any(getattr(s, "IsImpassible", False) for s in statics):
                continue

            dist_to_player = chebyshev_distance(px, py, sx, sy)
            stand_candidates.append((dist_to_player, (sx, sy)))

    if not stand_candidates:
        return None

    stand_candidates.sort(key=lambda item: item[0])
    return stand_candidates[0][1]


def find_nearby_deposits():
    """
    Scans the area around the player for mineable statics and ore nodes,
    excluding recently depleted veins and deposits requiring higher mining skill.
    Returns a sorted list of candidate deposits.
    """
    px = API.Player.X
    py = API.Player.Y

    skill_obj = API.GetSkill("Mining")
    player_skill = float(skill_obj.Value) if skill_obj else 0.0

    candidates = {}

    # 1. Scan statics (cave floors, cave walls, rock outcroppings, boulders)
    statics = API.GetStaticsInArea(
        px - SEARCH_RADIUS,
        py - SEARCH_RADIUS,
        px + SEARCH_RADIUS,
        py + SEARCH_RADIUS
    )

    if statics:
        for s in statics:
            coord = (int(s.X), int(s.Y))
            if coord in unreachable_coords or is_vein_depleted(coord[0], coord[1]):
                continue

            is_mineable = False
            if getattr(s, "IsCave", False):
                is_mineable = True
            elif s.Graphic in MINEABLE_GRAPHICS:
                is_mineable = True
            else:
                name = str(s.Name).lower() if s.Name else ""
                if any(k in name for k in ["ore", "deposit", "cave", "mountain", "stone", "boulder"]):
                    is_mineable = True

            if not is_mineable:
                continue

            if not can_mine_deposit(s, player_skill):
                debug_msg(f"Deposit at {coord} ({s.Name}) requires higher skill than {player_skill:.1f}, skipping.")
                continue

            if coord not in candidates:
                candidates[coord] = s

    # 2. Scan terrain land tiles (mountain slopes, rock faces, cave ground)
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

    # 3. Scan world ground items if any matching boulder/node graphics are nearby
    for bg_graphic in BOULDER_GRAPHICS:
        ground_items = API.FindTypeAll(bg_graphic, range=SEARCH_RADIUS)
        if ground_items:
            for item in ground_items:
                if item.Container:
                    continue
                coord = (int(item.X), int(item.Y))
                if coord in unreachable_coords or coord in candidates or is_vein_depleted(coord[0], coord[1]):
                    continue

                if not can_mine_deposit(item, player_skill):
                    debug_msg(f"Item deposit at {coord} requires higher skill than {player_skill:.1f}, skipping.")
                    continue

                candidates[coord] = item

    deposit_list = list(candidates.values())
    deposit_list.sort(key=lambda d: chebyshev_distance(px, py, int(d.X), int(d.Y)))
    return deposit_list


def navigate_to_deposit(deposit) -> bool:
    """
    Navigates the player to within mining reach (distance <= 2) of the deposit.
    Tries native pathfinding directly to the deposit with distance=1 then distance=2,
    and falls back to finding an adjacent walkable stand position.
    """
    tx = int(deposit.X)
    ty = int(deposit.Y)

    # Already adjacent / in reach
    if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
        return True

    update_status(f"Moving to ({tx}, {ty})")
    debug_msg(f"Pathfinding to deposit at ({tx}, {ty})")

    # Try native pathfinding directly to deposit within reach (distance 1 then distance 2)
    success = API.Pathfind(tx, ty, distance=1, run=True)
    if not success:
        success = API.Pathfind(tx, ty, distance=2, run=True)

    # Fallback: if direct pathfinding failed, try adjacent walkable stand position
    if not success:
        stand = get_walkable_mining_stand(tx, ty)
        if stand:
            sx, sy = stand
            debug_msg(f"Trying fallback pathfind to stand ({sx}, {sy})")
            success = API.Pathfind(sx, sy, distance=1, run=True)
            if not success:
                success = API.Pathfind(sx, sy, distance=0, run=True)

    if not success:
        return False

    elapsed = 0.0
    while API.Pathfinding() and not API.StopRequested and not is_stopped:
        if not check_ui_events():
            API.CancelPathfinding()
            return False

        API.Pause(0.2)
        elapsed += 0.2

        # Check if we arrived in mining reach early
        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
            API.CancelPathfinding()
            return True

        if elapsed >= PATHFIND_TIMEOUT:
            debug_msg(f"Pathfind to stand ({sx}, {sy}) timed out after {PATHFIND_TIMEOUT}s.")
            API.CancelPathfinding()
            return False

    return chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2


def mine_deposit(tool, deposit) -> None:
    """Mines the specified deposit until depleted, stopped, or weight is exceeded."""
    tx = int(deposit.X)
    ty = int(deposit.Y)
    tz = int(deposit.Z)
    tg = int(deposit.Graphic) if getattr(deposit, "Graphic", None) else 0

    # A tile is static if it has IsCave, is ApiStatic, or has graphic >= 0x4000
    is_static = hasattr(deposit, "IsCave") or getattr(deposit, "__class__", "") == "ApiStatic" or tg >= 0x4000

    swing = 0

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return

        if is_overburdened():
            update_status("Weight limit reached")
            API.SysMsg("Weight limit reached! Stopping miner.")
            return

        # Ensure player hasn't drifted out of reach
        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) > 2:
            debug_msg("Player moved out of reach.")
            break

        swing += 1
        update_status(f"Mining ({tx}, {ty}) #{swing}")

        before_ore = get_backpack_ore_count()
        API.ClearJournal()

        if API.HasTarget():
            API.CancelTarget()
            API.Pause(0.2)

        API.UseObject(tool)

        if not API.WaitForTarget(timeout=5):
            debug_msg(f"Swing #{swing}: Target cursor timed out.")
            break

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
            debug_msg(f"Target at ({tx}, {ty}) rel=({dx}, {dy}) not accepted, skipping tile.")
            API.CancelTarget()
            break

        API.Pause(SWING_DELAY)
        update_stats()

        # Tally ore gained (checking backpack delta and instant smelting messages)
        found_smelt = False
        entries = API.GetJournalEntries(3.0)
        if entries:
            for entry in entries:
                t = getattr(entry, "Text", "")
                if "smelt" in t.lower() and "ingot" in t.lower():
                    m = re.search(r"(\d+)\s+ingots?", t, re.IGNORECASE)
                    if m:
                        count = int(m.group(1))
                        increment_ores_mined(count)
                        found_smelt = True
                        break

        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        if not found_smelt:
            after_ore = get_backpack_ore_count()
            delta = max(0, after_ore - before_ore)
            if delta > 0:
                increment_ores_mined(delta)
            elif any("dig some" in t for t in recent_text) or API.InJournal("dig some"):
                increment_ores_mined(1)

        # Check if mining tool broke
        tool_broken = False
        for kw in TOOL_BROKEN_KEYWORDS:
            if any(kw in t for kw in recent_text) or API.InJournal(kw):
                API.SysMsg(f"Tool broke: '{kw}'")
                tool_broken = True
                break

        if tool_broken:
            tool = get_mining_tool()
            if not tool:
                update_status("No tool available")
                API.SysMsg("Out of mining tools! Stopping.")
                return

        # Check depletion journal messages
        depleted = False
        for kw in DEPLETED_KEYWORDS:
            if any(kw in t for kw in recent_text) or API.InJournal(kw):
                API.SysMsg(f"Deposit depleted: '{kw}'")
                depleted = True
                break

        if depleted:
            mark_vein_depleted(tx, ty)
            break


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    if DRESS_PROFILE:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE}'...")
        API.Dress(DRESS_PROFILE)
        API.Pause(1.0)

    tool = get_mining_tool()
    if not tool:
        API.SysMsg("No pickaxe or shovel found! Equip or carry a tool to start.")
        return

    # Render on-screen control Gump
    create_control_gump()
    update_stats()

    depleted_veins.clear()
    unreachable_coords.clear()

    update_status("Started")
    API.SysMsg(f"Auto miner started (Radius: {SEARCH_RADIUS}, History: {DEPOSIT_HISTORY_LIMIT} veins).")

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Check weight before searching for next deposit
        if is_overburdened():
            update_status("Weight limit reached")
            API.SysMsg("Weight limit reached! Stopping miner.")
            break

        # Re-verify tool
        tool = get_mining_tool()
        if not tool:
            update_status("No tool available")
            API.SysMsg("Pickaxe/shovel missing or broken! Stopping.")
            break

        # Find available deposits excluding recently visited
        update_status("Searching deposits...")
        candidates = find_nearby_deposits()
        if not candidates:
            update_status("No deposits found")
            API.SysMsg(f"No more harvestable ore deposits found within {SEARCH_RADIUS} tiles. Done.")
            break

        target_deposit = None
        for candidate in candidates:
            if not check_ui_events():
                break

            if navigate_to_deposit(candidate):
                target_deposit = candidate
                break
            else:
                # Unreachable deposit, mark visited so we skip it for now
                coord = (int(candidate.X), int(candidate.Y))
                unreachable_coords.append(coord)
                debug_msg(f"Deposit at {coord} unreachable, skipping.")

        if not target_deposit:
            update_status("No reachable deposits")
            API.SysMsg("Could not pathfind to any nearby ore deposits. Done.")
            break

        # Mine the reached deposit
        mine_deposit(tool, target_deposit)

        if is_overburdened() or is_stopped or API.StopRequested:
            break

        # Increment deposit counter and record entire vein in history
        increment_deposits_mined()
        mark_vein_depleted(int(target_deposit.X), int(target_deposit.Y))

        API.Pause(0.5)

    update_status("Finished")
    API.SysMsg("Auto miner finished.")
    dispose_gump()


main()
