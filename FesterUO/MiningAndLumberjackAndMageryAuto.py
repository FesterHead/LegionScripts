"""
MiningAndLumberjackAndMageryAuto.py - Automated Roaming Mining, Lumberjacking & Magery Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Combines automated roaming mining, lumberjacking, and Magery skill training into a unified,
    coordinated engine. By executing harvesting and spellcasting within a single orchestration
    loop, target cursor collisions, equip race conditions, and action desyncs between separate
    scripts are completely eliminated.

    - Alternating Harvesting Engine:
        * 1. Mines ore deposit(s) (tunable via Gump) until depleted.
        * 2. Executes a dedicated Magery training session to burn accumulated mana.
        * 3. Switches gear and chops tree(s) (tunable via Gump) until depleted.
        * 4. Executes a dedicated Magery training session to burn accumulated mana.
        * 5. Natural mana regeneration: while moving/pathfinding between nodes, mana restores.
    - Equipment & Dress Switching:
        * Switches to the "Mining" dress profile and equips a pickaxe/shovel during mining.
        * Switches to the "Lumberjack" dress profile and equips an axe during woodcutting.
        * Optionally equips a "Mage" dress profile during spellcasting cycles.
    - Magery Engine:
        * Bounded batch training cycle: casts skill-appropriate spells up to MAX_MAGERY_CASTS_PER_CYCLE
          or until mana is depleted.
        * Supports Resist Training (damaging spells on self with auto-healing) and Non-Resist Training.
        * Monitors Lower Reagent Cost (LRC %) and live counts for all 8 standard reagents.
        * Auto-heals with Greater Heal or Spirit Speak if health drops during Resist Training.
    - Integrated Control Gump with Live Ratio Tuning:
        * Real-time status for both harvesting and Magery actions.
        * Live skills: Mining, Lumberjacking, and Magery with automatic gain announcements.
        * Running counters: Veins mined, Total ore, Trees chopped, Total logs/wood.
        * Live Mana / Max Mana, LRC %, Strength, Dexterity, and Weight capacity monitoring.
        * Interactive Stepper Buttons ([-] / [+]): tune Veins/Cycle and Trees/Cycle live in-game.
        * Live 2-column reagent counter for all 8 standard reagents.
        * Interactive Pause / Resume and Stop buttons.
"""

from collections import deque
import re
from typing import List, Tuple, Optional, Dict
import API

# ==============================================================================
# Configuration - Harvesting
# ==============================================================================

# Script version
SCRIPT_VERSION: str = "1.0.0"

# Delay in seconds between harvesting swings (1.0s on fast shards, 4.5s on OSI)
SWING_DELAY: float = 1.0

# Harvesting ratio: trees to chop per mining spot (tunable live on the Gump!)
TREES_PER_MINING_SPOT: int = 4
MINING_SPOTS_PER_CYCLE: int = 1

# Dress configuration profiles configured in TazUO
DRESS_PROFILE_MINING: str = "Mining"
DRESS_PROFILE_LUMBERJACK: str = "Lumberjack"
# Optional separate dress profile for casting (leave empty "" to stay in current harvesting gear / LRC suit)
DRESS_PROFILE_MAGE: str = ""

# Search radius in tiles around the player to locate deposits and trees
SEARCH_RADIUS: int = 25

# Maximum number of recent deposits and trees to remember and avoid revisiting
DEPOSIT_HISTORY_LIMIT: int = 150
TREE_HISTORY_LIMIT: int = 50

# Radius in tiles to mark as depleted when a vein is exhausted (standard UO veins are 6-8 tiles)
VEIN_DEPLETION_RADIUS: int = 6

# Backpack weight protection
MAX_WEIGHT_CHECK: bool = True
WEIGHT_BUFFER: int = 15  # Stop when Weight >= WeightMax - WEIGHT_BUFFER

# Maximum seconds allowed to pathfind before skipping node
PATHFIND_TIMEOUT: float = 12.0

# Enable verbose logging in client console
DEBUG: bool = False

# ==============================================================================
# Configuration - Magery Training
# ==============================================================================

# Enable or disable Magery training alongside harvesting
TRAIN_MAGERY: bool = True

# Maximum number of Magery spell casts per training cycle before returning to harvesting
# (Set to 0 for unlimited / until mana is depleted)
MAX_MAGERY_CASTS_PER_CYCLE: int = 4

# Training mode:
# Set to True to cast offensive spells on self (Mind Blast, Energy Bolt, Flamestrike)
# to train Resisting Spells simultaneously with automated self-healing.
# Set to False to cast harmless spells (Mana Drain, Invisibility, Mana Vampire).
RESIST_TRAIN: bool = True

# Self-healing during Resist Training:
USE_SPIRIT_SPEAK: bool = False
USE_MAGERY_HEAL: bool = True

# Minimum additional mana buffer required (0 = cast as soon as spell mana cost is met)
MIN_MANA_TO_CAST: int = 0

# Target Magery skill level (stops training Magery when reached or at cap)
TARGET_MAGERY_SKILL: float = 100.0
MIN_MAGERY_SKILL: float = 35.0
ALLOW_LOW_SKILL: bool = True

# Delay in seconds after casting a Magery spell
CAST_DELAY: float = 2.0

# ==============================================================================
# Reagent Definitions & Spell Data
# ==============================================================================

REAGENT_DEFS = {
    "Black Pearl": {"graphics": {0x0F7A}, "keywords": ["black pearl", "black pearls"]},
    "Bloodmoss": {"graphics": {0x0F7B}, "keywords": ["bloodmoss", "blood moss"]},
    "Garlic": {"graphics": {0x0F84}, "keywords": ["garlic"]},
    "Ginseng": {"graphics": {0x0F85}, "keywords": ["ginseng"]},
    "Mandrake Root": {"graphics": {0x0F86}, "keywords": ["mandrake root", "mandrake"]},
    "Nightshade": {"graphics": {0x0F88}, "keywords": ["nightshade"]},
    "Sulfurous Ash": {"graphics": {0x0F8C}, "keywords": ["sulfurous ash", "sulfur ash"]},
    "Spiders' Silk": {"graphics": {0x0F8D}, "keywords": ["spiders' silk", "spider silk", "spiders silk", "spider's silk"]},
}

