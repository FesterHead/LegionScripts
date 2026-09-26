"""
MiningAndMageryAuto.py - Automated Roaming Mining & Magery Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Combines automated roaming mining and Magery skill training into a unified,
    coordinated engine. By running both within a single script, target cursor
    collisions, equip race conditions, and action desyncs between separate scripts
    are completely eliminated.

    - Mining Engine:
        * Scans nearby mountain terrain, cave floors/walls, rock outcroppings, and ore nodes.
        * Filters candidate deposits by the player's current Mining skill tier.
        * Pathfinds adjacent to candidate veins and harvests until depleted.
        * Loads the configured dress profile ("Mining") before every mine swing.
        * Tracks veins mined, ores mined, and backpack weight capacity.
    - Magery Engine:
        * Dedicated batch training cycle: Mines a deposit until empty, then burns available mana
          casting skill-appropriate Magery spells until spell points are depleted before moving.
        * Synergizes mana regeneration: While walking and mining the next node, mana naturally regenerates.
        * Supports Resist Training (damaging spells on self with auto-healing) and Non-Resist Training.
        * Monitors Lower Reagent Cost (LRC %) and live counts for all 8 standard reagents.
        * Auto-heals with Greater Heal or Spirit Speak if health drops during Resist Training.
    - Interactive Control Gump:
        * Displays mining status, veins/ores mined, live Mining and Magery skills with gain announcements.
        * Live Mana / Max Mana, LRC %, and two-column backpack reagent counter.
        * Interactive Pause / Resume and Stop buttons.
"""

from collections import deque
import re
from typing import List, Tuple, Optional
import API

# ==============================================================================
# Configuration - Mining
# ==============================================================================

# Delay in seconds between mining swings (1.0s on fast shards, 4.5s on OSI)
SWING_DELAY = 1.0

# Dress configuration profile to load before every swing and at startup
DRESS_PROFILE_MINING = "Mining"

# Search radius in tiles around the player to locate ore deposits
SEARCH_RADIUS = 25

# Maximum number of recent deposits/vein tiles to remember and avoid revisiting
DEPOSIT_HISTORY_LIMIT = 250

# Radius in tiles to mark as depleted when a vein is exhausted (standard UO veins are 8x8 blocks)
DEPLETED_VEIN_RADIUS = 8

# Backpack weight protection
MAX_WEIGHT_CHECK = True
WEIGHT_BUFFER = 15

# Maximum seconds allowed to pathfind to a deposit before skipping it
PATHFIND_TIMEOUT = 12.0

# Enable verbose logging in client console
DEBUG = False

# ==============================================================================
# Configuration - Magery Training
# ==============================================================================

# Enable or disable Magery training alongside mining
TRAIN_MAGERY = True

# Training mode:
# Set to True to cast offensive spells on self (Mind Blast, Energy Bolt, Flamestrike)
# to train Resisting Spells simultaneously with automated self-healing.
# Set to False to cast harmless spells (Mana Drain, Invisibility, Mana Vampire).
RESIST_TRAIN = True

# Self-healing during Resist Training:
USE_SPIRIT_SPEAK = False
USE_MAGERY_HEAL = True

# Minimum additional mana buffer required (0 = cast as soon as spell mana cost is met)
MIN_MANA_TO_CAST = 0

# Target Magery skill level (stops training Magery when reached or at cap)
TARGET_MAGERY_SKILL = 100.0
MIN_MAGERY_SKILL = 35.0
ALLOW_LOW_SKILL = True

# Delay in seconds after casting a Magery spell
CAST_DELAY = 2.0

# Optional separate dress profile for casting (leave empty "" to stay in mining gear)
DRESS_PROFILE_MAGE = ""


# ==============================================================================
# Mining Static & Land Graphic Definitions
# ==============================================================================

