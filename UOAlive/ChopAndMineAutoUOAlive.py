"""
ChopAndMineAutoUOAlive.py - Combined Roaming Lumberjack & Miner for UOAlive

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)
Target Shard: UOAlive

Description:
    Combines roaming lumberjacking and opportunistic mining across trees and mountain ridges:
    - Roams from tree to tree using TazUO's native tree static detection and pathfinding.
    - Upon arriving at each tree, scans surrounding tiles within mining reach (distance <= 2)
      for mountain rock faces, cave walls/floors, and boulders that haven't been mined yet.
    - If a mineable area is found:
        1. Automatically switches to the "Miner" dress profile (equips pickaxe or shovel).
        2. Mines the rock or cave spot until depleted.
        3. Automatically offloads all mined ore to the pack animal (Pack Llama, Pack Horse, Beetle).
    - Automatically switches to the "Lumberjack" dress profile (equips woodcutting axe).
    - Chops the tree until depleted.
    - Converts harvested logs into boards on the fly using the axe (halving wood weight).
    - Automatically offloads boards to the pack animal.
    - Maintains a FIFO history tracking recently harvested trees and mined veins to prevent looping.
    - Features an interactive, spacious control Gump (330x190) displaying:
        * Status, Trees & Boards (Backpack & Pet totals)
        * Veins & Ore (Backpack & Pet totals)
        * Dual Skill tracking: Lumberjacking & Mining with skill gain alerts
        * Character STR / DEX / Weight / Pack Pet indicator
        * Interactive Pause / Resume, Pack Pet (manual pet targeting / re-detection), and Stop controls.
    - Comprehensive weight and tool breakage protection with audible/visual auto-pauses.

Usage:
    1. Configure two dress profiles in TazUO: "Lumberjack" (with an axe) and "Miner" (with a pickaxe/shovel).
    2. Bring along a Pack Llama, Pack Horse, or Giant Beetle.
    3. Stand near an area with trees and rocky mountainsides.
    4. Start the script in TazUO.
    5. Monitor progress, Pause/Resume, select Pack Pet, or Stop via the on-screen Gump.
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

# Dress configuration profiles configured in TazUO
DRESS_PROFILE_LUMBERJACK: str = "Lumberjack"
DRESS_PROFILE_MINER: str = "Miner"

# Search radius in tiles around the player to locate candidate trees
SEARCH_RADIUS: int = 25

# Maximum number of recent trees to remember and avoid revisiting (FIFO queue)
TREE_HISTORY_LIMIT: int = 50

# Maximum number of recent mined veins to remember and avoid re-mining
MINING_HISTORY_LIMIT: int = 150

# Stop/Pause script if backpack weight is near capacity
MAX_WEIGHT_CHECK: bool = True
WEIGHT_BUFFER: int = 15  # Pause when Weight >= WeightMax - WEIGHT_BUFFER

# Maximum seconds allowed to pathfind to a tree before skipping it
PATHFIND_TIMEOUT: float = 12.0

# Alert sound played when auto-pausing (0x1F8 = classic system notice chime)
ALERT_SOUND: int = 0x1F8

# Automatically offload converted boards and mined ore to a nearby Pack Horse, Pack Llama, or Beetle
AUTO_PACK_ANIMAL_TRANSFER: bool = True
PACK_ANIMAL_MAX_DISTANCE: int = 3

# Safety limits for swings per node to avoid indefinite loops
MAX_TREE_SWINGS: int = 50
MAX_TREE_IDLE_SWINGS: int = 4

MAX_MINING_SWINGS: int = 40
MAX_MINING_IDLE_SWINGS: int = 4

# ==============================================================================
# Graphics Definitions
# ==============================================================================

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

# Mining tools
PICKAXE_GRAPHIC: int = 0x0E86
SHOVEL_GRAPHICS: List[int] = [0x0F39, 0x0F3A]
MINING_TOOL_GRAPHICS: List[int] = [0x0E86, 0x0F39, 0x0F3A]

# Log graphics (standard and special wood)
LOG_GRAPHICS: List[int] = [
    0x1BDD, 0x1BE0
]

# Board graphics (all standard and special wood varieties)
BOARD_GRAPHICS: List[int] = [
    0x1BD7, 0x1BD8, 0x1BD9, 0x1BDA, 0x1BDB, 0x1BDC, 0x1BE1, 0x1BE2
]

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

# Journal keywords indicating a tree is depleted
TREE_DEPLETED_KEYWORDS: List[str] = [
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
    "immune to your axe",
    "cannot be chopped",
    "use an axe on that",
    "use an axe"
]

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

# ==============================================================================
# Global Gump & State Management
# ==============================================================================

gump = None
lbl_status = None
lbl_trees = None
lbl_veins = None
lbl_skills = None
lbl_stats = None
btn_pause = None
btn_pet = None
btn_stop = None

is_paused: bool = False
is_stopped: bool = False
trees_harvested_count: int = 0
veins_mined_count: int = 0
pack_animal_serial: Optional[int] = None
pack_container_serial: Optional[int] = None
current_dress_profile: Optional[str] = None

# Depleted mining spots FIFO queue
depleted_mining_coords: deque[Tuple[int, int]] = deque(maxlen=MINING_HISTORY_LIMIT)

last_lumber_skill: Optional[float] = None
last_mining_skill: Optional[float] = None
last_str: Optional[int] = None
last_dex: Optional[int] = None


def debug_msg(text: str) -> None:
    """Outputs debug message if DEBUG is enabled."""
    if DEBUG:
        API.SysMsg(f"[Chop&Mine] {text}", 88)


def update_status(text: str) -> None:
    """Updates the status display on the Gump and prints to debug if enabled."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"
    debug_msg(text)