SPELL_REQUIREMENTS = {
    "Clumsy": (4, ["Bloodmoss", "Nightshade"]),
    "Fireball": (9, ["Black Pearl", "Sulfurous Ash"]),
    "Mana Drain": (11, ["Black Pearl", "Mandrake Root", "Spiders' Silk"]),
    "Mind Blast": (14, ["Black Pearl", "Mandrake Root", "Nightshade", "Sulfurous Ash"]),
    "Energy Bolt": (20, ["Black Pearl", "Nightshade"]),
    "Flamestrike": (40, ["Spiders' Silk", "Sulfurous Ash"]),
    "Invisibility": (20, ["Bloodmoss", "Nightshade"]),
    "Mana Vampire": (40, ["Black Pearl", "Bloodmoss", "Mandrake Root", "Spiders' Silk"]),
    "Greater Heal": (11, ["Garlic", "Ginseng", "Mandrake Root", "Spiders' Silk"]),
}

# ==============================================================================
# Harvesting Graphics & Depletion Keywords
# ==============================================================================

PICKAXE_GRAPHIC = 0x0E86
SHOVEL_GRAPHICS = [0x0F39, 0x0F3A]

AXE_GRAPHICS = [
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

MINING_DEPLETED_KEYWORDS = [
    "no metal here",
    "cannot mine that",
    "nothing here to mine",
    "cannot be mined",
    "there is no ore here",
    "you have depleted",
    "someone has already",
    "try mining elsewhere",
    "cannot see that",
    "can't reach",
    "no line of sight",
    "too far away",
    "target cannot be seen",
    "have no line of sight",
    "use a pickaxe",
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

MINING_STATICS = {
    0x021F, 0x0220, 0x0221, 0x0222, 0x0223, 0x0224, 0x0225, 0x0226,
    0x0227, 0x0228, 0x0229, 0x022A, 0x022B, 0x022C, 0x022D, 0x022E,
    0x022F, 0x0230, 0x0231, 0x0232, 0x0233, 0x0234, 0x0235, 0x0236,
    0x0237, 0x0238, 0x0239, 0x023A, 0x023B, 0x023C, 0x023D, 0x023E,
    0x023F, 0x0240, 0x0241, 0x0242, 0x0243, 0x0244, 0x0245, 0x0246,
    0x0247, 0x0248, 0x0249, 0x024A, 0x024B, 0x024C, 0x024D, 0x024E,
    0x024F, 0x0250, 0x0251, 0x0252, 0x0253, 0x0254, 0x0255, 0x0256,
    0x0257, 0x0258, 0x0259, 0x025A, 0x025B, 0x025C, 0x025D, 0x025E,
    0x025F, 0x0260, 0x0261, 0x0262, 0x0263, 0x0264, 0x0265, 0x0266,
    0x0267, 0x0268, 0x0269, 0x026A, 0x026B, 0x026C, 0x026D, 0x026E,
    0x026F, 0x0270, 0x0271, 0x0272, 0x0273, 0x0274, 0x0275, 0x0276,
    0x0277, 0x0278, 0x0279, 0x027A, 0x027B, 0x027C, 0x027D, 0x027E,
    0x027F, 0x0280, 0x0281, 0x0282, 0x0283, 0x0284, 0x0285, 0x0286,
    0x0287, 0x0288, 0x0289, 0x028A, 0x028B, 0x028C, 0x028D, 0x028E,
    0x028F, 0x0290, 0x0291, 0x0292, 0x0293, 0x0294, 0x0295, 0x0296,
    0x0297, 0x0298, 0x0299, 0x029A, 0x029B, 0x029C, 0x029D, 0x029E,
    0x029F, 0x02A0, 0x02A1, 0x02A2, 0x02A3, 0x02A4, 0x02A5, 0x02A6,
    0x02A7, 0x02A8, 0x02A9, 0x02AA, 0x02AB, 0x02AC, 0x02AD, 0x02AE,
    0x02AF, 0x02B0, 0x02B1, 0x02B2, 0x02B3, 0x02B4, 0x02B5, 0x02B6,
    0x02B7, 0x02B8, 0x02B9, 0x02BA, 0x02BB, 0x02BC, 0x02BD, 0x02BE,
    0x02BF, 0x02C0, 0x02C1, 0x02C2, 0x02C3, 0x02C4, 0x02C5, 0x02C6,
    0x02C7, 0x02C8, 0x02C9, 0x02CA, 0x02CB, 0x02CC, 0x02CD, 0x02CE,
    0x02CF, 0x02D0, 0x02D1, 0x02D2, 0x02D3, 0x02D4, 0x02D5, 0x02D6,
    0x02D7, 0x02D8, 0x02D9, 0x02DA, 0x02DB, 0x02DC, 0x02DD, 0x02DE,
    0x02DF, 0x02E0, 0x02E1, 0x02E2, 0x02E3, 0x02E4, 0x02E5, 0x02E6,
    0x02E7, 0x02E8, 0x02E9, 0x02EA, 0x02EB, 0x02EC, 0x02ED, 0x02EE,
    0x02EF, 0x02F0, 0x02F1, 0x02F2, 0x02F3, 0x02F4, 0x02F5, 0x02F6,
    0x02F7, 0x02F8, 0x02F9, 0x02FA, 0x02FB, 0x02FC, 0x02FD, 0x02FE,
    0x02FF, 0x0300, 0x0301, 0x0302, 0x0303, 0x0304, 0x0305, 0x0306,
    0x0307, 0x0308, 0x0309, 0x030A, 0x030B, 0x030C, 0x030D, 0x030E,
    0x030F, 0x0310, 0x0311, 0x0312, 0x0313, 0x0314, 0x0315, 0x0316,
    0x0317, 0x0318, 0x0319, 0x031A, 0x031B, 0x031C, 0x031D, 0x031E,
    0x031F, 0x0320, 0x0321, 0x0322, 0x0323, 0x0324, 0x0325, 0x0326,
    0x0327, 0x0328, 0x0329, 0x032A, 0x032B, 0x032C, 0x032D, 0x032E,
    0x032F, 0x0330, 0x0331, 0x0332, 0x0333, 0x0334, 0x0335, 0x0336,
    0x0337, 0x0338, 0x0339, 0x033A, 0x033B, 0x033C, 0x033D, 0x033E,
    0x033F, 0x0340, 0x0341, 0x0342, 0x0343, 0x0344, 0x0345, 0x0346,
    0x0347, 0x0348, 0x0349, 0x034A, 0x034B, 0x034C, 0x034D, 0x034E,
    0x034F, 0x0350, 0x0351, 0x0352, 0x0353, 0x0354, 0x0355, 0x0356,
    0x0357, 0x0358, 0x0359, 0x035A, 0x035B, 0x035C, 0x035D, 0x035E,
    0x035F, 0x0360, 0x0361, 0x0362, 0x0363, 0x0364, 0x0365, 0x0366,
    0x0367, 0x0368, 0x0369, 0x036A, 0x036B, 0x036C, 0x036D, 0x036E,
    0x036F, 0x0370, 0x0371, 0x0372, 0x0373, 0x0374, 0x0375, 0x0376,
    0x0377, 0x0378, 0x0379, 0x037A, 0x037B, 0x037C, 0x037D, 0x037E,
    0x037F, 0x0380, 0x0381, 0x0382, 0x0383, 0x0384, 0x0385, 0x0386,
    0x0387, 0x0388, 0x0389, 0x038A, 0x038B, 0x038C, 0x038D, 0x038E,
    0x038F, 0x0390, 0x0391, 0x0392, 0x0393, 0x0394, 0x0395, 0x0396,
    0x0397, 0x0398, 0x0399, 0x039A, 0x039B, 0x039C, 0x039D, 0x039E,
    0x039F, 0x03A0, 0x03A1, 0x03A2, 0x03A3, 0x03A4, 0x03A5, 0x03A6,
    0x03A7, 0x03A8, 0x03A9, 0x03AA, 0x03AB, 0x03AC, 0x03AD, 0x03AE,
    0x03AF, 0x03B0, 0x03B1, 0x03B2, 0x03B3, 0x03B4, 0x03B5, 0x03B6,
    0x03B7, 0x03B8, 0x03B9, 0x03BA, 0x03BB, 0x03BC, 0x03BD, 0x03BE,
    0x03BF, 0x03C0, 0x03C1, 0x03C2, 0x03C3, 0x03C4, 0x03C5, 0x03C6,
    0x03C7, 0x03C8, 0x03C9, 0x03CA, 0x03CB, 0x03CC, 0x03CD, 0x03CE,
    0x03CF, 0x03D0, 0x03D1, 0x03D2, 0x03D3, 0x03D4, 0x03D5, 0x03D6,
    0x03D7, 0x03D8, 0x03D9, 0x03DA, 0x03DB, 0x03DC, 0x03DD, 0x03DE,
    0x03DF, 0x03E0, 0x03E1, 0x03E2, 0x03E3, 0x03E4, 0x03E5, 0x03E6,
    0x03E7, 0x03E8, 0x03E9, 0x03EA, 0x03EB, 0x03EC, 0x03ED, 0x03EE,
    0x03EF, 0x03F0, 0x03F1, 0x03F2, 0x03F3, 0x03F4, 0x03F5, 0x03F6,
    0x03F7, 0x03F8, 0x03F9, 0x03FA, 0x03FB, 0x03FC, 0x03FD, 0x03FE,
    0x03FF, 0x0400, 0x0401, 0x0402, 0x0403, 0x0404, 0x0405, 0x0406,
    0x0407, 0x0408, 0x0409, 0x040A, 0x040B, 0x040C, 0x040D, 0x040E,
    0x040F, 0x0410, 0x0411, 0x0412, 0x0413, 0x0414, 0x0415, 0x0416,
    0x0417, 0x0418, 0x0419, 0x041A, 0x041B, 0x041C, 0x041D, 0x041E,
    0x041F, 0x0420, 0x0421, 0x0422, 0x0423, 0x0424, 0x0425, 0x0426,
    0x0427, 0x0428, 0x0429, 0x042A, 0x042B, 0x042C, 0x042D, 0x042E,
    0x042F, 0x0430,
}

BOULDER_STATICS = {
    0x1363, 0x1364, 0x1365, 0x1366, 0x1367, 0x1368, 0x1369, 0x136A,
    0x136B, 0x136C, 0x136D,
}

MINING_LAND_TILES = {
    0x00E4, 0x00E5, 0x00E6, 0x00E7,
    0x00F8, 0x00FB, 0x00FC, 0x00FD, 0x00FE, 0x00FF,
    0x0100, 0x0101, 0x0102, 0x0103,
    0x021F, 0x0220, 0x0221, 0x0222, 0x0223, 0x0224, 0x0225, 0x0226,
    0x0227, 0x0228, 0x0229, 0x022A, 0x022B, 0x022C, 0x022D, 0x022E,
    0x022F, 0x0230,
}

TREE_GRAPHICS = {
    0x0CD0, 0x0CD3, 0x0CD6, 0x0CD8, 0x0CDA, 0x0CDD, 0x0CE0, 0x0CE3,
    0x0CE6, 0x0CF8, 0x0CFB, 0x0CFE, 0x0D01, 0x0D25, 0x0D27, 0x0D42,
    0x0D43, 0x0D44, 0x0D57, 0x0D58, 0x0D59, 0x0D5A, 0x0D5B, 0x0D6E,
    0x0D6F, 0x0D70, 0x0D71, 0x0D72, 0x0D84, 0x0D85, 0x0D86,
}

# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_magery_status = None
lbl_mine_skill = None
lbl_lumber_skill = None
lbl_magery_skill = None
lbl_mana = None
lbl_mine_stats = None
lbl_lumber_stats = None
lbl_char_stats = None
lbl_weight = None
lbl_mine_spots = None
lbl_tree_spots = None
btn_mine_dec = None
btn_mine_inc = None
btn_tree_dec = None
btn_tree_inc = None
lbl_reagents: Dict[str, object] = {}
btn_pause = None
btn_stop = None

is_paused: bool = False
is_stopped: bool = False
current_mode: str = "mine"

last_mining_skill: Optional[float] = None
last_lumber_skill: Optional[float] = None
last_magery_skill: Optional[float] = None
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


def update_magery_status(text: str) -> None:
    global lbl_magery_status
    if lbl_magery_status:
        lbl_magery_status.Text = f"Mage: {text}"


def scan_backpack_reagents() -> Dict[str, int]:
    """Scans player backpack recursively to count all 8 reagents."""
    counts = {name: 0 for name in REAGENT_DEFS}
    if not API.Player:
        return counts

    items = API.ItemsInContainer(API.Backpack, recursive=True)
    if not items:
        items = API.ItemsInContainer(API.Backpack)
    if not items:
        return counts

    for item in items:
        g = getattr(item, "Graphic", 0)
        amt = getattr(item, "Amount", 1) or 1
        name = str(getattr(item, "Name", "") or "").lower()

        for reg_name, data in REAGENT_DEFS.items():
            if g in data["graphics"] or any(k in name for k in data["keywords"]):
                counts[reg_name] += amt
                break

    return counts


def update_stats(force_reagents: bool = False) -> None:
    global last_mining_skill, last_lumber_skill, last_magery_skill, last_str, last_dex
    global lbl_mine_skill, lbl_lumber_skill, lbl_magery_skill, lbl_mana
    global lbl_mine_stats, lbl_lumber_stats, lbl_char_stats, lbl_weight

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
        lbl_lumber_skill.Text = f"Lumber: {val:.1f} / {cap:.1f}"
        if last_lumber_skill is not None and val > last_lumber_skill:
            gain = val - last_lumber_skill
            API.SysMsg(f"[Lumberjack] Skill gained +{gain:.1f}! New skill: {val:.1f}")
        last_lumber_skill = val

    # 3. Magery Skill
    mag_skill = API.GetSkill("Magery")
    if mag_skill and lbl_magery_skill:
        val = float(mag_skill.Value)
        cap = float(mag_skill.Cap)
        lbl_magery_skill.Text = f"Magery: {val:.1f} / {cap:.1f}"
        if last_magery_skill is not None and val > last_magery_skill:
            gain = val - last_magery_skill
            API.SysMsg(f"[Magery] Skill gained +{gain:.1f}! New skill: {val:.1f}")
        last_magery_skill = val

    # 4. Mana and LRC
    if lbl_mana:
        mana = API.Player.Mana or 0
        mana_max = API.Player.ManaMax or 0
        lrc = API.Player.LowerReagentCost or 0
        lbl_mana.Text = f"Mana: {mana}/{mana_max} | LRC: {lrc}%"

    # 5. Harvesting stats
    if lbl_mine_stats:
        lbl_mine_stats.Text = f"Mined: {veins_mined}v | {total_ores} ore"
    if lbl_lumber_stats:
        lbl_lumber_stats.Text = f"Chopped: {trees_chopped}t | {total_wood} logs"

    # 6. Attributes and Weight
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

    w = API.Player.Weight or 0
    w_max = API.Player.WeightMax or 0
    if lbl_weight:
        lbl_weight.Text = f"Weight: {w} / {w_max}"

    # 7. Reagent counts
    if lbl_reagents:
        lrc = API.Player.LowerReagentCost or 0
        if lrc >= 100:
            for reg, lbl in lbl_reagents.items():
                lbl.Text = f"{reg}: 100% LRC"
        else:
            counts = scan_backpack_reagents()
            for reg, lbl in lbl_reagents.items():
                amt = counts.get(reg, 0)
                lbl.Text = f"{reg}: {amt}"


def on_mine_spots_dec() -> None:
    global MINING_SPOTS_PER_CYCLE, lbl_mine_spots
    if MINING_SPOTS_PER_CYCLE > 1:
        MINING_SPOTS_PER_CYCLE -= 1
        if lbl_mine_spots:
            lbl_mine_spots.Text = str(MINING_SPOTS_PER_CYCLE)
        API.SysMsg(f"[Config] Veins per cycle set to {MINING_SPOTS_PER_CYCLE}")


def on_mine_spots_inc() -> None:
    global MINING_SPOTS_PER_CYCLE, lbl_mine_spots
    if MINING_SPOTS_PER_CYCLE < 50:
        MINING_SPOTS_PER_CYCLE += 1
        if lbl_mine_spots:
            lbl_mine_spots.Text = str(MINING_SPOTS_PER_CYCLE)
        API.SysMsg(f"[Config] Veins per cycle set to {MINING_SPOTS_PER_CYCLE}")


def on_tree_spots_dec() -> None:
    global TREES_PER_MINING_SPOT, lbl_tree_spots
    if TREES_PER_MINING_SPOT > 1:
        TREES_PER_MINING_SPOT -= 1
        if lbl_tree_spots:
            lbl_tree_spots.Text = str(TREES_PER_MINING_SPOT)
        API.SysMsg(f"[Config] Trees per cycle set to {TREES_PER_MINING_SPOT}")


def on_tree_spots_inc() -> None:
    global TREES_PER_MINING_SPOT, lbl_tree_spots
    if TREES_PER_MINING_SPOT < 50:
        TREES_PER_MINING_SPOT += 1
        if lbl_tree_spots:
            lbl_tree_spots.Text = str(TREES_PER_MINING_SPOT)
        API.SysMsg(f"[Config] Trees per cycle set to {TREES_PER_MINING_SPOT}")


def check_stepper_clicks() -> None:
    """Fallback click processing for Gump stepper buttons."""
    if btn_mine_dec and getattr(btn_mine_dec, "HasBeenClicked", lambda: False)():
        on_mine_spots_dec()
    if btn_mine_inc and getattr(btn_mine_inc, "HasBeenClicked", lambda: False)():
        on_mine_spots_inc()
    if btn_tree_dec and getattr(btn_tree_dec, "HasBeenClicked", lambda: False)():
        on_tree_spots_dec()
    if btn_tree_inc and getattr(btn_tree_inc, "HasBeenClicked", lambda: False)():
        on_tree_spots_inc()


def on_pause_clicked() -> None:
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Miner, Lumberjack & Mage paused." if is_paused else "Miner, Lumberjack & Mage resumed.")


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
    """Initializes and renders the combined Miner, Lumberjack & Mage Gump."""
    global gump, lbl_status, lbl_magery_status, lbl_mine_skill, lbl_lumber_skill, lbl_magery_skill, lbl_mana
    global lbl_mine_stats, lbl_lumber_stats, lbl_char_stats, lbl_weight, btn_pause, btn_stop
    global lbl_mine_spots, lbl_tree_spots, btn_mine_dec, btn_mine_inc, btn_tree_dec, btn_tree_inc, lbl_reagents

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 340, 285)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 340, 285)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("Miner, Lumberjack & Mage", 53)
    title.SetPos(10, 8)
    gump.Add(title)
    lbl_author = API.Gumps.CreateGumpLabel(f"by FesterHead v{SCRIPT_VERSION}", 996)
    lbl_author.SetPos(205, 8)
    gump.Add(lbl_author)

    # Harvest Status
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 26)
    gump.Add(lbl_status)

    # Magery Status
    lbl_magery_status = API.Gumps.CreateGumpLabel("Mage: Initializing...", 53)
    lbl_magery_status.SetPos(10, 42)
    gump.Add(lbl_magery_status)

    # Skills Row 1: Mining & Lumberjack
    lbl_mine_skill = API.Gumps.CreateGumpLabel("Mining: -- / --", 996)
    lbl_mine_skill.SetPos(10, 60)
    gump.Add(lbl_mine_skill)

    lbl_lumber_skill = API.Gumps.CreateGumpLabel("Lumber: -- / --", 996)
    lbl_lumber_skill.SetPos(175, 60)
    gump.Add(lbl_lumber_skill)

    # Skills Row 2: Magery & Mana/LRC
    lbl_magery_skill = API.Gumps.CreateGumpLabel("Magery: -- / --", 996)
    lbl_magery_skill.SetPos(10, 76)
    gump.Add(lbl_magery_skill)

    lbl_mana = API.Gumps.CreateGumpLabel("Mana: --/-- | LRC: --%", 996)
    lbl_mana.SetPos(175, 76)
    gump.Add(lbl_mana)

    # Stats Row 1: Mined & Chopped counters
    lbl_mine_stats = API.Gumps.CreateGumpLabel("Mined: 0v | 0 ore", 53)
    lbl_mine_stats.SetPos(10, 94)
    gump.Add(lbl_mine_stats)

    lbl_lumber_stats = API.Gumps.CreateGumpLabel("Chopped: 0t | 0 logs", 53)
    lbl_lumber_stats.SetPos(175, 94)
    gump.Add(lbl_lumber_stats)

    # Stats Row 2: Weight & Attributes
    lbl_weight = API.Gumps.CreateGumpLabel("Weight: -- / --", 996)
    lbl_weight.SetPos(10, 112)
    gump.Add(lbl_weight)

    lbl_char_stats = API.Gumps.CreateGumpLabel("Str: -- | Dex: --", 996)
    lbl_char_stats.SetPos(175, 112)
    gump.Add(lbl_char_stats)

    # Tuning: Veins/Cycle & Trees/Cycle steppers
    lbl_mine_title = API.Gumps.CreateGumpLabel("Veins/Cycle:", 88)
    lbl_mine_title.SetPos(10, 133)
    gump.Add(lbl_mine_title)

    btn_mine_dec = API.Gumps.CreateSimpleButton("-", 20, 20)
    btn_mine_dec.SetPos(95, 132)
    API.Gumps.AddControlOnClick(btn_mine_dec, on_mine_spots_dec)
    gump.Add(btn_mine_dec)

    lbl_mine_spots = API.Gumps.CreateGumpLabel(str(MINING_SPOTS_PER_CYCLE), 53)
    lbl_mine_spots.SetPos(120, 133)
    gump.Add(lbl_mine_spots)

    btn_mine_inc = API.Gumps.CreateSimpleButton("+", 20, 20)
    btn_mine_inc.SetPos(142, 132)
    API.Gumps.AddControlOnClick(btn_mine_inc, on_mine_spots_inc)
    gump.Add(btn_mine_inc)

    lbl_tree_title = API.Gumps.CreateGumpLabel("Trees/Cycle:", 88)
    lbl_tree_title.SetPos(175, 133)
    gump.Add(lbl_tree_title)

    btn_tree_dec = API.Gumps.CreateSimpleButton("-", 20, 20)
    btn_tree_dec.SetPos(260, 132)
    API.Gumps.AddControlOnClick(btn_tree_dec, on_tree_spots_dec)
    gump.Add(btn_tree_dec)

    lbl_tree_spots = API.Gumps.CreateGumpLabel(str(TREES_PER_MINING_SPOT), 53)
    lbl_tree_spots.SetPos(285, 133)
    gump.Add(lbl_tree_spots)

    btn_tree_inc = API.Gumps.CreateSimpleButton("+", 20, 20)
    btn_tree_inc.SetPos(307, 132)
    API.Gumps.AddControlOnClick(btn_tree_inc, on_tree_spots_inc)
    gump.Add(btn_tree_inc)

    # Reagents Header & Columns
    reagents_hdr = API.Gumps.CreateGumpLabel("Reagents:", 53)
    reagents_hdr.SetPos(10, 156)
    gump.Add(reagents_hdr)

    col1 = ["Black Pearl", "Bloodmoss", "Garlic", "Ginseng"]
    col2 = ["Mandrake Root", "Nightshade", "Sulfurous Ash", "Spiders' Silk"]

    lbl_reagents = {}
    for idx, reg in enumerate(col1):
        lbl = API.Gumps.CreateGumpLabel(f"{reg}: --", 996)
        lbl.SetPos(14, 172 + (idx * 16))
        gump.Add(lbl)
        lbl_reagents[reg] = lbl

    for idx, reg in enumerate(col2):
        lbl = API.Gumps.CreateGumpLabel(f"{reg}: --", 996)
        lbl.SetPos(175, 172 + (idx * 16))
        gump.Add(lbl)
        lbl_reagents[reg] = lbl

    # Control Buttons: Pause / Stop
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 150, 25)
    btn_pause.SetPos(15, 248)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 150, 25)
    btn_stop.SetPos(175, 248)
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
    check_stepper_clicks()
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
        check_stepper_clicks()
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
    global is_stopped
    is_stopped = True
    if API.Pathfinding():
        API.CancelPathfinding()
    dispose_gump()
    API.SysMsg("Miner, Lumberjack & Mage stopped.")

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
    items = API.ItemsInContainer(API.Backpack)
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
    items = API.ItemsInContainer(API.Backpack)
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


