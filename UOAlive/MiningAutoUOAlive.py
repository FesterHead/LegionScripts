"""
MiningAutoUOAlive.py - Automated Roaming Mining Script for UOAlive

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)
Target Shard: UOAlive

Description:
    Fully automated roaming mining script designed for mountainsides, caves, and rock nodes:
    - Automatically loads and equips the configured "Miner" dress profile (or pickaxe/shovel).
    - Intelligent Spatial Scanning:
        * Scans within SEARCH_RADIUS (25 tiles) for cave floors/walls, mountain rock statics,
          boulders, and mountain land tiles.
        * Filters candidate deposits to match your player's current Mining skill tier.
        * Selects the nearest unvisited vein and navigates to within mining reach (distance <= 2)
          using intelligent walkable stand pathfinding.
    - Automated Pack Animal Offloading:
        * Automatically detects a nearby Pack Llama, Pack Horse, or Giant Beetle.
        * Offloads newly mined ore stacks directly into the pack animal's backpack.
    - Vein Memory & Loop Prevention:
        * Remembers the last 150 mined vein coordinates in a FIFO history queue with
          depletion radius tracking to avoid re-mining exhausted veins.
    - Weight & Tool Breakage Protection:
        * Monitors backpack weight and offloads to the pack pet before pausing.
        * Triggers an overhead warning and audible chime when full or when tools are missing.
    - Interactive Control Gump (330x165):
        * Displays Status, Veins Mined & Ore (Backpack + Pet totals),
          live Mining skill with gain announcements, STR / DEX / Weight / Pack Pet status.
        * Interactive Pause / Resume, Pack Pet (manual pet targeting / re-detection), and Stop buttons.

Usage:
    1. Ensure you have a pickaxe or shovel in your hands or backpack.
    2. (Recommended) Configure a "Miner" dress profile in TazUO.
    3. Bring along a Pack Llama, Pack Horse, or Giant Beetle.
    4. Stand near mountains, rock ridges, or inside a cave.
    5. Start the script in TazUO.
"""

from collections import deque
from typing import List, Optional, Set, Tuple
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Enable verbose logging in the client console/journal
DEBUG: bool = False

# Delay in seconds between harvesting swings. Fast shards like UOAlive support 1.0s.
SWING_DELAY: float = 1.0

# Dress configuration profile configured in TazUO (set to None or "" to disable)
DRESS_PROFILE: str = "Miner"

# Search radius in tiles around the player to locate candidate mining spots
SEARCH_RADIUS: int = 25

# Maximum number of recent veins to remember and avoid revisiting (FIFO queue)
VEIN_HISTORY_LIMIT: int = 150

# Radius in tiles to treat as depleted around a depleted mining spot
VEIN_DEPLETION_RADIUS: int = 2

# Backpack weight protection
MAX_WEIGHT_CHECK: bool = True
WEIGHT_BUFFER: int = 15  # Pause when Weight >= WeightMax - WEIGHT_BUFFER

# Maximum seconds allowed to pathfind to a deposit before skipping it
PATHFIND_TIMEOUT: float = 12.0

# Alert sound played when auto-pausing (0x1F8 = classic system notice chime)
ALERT_SOUND: int = 0x1F8

# Automatically offload mined ore to a nearby Pack Horse, Pack Llama, or Beetle
AUTO_PACK_ANIMAL_TRANSFER: bool = True
PACK_ANIMAL_MAX_DISTANCE: int = 3

# Safety limits for swings per vein to avoid indefinite loops
MAX_VEIN_SWINGS: int = 40
MAX_IDLE_SWINGS: int = 4

# ==============================================================================
# Graphics Definitions
# ==============================================================================

# Mining tools
PICKAXE_GRAPHIC: int = 0x0E86
SHOVEL_GRAPHICS: List[int] = [0x0F39, 0x0F3A]
MINING_TOOL_GRAPHICS: List[int] = [0x0E86, 0x0F39, 0x0F3A]

# Ore graphics (small, medium, large, small pile)
ORE_GRAPHICS: List[int] = [
    0x19B7, 0x19B8, 0x19B9, 0x19BA
]

# Pack animals (Pack Horse, Pack Llama, Giant Beetle)
PACK_ANIMAL_GRAPHICS: List[int] = [
    0x0123,  # Pack Horse
    0x0124,  # Pack Llama
    0x0317,  # Giant Beetle
]