PICKAXE_GRAPHIC = 0x0E86
SHOVEL_GRAPHICS = [0x0F39, 0x0F3A]

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
    0x03EF, 0x03F0, 0x03F1, 0x03F2,
    0x053B, 0x053C, 0x053D, 0x053E, 0x053F, 0x0540, 0x0541, 0x0542,
    0x0543, 0x0544, 0x0545, 0x0546, 0x0547, 0x0548, 0x0549, 0x054A,
    0x054B, 0x054C, 0x054D, 0x054E, 0x054F, 0x0550, 0x0551, 0x0552,
    0x0553,
    0x08CD, 0x08CE, 0x08CF, 0x08D0, 0x08D1, 0x08D2, 0x08D3, 0x08D4,
    0x08D5, 0x08D6, 0x08D7, 0x08D8, 0x08D9, 0x08DA, 0x08DB, 0x08DC,
    0x08DD, 0x08DE, 0x08DF, 0x08E0, 0x08E1, 0x08E2, 0x08E3, 0x08E4,
    0x08E5, 0x08E6, 0x08E7, 0x08E8, 0x08E9, 0x08EA, 0x08EB, 0x08EC,
    0x08ED, 0x08EE, 0x08EF, 0x08F0, 0x08F1, 0x08F2, 0x08F3, 0x08F4,
    0x08F5, 0x08F6, 0x08F7, 0x08F8, 0x08F9, 0x08FA, 0x08FB, 0x08FC,
    0x08FD, 0x08FE, 0x08FF, 0x0900, 0x0901, 0x0902, 0x0903, 0x0904,
    0x0905, 0x0906, 0x0907, 0x0908, 0x0909, 0x090A, 0x090B, 0x090C,
    0x090D, 0x090E, 0x090F, 0x0910, 0x0911, 0x0912, 0x0913
}

MINING_LAND_TILES = {
    0x00E2, 0x00E3, 0x00E4, 0x00E5, 0x00E6, 0x00E7,
    0x00EC, 0x00ED, 0x00EE, 0x00EF, 0x00F0, 0x00F1, 0x00F2, 0x00F3,
    0x00F4, 0x00F5, 0x00F6, 0x00F7,
    0x00F8, 0x00F9, 0x00FA, 0x00FB,
    0x0100, 0x0101, 0x0102, 0x0103,
    0x0104, 0x0105, 0x0106, 0x0107,
    0x0110, 0x0111, 0x0112, 0x0113,
    0x0114, 0x0115, 0x0116, 0x0117,
    0x0118, 0x0119, 0x011A, 0x011B, 0x011C, 0x011D
}

ORE_GRAPHICS = {0x19B7, 0x19B8, 0x19B9, 0x19BA}

DEPLETED_KEYWORDS = [
    "no metal here",
    "not enough metal",
    "cannot see that",
    "can't reach",
    "no line of sight",
    "too far away",
    "target cannot be seen",
    "have no line of sight",
    "try mining elsewhere",
    "you have depleted",
    "someone has already",
    "nothing here to mine",
    "mine that",
    "cannot be mined"
]

TOOL_BROKEN_KEYWORDS = [
    "broke your pick",
    "broke your shovel",
    "your tool broke",
    "worn out your tool",
    "destroyed your tool"
]

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
    "Heal": (4, ["Garlic", "Ginseng", "Spiders' Silk"]),
}


# ==============================================================================
# Global State & Control Gump
# ==============================================================================

gump = None
lbl_status = None
lbl_magery_status = None
lbl_harvest_stats = None
lbl_mining_skill = None
lbl_magery_skill = None
lbl_mana = None
lbl_reagents = {}
btn_pause = None
btn_stop = None

is_paused = False
is_stopped = False

total_deposits_mined = 0
total_ores_mined = 0
last_mining_skill = None
last_magery_skill = None
cached_reagents = {name: 0 for name in REAGENT_DEFS}

depleted_veins = deque(maxlen=DEPOSIT_HISTORY_LIMIT)
unreachable_coords = deque(maxlen=50)