# ==============================================================================
# Magery Training Engine
# ==============================================================================

def get_magery_spell(skill: float, cap: float) -> Optional[Tuple[str, int, List[str]]]:
    """Determines the appropriate spell based on current Magery skill and mode."""
    if skill >= cap or skill >= TARGET_MAGERY_SKILL:
        return None

    if RESIST_TRAIN:
        if skill < 40.0:
            return ("Fireball", SPELL_REQUIREMENTS["Fireball"][0], SPELL_REQUIREMENTS["Fireball"][1]) if ALLOW_LOW_SKILL else None
        elif skill < 60.0:
            return ("Mind Blast", SPELL_REQUIREMENTS["Mind Blast"][0], SPELL_REQUIREMENTS["Mind Blast"][1])
        elif skill < 80.0:
            return ("Energy Bolt", SPELL_REQUIREMENTS["Energy Bolt"][0], SPELL_REQUIREMENTS["Energy Bolt"][1])
        else:
            return ("Flamestrike", SPELL_REQUIREMENTS["Flamestrike"][0], SPELL_REQUIREMENTS["Flamestrike"][1])
    else:
        if skill < 40.0:
            return ("Clumsy", SPELL_REQUIREMENTS["Clumsy"][0], SPELL_REQUIREMENTS["Clumsy"][1]) if ALLOW_LOW_SKILL else None
        elif skill < 60.0:
            return ("Mana Drain", SPELL_REQUIREMENTS["Mana Drain"][0], SPELL_REQUIREMENTS["Mana Drain"][1])
        elif skill < 80.0:
            return ("Invisibility", SPELL_REQUIREMENTS["Invisibility"][0], SPELL_REQUIREMENTS["Invisibility"][1])
        else:
            return ("Mana Vampire", SPELL_REQUIREMENTS["Mana Vampire"][0], SPELL_REQUIREMENTS["Mana Vampire"][1])