# Standard UO mountain land and static tile IDs (ServUO engine)
SERVUO_MINEABLE_TILES: List[int] = [
    220, 221, 222, 223, 224, 225, 226, 227, 228, 229,
    230, 231, 236, 237, 238, 239, 240, 241, 242, 243,
    244, 245, 246, 247, 252, 253, 254, 255, 256, 257,
    258, 259, 260, 261, 262, 263, 268, 269, 270, 271,
    272, 273, 274, 275, 276, 277, 278, 279, 282, 283,
    284, 285, 286, 287, 288, 289, 290, 291, 292, 293,
    294, 295, 296, 297, 298, 299, 300, 301, 321, 322,
    323, 324, 467, 468, 469, 470, 471, 472, 473, 474,
    476, 477, 478, 479, 480, 481, 482, 483, 484, 485,
    486, 487, 492, 493, 494, 495, 543, 544, 545, 546,
    547, 548, 549, 550, 551, 552, 553, 554, 555, 556,
    557, 558, 559, 560, 561, 562, 563, 564, 565, 566,
    567, 568, 569, 570, 571, 572, 573, 574, 575, 576,
    577, 578, 579, 581, 582, 583, 584, 585, 586, 587,
    588, 589, 590, 591, 592, 593, 594, 595, 596, 597,
    598, 599, 600, 601, 610, 611, 612, 613, 1010,
    1741, 1742, 1743, 1744, 1745, 1746, 1747, 1748, 1749,
    1750, 1751, 1752, 1753, 1754, 1755, 1756, 1757, 1771,
    1772, 1773, 1774, 1775, 1776, 1777, 1778, 1779, 1780,
    1781, 1782, 1783, 1784, 1785, 1786, 1787, 1788, 1789,
    1790, 1801, 1802, 1803, 1804, 1805, 1806, 1807, 1808,
    1809, 1811, 1812, 1813, 1814, 1815, 1816, 1817, 1818,
    1819, 1820, 1821, 1822, 1823, 1824, 1831, 1832, 1833,
    1834, 1835, 1836, 1837, 1838, 1839, 1840, 1841, 1842,
    1843, 1844, 1845, 1846, 1847, 1848, 1849, 1850, 1851,
    1852, 1853, 1854, 1861, 1862, 1863, 1864, 1865, 1866,
    1867, 1868, 1869, 1870, 1871, 1872, 1873, 1874, 1875,
    1876, 1877, 1878, 1879, 1880, 1881, 1882, 1883, 1884,
    1981, 1982, 1983, 1984, 1985, 1986, 1987, 1988, 1989,
    1990, 1991, 1992, 1993, 1994, 1995, 1996, 1997, 1998,
    1999, 2000, 2001, 2002, 2003, 2004, 2028, 2029, 2030,
    2031, 2032, 2033, 2100, 2101, 2102, 2103, 2104, 2105,
    0x053B, 0x053C, 0x053D, 0x053E, 0x053F, 0x0540, 0x0541,
    0x0542, 0x0543, 0x0544, 0x0545, 0x0546, 0x0547, 0x0548,
    0x0549, 0x054A, 0x054B, 0x054C, 0x054D, 0x054E, 0x054F,
    0x0551, 0x0552, 0x0553, 0x056A,
    0x453B, 0x453C, 0x453D, 0x453E, 0x453F, 0x4540, 0x4541,
    0x4542, 0x4543, 0x4544, 0x4545, 0x4546, 0x4547, 0x4548,
    0x4549, 0x454A, 0x454B, 0x454C, 0x454D, 0x454E, 0x454F
]

BOULDER_GRAPHICS: List[int] = [
    0x0E56, 0x0E57, 0x0E58, 0x0E59, 0x0E5A, 0x0E5B, 0x0E5C, 0x0E5D, 0x0E5E, 0x0E5F,
    0x1363, 0x1364, 0x1365, 0x1366, 0x1367, 0x1368, 0x1369, 0x136A, 0x136B, 0x136C, 0x136D
]

MINEABLE_GRAPHICS: Set[int] = set(SERVUO_MINEABLE_TILES + BOULDER_GRAPHICS)