def update_status(text: str) -> None:
    """Updates the status display on the Gump."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def update_magery_status(text: str) -> None:
    """Updates the Magery status display on the Gump."""
    global lbl_magery_status
    if lbl_magery_status:
        lbl_magery_status.Text = f"Mage: {text}"


def scan_backpack_reagents():
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
    """Updates mining stats, Magery skill, Mana, LRC, and Reagents on the Gump."""
    global last_mining_skill, last_magery_skill, cached_reagents

    if lbl_harvest_stats:
        lbl_harvest_stats.Text = f"Veins: {total_deposits_mined} | Ores: {total_ores_mined}"

    # Update Mining Skill
    m_skill = API.GetSkill("Mining")
    if m_skill and lbl_mining_skill:
        val = float(m_skill.Value)
        cap = float(m_skill.Cap)
        lbl_mining_skill.Text = f"Mining: {val:.1f} / {cap:.1f}"
        if last_mining_skill is not None and val > last_mining_skill:
            API.SysMsg(f"Mining gained +{val - last_mining_skill:.1f}! New skill: {val:.1f}")
        last_mining_skill = val

    # Update Magery Skill
    mag_skill = API.GetSkill("Magery")
    if mag_skill and lbl_magery_skill:
        val = float(mag_skill.Value)
        cap = float(mag_skill.Cap)
        lbl_magery_skill.Text = f"Magery: {val:.1f} / {cap:.1f}"
        if last_magery_skill is not None and val > last_magery_skill:
            API.SysMsg(f"Magery gained +{val - last_magery_skill:.1f}! New skill: {val:.1f}")
        last_magery_skill = val

    # Update Mana & LRC
    if lbl_mana and API.Player:
        cur_mana = API.Player.Mana if API.Player.Mana is not None else 0
        max_mana = API.Player.ManaMax if API.Player.ManaMax is not None else 0
        lrc = getattr(API.Player, "LowerReagentCost", None)
        lrc_str = f"{lrc}%" if lrc is not None else "--"
        lbl_mana.Text = f"Mana: {cur_mana}/{max_mana} | LRC: {lrc_str}"

    # Update Reagents display
    if force_reagents:
        cached_reagents = scan_backpack_reagents()

    for reg_name, lbl in lbl_reagents.items():
        if lbl:
            lbl.Text = f"{reg_name}: {cached_reagents.get(reg_name, 0)}"


def on_pause_clicked() -> None:
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Miner & Mage paused." if is_paused else "Miner & Mage resumed.")


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
        is_stopped = True
        if API.Pathfinding():
            API.CancelPathfinding()
        API.Stop()


def create_control_gump():
    """Creates the unified Miner & Mage control Gump."""
    global gump, lbl_status, lbl_magery_status, lbl_harvest_stats, lbl_mining_skill, lbl_magery_skill, lbl_mana, lbl_reagents, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 310, 266)

    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 310, 266)
    gump.Add(bg)

    title = API.Gumps.CreateGumpLabel("FesterUO Miner & Mage", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 26)
    gump.Add(lbl_status)

    lbl_magery_status = API.Gumps.CreateGumpLabel("Mage: Initializing...", 53)
    lbl_magery_status.SetPos(10, 44)
    gump.Add(lbl_magery_status)

    lbl_harvest_stats = API.Gumps.CreateGumpLabel("Veins: 0 | Ores: 0", 996)
    lbl_harvest_stats.SetPos(10, 62)
    gump.Add(lbl_harvest_stats)

    lbl_mining_skill = API.Gumps.CreateGumpLabel("Mining: -- / --", 996)
    lbl_mining_skill.SetPos(10, 80)
    gump.Add(lbl_mining_skill)

    lbl_magery_skill = API.Gumps.CreateGumpLabel("Magery: -- / --", 996)
    lbl_magery_skill.SetPos(10, 98)
    gump.Add(lbl_magery_skill)

    lbl_mana = API.Gumps.CreateGumpLabel("Mana: --/-- | LRC: --%", 996)
    lbl_mana.SetPos(10, 116)
    gump.Add(lbl_mana)

    reagents_hdr = API.Gumps.CreateGumpLabel("Reagents:", 53)
    reagents_hdr.SetPos(10, 136)
    gump.Add(reagents_hdr)

    col1 = ["Black Pearl", "Bloodmoss", "Garlic", "Ginseng"]
    col2 = ["Mandrake Root", "Nightshade", "Sulfurous Ash", "Spiders' Silk"]

    lbl_reagents = {}
    for idx, reg in enumerate(col1):
        lbl = API.Gumps.CreateGumpLabel(f"{reg}: --", 996)
        lbl.SetPos(14, 154 + (idx * 16))
        gump.Add(lbl)
        lbl_reagents[reg] = lbl

    for idx, reg in enumerate(col2):
        lbl = API.Gumps.CreateGumpLabel(f"{reg}: --", 996)
        lbl.SetPos(156, 154 + (idx * 16))
        gump.Add(lbl)
        lbl_reagents[reg] = lbl

    btn_pause = API.Gumps.CreateSimpleButton("Pause", 75, 22)
    btn_pause.SetPos(35, 232)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 75, 22)
    btn_stop.SetPos(195, 232)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)
    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    global gump
    if gump and not gump.IsDisposed:
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
# Helper Functions - Mining
# ==============================================================================

def on_stop() -> None:
    if API.Pathfinding():
        API.CancelPathfinding()
    dispose_gump()
    API.SysMsg("Miner & Mage stopped.")

API.OnStop(on_stop)


def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def get_mining_tool():
    """Finds an equipped pickaxe or shovel, or one in the backpack."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item:
            g = item.Graphic
            name = str(item.Name).lower() if item.Name else ""
            if g == PICKAXE_GRAPHIC or g in SHOVEL_GRAPHICS or "pick" in name or "shovel" in name:
                return item

    pick = API.FindType(PICKAXE_GRAPHIC, API.Backpack)
    if pick:
        return pick

    for sg in SHOVEL_GRAPHICS:
        shovel = API.FindType(sg, API.Backpack)
        if shovel:
            return shovel

    items = API.ItemsInContainer(API.Backpack)
    if items:
        for item in items:
            name = str(item.Name).lower() if item.Name else ""
            if "pick" in name or "shovel" in name:
                return item

    return None