def check_reagents(regs: List[str]) -> Tuple[bool, Optional[str]]:
    """Checks if reagents are present or bypassed by 100% Lower Reagent Cost."""
    if not API.Player:
        return True, None
    lrc = getattr(API.Player, "LowerReagentCost", 0) or 0
    if lrc >= 100:
        return True, None
    counts = scan_backpack_reagents()
    for r in regs:
        if counts.get(r, 0) < 1:
            return False, r
    return True, None


def burn_magery_cycle() -> None:
    """
    Executes a dedicated Magery training session after a deposit or tree is depleted.
    Casts the appropriate skill-tier spell on self until mana is depleted,
    the maximum cast limit per cycle is reached, Magery target is reached,
    or reagents are exhausted.
    """
    if not TRAIN_MAGERY or not API.Player:
        update_magery_status("Disabled")
        return

    m_skill = API.GetSkill("Magery")
    if not m_skill:
        update_magery_status("Skill not found")
        return

    val = float(m_skill.Value)
    cap = float(m_skill.Cap)
    if val >= TARGET_MAGERY_SKILL or val >= cap:
        update_magery_status(f"Complete ({val:.1f})")
        return

    spell_info = get_magery_spell(val, cap)
    if not spell_info:
        update_magery_status("Vendor train req" if val < MIN_MAGERY_SKILL else "Complete")
        return

    spell_name, mana_cost, regs = spell_info
    cur_mana = API.Player.Mana or 0
    required_mana = max(mana_cost, MIN_MANA_TO_CAST)
    if cur_mana < required_mana:
        update_magery_status(f"Mana Low ({cur_mana})")
        return

    # Equip Mage profile if configured
    if DRESS_PROFILE_MAGE:
        API.Dress(DRESS_PROFILE_MAGE)
        API.Pause(0.4)

    casts = 0
    update_magery_status(f"Burning Mana ({cur_mana})...")
    limit_str = f" [Limit: {MAX_MAGERY_CASTS_PER_CYCLE}]" if MAX_MAGERY_CASTS_PER_CYCLE > 0 else ""
    API.SysMsg(f"[Magery] Node depleted. Training {spell_name} (Mana: {cur_mana}){limit_str}...")

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Check cast limit per cycle
        if MAX_MAGERY_CASTS_PER_CYCLE > 0 and casts >= MAX_MAGERY_CASTS_PER_CYCLE:
            update_magery_status(f"Cast limit reached ({casts})")
            API.SysMsg(f"[Magery] Cast limit ({MAX_MAGERY_CASTS_PER_CYCLE}) reached. Returning to harvest.")
            break

        # Check skill progress
        m_skill = API.GetSkill("Magery")
        if not m_skill:
            break
        val = float(m_skill.Value)
        cap = float(m_skill.Cap)
        if val >= TARGET_MAGERY_SKILL or val >= cap:
            update_magery_status(f"Complete ({val:.1f})")
            API.SysMsg(f"[Magery] Target reached: {val:.1f}!")
            break

        spell_info = get_magery_spell(val, cap)
        if not spell_info:
            break
        spell_name, mana_cost, regs = spell_info

        # Check mana
        cur_mana = API.Player.Mana or 0
        required_mana = max(mana_cost, MIN_MANA_TO_CAST)
        if cur_mana < required_mana:
            update_magery_status(f"Mana Depleted ({cur_mana})")
            API.SysMsg(f"[Magery] Mana depleted ({cur_mana}/{required_mana}). Ready to harvest.")
            break

        # Check healing if damaged during resist training
        if RESIST_TRAIN and API.Player.HitsDiff > 15:
            cur_hits = API.Player.Hits or 0
            max_hits = API.Player.HitsMax or 0
            update_status(f"Healing ({cur_hits}/{max_hits})...")
            update_magery_status(f"Healing ({cur_hits}/{max_hits})")

            if USE_SPIRIT_SPEAK and (API.Player.ManaDiff is None or API.Player.ManaDiff < 10):
                API.UseSkill("Spirit Speak")
                if not wait_with_ui(4.0):
                    break
            elif USE_MAGERY_HEAL and (API.Player.Mana or 0) >= 11:
                has_regs, _ = check_reagents(SPELL_REQUIREMENTS["Greater Heal"][1])
                if has_regs:
                    API.CastSpell("Greater Heal")
                    if API.WaitForTarget(timeout=4.0):
                        API.TargetSelf()
                    if not wait_with_ui(2.0):
                        break

        # Check reagents
        has_regs, missing = check_reagents(regs)
        if not has_regs:
            update_magery_status(f"Missing {missing}")
            API.SysMsg(f"[Magery] Cannot cast {spell_name}: Missing {missing} (LRC < 100%).")
            break

        # Cast spell
        casts += 1
        if MAX_MAGERY_CASTS_PER_CYCLE > 0:
            update_magery_status(f"Cast #{casts}/{MAX_MAGERY_CASTS_PER_CYCLE}: {spell_name}")
        else:
            update_magery_status(f"Cast #{casts}: {spell_name}")
        API.CastSpell(spell_name)
        if API.WaitForTarget(timeout=4.5):
            API.TargetSelf()
        else:
            update_magery_status("Cast interrupted")
            API.SysMsg(f"[Magery] Cast interrupted or timed out.")

        update_stats(force_reagents=True)
        if not wait_with_ui(CAST_DELAY):
            break

        # Check if limit reached after cast delay
        if MAX_MAGERY_CASTS_PER_CYCLE > 0 and casts >= MAX_MAGERY_CASTS_PER_CYCLE:
            update_magery_status(f"Cast limit reached ({casts})")
            API.SysMsg(f"[Magery] Cast limit ({MAX_MAGERY_CASTS_PER_CYCLE}) reached. Returning to harvest.")
            break

    # Re-equip appropriate harvest gear after spell cycle
    if DRESS_PROFILE_MAGE:
        if current_mode == "mine":
            switch_to_mining(force=True)
        else:
            switch_to_lumberjack(force=True)
        API.Pause(0.8)
    else:
        API.Pause(0.6)