# Journal keywords indicating a mining vein is depleted
MINING_DEPLETED_KEYWORDS: List[str] = [
    "no metal here",
    "no ore here",
    "not enough metal",
    "not enough ore",
    "nothing here to mine",
    "cannot see that",
    "can't reach",
    "too far away",
    "can't mine that",
    "cannot mine that",
    "can't mine there",
    "target cannot be seen",
    "you have depleted",
    "someone has already",
    "try mining elsewhere",
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

# ==============================================================================
# Global Gump & State Management
# ==============================================================================

gump = None
lbl_status = None
lbl_veins = None
lbl_skill = None
lbl_stats = None
btn_pause = None
btn_pet = None
btn_stop = None

is_paused: bool = False
is_stopped: bool = False
veins_mined_count: int = 0
pack_animal_serial: Optional[int] = None
pack_container_serial: Optional[int] = None

# Depleted veins history queue
depleted_veins_queue: deque[Tuple[int, int]] = deque(maxlen=VEIN_HISTORY_LIMIT)
unreachable_coords: Set[Tuple[int, int]] = set()

last_mining_skill: Optional[float] = None
last_str: Optional[int] = None
last_dex: Optional[int] = None


def debug_msg(text: str) -> None:
    """Outputs debug message if DEBUG is enabled."""
    if DEBUG:
        API.SysMsg(f"[Miner] {text}", 88)


def update_status(text: str) -> None:
    """Updates the status display on the Gump and prints to debug if enabled."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"
    debug_msg(text)


def increment_veins_mined() -> None:
    """Increments vein counter and refreshes Gump stats."""
    global veins_mined_count
    veins_mined_count += 1
    update_stats()


def update_stats() -> None:
    """Refreshes Mining skill, STR, DEX, Weight, Vein & Ore counts on the Gump."""
    global last_mining_skill, last_str, last_dex, lbl_veins, lbl_skill, lbl_stats

    # 1. Update Veins & Ore count display (backpack + pack pet)
    if lbl_veins:
        bp_o = get_backpack_ore_count()
        pet_o = get_pack_animal_ore_count()
        if pet_o > 0 or pack_animal_serial:
            lbl_veins.Text = f"Veins: {veins_mined_count} | Ore: {bp_o} (Pet: {pet_o})"
        else:
            lbl_veins.Text = f"Veins: {veins_mined_count} | Ore: {bp_o}"

    # 2. Update Mining skill
    skill_obj = API.GetSkill("Mining")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        lbl_skill.Text = f"Mining: {val:.1f} / {cap:.1f}"
        if last_mining_skill is not None and val > last_mining_skill:
            gain = val - last_mining_skill
            API.SysMsg(f"Mining gained +{gain:.1f}! New skill: {val:.1f}", 68)
        last_mining_skill = val

    # 3. Update STR, DEX, Backpack Weight, and Pack Pet indicator
    cur_str = API.Player.Strength
    cur_dex = API.Player.Dexterity
    cur_wt = API.Player.Weight
    max_wt = API.Player.WeightMax

    if lbl_stats and cur_str is not None and cur_dex is not None:
        wt_str = f"{cur_wt}/{max_wt}" if cur_wt is not None and max_wt is not None else "--/--"
        pet_str = ""
        animal = find_nearby_pack_animal(max_distance=PACK_ANIMAL_MAX_DISTANCE)
        if animal:
            pname = getattr(animal, "Name", "Pet") or "Pet"
            pet_str = f" | {pname[:12]}"
        lbl_stats.Text = f"STR: {cur_str} | DEX: {cur_dex} | Wt: {wt_str}{pet_str}"

        if last_str is not None and cur_str > last_str:
            API.SysMsg(f"Strength increased to {cur_str}!", 68)
        if last_dex is not None and cur_dex > last_dex:
            API.SysMsg(f"Dexterity increased to {cur_dex}!", 68)
        last_str = cur_str
        last_dex = cur_dex


def trigger_overweight_pause() -> None:
    """Auto-pauses the script when the player is full."""
    global is_paused, btn_pause
    if not is_paused:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused: Too Full!")
        API.HeadMsg("TOO FULL! SCRIPT PAUSED", API.Player, 32)
        API.SysMsg("Weight capacity reached! Auto-paused for resource unloading.", 32)
        if ALERT_SOUND > 0:
            API.PlaySound(ALERT_SOUND)


def trigger_tool_missing_pause() -> None:
    """Auto-pauses the script when pickaxe or shovel is missing or broken."""
    global is_paused, btn_pause
    if not is_paused:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused: No Tool!")
        API.HeadMsg("NO PICKAXE! SCRIPT PAUSED", API.Player, 32)
        API.SysMsg("Pickaxe/shovel missing or broken! Auto-paused so you can equip a replacement.", 32)
        if ALERT_SOUND > 0:
            API.PlaySound(ALERT_SOUND)


def on_pause_clicked() -> None:
    """Callback triggered when the Pause/Resume button is clicked on the Gump."""
    global is_paused, btn_pause
    if is_paused:
        transfer_ore_to_pack_animal()
        if is_overburdened():
            API.SysMsg("Still too full! Please offload ore or lighten your pack before resuming.", 32)
            API.HeadMsg("STILL OVERWEIGHT!", API.Player, 32)
            return

        if not get_mining_tool():
            API.SysMsg("No pickaxe/shovel found in hands or backpack! Please equip one first.", 32)
            API.HeadMsg("NO TOOL FOUND!", API.Player, 32)
            return

        is_paused = False
        if btn_pause:
            btn_pause.SetText("Pause")
        update_status("Resuming...")
        API.SysMsg("Auto miner resumed.")
    else:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused")
        API.SysMsg("Auto miner paused.")


def on_pack_pet_clicked() -> None:
    """Allows player to manually select their Pack Horse, Pack Llama, or Giant Beetle."""
    global pack_animal_serial, pack_container_serial
    API.SysMsg("Target your Pack Horse, Pack Llama, or Beetle (or press ESC to auto-detect)...")
    target_serial = API.RequestTarget(timeout=10.0)
    if target_serial and target_serial != API.Player.Serial:
        mob = API.FindMobile(target_serial)
        if mob:
            pack_animal_serial = target_serial
            pack_container_serial = None
            name = getattr(mob, "Name", "Pack Pet") or "Pack Pet"
            API.SysMsg(f"Pack animal set to {name} [0x{target_serial:X}].", 68)
            container = get_pack_animal_container(mob, open_if_needed=True)
            if container:
                pack_container_serial = getattr(container, "Serial", container)
            transfer_ore_to_pack_animal()
            update_stats()
            return

    # Fallback: scan and auto-detect nearest pack animal
    animal = find_nearby_pack_animal(max_distance=4)
    if animal:
        name = getattr(animal, "Name", "Pack Pet") or "Pack Pet"
        API.SysMsg(f"Auto-detected pack animal: {name} [0x{animal.Serial:X}].", 68)
        container = get_pack_animal_container(animal, open_if_needed=True)
        if container:
            pack_container_serial = getattr(container, "Serial", container)
        transfer_ore_to_pack_animal()
    else:
        API.SysMsg("No pack animal detected within reach.", 53)
    update_stats()


def on_stop_clicked() -> None:
    """Callback triggered when the Stop button is clicked on the Gump."""
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


def create_control_gump():
    """Initializes and renders the interactive UOAlive Auto Miner Gump."""
    global gump, lbl_status, lbl_veins, lbl_skill, lbl_stats, btn_pause, btn_pet, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 330, 165)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 330, 165)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("UOAlive Auto Miner", 53)
    title.SetPos(12, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(12, 30)
    gump.Add(lbl_status)

    # Veins mined and ore counter
    lbl_veins = API.Gumps.CreateGumpLabel("Veins: 0 | Ore: 0", 996)
    lbl_veins.SetPos(12, 52)
    gump.Add(lbl_veins)

    # Skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Mining: --", 996)
    lbl_skill.SetPos(12, 74)
    gump.Add(lbl_skill)

    # Stats and Weight label
    lbl_stats = API.Gumps.CreateGumpLabel("STR: -- | DEX: -- | Wt: --/--", 996)
    lbl_stats.SetPos(12, 96)
    gump.Add(lbl_stats)

    # Pause / Resume button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 85, 24)
    btn_pause.SetPos(15, 126)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Pack Pet button
    btn_pet = API.Gumps.CreateSimpleButton("Pack Pet", 95, 24)
    btn_pet.SetPos(115, 126)
    API.Gumps.AddControlOnClick(btn_pet, on_pack_pet_clicked)
    gump.Add(btn_pet)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 85, 24)
    btn_stop.SetPos(225, 126)
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
    """Processes Gump callbacks, updates stats, and handles pause states."""
    global is_paused, is_stopped
    API.ProcessCallbacks()
    update_stats()

    if is_stopped or API.StopRequested:
        return False

    if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
        on_stop_clicked()
        return False

    if btn_pet and getattr(btn_pet, "HasBeenClicked", lambda: False)():
        on_pack_pet_clicked()

    if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
        on_pause_clicked()

    while is_paused and not API.StopRequested and not is_stopped:
        if API.Pathfinding():
            API.CancelPathfinding()
        API.Pause(0.2)
        API.ProcessCallbacks()
        update_stats()
        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_pet and getattr(btn_pet, "HasBeenClicked", lambda: False)():
            on_pack_pet_clicked()
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            on_pause_clicked()
            if not is_paused:
                break

    return not is_stopped and not API.StopRequested


# ==============================================================================
# Equipment & Tool Management
# ==============================================================================

def clear_hands() -> bool:
    """
    Un-equips weapons or shields in both hands to the backpack.
    Prevents 'You can only wield one weapon at a time' server errors.
    """
    cleared = False
    if API.ClearRightHand():
        cleared = True
    if API.ClearLeftHand():
        cleared = True
    if cleared:
        API.Pause(0.6)
    return cleared


def get_equipped_mining_tool():
    """Checks equipped weapon layers for an equipped pickaxe or shovel."""
    for layer in ["TwoHanded", "OneHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in MINING_TOOL_GRAPHICS:
            return item
    return None


def get_mining_tool():
    """Checks equipped layers and backpack for a pickaxe or shovel, equipping if needed."""
    tool = get_equipped_mining_tool()
    if tool:
        return tool

    clear_hands()

    for graphic in MINING_TOOL_GRAPHICS:
        item = API.FindType(graphic, API.Backpack)
        if item:
            API.EquipItem(item.Serial)
            API.Pause(0.6)
            tool = get_equipped_mining_tool()
            if tool:
                return tool
            return item
    return None


# ==============================================================================
# Inventory & Pack Animal Helpers
# ==============================================================================

def get_all_backpack_items() -> List:
    """Safely retrieves all items inside the player's backpack using recursive=False."""
    all_items = []
    to_scan = [API.Backpack]
    visited = set()

    while to_scan:
        container_id = to_scan.pop(0)
        if not container_id or container_id in visited:
            continue
        visited.add(container_id)

        items = API.ItemsInContainer(container_id, recursive=False)
        if items is None:
            items = API.ItemsInContainer(container_id)
        if items:
            for item in items:
                all_items.append(item)
                graphic = getattr(item, "Graphic", 0)
                if getattr(item, "IsContainer", False) or graphic in [
                    0x0E75, 0x0E76, 0x0E79, 0x0E7D, 0x0E7E, 0x0E80, 0x09B0, 0x0E40, 0x0E41, 0x0E42, 0x0E43
                ]:
                    sub_serial = getattr(item, "Serial", None)
                    if sub_serial and sub_serial not in visited:
                        to_scan.append(sub_serial)

    return all_items


def get_backpack_ore_count() -> int:
    """Counts total ore currently inside the player's backpack."""
    total = 0
    items = get_all_backpack_items()
    for item in items:
        graphic = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()
        if graphic in ORE_GRAPHICS or ("ore" in name and "scoreboard" not in name):
            total += getattr(item, "Amount", 1) or 1
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


def find_nearby_pack_animal(max_distance: int = PACK_ANIMAL_MAX_DISTANCE):
    """Finds a nearby Pack Horse, Pack Llama, or Giant Beetle."""
    global pack_animal_serial

    if pack_animal_serial:
        mob = API.FindMobile(pack_animal_serial)
        if mob and not getattr(mob, "IsDead", False):
            if chebyshev_distance(API.Player.X, API.Player.Y, mob.X, mob.Y) <= max_distance:
                return mob

    mobiles = API.GetAllMobiles()
    if not mobiles:
        return None

    px = API.Player.X
    py = API.Player.Y
    closest_mob = None
    min_dist = max_distance + 1

    for mob in mobiles:
        if not mob or mob.Serial == API.Player.Serial or getattr(mob, "IsDead", False):
            continue
        graphic = getattr(mob, "Graphic", 0)
        if graphic in PACK_ANIMAL_GRAPHICS:
            dist = chebyshev_distance(px, py, mob.X, mob.Y)
            if dist <= max_distance and dist < min_dist:
                min_dist = dist
                closest_mob = mob

    if closest_mob:
        pack_animal_serial = closest_mob.Serial
        return closest_mob

    return None


def get_pack_animal_container(animal, open_if_needed: bool = False):
    """Retrieves the backpack/container item for the pack animal."""
    global pack_container_serial
    if not animal:
        return None

    animal_serial = getattr(animal, "Serial", animal)

    if pack_container_serial:
        cont = API.FindItem(pack_container_serial)
        if cont:
            return cont

    if hasattr(animal, "Backpack") and animal.Backpack:
        pack_container_serial = getattr(animal.Backpack, "Serial", animal.Backpack)
        return animal.Backpack

    layer_item = API.FindLayer("Backpack", animal_serial)
    if layer_item:
        pack_container_serial = getattr(layer_item, "Serial", layer_item)
        return layer_item

    if open_if_needed:
        API.UseObject(animal_serial)
        API.Pause(0.5)

        if hasattr(animal, "Backpack") and animal.Backpack:
            pack_container_serial = getattr(animal.Backpack, "Serial", animal.Backpack)
            return animal.Backpack

        layer_item = API.FindLayer("Backpack", animal_serial)
        if layer_item:
            pack_container_serial = getattr(layer_item, "Serial", layer_item)
            return layer_item

    return None


def get_pack_animal_ore_count() -> int:
    """Counts total ore currently inside the pack animal's backpack."""
    try:
        animal = find_nearby_pack_animal(PACK_ANIMAL_MAX_DISTANCE)
        if not animal:
            return 0

        container = get_pack_animal_container(animal, open_if_needed=False)
        if not container:
            return 0

        cont_serial = getattr(container, "Serial", container)
        items = API.ItemsInContainer(cont_serial, recursive=False)
        if not items:
            return 0

        total = 0
        for item in items:
            graphic = getattr(item, "Graphic", 0)
            name = str(getattr(item, "Name", "") or "").lower()
            if graphic in ORE_GRAPHICS or ("ore" in name and "scoreboard" not in name):
                total += getattr(item, "Amount", 1) or 1
        return total
    except Exception:
        return 0


def transfer_ore_to_pack_animal() -> int:
    """Transfers ore stacks from player backpack to the pack animal."""
    if not AUTO_PACK_ANIMAL_TRANSFER:
        return 0

    animal = find_nearby_pack_animal(PACK_ANIMAL_MAX_DISTANCE)
    if not animal:
        return 0

    container = get_pack_animal_container(animal, open_if_needed=True)
    if not container:
        return 0

    dest_serial = getattr(container, "Serial", container)
    animal_name = getattr(animal, "Name", "Pack Pet") or "Pack Pet"

    items = get_all_backpack_items()
    ore_serials: List[int] = []
    for item in items:
        graphic = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()
        if graphic in ORE_GRAPHICS or ("ore" in name and "scoreboard" not in name):
            serial = getattr(item, "Serial", None)
            if serial and serial not in ore_serials:
                ore_serials.append(serial)

    if not ore_serials:
        return 0

    transferred = 0
    for serial in ore_serials:
        if API.StopRequested or is_stopped:
            break

        if chebyshev_distance(API.Player.X, API.Player.Y, animal.X, animal.Y) > PACK_ANIMAL_MAX_DISTANCE:
            debug_msg("Pack animal moved out of range during ore transfer.")
            break

        API.MoveItem(serial, dest_serial, 0)
        API.Pause(0.6)
        transferred += 1

    if transferred > 0:
        API.SysMsg(f"Transferred {transferred} ore stack(s) to {animal_name}.", 68)
        update_stats()

    return transferred


# ==============================================================================
# Mining Detection & Navigation Logic
# ==============================================================================

def is_vein_depleted(x: int, y: int) -> bool:
    """Checks whether the coordinate was recently mined within depletion radius."""
    for dx, dy in depleted_veins_queue:
        if chebyshev_distance(x, y, dx, dy) <= VEIN_DEPLETION_RADIUS:
            return True
    return False


def can_mine_deposit(deposit, player_mining: float) -> bool:
    """Checks if the player's mining skill is sufficient for this deposit."""
    name = str(getattr(deposit, "Name", "") or "").lower()
    for ore_name, req in ORE_SKILL_REQUIREMENTS.items():
        if ore_name in name:
            return player_mining >= req
    return True


def get_walkable_mining_stand(tx: int, ty: int) -> Optional[Tuple[int, int]]:
    """
    Finds a walkable position (grass, dirt, road, cave floor) within mining reach (distance <= 2)
    of the mountain or rock tile (tx, ty).
    """
    px = API.Player.X
    py = API.Player.Y

    stand_candidates = []
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx == 0 and dy == 0:
                continue
            dist_to_rock = max(abs(dx), abs(dy))
            if dist_to_rock > 2:
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
    Scans the area around the player for mineable statics and land tiles,
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
                name = str(getattr(s, "Name", "") or "").lower()
                if any(k in name for k in ["ore", "deposit", "cave", "mountain", "stone", "boulder", "rock"]):
                    is_mineable = True

            if not is_mineable:
                continue

            if not can_mine_deposit(s, player_skill):
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
                    continue

                candidates[coord] = item

    deposit_list = list(candidates.values())
    deposit_list.sort(key=lambda d: chebyshev_distance(px, py, int(d.X), int(d.Y)))
    return deposit_list


def navigate_to_deposit(deposit) -> bool:
    """
    Navigates the player to within mining reach (distance <= 2) of the deposit.
    Tries native pathfinding with distance=1 then distance=2, falling back to
    an adjacent walkable stand position.
    """
    tx = int(deposit.X)
    ty = int(deposit.Y)

    # Already within reach
    if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
        return True

    update_status(f"Moving to ({tx}, {ty})")
    debug_msg(f"Pathfinding to deposit at ({tx}, {ty})")

    success = API.Pathfind(tx, ty, distance=1, run=True)
    if not success:
        success = API.Pathfind(tx, ty, distance=2, run=True)

    if not success:
        stand = get_walkable_mining_stand(tx, ty)
        if stand:
            sx, sy = stand
            debug_msg(f"Trying fallback pathfind to stand ({sx}, {sy})")
            success = API.Pathfind(sx, sy, distance=0, run=True)

    if not success:
        return False

    elapsed = 0.0
    check_interval = 0.25

    while elapsed < PATHFIND_TIMEOUT and not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return False

        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
            debug_msg(f"Arrived at deposit ({tx}, {ty}) within reach.")
            if API.Pathfinding():
                API.CancelPathfinding()
            return True

        if not API.Pathfinding():
            debug_msg("Pathfinding idle before reaching deposit, retrying...")
            stand = get_walkable_mining_stand(tx, ty)
            if stand:
                API.Pathfind(stand[0], stand[1], distance=0, run=True)
            else:
                API.Pathfind(tx, ty, distance=2, run=True)

        API.Pause(check_interval)
        elapsed += check_interval

    if API.Pathfinding():
        API.CancelPathfinding()

    return chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2


def mine_deposit(tool, deposit) -> None:
    """Repeatedly swings the mining tool at the deposit until depleted."""
    tx = int(deposit.X)
    ty = int(deposit.Y)
    tz = int(getattr(deposit, "Z", 0) or 0)
    tg = int(getattr(deposit, "Graphic", 0) or 0)

    # Check if static or land tile
    is_static = hasattr(deposit, "IsCave") or hasattr(deposit, "IsTree") or "static" in type(deposit).__name__.lower()

    debug_msg(f"Mining deposit at ({tx}, {ty}, {tz}) Graphic: 0x{tg:04X} Static: {is_static}")
    swing = 0
    consecutive_idle_swings = 0

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return

        if swing >= MAX_VEIN_SWINGS:
            debug_msg(f"Deposit at ({tx}, {ty}) reached maximum swings ({MAX_VEIN_SWINGS}).")
            break

        if consecutive_idle_swings >= MAX_IDLE_SWINGS:
            debug_msg(f"Deposit at ({tx}, {ty}) not yielding ore after {MAX_IDLE_SWINGS} swings, moving on.")
            break

        # Check weight before swinging
        if is_overburdened():
            transfer_ore_to_pack_animal()
            if is_overburdened():
                trigger_overweight_pause()
                if not check_ui_events():
                    return

        # Verify tool
        tool = get_mining_tool()
        if not tool:
            trigger_tool_missing_pause()
            if not check_ui_events():
                return
            tool = get_mining_tool()
            if not tool:
                return

        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) > 2:
            debug_msg("Player moved out of mining reach.")
            break

        tool_serial = getattr(tool, "Serial", tool)
        swing += 1
        update_status(f"Mining ({tx}, {ty}) #{swing}")
        API.ClearJournal()

        API.UseObject(tool_serial)

        if API.WaitForTarget(timeout=2.5):
            dx = tx - API.Player.X
            dy = ty - API.Player.Y
            target_accepted = False

            if is_static:
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
                debug_msg(f"Target at ({tx}, {ty}) not accepted.")
                API.CancelTarget()
                consecutive_idle_swings += 1
                if consecutive_idle_swings >= MAX_IDLE_SWINGS:
                    break
                continue

            API.Pause(SWING_DELAY)
            update_stats()
        else:
            debug_msg(f"Mining swing #{swing}: Target cursor timed out.")
            consecutive_idle_swings += 1
            continue

        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        got_ore = any(kw in t for kw in ["ore", "metal", "loosen", "put some", "place some"] for t in recent_text)
        if got_ore:
            consecutive_idle_swings = 0
            transfer_ore_to_pack_animal()
        else:
            consecutive_idle_swings += 1

        depleted = False
        for kw in MINING_DEPLETED_KEYWORDS:
            if any(kw in t for t in recent_text) or API.InJournal(kw):
                API.SysMsg(f"Vein finished: '{kw}'")
                depleted = True
                break

        if depleted:
            break

    API.CancelTarget()
    API.Pause(0.5)
    transfer_ore_to_pack_animal()


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    # Settle any lingering UI action delays
    API.CancelTarget()
    API.Pause(0.5)

    if DRESS_PROFILE:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE}'...")
        clear_hands()
        API.Dress(DRESS_PROFILE)
        API.Pause(1.0)

    tool = get_mining_tool()
    if not tool:
        API.SysMsg("No pickaxe or shovel found in hands or backpack! Equip one to start.", 32)
        return

    # Render on-screen control Gump
    create_control_gump()
    update_stats()

    update_status("Started")
    API.SysMsg(f"Auto miner started (Radius: {SEARCH_RADIUS}, History: {VEIN_HISTORY_LIMIT}).")

    # Initial cleanup of any loose ore already in backpack
    transfer_ore_to_pack_animal()

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Verify tool
        tool = get_mining_tool()
        if not tool:
            trigger_tool_missing_pause()
            if not check_ui_events():
                break
            tool = get_mining_tool()
            if not tool:
                break

        # Check weight before locating next deposit
        if is_overburdened():
            transfer_ore_to_pack_animal()
            if is_overburdened():
                trigger_overweight_pause()
                if not check_ui_events():
                    break

        # Find candidate deposits
        update_status("Searching for veins...")
        deposits = find_nearby_deposits()
        if not deposits:
            update_status("No more veins")
            API.SysMsg(f"No more harvestable veins found within {SEARCH_RADIUS} tiles. Done.")
            break

        target_deposit = None
        for dep in deposits:
            if not check_ui_events():
                break

            if navigate_to_deposit(dep):
                target_deposit = dep
                break
            else:
                coord = (int(dep.X), int(dep.Y))
                unreachable_coords.add(coord)
                depleted_veins_queue.append(coord)
                debug_msg(f"Deposit at {coord} unreachable, skipping.")

        if not target_deposit:
            update_status("No reachable veins")
            API.SysMsg("Could not pathfind to any nearby veins within reach. Done.")
            break

        # Mine the reached deposit
        mine_deposit(tool, target_deposit)

        # Increment vein count and record in history
        increment_veins_mined()
        coord = (int(target_deposit.X), int(target_deposit.Y))
        depleted_veins_queue.append(coord)
        debug_msg(f"Recorded vein {coord} in history (Total tracked: {len(depleted_veins_queue)}/{VEIN_HISTORY_LIMIT}).")

        # Offload any remaining ore to pack animal
        transfer_ore_to_pack_animal()

        API.Pause(0.5)

    update_status("Finished")
    API.SysMsg("Auto miner finished.")
    dispose_gump()


main()