def get_backpack_ore_count() -> int:
    items = API.ItemsInContainer(API.Backpack)
    if not items:
        return 0
    total = 0
    for item in items:
        g = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "")).lower()
        if g in ORE_GRAPHICS or "ore" in name:
            amt = getattr(item, "Amount", 1) or 1
            total += amt
    return total


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


def is_vein_depleted(x: int, y: int) -> bool:
    for vx, vy in depleted_veins:
        if chebyshev_distance(x, y, vx, vy) <= DEPLETED_VEIN_RADIUS:
            return True
    return False


def mark_vein_depleted(x: int, y: int) -> None:
    depleted_veins.append((x, y))


def find_nearby_deposits():
    px = API.Player.X
    py = API.Player.Y
    candidates = {}

    # Scan static cave and rock objects
    statics = API.GetStaticsInArea(px - SEARCH_RADIUS, py - SEARCH_RADIUS, px + SEARCH_RADIUS, py + SEARCH_RADIUS)
    if statics:
        for s in statics:
            sg = getattr(s, "Graphic", 0)
            if sg in MINING_STATICS:
                coord = (int(s.X), int(s.Y))
                if not is_vein_depleted(coord[0], coord[1]) and coord not in unreachable_coords:
                    if coord not in candidates:
                        candidates[coord] = s

    # Scan terrain land tiles
    for dx in range(-SEARCH_RADIUS, SEARCH_RADIUS + 1):
        for dy in range(-SEARCH_RADIUS, SEARCH_RADIUS + 1):
            lx = px + dx
            ly = py + dy
            if is_vein_depleted(lx, ly) or (lx, ly) in unreachable_coords:
                continue
            tile = API.GetTile(lx, ly)
            if tile and getattr(tile, "Graphic", 0) in MINING_LAND_TILES:
                coord = (lx, ly)
                if coord not in candidates:
                    candidates[coord] = tile

    deposit_list = list(candidates.values())
    deposit_list.sort(key=lambda d: chebyshev_distance(px, py, int(d.X), int(d.Y)))
    return deposit_list


def navigate_to_deposit(deposit) -> bool:
    tx = int(deposit.X)
    ty = int(deposit.Y)

    if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
        return True

    update_status(f"Moving to ({tx}, {ty})")
    success = API.Pathfind(tx, ty, distance=1, run=True)
    if not success:
        success = API.Pathfind(tx, ty, distance=2, run=True)

    if not success:
        return False

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
            return False

    return chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2


# ==============================================================================
# Helper Functions - Magery Coordination
# ==============================================================================