# ==============================================================================
# Mining Engine
# ==============================================================================

def is_vein_depleted(x: int, y: int) -> bool:
    for dx, dy in depleted_veins:
        if max(abs(x - dx), abs(y - dy)) <= VEIN_DEPLETION_RADIUS:
            return True
    return False


def mark_vein_depleted(x: int, y: int) -> None:
    depleted_veins.append((x, y))


def find_nearby_deposits():
    """Scans for nearby cave tiles, boulders, and mountain slopes within SEARCH_RADIUS."""
    px = API.Player.X
    py = API.Player.Y
    candidates = []

    # 1. Static cave floors & mountain rock
    statics = API.GetStaticTiles(px - SEARCH_RADIUS, py - SEARCH_RADIUS, px + SEARCH_RADIUS, py + SEARCH_RADIUS)
    if statics:
        for s in statics:
            if not s:
                continue
            sx, sy = s.X, s.Y
            if (sx, sy) in unreachable_coords or is_vein_depleted(sx, sy):
                continue
            if s.Id in MINING_STATICS or s.Id in BOULDER_STATICS:
                candidates.append(s)

    # 2. Land tiles (cave ground & mountain slopes)
    land = API.GetLandTiles(px - SEARCH_RADIUS, py - SEARCH_RADIUS, px + SEARCH_RADIUS, py + SEARCH_RADIUS)
    if land:
        for lt in land:
            if not lt:
                continue
            lx, ly = lt.X, lt.Y
            if (lx, ly) in unreachable_coords or is_vein_depleted(lx, ly):
                continue
            if lt.Id in MINING_LAND_TILES:
                candidates.append(lt)

    # Sort closest to player first
    candidates.sort(key=lambda t: chebyshev_distance(px, py, t.X, t.Y))
    return candidates


