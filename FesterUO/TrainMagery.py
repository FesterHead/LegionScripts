"""
TrainMagery.py - Magery Skill Training Script with Interactive Control Gump

Target Client: TazUO (Legion Scripting Engine)
Author: FesterHead
Source Reference: https://github.com/PlayTazUO/PublicLegionScripts/blob/main/Skills/Any/Train%20Magery.py
Derived from: Converted from https://github.com/matsamilla/Razor-Enhanced/blob/master/Skills/train_Magery.py via TazUO PublicLegionScripts

Description:
    Automatically trains Magery to Grandmaster (or configured skill cap) by casting
    the optimal circle spells based on current skill level. Supports two training modes:
    - Resist Training (default): Casts offensive spells on self (Mind Blast, Energy Bolt,
      Flamestrike) to train Resisting Spells simultaneously, with automated self-healing.
    - Non-Resist Training: Casts non-damaging spells (Mana Drain, Invisibility, Mana Vampire)
      for safe, passive training.

Features:
    - Interactive control Gump showing:
      * Real-time training status (Casting, Meditating, Healing, Waiting for Mana, Paused, Finished)
      * Magery skill level, skill cap, and automatic skill gain announcements
      * Current Mana / Max Mana and Lower Reagent Cost (LRC %)
      * Live backpack inventory counter for all 8 standard reagents
      * Interactive Pause / Resume button
      * Interactive Stop button
    - Startup validation:
      * Validates minimum Magery skill and offers guidance for vendor training
      * Inspects mana and verifies required reagents if LRC is under 100%
      * Alerts if Magery skill lock arrow is not set to Up (▲)
    - Auto-Meditation and mana regeneration cycles
    - Automated self-healing (Spirit Speak or Greater Heal) during Resist Training
    - Optional dress profile auto-equip (e.g. LRC suit or spellcasting gear)
    - Safe lifecycle management, UI event processing, and clean Gump disposal
"""

import API

# ==============================================================================
# Configuration
# ==============================================================================

# Training mode:
# Set to True to cast offensive spells on yourself (Mind Blast, Energy Bolt, Flamestrike)
# to train Resisting Spells simultaneously while leveling Magery.
# Set to False to cast harmless spells (Mana Drain, Invisibility, Mana Vampire).
RESIST_TRAIN = True

# Healing configuration (active during RESIST_TRAIN):
# USE_SPIRIT_SPEAK: Use Spirit Speak skill to heal when HP drops.
# USE_MAGERY_HEAL: Cast Greater Heal / Heal on yourself when HP drops.
USE_SPIRIT_SPEAK = False
USE_MAGERY_HEAL = True

# Mana management:
# USE_MEDITATION: Automatically attempt Meditation when mana drops below threshold.
# MANA_REGEN_THRESHOLD: Mana level that triggers a meditation/regeneration cycle.
# MEDITATE_DELAY: Cooldown delay (seconds) between Meditation skill attempts.
USE_MEDITATION = True
MANA_REGEN_THRESHOLD = 40
MEDITATE_DELAY = 10.0

# Delays and thresholds:
# CAST_DELAY: Seconds to wait after casting a spell before the next action.
# TARGET_SKILL: Target Magery skill level (stops when reached or at skill cap).
# MIN_SKILL: Threshold below which vendor training is strongly recommended.
# ALLOW_LOW_SKILL: If True, allows training below MIN_SKILL using low-circle spells.
CAST_DELAY = 2.5
TARGET_SKILL = 100.0
MIN_SKILL = 35.0
ALLOW_LOW_SKILL = True

# Optional dress profile to load on startup (e.g., "Mage", "LRC", "Spellcasting"):
# Leave empty ("") if you do not want to load a profile automatically.
DRESS_PROFILE = ""


# ==============================================================================
# Reagent Definitions & Spell Data
# ==============================================================================

REAGENT_DEFS = {
    "Black Pearl": {
        "graphics": {0x0F7A},
        "keywords": ["black pearl", "black pearls"],
    },
    "Bloodmoss": {
        "graphics": {0x0F7B},
        "keywords": ["bloodmoss", "blood moss"],
    },
    "Garlic": {
        "graphics": {0x0F84},
        "keywords": ["garlic"],
    },
    "Ginseng": {
        "graphics": {0x0F85},
        "keywords": ["ginseng"],
    },
    "Mandrake Root": {
        "graphics": {0x0F86},
        "keywords": ["mandrake root", "mandrake"],
    },
    "Nightshade": {
        "graphics": {0x0F88},
        "keywords": ["nightshade"],
    },
    "Sulfurous Ash": {
        "graphics": {0x0F8C},
        "keywords": ["sulfurous ash", "sulfur ash"],
    },
    "Spiders' Silk": {
        "graphics": {0x0F8D},
        "keywords": ["spiders' silk", "spider silk", "spiders silk", "spider's silk"],
    },
}