def increment_trees_harvested() -> None:
    """Increments the tree counter and updates the Gump label."""
    global trees_harvested_count
    trees_harvested_count += 1
    update_stats()


def update_stats() -> None:
    """Updates Lumberjacking & Mining skills, STR, DEX, Weight, and Pet stats on the Gump."""
    global last_lumber_skill, last_mining_skill, last_str, last_dex
    global lbl_trees, lbl_veins, lbl_skills, lbl_stats

    # 1. Update Trees & Boards count display (backpack + pack pet)
    if lbl_trees:
        bp_b = get_backpack_board_count()
        pet_b = get_pack_animal_board_count()
        if pet_b > 0 or pack_animal_serial:
            lbl_trees.Text = f"Trees: {trees_harvested_count} | Boards: {bp_b} (Pet: {pet_b})"
        else:
            lbl_trees.Text = f"Trees: {trees_harvested_count} | Boards: {bp_b}"

    # 2. Update Veins & Ore count display (backpack + pack pet)
    if lbl_veins:
        bp_o = get_backpack_ore_count()
        pet_o = get_pack_animal_ore_count()
        if pet_o > 0 or pack_animal_serial:
            lbl_veins.Text = f"Veins: {veins_mined_count} | Ore: {bp_o} (Pet: {pet_o})"
        else:
            lbl_veins.Text = f"Veins: {veins_mined_count} | Ore: {bp_o}"

    # 3. Update Lumberjacking and Mining skills
    lj_obj = API.GetSkill("Lumberjacking") or API.GetSkill("Lumberjack")
    mn_obj = API.GetSkill("Mining")

    lj_val = float(lj_obj.Value) if lj_obj else 0.0
    mn_val = float(mn_obj.Value) if mn_obj else 0.0

    if lbl_skills:
        lbl_skills.Text = f"Lumber: {lj_val:.1f} | Mining: {mn_val:.1f}"

    if last_lumber_skill is not None and lj_val > last_lumber_skill:
        gain = lj_val - last_lumber_skill
        API.SysMsg(f"Lumberjacking gained +{gain:.1f}! New: {lj_val:.1f}", 68)
    last_lumber_skill = lj_val

    if last_mining_skill is not None and mn_val > last_mining_skill:
        gain = mn_val - last_mining_skill
        API.SysMsg(f"Mining gained +{gain:.1f}! New: {mn_val:.1f}", 68)
    last_mining_skill = mn_val

    # 4. Update STR, DEX, Backpack Weight, and Pack Pet indicator
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
    """Auto-pauses the script when the player is full and triggers an audible and visual alert."""
    global is_paused, btn_pause
    if not is_paused:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused: Too Full!")
        API.HeadMsg("TOO FULL! SCRIPT PAUSED", API.Player, 32)
        API.SysMsg("Weight capacity reached! Auto-paused for resource management.", 32)
        if ALERT_SOUND > 0:
            API.PlaySound(ALERT_SOUND)