def navigate_to_deposit(deposit, spot_index: int = 1, total_spots: int = 1) -> bool:
    """Pathfinds within mining reach (distance <= 2) of candidate deposit."""
    px, py = API.Player.X, API.Player.Y
    tx, ty = deposit.X, deposit.Y
    dist = chebyshev_distance(px, py, tx, ty)

    if dist <= 2:
        return True

    update_status(f"Pathfinding to vein ({spot_index}/{total_spots})...")
    API.Pathfind(tx, ty, distance=2)

    start_time = 0.0
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return False

        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
            if API.Pathfinding():
                API.CancelPathfinding()
            return True

        if not API.Pathfinding():
            break

        API.Pause(0.2)
        start_time += 0.2
        if start_time > PATHFIND_TIMEOUT:
            if API.Pathfinding():
                API.CancelPathfinding()
            break

    dist_after = chebyshev_distance(API.Player.X, API.Player.Y, tx, ty)
    if dist_after <= 2:
        return True

    unreachable_coords.add((tx, ty))
    return False


def get_backpack_ore_count() -> int:
    """Returns total count of raw ore items in the backpack."""
    ore_graphics = [0x19B7, 0x19B8, 0x19B9, 0x19BA]
    total = 0
    for g in ore_graphics:
        items = API.FindTypes([g], API.Backpack)
        if items:
            for item in items:
                total += (item.Amount or 1)
    return total