# Spell definitions: (mana_cost, [required_reagents])
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
# Global Gump & State Management
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_mana = None
lbl_reagents = {}
btn_pause = None
btn_stop = None

is_paused = False
is_stopped = False
last_skill = None
last_meditation_time = 0.0
last_reagent_scan_time = 0.0
cached_reagents = {name: 0 for name in REAGENT_DEFS}


def update_status(text: str) -> None:
    """Updates the status display on the Gump."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def scan_backpack_reagents():
    """Scans the player's backpack (including sub-containers) and tallies all 8 reagents."""
    counts = {name: 0 for name in REAGENT_DEFS}
    if not API.Player:
        return counts

    # Search recursively for reagents in pouches/bags
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


def update_stats(force_reagent_scan: bool = False) -> None:
    """Updates Magery skill, Mana, LRC, and Reagents on the Gump and announces skill gains."""
    global last_skill, lbl_skill, lbl_mana, cached_reagents, last_reagent_scan_time

    # Update Magery skill
    skill_obj = API.GetSkill("Magery")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        lbl_skill.Text = f"Magery: {val:.1f} / {cap:.1f}"
        if last_skill is not None and val > last_skill:
            gain = val - last_skill
            API.SysMsg(f"Magery gained +{gain:.1f}! New skill: {val:.1f}")
        last_skill = val

    # Update Mana & LRC
    if lbl_mana and API.Player:
        cur_mana = API.Player.Mana if API.Player.Mana is not None else 0
        max_mana = API.Player.ManaMax if API.Player.ManaMax is not None else 0
        lrc = getattr(API.Player, "LowerReagentCost", None)
        lrc_str = f"{lrc}%" if lrc is not None else "--"
        lbl_mana.Text = f"Mana: {cur_mana} / {max_mana}  |  LRC: {lrc_str}"

    # Update Reagents display
    if force_reagent_scan:
        cached_reagents = scan_backpack_reagents()

    for reg_name, lbl in lbl_reagents.items():
        if lbl:
            cnt = cached_reagents.get(reg_name, 0)
            lbl.Text = f"{reg_name}: {cnt}"


def on_pause_clicked() -> None:
    """Callback triggered when the Pause/Resume button is clicked."""
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Magery trainer paused." if is_paused else "Magery trainer resumed.")


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


def create_control_gump():
    """Initializes and renders the interactive Magery Trainer Gump."""
    global gump, lbl_status, lbl_skill, lbl_mana, lbl_reagents, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 310, 235)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 310, 235)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("Magery Trainer", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Magery: -- / --", 996)
    lbl_skill.SetPos(10, 48)
    gump.Add(lbl_skill)

    # Mana & LRC label
    lbl_mana = API.Gumps.CreateGumpLabel("Mana: -- / --  |  LRC: --%", 996)
    lbl_mana.SetPos(10, 68)
    gump.Add(lbl_mana)

    # Reagents section header
    reagents_hdr = API.Gumps.CreateGumpLabel("Reagents (Backpack):", 53)
    reagents_hdr.SetPos(10, 90)
    gump.Add(reagents_hdr)

    # Reagents labels arranged in two clean columns
    col1_reagents = ["Black Pearl", "Bloodmoss", "Garlic", "Ginseng"]
    col2_reagents = ["Mandrake Root", "Nightshade", "Sulfurous Ash", "Spiders' Silk"]

    lbl_reagents = {}
    for idx, reg_name in enumerate(col1_reagents):
        y_pos = 110 + (idx * 18)
        lbl = API.Gumps.CreateGumpLabel(f"{reg_name}: --", 996)
        lbl.SetPos(14, y_pos)
        gump.Add(lbl)
        lbl_reagents[reg_name] = lbl

    for idx, reg_name in enumerate(col2_reagents):
        y_pos = 110 + (idx * 18)
        lbl = API.Gumps.CreateGumpLabel(f"{reg_name}: --", 996)
        lbl.SetPos(156, y_pos)
        gump.Add(lbl)
        lbl_reagents[reg_name] = lbl

    # Pause button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 75, 22)
    btn_pause.SetPos(35, 196)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 75, 22)
    btn_stop.SetPos(195, 196)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Handle right-click close
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

    # If paused, wait in loop while continuing to process UI events
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
    """
    Waits for the specified duration in small slices, processing UI events.
    Returns False if stopped or cancelled.
    """
    elapsed = 0.0
    step = 0.2
    while elapsed < seconds:
        if not check_ui_events():
            return False
        API.Pause(step)
        elapsed += step
    return check_ui_events()