def trigger_tool_missing_pause(tool_type: str = "tool") -> None:
    """Auto-pauses the script when a harvesting tool is missing or broken."""
    global is_paused, btn_pause
    if not is_paused:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        msg = f"Paused: No {tool_type.capitalize()}!"
        update_status(msg)
        API.HeadMsg(f"NO {tool_type.upper()}! SCRIPT PAUSED", API.Player, 32)
        API.SysMsg(f"{tool_type.capitalize()} missing or broken! Auto-paused so you can equip a new one.", 32)
        if ALERT_SOUND > 0:
            API.PlaySound(ALERT_SOUND)


def on_pause_clicked() -> None:
    """Callback triggered when the Pause/Resume button is clicked on the Gump."""
    global is_paused, btn_pause
    if is_paused:
        # Attempt offloading to pack animal before resuming
        transfer_resources_to_pack_animal()
        if is_overburdened():
            API.SysMsg("Still too full! Please store boards/ore before resuming.", 32)
            API.HeadMsg("STILL OVERWEIGHT!", API.Player, 32)
            return

        is_paused = False
        if btn_pause:
            btn_pause.SetText("Pause")
        update_status("Resuming...")
        API.SysMsg("Auto lumberjack & miner resumed.")
    else:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused")
        API.SysMsg("Auto lumberjack & miner paused.")


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
            transfer_resources_to_pack_animal()
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
        transfer_resources_to_pack_animal()
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
    """Initializes and renders the interactive UOAlive Auto Lumberjack & Miner Gump."""
    global gump, lbl_status, lbl_trees, lbl_veins, lbl_skills, lbl_stats, btn_pause, btn_pet, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 330, 190)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 330, 190)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("UOAlive Auto Lumberjack & Miner", 53)
    title.SetPos(12, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(12, 30)
    gump.Add(lbl_status)

    # Trees harvested and boards counter
    lbl_trees = API.Gumps.CreateGumpLabel("Trees: 0 | Boards: 0", 996)
    lbl_trees.SetPos(12, 52)
    gump.Add(lbl_trees)

    # Veins mined and ore counter
    lbl_veins = API.Gumps.CreateGumpLabel("Veins: 0 | Ore: 0", 996)
    lbl_veins.SetPos(12, 74)
    gump.Add(lbl_veins)

    # Skills label (Lumberjack & Mining)
    lbl_skills = API.Gumps.CreateGumpLabel("Lumber: -- | Mining: --", 996)
    lbl_skills.SetPos(12, 96)
    gump.Add(lbl_skills)

    # Stats and Weight label
    lbl_stats = API.Gumps.CreateGumpLabel("STR: -- | DEX: -- | Wt: --/--", 996)
    lbl_stats.SetPos(12, 118)
    gump.Add(lbl_stats)

    # Pause / Resume button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 85, 24)
    btn_pause.SetPos(15, 148)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Pack Pet button
    btn_pet = API.Gumps.CreateSimpleButton("Pack Pet", 95, 24)
    btn_pet.SetPos(115, 148)
    API.Gumps.AddControlOnClick(btn_pet, on_pack_pet_clicked)
    gump.Add(btn_pet)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 85, 24)
    btn_stop.SetPos(225, 148)
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
# Dress Profile & Equipment Management
# ==============================================================================