def mine_deposit(deposit, spot_index: int = 1, total_spots: int = 1) -> None:
    """Mines deposit continuously until depleted, updating stats and Gump."""
    global veins_mined, total_ores

    tx, ty, tz = deposit.X, deposit.Y, deposit.Z
    last_ore_count = get_backpack_ore_count()
    consecutive_no_ore = 0

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return

        if is_overburdened():
            update_status("Overweight")
            API.SysMsg("Weight limit reached! Stopping miner.")
            return

        tool = get_mining_tool()
        if not tool:
            update_status("No tool")
            API.SysMsg("Pickaxe/shovel broken or missing!")
            return

        update_status(f"Mining vein ({spot_index}/{total_spots})...")
        API.ClearJournal()

        API.UseObject(tool.Serial)
        if not API.WaitForTarget(timeout=2.0):
            debug_msg("Timeout waiting for mining target cursor.")
            API.Pause(0.5)
            continue

        deposit_id = getattr(deposit, "Id", None) or getattr(deposit, "Graphic", 0)
        API.Target(deposit.Serial if hasattr(deposit, "Serial") and deposit.Serial else (tx, ty, tz, deposit_id))

        API.Pause(SWING_DELAY)
        update_stats()

        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        new_ore_count = get_backpack_ore_count()
        delta = new_ore_count - last_ore_count
        if delta > 0:
            total_ores += delta
            last_ore_count = new_ore_count
            consecutive_no_ore = 0
        elif any("you put" in t and "ore" in t for t in recent_text) or API.InJournal("you put"):
            total_ores += 1
            consecutive_no_ore = 0
        else:
            consecutive_no_ore += 1

        if consecutive_no_ore >= 8:
            debug_msg("Consecutive swing threshold met without ore, vein depleted.")
            mark_vein_depleted(tx, ty)
            veins_mined += 1
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
            veins_mined += 1
            break