# ==============================================================================
# Skill Progression & Spell Selection
# ==============================================================================

def get_spell_info(skill: float, cap: float):
    """
    Determines spell name, mana cost, and required reagents based on current skill level.
    Returns (spell_name, mana_cost, reagents) or None if skill has reached TARGET_SKILL or cap.
    """
    if skill >= TARGET_SKILL or skill >= cap:
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

    mana_cost, reagents = SPELL_REQUIREMENTS[spell_name]
    return (spell_name, mana_cost, reagents)


def check_reagent_availability(reagents):
    """
    Verifies that required reagents are present in the backpack.
    Players with 100% Lower Reagent Cost (LRC) bypass reagent requirements.
    """
    if not API.Player:
        return True, ""

    lrc = getattr(API.Player, "LowerReagentCost", 0) or 0
    if lrc >= 100:
        return True, ""

    counts = scan_backpack_reagents()
    for reg in reagents:
        if counts.get(reg, 0) < 1:
            return False, reg
    return True, ""


# ==============================================================================
# Healing & Mana Regeneration
# ==============================================================================

def handle_healing() -> bool:
    """
    Handles player health restoration during Resist Training when damaged.
    Returns False if execution was stopped/interrupted.
    """
    if not API.Player:
        return True

    # If hits are down by more than 15, heal up before casting more damage spells
    while API.Player.HitsDiff > 15 and not API.StopRequested and not is_stopped:
        cur_hits = API.Player.Hits if API.Player.Hits is not None else 0
        max_hits = API.Player.HitsMax if API.Player.HitsMax is not None else 0
        update_status(f"Healing ({cur_hits}/{max_hits})...")
        update_stats(force_reagent_scan=False)

        if USE_SPIRIT_SPEAK and (API.Player.ManaDiff is None or API.Player.ManaDiff < 10):
            API.UseSkill("Spirit Speak")
            if not wait_with_ui(5.0):
                return False
        elif USE_MAGERY_HEAL:
            heal_mana = 11 if API.Player.Mana >= 11 else 4
            heal_spell = "Greater Heal" if API.Player.Mana >= 11 else "Heal"

            has_regs, missing = check_reagent_availability(SPELL_REQUIREMENTS[heal_spell][1])
            if has_regs and API.Player.Mana >= heal_mana:
                API.CastSpell(heal_spell)
                if API.WaitForTarget(timeout=4.0):
                    API.TargetSelf()
                if not wait_with_ui(2.0):
                    return False
            else:
                # Insufficient mana or regs to heal; wait for mana or pause
                if not handle_mana_recovery(target_mana=heal_mana):
                    return False
        else:
            # Passive wait for hit points to recover
            if not wait_with_ui(2.0):
                return False

    return True


def handle_mana_recovery(target_mana=None) -> bool:
    """
    Restores mana by meditating or pausing until mana reaches target_mana (or max mana).
    Returns False if stopped or cancelled.
    """
    global last_meditation_time
    if not API.Player:
        return True

    cur_mana = API.Player.Mana if API.Player.Mana is not None else 0
    max_mana = API.Player.ManaMax if API.Player.ManaMax is not None else 0

    threshold = target_mana if target_mana is not None else max_mana

    if cur_mana < threshold:
        while API.Player and API.Player.Mana < threshold and not API.StopRequested and not is_stopped:
            cur_mana = API.Player.Mana if API.Player.Mana is not None else 0
            update_status(f"Regenerating Mana ({cur_mana}/{threshold})...")
            update_stats(force_reagent_scan=False)

            if USE_MEDITATION and not API.BuffExists("Meditation"):
                API.UseSkill("Meditation")
                if not wait_with_ui(MEDITATE_DELAY):
                    return False
            else:
                if not wait_with_ui(1.0):
                    return False

    return not (is_stopped or API.StopRequested)


# ==============================================================================
# Lifecycle Callbacks
# ==============================================================================

def on_stop() -> None:
    """Invoked when the script is stopped from the client UI."""
    dispose_gump()
    API.SysMsg("Magery training stopped.")

API.OnStop(on_stop)


# ==============================================================================
# Main Training Loop
# ==============================================================================