def clear_hands() -> bool:
    """
    Un-equips any weapons, tools, or shields in both hands to the backpack.
    Prevents 'You can only wield one weapon at a time' server errors.
    """
    cleared = False
    right = API.ClearRightHand()
    if right:
        cleared = True
    left = API.ClearLeftHand()
    if left:
        cleared = True
    if cleared:
        API.Pause(0.6)
    return cleared


def set_dress_profile(profile_name: str) -> bool:
    """
    Loads and equips the specified dress profile.
    Clears hands first to avoid weapon collision errors on weapon-swapping.
    """
    global current_dress_profile
    if not profile_name:
        return True

    update_status(f"Equipping {profile_name}...")
    debug_msg(f"Switching dress profile to '{profile_name}'")
    API.SysMsg(f"Equipping '{profile_name}' dress profile...", 68)

    # Clear hands before dressing to allow clean weapon equip
    clear_hands()

    API.Dress(profile_name)
    API.Pause(1.0)
    current_dress_profile = profile_name
    return True


def get_equipped_axe():
    """Checks two-hand and one-hand weapon layers for an equipped woodcutting axe."""
    for layer in ["TwoHanded", "OneHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in AXE_GRAPHICS:
            return item
    return None


def equip_axe():
    """Finds an axe in hands or backpack and equips it."""
    axe = get_equipped_axe()
    if axe:
        return axe

    # If holding another weapon/tool (like a pickaxe), clear hands first
    clear_hands()

    for graphic in AXE_GRAPHICS:
        item = API.FindType(graphic, API.Backpack)
        if item:
            API.EquipItem(item.Serial)
            API.Pause(0.6)
            axe = get_equipped_axe()
            if axe:
                return axe
    return None


def get_equipped_mining_tool():
    """Checks equipped layers for a pickaxe or shovel."""
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

    # Clear hands before equipping mining tool
    clear_hands()

    # Check backpack and attempt equipping
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
    """
    Safely retrieves all items inside the player's backpack using recursive=False,
    and manually traverses sub-containers to prevent client engine recursion issues.
    """
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


def get_backpack_board_count() -> int:
    """Counts total boards currently inside the player's backpack."""
    total = 0
    items = get_all_backpack_items()
    for item in items:
        graphic = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()
        if graphic in BOARD_GRAPHICS or ("board" in name and "scoreboard" not in name and "chessboard" not in name):
            total += getattr(item, "Amount", 1) or 1
    return total


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
    """
    Finds a nearby Pack Horse, Pack Llama, or Giant Beetle.
    If a specific animal was selected via Gump, it is prioritized if still in reach.
    Otherwise, scans surrounding mobiles for pack animals within max_distance.
    """
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
    """
    Retrieves the backpack/container item for the pack animal.
    Attempts multiple discovery methods.
    """
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


def get_pack_animal_board_count() -> int:
    """Counts total boards currently inside the pack animal's backpack."""
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
            if graphic in BOARD_GRAPHICS or ("board" in name and "scoreboard" not in name and "chessboard" not in name):
                total += getattr(item, "Amount", 1) or 1
        return total
    except Exception:
        return 0


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


def transfer_boards_to_pack_animal() -> int:
    """Transfers board stacks from player backpack to the pack animal."""
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
    board_serials: List[int] = []
    for item in items:
        graphic = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()
        if graphic in BOARD_GRAPHICS or ("board" in name and "scoreboard" not in name and "chessboard" not in name):
            serial = getattr(item, "Serial", None)
            if serial and serial not in board_serials:
                board_serials.append(serial)

    if not board_serials:
        return 0

    transferred = 0
    for serial in board_serials:
        if API.StopRequested or is_stopped:
            break

        if chebyshev_distance(API.Player.X, API.Player.Y, animal.X, animal.Y) > PACK_ANIMAL_MAX_DISTANCE:
            debug_msg("Pack animal moved out of range during board transfer.")
            break

        API.MoveItem(serial, dest_serial, 0)
        API.Pause(0.6)
        transferred += 1

    if transferred > 0:
        API.SysMsg(f"Transferred {transferred} board stack(s) to {animal_name}.", 68)
        update_stats()

    return transferred


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


def transfer_resources_to_pack_animal() -> int:
    """Transfers both boards and ore to the pack animal."""
    b = transfer_boards_to_pack_animal()
    o = transfer_ore_to_pack_animal()
    return b + o


# ==============================================================================
# Wood Harvesting & Board Conversion Logic
# ==============================================================================

def get_backpack_logs() -> List[int]:
    """Finds all log item serials inside the player's backpack."""
    log_serials: List[int] = []
    items = get_all_backpack_items()
    for item in items:
        graphic = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()
        if graphic in LOG_GRAPHICS or ("log" in name and "clog" not in name and "blog" not in name):
            serial = getattr(item, "Serial", None)
            if serial and serial not in log_serials:
                log_serials.append(serial)
    return log_serials


def convert_logs_to_boards(axe=None) -> int:
    """
    Converts all logs in the player's backpack into boards using the axe.
    Immediately offloads cut boards to the pack animal.
    """
    if API.StopRequested or is_stopped:
        return 0

    log_serials = get_backpack_logs()
    if not log_serials:
        return 0

    axe_item = get_equipped_axe() or equip_axe()
    if not axe_item:
        debug_msg("Cannot convert logs: No axe equipped or found.")
        return 0

    axe_serial = getattr(axe_item, "Serial", axe_item)
    API.CancelTarget()
    API.Pause(0.6)

    update_status("Cutting logs into boards...")
    API.SysMsg(f"Cutting {len(log_serials)} log stack(s) into boards...")

    converted_count = 0
    for serial in log_serials:
        if API.StopRequested or is_stopped:
            break

        item = API.FindItem(serial)
        if not item:
            continue

        if not API.FindItem(axe_serial):
            axe_item = equip_axe()
            if not axe_item:
                break
            axe_serial = getattr(axe_item, "Serial", axe_item)

        success = False
        for attempt in range(3):
            if API.StopRequested or is_stopped:
                break

            API.CancelTarget()
            API.ClearJournal()
            API.UseObject(axe_serial)

            if API.WaitForTarget(timeout=2.5):
                API.Target(serial)
                API.Pause(0.15)
                if API.HasTarget():
                    try:
                        if hasattr(item, "Target"):
                            item.Target()
                    except Exception:
                        pass
                API.Pause(0.5)
                success = True
                converted_count += 1
                update_stats()
                break
            else:
                API.Pause(0.5)

        if not success:
            debug_msg(f"Failed to convert log stack {serial} after 3 attempts.")

    if converted_count > 0:
        API.SysMsg(f"Converted logs into boards ({converted_count} stack(s) cut).")
        if AUTO_PACK_ANIMAL_TRANSFER:
            transfer_boards_to_pack_animal()

    update_stats()
    return converted_count


def find_nearby_trees(history: Set[Tuple[int, int]]):
    """Scans for nearby tree statics, excluding recently visited ones."""
    px = API.Player.X
    py = API.Player.Y
    pz = API.Player.Z or 0
    statics = API.GetStaticsInArea(
        px - SEARCH_RADIUS,
        py - SEARCH_RADIUS,
        px + SEARCH_RADIUS,
        py + SEARCH_RADIUS
    )

    if not statics:
        return []

    candidates = {}
    for s in statics:
        if not s.IsTree:
            continue

        coord = (int(s.X), int(s.Y))
        if coord in history:
            continue

        # Keep the static closest to ground level (trunk)
        if coord not in candidates:
            candidates[coord] = s
        else:
            existing = candidates[coord]
            if abs(s.Z - pz) < abs(existing.Z - pz):
                candidates[coord] = s

    candidate_list = list(candidates.values())
    candidate_list.sort(key=lambda t: chebyshev_distance(px, py, t.X, t.Y))
    return candidate_list


def navigate_to_tree(tree) -> bool:
    """Pathfinds adjacent to the tree within chopping reach (distance <= 2)."""
    tx = int(tree.X)
    ty = int(tree.Y)
    tz = int(tree.Z or 0)

    if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
        return True

    update_status(f"Walking to tree ({tx}, {ty})")
    debug_msg(f"Pathfinding towards tree ({tx}, {ty})...")

    API.Pathfind(tx, ty, tz, distance=1, wait=False, run=True)

    elapsed = 0.0
    check_interval = 0.25

    while elapsed < PATHFIND_TIMEOUT and not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return False

        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
            debug_msg(f"Reached tree ({tx}, {ty}) within reach.")
            if API.Pathfinding():
                API.CancelPathfinding()
            return True

        if not API.Pathfinding():
            debug_msg("Pathfinding idle before reaching tree, retrying...")
            API.Pathfind(tx, ty, tz, distance=1, wait=False, run=True)

        API.Pause(check_interval)
        elapsed += check_interval

    if API.Pathfinding():
        API.CancelPathfinding()

    return chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2


def chop_tree(axe, tree) -> None:
    """Repeatedly chops the tree until depleted, then converts logs to boards."""
    tx = int(tree.X)
    ty = int(tree.Y)
    tz = int(tree.Z or 0)
    tg = int(tree.Graphic)

    debug_msg(f"Starting tree chop at ({tx}, {ty}, {tz}) Graphic: 0x{tg:04X}")
    swing = 0
    consecutive_idle_swings = 0

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return

        if swing >= MAX_TREE_SWINGS:
            debug_msg(f"Tree at ({tx}, {ty}) reached maximum swings limit ({MAX_TREE_SWINGS}).")
            break

        if consecutive_idle_swings >= MAX_TREE_IDLE_SWINGS:
            debug_msg(f"Tree at ({tx}, {ty}) not yielding wood after {MAX_TREE_IDLE_SWINGS} swings, skipping.")
            break

        if not API.FindItem(axe.Serial):
            axe = equip_axe()
            if not axe:
                trigger_tool_missing_pause("axe")
                if not check_ui_events():
                    return
                axe = equip_axe()
                if not axe:
                    return

        # Check weight before swinging
        if is_overburdened():
            convert_logs_to_boards(axe)
            if AUTO_PACK_ANIMAL_TRANSFER:
                transfer_resources_to_pack_animal()
            if is_overburdened():
                trigger_overweight_pause()
                if not check_ui_events():
                    return

        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) > 2:
            debug_msg("Player moved out of tree chopping reach.")
            break

        swing += 1
        update_status(f"Chopping ({tx}, {ty}) #{swing}")
        API.ClearJournal()

        API.UseObject(axe)

        if API.WaitForTarget(timeout=2.5):
            dx = tx - API.Player.X
            dy = ty - API.Player.Y
            target_accepted = False

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

            if not target_accepted and API.HasTarget():
                debug_msg(f"Tree target at ({tx}, {ty}) not accepted.")
                API.CancelTarget()
                consecutive_idle_swings += 1
                if consecutive_idle_swings >= MAX_TREE_IDLE_SWINGS:
                    break
                continue

            API.Pause(SWING_DELAY)
            update_stats()
        else:
            debug_msg(f"Tree swing #{swing}: Target cursor timed out.")
            consecutive_idle_swings += 1
            continue

        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        got_wood = any(kw in t for kw in ["logs", "wood", "hack", "produce", "fell"] for t in recent_text)
        if got_wood:
            consecutive_idle_swings = 0
        else:
            consecutive_idle_swings += 1

        depleted = False
        for kw in TREE_DEPLETED_KEYWORDS:
            if any(kw in t for t in recent_text) or API.InJournal(kw):
                API.SysMsg(f"Tree finished: '{kw}'")
                depleted = True
                break

        if depleted:
            break

    API.CancelTarget()
    API.Pause(0.6)
    convert_logs_to_boards(axe)
    transfer_resources_to_pack_animal()


