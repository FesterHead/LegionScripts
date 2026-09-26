"""
ChopTreeAndMageryAuto.py - Automated Roaming Lumberjacking & Magery Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Combines automated roaming lumberjacking and Magery skill training into a unified,
    coordinated engine. By running both within a single script, target cursor
    collisions, equip race conditions, and action desyncs between separate scripts
    are completely eliminated.

    - Lumberjacking Engine:
        * Scans nearby static trees using TazUO's native tree detection.
        * Selects the nearest unvisited tree within SEARCH_RADIUS and pathfinds to within reach.
        * Loads the configured dress profile ("Lumberjack") before every axe swing.
        * Continuously chops until the tree is depleted, tracking trees harvested and weight limits.
        * Maintains a tree history queue to prevent revisiting recently chopped trees.
    - Magery Engine:
        * Dedicated batch training cycle: Chops a tree until empty, then burns available mana
          casting skill-appropriate Magery spells until spell points are depleted before moving.
        * Synergizes mana regeneration: While walking and chopping the next tree, mana naturally regenerates.
        * Supports Resist Training (damaging spells on self with auto-healing) and Non-Resist Training.
        * Monitors Lower Reagent Cost (LRC %) and live counts for all 8 standard reagents.
        * Auto-heals with Greater Heal or Spirit Speak if health drops during Resist Training.
    - Interactive Control Gump:
        * Displays action status, trees harvested, live Lumberjacking and Magery skills with gain announcements.
        * Live Mana / Max Mana, LRC %, and two-column backpack reagent counter.
        * Interactive Pause / Resume and Stop buttons.
"""

from collections import deque
from typing import List, Tuple, Optional
import API

# ==============================================================================
# Configuration - Lumberjacking
# ==============================================================================

# Delay in seconds between chopping swings (1.0s on fast shards, 4.5s on OSI)
SWING_DELAY = 1.0

# Dress configuration profile to load before every swing and at startup
DRESS_PROFILE_LUMBERJACK = "Lumberjack"

# Search radius in tiles around the player to locate trees
SEARCH_RADIUS = 25

# Maximum number of recent trees to remember and avoid revisiting
TREE_HISTORY_LIMIT = 30

# Backpack weight protection
MAX_WEIGHT_CHECK = True
WEIGHT_BUFFER = 15

# Maximum seconds allowed to pathfind to a tree before skipping it
PATHFIND_TIMEOUT = 12.0

# Enable verbose logging in client console
DEBUG = False

DEPLETED_KEYWORDS = [
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
    "use an axe on that"
]

# ==============================================================================
# Configuration - Magery Training
# ==============================================================================

# Enable or disable Magery training alongside lumberjacking
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

# Optional separate dress profile for casting (leave empty "" to stay in lumberjack gear)
DRESS_PROFILE_MAGE = ""


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
lbl_lumber_skill = None
lbl_magery_skill = None
lbl_mana = None
lbl_reagents = {}
btn_pause = None
btn_stop = None

is_paused = False
is_stopped = False

total_trees_harvested = 0
last_lumber_skill = None
last_magery_skill = None
cached_reagents = {name: 0 for name in REAGENT_DEFS}

recent_trees = deque(maxlen=TREE_HISTORY_LIMIT)


def update_status(text: str) -> None:
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def update_magery_status(text: str) -> None:
    global lbl_magery_status
    if lbl_magery_status:
        lbl_magery_status.Text = f"Mage: {text}"


def scan_backpack_reagents():
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
    global last_lumber_skill, last_magery_skill, cached_reagents

    if lbl_harvest_stats:
        lbl_harvest_stats.Text = f"Trees Harvested: {total_trees_harvested}"

    # Update Lumberjacking Skill
    l_skill = API.GetSkill("Lumberjacking")
    if l_skill and lbl_lumber_skill:
        val = float(l_skill.Value)
        cap = float(l_skill.Cap)
        lbl_lumber_skill.Text = f"Lumberjack: {val:.1f} / {cap:.1f}"
        if last_lumber_skill is not None and val > last_lumber_skill:
            API.SysMsg(f"Lumberjacking gained +{val - last_lumber_skill:.1f}! New skill: {val:.1f}")
        last_lumber_skill = val

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
    API.SysMsg("Lumberjack & Mage paused." if is_paused else "Lumberjack & Mage resumed.")


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
    global gump, lbl_status, lbl_magery_status, lbl_harvest_stats, lbl_lumber_skill, lbl_magery_skill, lbl_mana, lbl_reagents, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 310, 266)

    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 310, 266)
    gump.Add(bg)

    title = API.Gumps.CreateGumpLabel("FesterUO Lumberjack & Mage", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 26)
    gump.Add(lbl_status)

    lbl_magery_status = API.Gumps.CreateGumpLabel("Mage: Initializing...", 53)
    lbl_magery_status.SetPos(10, 44)
    gump.Add(lbl_magery_status)

    lbl_harvest_stats = API.Gumps.CreateGumpLabel("Trees Harvested: 0", 996)
    lbl_harvest_stats.SetPos(10, 62)
    gump.Add(lbl_harvest_stats)

    lbl_lumber_skill = API.Gumps.CreateGumpLabel("Lumberjack: -- / --", 996)
    lbl_lumber_skill.SetPos(10, 80)
    gump.Add(lbl_lumber_skill)

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
# Helper Functions - Lumberjacking
# ==============================================================================