# ==============================================================================
# Lumberjacking Engine
# ==============================================================================

def find_nearby_trees():
    """Scans for nearby static trees within SEARCH_RADIUS."""
    px = API.Player.X
    py = API.Player.Y
    candidates = []

    statics = API.GetStaticTiles(px - SEARCH_RADIUS, py - SEARCH_RADIUS, px + SEARCH_RADIUS, py + SEARCH_RADIUS)
    if statics:
        for s in statics:
            if not s:
                continue
            sx, sy = s.X, s.Y
            if (sx, sy) in unreachable_coords or (sx, sy) in depleted_trees:
                continue
            if s.Id in TREE_GRAPHICS:
                candidates.append(s)

    candidates.sort(key=lambda t: chebyshev_distance(px, py, t.X, t.Y))
    return candidates


def navigate_to_tree(tree, tree_index: int = 1, total_trees: int = 1) -> bool:
    """Pathfinds within woodcutting reach (distance <= 2) of candidate tree."""
    px, py = API.Player.X, API.Player.Y
    tx, ty = tree.X, tree.Y
    dist = chebyshev_distance(px, py, tx, ty)

    if dist <= 2:
        return True

    update_status(f"Pathfinding to tree ({tree_index}/{total_trees})...")
    API.Pathfind(tx, ty, distance=1)

    start_time = 0.0
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return False

        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
            if API.Pathfinding():
                API.CancelPathfinding()
            return True

        if not API.Pathfinding():
            break

        API.Pause(0.2)
        start_time += 0.2
        if start_time > PATHFIND_TIMEOUT:
            if API.Pathfinding():
                API.CancelPathfinding()
            break

    dist_after = chebyshev_distance(API.Player.X, API.Player.Y, tx, ty)
    if dist_after <= 2:
        return True

    unreachable_coords.add((tx, ty))
    return False


def get_backpack_wood_count() -> int:
    """Returns total count of logs / kindling in the backpack."""
    log_graphics = [0x1BDD, 0x1BE0, 0x0DE1, 0x0DE2]
    total = 0
    for g in log_graphics:
        items = API.FindTypes([g], API.Backpack)
        if items:
            for item in items:
                total += (item.Amount or 1)
    return total


def chop_tree(tree, tree_index: int = 1, total_trees: int = 1) -> None:
    """Chops tree continuously until depleted, updating stats and Gump."""
    global trees_chopped, total_wood

    tx, ty, tz = tree.X, tree.Y, tree.Z
    last_wood_count = get_backpack_wood_count()
    consecutive_no_wood = 0

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return

        if is_overburdened():
            update_status("Overweight")
            API.SysMsg("Weight limit reached! Stopping lumberjack.")
            return

        axe = get_axe()
        if not axe:
            update_status("No axe")
            API.SysMsg("Axe broken or missing!")
            return

        update_status(f"Chopping tree ({tree_index}/{total_trees})...")
        API.ClearJournal()

        API.UseObject(axe.Serial)
        if not API.WaitForTarget(timeout=2.0):
            debug_msg("Timeout waiting for axe target cursor.")
            API.Pause(0.5)
            continue

        tree_id = getattr(tree, "Id", None) or getattr(tree, "Graphic", 0)
        API.Target(tree.Serial if hasattr(tree, "Serial") and tree.Serial else (tx, ty, tz, tree_id))

        API.Pause(SWING_DELAY)
        update_stats()

        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        new_wood_count = get_backpack_wood_count()
        delta = new_wood_count - last_wood_count
        if delta > 0:
            total_wood += delta
            last_wood_count = new_wood_count
            consecutive_no_wood = 0
        elif any("chop some" in t or "put some wood" in t for t in recent_text) or API.InJournal("chop some"):
            total_wood += 1
            consecutive_no_wood = 0
        else:
            consecutive_no_wood += 1

        if consecutive_no_wood >= 8:
            debug_msg("Consecutive chop threshold met without wood, tree depleted.")
            depleted_trees.append((tx, ty))
            trees_chopped += 1
            return

        # Check depletion
        depleted = False
        for kw in CHOP_DEPLETED_KEYWORDS:
            if any(kw in t for t in recent_text) or API.InJournal(kw):
                debug_msg(f"Tree depleted: '{kw}'")
                depleted = True
                break

        if depleted:
            depleted_trees.append((tx, ty))
            trees_chopped += 1
            break


# ==============================================================================
# Main Orchestration Loop
# ==============================================================================

def main():
    API.SysMsg("=== FesterUO Miner, Lumberjack & Mage ===")

    # Initial check of tools
    mining_tool = get_mining_tool()
    axe = get_axe()

    if not mining_tool or not axe:
        API.SysMsg("Harvest & Mage: Please carry both a pickaxe/shovel and an axe in hands or backpack!")
        return

    # Equip initial mining gear
    switch_to_mining(force=True)

    create_control_gump()
    update_stats(force_reagents=True)
    update_status("Started")
    update_magery_status("Ready")

    API.SysMsg(f"Engine started (Radius: {SEARCH_RADIUS}t, Ratio: {TREES_PER_MINING_SPOT} trees / {MINING_SPOTS_PER_CYCLE} vein, Mage: {'ON' if TRAIN_MAGERY else 'OFF'}).")

    global current_mode
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
                    # Dedicated Magery training cycle after vein is depleted
                    if TRAIN_MAGERY and not is_stopped and not API.StopRequested:
                        burn_magery_cycle()
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
                    # Dedicated Magery training cycle after tree is depleted
                    if TRAIN_MAGERY and not is_stopped and not API.StopRequested:
                        burn_magery_cycle()
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
    API.SysMsg("Miner, Lumberjack & Mage finished.")


main()