# ==============================================================================
# Mining Logic
# ==============================================================================

def is_mining_spot_depleted(x: int, y: int) -> bool:
    """Checks whether the coordinate was recently mined within depletion radius."""
    for dx, dy in depleted_mining_coords:
        if chebyshev_distance(x, y, dx, dy) <= 2:
            return True
    return False


def find_mineable_spots_in_reach(max_reach: int = 2) -> List[dict]:
    """
    Scans tiles within max_reach (distance <= 2) from current player position
    for mineable statics or land tiles that haven't been depleted yet.
    """
    px = API.Player.X
    py = API.Player.Y

    spots = []
    visited_coords = set()

    # 1. Statics within reach (cave walls, floors, mountain rocks, boulders)
    statics = API.GetStaticsInArea(px - max_reach, py - max_reach, px + max_reach, py + max_reach)
    if statics:
        for s in statics:
            coord = (int(s.X), int(s.Y))
            if coord in visited_coords or is_mining_spot_depleted(coord[0], coord[1]):
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

            if is_mineable:
                visited_coords.add(coord)
                spots.append({
                    "x": int(s.X),
                    "y": int(s.Y),
                    "z": int(s.Z or 0),
                    "graphic": int(s.Graphic),
                    "is_static": True,
                    "name": getattr(s, "Name", "Rock/Cave") or "Rock/Cave"
                })

    # 2. Terrain land tiles within reach (mountain ridges, slopes, rock floors)
    for dy in range(-max_reach, max_reach + 1):
        for dx in range(-max_reach, max_reach + 1):
            tx = px + dx
            ty = py + dy
            coord = (tx, ty)
            if coord in visited_coords or is_mining_spot_depleted(tx, ty):
                continue

            tile = API.GetTile(tx, ty)
            if tile and tile.Graphic in MINEABLE_GRAPHICS:
                visited_coords.add(coord)
                spots.append({
                    "x": tx,
                    "y": ty,
                    "z": int(getattr(tile, "Z", 0) or 0),
                    "graphic": int(tile.Graphic),
                    "is_static": False,
                    "name": "Mountain Terrain"
                })

    return spots