def main():
    API.SysMsg("Starting Magery training...")
    if DRESS_PROFILE:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE}'...")
        API.Dress(DRESS_PROFILE)
        API.Pause(0.8)

    create_control_gump()
    update_status("Checking requirements...")
    update_stats(force_reagent_scan=True)

    try:
        # Initial skill retrieval
        skill_obj = API.GetSkill("Magery")
        if not skill_obj:
            update_status("Error: Skill not found")
            API.SysMsg("Cannot start training: Could not retrieve Magery skill.")
            wait_with_ui(3.0)
            return

        # Check if Magery skill is locked or set to down
        lock_val = getattr(skill_obj, "Lock", 0)
        if lock_val != 0 and lock_val != "Up":
            API.SysMsg("Notice: Magery skill arrow is not set to Up (▲) in your Skills list!")

        skill = float(skill_obj.Value)
        cap = float(skill_obj.Cap)

        # Minimum skill check for vendor training guidance
        if skill < MIN_SKILL and not ALLOW_LOW_SKILL:
            update_status("Train with Vendor first")
            API.SysMsg(f"Magery ({skill:.1f}) is below {MIN_SKILL:.1f}. Train with a Mage vendor in town first!")
            if API.Player:
                API.HeadMsg("Train Magery from a vendor first!", API.Player)
            wait_with_ui(4.0)
            return

        spell_info = get_spell_info(skill, cap)
        if not spell_info:
            update_status(f"Finished ({skill:.1f})")
            API.SysMsg(f"Magery is already at or above target skill ({skill:.1f} / {TARGET_SKILL:.1f}).")
            wait_with_ui(3.0)
            return

        spell_name, mana_cost, reagents = spell_info

        # Initial reagent check (if LRC < 100%)
        has_regs, missing = check_reagent_availability(reagents)
        if not has_regs:
            update_status(f"Missing {missing}")
            API.SysMsg(f"Cannot start training: Insufficient {missing} to cast {spell_name}. (LRC < 100%)")
            wait_with_ui(3.5)
            return

        # Initial mana check
        max_mana = API.Player.ManaMax if (API.Player and API.Player.ManaMax is not None) else 0
        if max_mana < mana_cost:
            update_status(f"Max Mana Low ({max_mana}/{mana_cost})")
            API.SysMsg(f"Cannot start training: Maximum mana ({max_mana}) is below {spell_name} cost ({mana_cost}).")
            wait_with_ui(3.5)
            return

        # Main training loop
        while not API.StopRequested and not is_stopped:
            if not check_ui_events():
                break

            skill_obj = API.GetSkill("Magery")
            if not skill_obj:
                update_status("Error: Skill not found")
                API.SysMsg("Could not retrieve Magery skill.")
                break

            skill = float(skill_obj.Value)
            cap = float(skill_obj.Cap)
            spell_info = get_spell_info(skill, cap)

            if not spell_info:
                update_status(f"Finished ({skill:.1f})")
                API.SysMsg(f"Magery training complete ({skill:.1f})!")
                if API.Player:
                    API.HeadMsg("You Grandmastered Magery!", API.Player)
                wait_with_ui(3.0)
                break

            spell_name, mana_cost, reagents = spell_info

            # Handle healing when damaged during resist training
            if RESIST_TRAIN:
                if not handle_healing():
                    break

            # Check and restore mana if below spell requirement or threshold
            cur_mana = API.Player.Mana if (API.Player and API.Player.Mana is not None) else 0
            if cur_mana < mana_cost or cur_mana < MANA_REGEN_THRESHOLD:
                if not handle_mana_recovery(target_mana=API.Player.ManaMax if API.Player else 100):
                    break

            # Verify reagents before casting (if LRC < 100%)
            has_regs, missing = check_reagent_availability(reagents)
            if not has_regs:
                update_status(f"Out of {missing}")
                API.SysMsg(f"Training stopped: Out of {missing} required for {spell_name}.")
                wait_with_ui(3.5)
                break

            # Cast Spell
            update_status(f"Casting {spell_name}...")
            API.CastSpell(spell_name)

            # Wait for targeting cursor and target self
            if API.WaitForTarget(timeout=4.5):
                API.TargetSelf()

            # Refresh reagents and stats after cast
            update_stats(force_reagent_scan=True)

            # Wait after cast while remaining responsive to UI events
            if not wait_with_ui(CAST_DELAY):
                break

            # Small slice pause between iterations
            API.Pause(0.1)

    finally:
        dispose_gump()
        API.SysMsg("Magery training finished.")


main()