def get_magery_spell(skill: float, cap: float):
    if skill >= TARGET_MAGERY_SKILL or skill >= cap:
        return None

    if RESIST_TRAIN:
        if skill < 30.0:
            spell_name = "Clumsy" if ALLOW_LOW_SKILL else None
        elif skill < 45.0:
            spell_name = "Fireball" if ALLOW_LOW_SKILL else None
        elif skill < 60.0:
            spell_name = "Mind Blast"
        elif skill < 85.0:
            spell_name = "Energy Bolt"
        else:
            spell_name = "Flamestrike"
    else:
        if skill < 30.0:
            spell_name = "Clumsy" if ALLOW_LOW_SKILL else None
        elif skill < 55.0:
            spell_name = "Mana Drain"
        elif skill < 75.0:
            spell_name = "Invisibility"
        else:
            spell_name = "Mana Vampire"

    if not spell_name or spell_name not in SPELL_REQUIREMENTS:
        return None

    mana_cost, regs = SPELL_REQUIREMENTS[spell_name]
    return spell_name, mana_cost, regs


def check_reagents(regs):
    if not API.Player:
        return True, ""
    lrc = getattr(API.Player, "LowerReagentCost", 0) or 0
    if lrc >= 100:
        return True, ""
    counts = scan_backpack_reagents()
    for r in regs:
        if counts.get(r, 0) < 1:
            return False, r
    return True, ""


last_mage_warn_time = 0.0


def burn_magery_cycle() -> None:
    """
    Executes a dedicated Magery training session after a deposit is depleted.
    Casts the appropriate skill-tier spell on self until mana is depleted,
    Magery target is reached, or reagents are exhausted.
    """
    global last_mage_warn_time
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
        API.Pause(0.3)

    casts = 0
    update_magery_status(f"Burning Mana ({cur_mana})...")
    API.SysMsg(f"[Magery] Node depleted. Training {spell_name} (Mana: {cur_mana})...")

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
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
            API.SysMsg(f"[Magery] Mana depleted ({cur_mana}/{required_mana}). Ready to mine.")
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

        # Cast
        casts += 1
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

    # Re-equip mining gear and pause for spell recovery cooldown
    if DRESS_PROFILE_MINING:
        API.Dress(DRESS_PROFILE_MINING)
        API.Pause(1.0)
    else:
        API.Pause(1.0)


# ==============================================================================
# Mining Routine
# ==============================================================================