def mine_spot(tool, spot: dict) -> bool:
    """
    Repeatedly swings the mining tool at the specified spot until depleted.
    Transfers mined ore to the pack animal.
    Returns True if completed.
    """
    global veins_mined_count
    tx = spot["x"]
    ty = spot["y"]
    tz = spot["z"]
    tg = spot["graphic"]
    is_static = spot["is_static"]

    debug_msg(f"Mining spot at ({tx}, {ty}) Graphic: 0x{tg:04X} Static: {is_static}")
    swing = 0
    consecutive_idle_swings = 0

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return False

        if swing >= MAX_MINING_SWINGS:
            debug_msg(f"Mining spot ({tx}, {ty}) reached max swings ({MAX_MINING_SWINGS}).")
            break

        if consecutive_idle_swings >= MAX_MINING_IDLE_SWINGS:
            debug_msg(f"Mining spot ({tx}, {ty}) idle for {MAX_MINING_IDLE_SWINGS} swings, stopping spot.")
            break

        # Check weight before swinging
        if is_overburdened():
            transfer_resources_to_pack_animal()
            if is_overburdened():
                trigger_overweight_pause()
                if not check_ui_events():
                    return False

        # Ensure tool is available
        tool = get_mining_tool()
        if not tool:
            trigger_tool_missing_pause("pickaxe/shovel")
            if not check_ui_events():
                return False
            tool = get_mining_tool()
            if not tool:
                return False

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
                debug_msg(f"Mining target at ({tx}, {ty}) not accepted.")
                API.CancelTarget()
                consecutive_idle_swings += 1
                if consecutive_idle_swings >= MAX_MINING_IDLE_SWINGS:
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
    API.Pause(0.4)
    transfer_ore_to_pack_animal()
    depleted_mining_coords.append((tx, ty))
    veins_mined_count += 1
    update_stats()
    return True


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    # Ensure any lingering target cursors or action cooldowns are settled
    API.CancelTarget()
    API.Pause(0.5)

    # Start with Lumberjack profile
    set_dress_profile(DRESS_PROFILE_LUMBERJACK)

    axe = equip_axe()
    if not axe:
        API.SysMsg("No axe found in hands or backpack! Equip an axe to start.", 32)
        return

    # Render on-screen control Gump
    create_control_gump()
    update_stats()

    # FIFO history queue to prevent repeating the last 50 trees
    visited_queue: deque[Tuple[int, int]] = deque(maxlen=TREE_HISTORY_LIMIT)
    visited_set: Set[Tuple[int, int]] = set()

    update_status("Started")
    API.SysMsg(f"Auto lumberjack & miner started (Radius: {SEARCH_RADIUS}, History: {TREE_HISTORY_LIMIT}).")

    # Initial cleanup of any logs or ore already in backpack
    convert_logs_to_boards(axe)
    transfer_resources_to_pack_animal()

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Check weight before locating next tree
        if is_overburdened():
            convert_logs_to_boards(axe)
            transfer_resources_to_pack_animal()
            if is_overburdened():
                trigger_overweight_pause()
                if not check_ui_events():
                    break

        # Find available trees excluding recently visited
        update_status("Searching for trees...")
        candidates = find_nearby_trees(visited_set)
        if not candidates:
            update_status("No more trees")
            API.SysMsg(f"No more harvestable trees found within {SEARCH_RADIUS} tiles. Done.")
            break

        target_tree = None
        for candidate in candidates:
            if not check_ui_events():
                break

            if navigate_to_tree(candidate):
                target_tree = candidate
                break
            else:
                coord = (int(candidate.X), int(candidate.Y))
                visited_queue.append(coord)
                visited_set = set(visited_queue)
                debug_msg(f"Tree at {coord} unreachable, skipping.")

        if not target_tree:
            update_status("No reachable trees")
            API.SysMsg("Could not pathfind to any nearby trees within reach. Done.")
            break

        # ======================================================================
        # Arrived at tree: Check for nearby mineable areas within reach (<= 2)
        # ======================================================================
        mineable_spots = find_mineable_spots_in_reach(max_reach=2)
        if mineable_spots:
            API.SysMsg(f"Found {len(mineable_spots)} mineable spot(s) nearby. Switching to Miner...", 68)
            set_dress_profile(DRESS_PROFILE_MINER)
            tool = get_mining_tool()
            if tool:
                for spot in mineable_spots:
                    if API.StopRequested or is_stopped:
                        break
                    mine_spot(tool, spot)
            else:
                API.SysMsg("Mineable area detected, but no pickaxe/shovel found in 'Miner' profile or backpack.", 53)

        # ======================================================================
        # Switch back to Lumberjack profile and chop the tree
        # ======================================================================
        set_dress_profile(DRESS_PROFILE_LUMBERJACK)
        axe = equip_axe()
        if not axe:
            trigger_tool_missing_pause("axe")
            if not check_ui_events():
                break
            axe = equip_axe()
            if not axe:
                break

        chop_tree(axe, target_tree)

        # Increment tree count on Gump and record in history queue
        increment_trees_harvested()
        tree_coord = (int(target_tree.X), int(target_tree.Y))
        visited_queue.append(tree_coord)
        visited_set = set(visited_queue)
        debug_msg(f"Recorded tree {tree_coord} in history (Total tracked: {len(visited_queue)}/{TREE_HISTORY_LIMIT}).")

        # Convert leftover logs to boards and offload resources
        convert_logs_to_boards(axe)
        transfer_resources_to_pack_animal()

        API.Pause(0.5)

    update_status("Finished")
    API.SysMsg("Auto lumberjack & miner finished.")
    dispose_gump()


main()