def on_stop() -> None:
    if API.Pathfinding():
        API.CancelPathfinding()
    dispose_gump()
    API.SysMsg("Lumberjack & Mage stopped.")

API.OnStop(on_stop)


def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def get_equipped_axe():
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item:
            return item
    return None


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


def find_nearby_trees(history: set):
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
        if coord in history:
            continue
        if coord not in candidates:
            candidates[coord] = s

    tree_list = list(candidates.values())
    tree_list.sort(key=lambda t: chebyshev_distance(px, py, int(t.X), int(t.Y)))
    return tree_list


def navigate_to_tree(tree) -> bool:
    tx = int(tree.X)
    ty = int(tree.Y)

    if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) <= 2:
        return True

    update_status(f"Moving to ({tx}, {ty})")
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
            debug_msg(f"Pathfinding to ({tx}, {ty}) timed out.")
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
    Executes a dedicated Magery training session after a tree is depleted.
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
    API.SysMsg(f"[Magery] Tree depleted. Training {spell_name} (Mana: {cur_mana})...")

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
            API.SysMsg(f"[Magery] Mana depleted ({cur_mana}/{required_mana}). Ready to chop.")
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

    # Re-equip lumberjack gear and pause for spell recovery cooldown
    if DRESS_PROFILE_LUMBERJACK:
        API.Dress(DRESS_PROFILE_LUMBERJACK)
        API.Pause(1.0)
    else:
        API.Pause(1.0)


# ==============================================================================
# Lumberjacking Routine
# ==============================================================================

def chop_tree(tree) -> None:
    tx = int(tree.X)
    ty = int(tree.Y)
    tz = int(tree.Z)
    tg = int(tree.Graphic)

    swing = 0

    # Ensure lumberjack outfit is equipped before beginning to chop this tree
    if DRESS_PROFILE_LUMBERJACK:
        API.Dress(DRESS_PROFILE_LUMBERJACK)
        API.Pause(0.8)

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            return

        if is_overburdened():
            update_status("Weight limit reached")
            API.SysMsg("Weight limit reached! Stopping lumberjack.")
            return

        if chebyshev_distance(API.Player.X, API.Player.Y, tx, ty) > 2:
            debug_msg("Player moved out of reach.")
            break

        axe = get_equipped_axe()
        if not axe:
            # Try reloading dress profile to equip axe
            if DRESS_PROFILE_LUMBERJACK:
                API.Dress(DRESS_PROFILE_LUMBERJACK)
                API.Pause(1.0)
                axe = get_equipped_axe()
            if not axe:
                update_status("No axe equipped")
                API.SysMsg("No axe found in hands! Stopping.")
                return

        swing += 1
        update_status(f"Chopping ({tx}, {ty}) #{swing}")

        # Attempt to get target cursor with action delay retry
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

        # Target the tree static
        API.Target(tx, ty, tz, tg)

        API.Pause(SWING_DELAY)
        update_stats()

        # Check depletion
        entries = API.GetJournalEntries(SWING_DELAY + 2.0)
        recent_text = [str(e.Text).lower() for e in entries] if entries else []

        depleted = False
        for kw in DEPLETED_KEYWORDS:
            if any(kw in t for t in recent_text) or API.InJournal(kw):
                debug_msg(f"Tree depleted: '{kw}'")
                depleted = True
                break

        if depleted:
            break


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    if DRESS_PROFILE_LUMBERJACK:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE_LUMBERJACK}'...")
        API.Dress(DRESS_PROFILE_LUMBERJACK)
        API.Pause(1.0)

    axe = get_equipped_axe()
    if not axe:
        API.SysMsg("No axe equipped! Please equip an axe to start.")
        return

    create_control_gump()
    update_stats(force_reagents=True)

    recent_trees.clear()

    update_status("Started")
    API.SysMsg(f"Lumberjack & Mage started (Radius: {SEARCH_RADIUS}, History: {TREE_HISTORY_LIMIT} trees).")

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
            API.SysMsg("Weight limit reached! Stopping lumberjack.")
            break

        axe = get_equipped_axe()
        if not axe:
            if DRESS_PROFILE_LUMBERJACK:
                API.Dress(DRESS_PROFILE_LUMBERJACK)
                API.Pause(1.0)
                axe = get_equipped_axe()
            if not axe:
                update_status("No axe equipped")
                API.SysMsg("Axe missing or broken! Stopping.")
                break

        update_status("Searching trees...")
        candidates = find_nearby_trees(set(recent_trees))
        if not candidates:
            update_status("No trees found")
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
                recent_trees.append((int(candidate.X), int(candidate.Y)))
                debug_msg(f"Tree at ({candidate.X}, {candidate.Y}) unreachable, skipping.")

        if not target_tree:
            update_status("No reachable trees")
            API.SysMsg("Could not pathfind to any nearby trees. Done.")
            break

        # Chop reached tree until depleted
        chop_tree(target_tree)

        if is_overburdened() or is_stopped or API.StopRequested:
            break

        global total_trees_harvested
        total_trees_harvested += 1
        recent_trees.append((int(target_tree.X), int(target_tree.Y)))

        # Tree depleted: burn mana on Magery training
        burn_magery_cycle()

        API.Pause(0.4)

    update_status("Finished")
    API.SysMsg("Lumberjack & Mage finished.")
    dispose_gump()


main()