def mine_deposit(deposit) -> None:
    tx = int(deposit.X)
    ty = int(deposit.Y)
    tz = int(deposit.Z)
    tg = int(deposit.Graphic) if getattr(deposit, "Graphic", None) else 0

    is_static = hasattr(deposit, "IsCave") or getattr(deposit, "__class__", "") == "ApiStatic" or tg >= 0x4000
    swing = 0

    # Ensure mining outfit is equipped before beginning to mine this deposit
    if DRESS_PROFILE_MINING:
        API.Dress(DRESS_PROFILE_MINING)
        API.Pause(0.8)

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return

        if is_overburdened():
            update_status("Weight limit reached")
            API.SysMsg("Weight limit reached! Stopping miner.")
            return

        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) > 2:
            debug_msg("Player moved out of reach.")
            break

        tool = get_mining_tool()
        if not tool:
            # Try reloading dress profile to retrieve or equip a spare tool
            if DRESS_PROFILE_MINING:
                API.Dress(DRESS_PROFILE_MINING)
                API.Pause(1.0)
                tool = get_mining_tool()
            if not tool:
                update_status("No tool available")
                API.SysMsg("Pickaxe/shovel missing or broken! Stopping.")
                return

        swing += 1
        update_status(f"Mining ({tx}, {ty}) #{swing}")

        before_ore = get_backpack_ore_count()

        # Attempt to get target cursor with action delay retry
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

            # Check if server asked to wait
            entries = API.GetJournalEntries(2.0)
            j_text = [str(e.Text).lower() for e in entries] if entries else []
            if any("must wait" in t or "wait to perform" in t for t in j_text) or API.InJournal("must wait"):
                update_status(f"Action delay ({attempt + 1}/3)...")
                API.Pause(1.2)
            else:
                API.Pause(0.5)

        if not target_ready:
            debug_msg(f"Swing #{swing}: Target cursor timed out after retries.")
            break

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
            debug_msg(f"Target at ({tx}, {ty}) rel=({dx}, {dy}) not accepted, skipping tile.")
            API.CancelTarget()
            break

        API.Pause(SWING_DELAY)
        update_stats()

        # Tally ore gained
        found_smelt = False
        entries = API.GetJournalEntries(3.0)
        if entries:
            for entry in entries:
                t = getattr(entry, "Text", "")
                if "smelt" in t.lower() and "ingot" in t.lower():
                    m = re.search(r"(\d+)\s+ingots?", t, re.IGNORECASE)
                    if m:
                        count = int(m.group(1))
                        global total_ores_mined
                        total_ores_mined += count
                        found_smelt = True
                        break

        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        if not found_smelt:
            after_ore = get_backpack_ore_count()
            delta = max(0, after_ore - before_ore)
            if delta > 0:
                total_ores_mined += delta
            elif any("dig some" in t for t in recent_text) or API.InJournal("dig some"):
                total_ores_mined += 1

        # Check tool breakage
        tool_broken = False
        for kw in TOOL_BROKEN_KEYWORDS:
            if any(kw in t for t in recent_text) or API.InJournal(kw):
                API.SysMsg(f"Tool broke: '{kw}'")
                tool_broken = True
                break

        if tool_broken:
            if DRESS_PROFILE_MINING:
                API.Dress(DRESS_PROFILE_MINING)
                API.Pause(0.5)
            tool = get_mining_tool()
            if not tool:
                update_status("No tool available")
                API.SysMsg("Out of mining tools! Stopping.")
                return

        # Check depletion
        depleted = False
        for kw in DEPLETED_KEYWORDS:
            if any(kw in t for t in recent_text) or API.InJournal(kw):
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
    if DRESS_PROFILE_MINING:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE_MINING}'...")
        API.Dress(DRESS_PROFILE_MINING)
        API.Pause(1.0)

    tool = get_mining_tool()
    if not tool:
        API.SysMsg("No pickaxe or shovel found! Equip or carry a tool to start.")
        return

    create_control_gump()
    update_stats(force_reagents=True)

    depleted_veins.clear()
    unreachable_coords.clear()

    update_status("Started")
    API.SysMsg(f"Miner & Mage started (Radius: {SEARCH_RADIUS}, History: {DEPOSIT_HISTORY_LIMIT} veins).")

    # Announce Magery state on start
    m_skill = API.GetSkill("Magery")
    if m_skill and TRAIN_MAGERY:
        val = float(m_skill.Value)
        cap = float(m_skill.Cap)
        spell_info = get_magery_spell(val, cap)
        if spell_info:
            s_name, s_mana, s_regs = spell_info
            cur_mana = API.Player.Mana or 0
            API.SysMsg(f"[Magery] Training active: {s_name} ({s_mana} mana) | Current: {val:.1f}/{TARGET_MAGERY_SKILL:.1f} | Mana: {cur_mana}")
            # If starting with plenty of mana, run an initial training cycle
            if cur_mana >= max(s_mana * 2, 20):
                burn_magery_cycle()
        else:
            API.SysMsg(f"[Magery] Skill ({val:.1f}) is already at or above target ({TARGET_MAGERY_SKILL:.1f}).")

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        if is_overburdened():
            update_status("Weight limit reached")
            API.SysMsg("Weight limit reached! Stopping miner.")
            break

        tool = get_mining_tool()
        if not tool:
            update_status("No tool available")
            API.SysMsg("Pickaxe/shovel missing or broken! Stopping.")
            break

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
                coord = (int(candidate.X), int(candidate.Y))
                unreachable_coords.append(coord)
                debug_msg(f"Deposit at {coord} unreachable, skipping.")

        if not target_deposit:
            update_status("No reachable deposits")
            API.SysMsg("Could not pathfind to any nearby ore deposits. Done.")
            break

        # Mine reached deposit until depleted
        mine_deposit(target_deposit)

        if is_overburdened() or is_stopped or API.StopRequested:
            break

        global total_deposits_mined
        total_deposits_mined += 1
        mark_vein_depleted(int(target_deposit.X), int(target_deposit.Y))

        # Deposit depleted: burn mana on Magery training
        burn_magery_cycle()

        API.Pause(0.4)

    update_status("Finished")
    API.SysMsg("Miner & Mage finished.")
    dispose_gump()


main()
