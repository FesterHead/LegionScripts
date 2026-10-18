"""
TrainProvokeAndPeace.py - Automated Provoke & Peace Barding Trainer with Control Gump

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Fully automated Provoke & Peace barding training engine for TazUO:
    1. Prompts the player to target two captive or field creatures (e.g. two bulls, bears, or hinds).
    2. Provokes Creature 1 onto Creature 2 (training Provocation and Musicianship).
    3. Waits for the barding cooldown timer.
    4. Peaces Creature 1 (or alternates between creatures) to pacify combat and allow HP regeneration
       (training Peacemaking and Musicianship).
    5. Waits for cooldown and seamlessly repeats the cycle indefinitely.

Features:
    - Triple Skill Training:
        * Concurrently trains Provocation, Peacemaking, and Musicianship.
        * Live skill tracking with real-time gain announcements (+X.X).
    - Multi-Instrument Auto-Detection & Breakage Recovery:
        * Scans backpack for any standard musical instrument (Harp, Lute, Drum, Tambourine, Flute, Horn).
        * Monitors for instrument breakage in the journal and automatically selects spare instruments.
        * Safely pauses when out of instruments.
    - Live Target Monitoring & Safety:
        * Tracks real-time distance and Hit Points percentage for both targets on the Gump.
        * Alerts if a target dies, despawns, or wanders out of barding range (distance > 12).
    - Interactive Control Gump:
        * Real-time activity status (Provoking, Peacing, Waiting Cooldown, Paused).
        * Triple skill progression display (Provocation, Peacemaking, Musicianship).
        * Target 1 and Target 2 name, distance, and HP% indicators.
        * Provoke, Peace, and spare instrument counters.
        * Interactive delay tuning stepper ([-] 6.0s [+]) to calibrate barding cooldown live.
        * Interactive Retarget 1, Retarget 2, Pause / Resume, and Stop controls.
    - Loop Safety:
        * Strict API.StopRequested checks, UI event pump, and OnStop hook.
        * Direct execution when double-clicked in TazUO.
"""

from typing import Optional, List, Dict, Any, Set
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Script version
SCRIPT_VERSION: str = "1.0.0"

# Target skill caps to stop training (None = train until character skill cap)
TARGET_PROVOKING_SKILL: Optional[float] = None
TARGET_PEACEMAKING_SKILL: Optional[float] = None
TARGET_MUSICIANSHIP_SKILL: Optional[float] = None

# Delay in seconds between barding actions (standard UO barding cooldown is 5.0 - 10.0s)
BARDING_COOLDOWN: float = 6.0

# Timeout in seconds when waiting for target cursors from the server
TARGET_TIMEOUT: float = 3.0

# Maximum distance to maintain targets before pausing
MAX_TARGET_DISTANCE: int = 12

# System message hues
HUE_INFO: int = 68      # Cyan / Light Blue
HUE_SUCCESS: int = 63   # Bright Green
HUE_WARN: int = 53      # Gold / Yellow
HUE_ALERT: int = 38     # Red

# Enable verbose debug logging to client console
DEBUG: bool = False

# ==============================================================================
# Musical Instrument Definitions
# ==============================================================================

INSTRUMENT_GRAPHICS: Dict[int, str] = {
    0x0EB1: "Standing Harp",
    0x0EB2: "Lap Harp",
    0x0EB3: "Lute",
    0x0EB4: "Lute",
    0x0E9C: "Drum",
    0x0E9D: "Tambourine",
    0x0E9E: "Tambourine (Tassel)",
    0x2805: "Bamboo Flute",
    0x2807: "Bamboo Flute",
    0x0FC7: "Fire Horn",
    0x1398: "Aud-Char",
}

ALL_INSTRUMENT_GRAPHICS: Set[int] = set(INSTRUMENT_GRAPHICS.keys())

# Journal patterns indicating instrument breakage
BROKEN_PATTERNS: List[str] = [
    "broke your instrument",
    "instrument broke",
    "your instrument has broken",
    "broke into pieces",
    "worn out",
    "destroyed",
]

# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_prov_skill = None
lbl_peace_skill = None
lbl_music_skill = None
lbl_target1 = None
lbl_target2 = None
lbl_counts = None
lbl_delay = None
btn_pause = None
btn_target1 = None
btn_target2 = None
btn_delay_dec = None
btn_delay_inc = None
btn_stop = None

target1_serial: Optional[int] = None
target2_serial: Optional[int] = None
target1_name: str = "Not Set"
target2_name: str = "Not Set"

is_paused: bool = False
is_stopped: bool = False

provoke_attempts: int = 0
peace_attempts: int = 0
total_instruments_broken: int = 0

last_prov_skill: Optional[float] = None
last_peace_skill: Optional[float] = None
last_music_skill: Optional[float] = None

peace_toggle: bool = False  # Alternates peacing between Target 1 and Target 2

# ==============================================================================
# Helper & Logging Functions
# ==============================================================================

def debug_msg(msg: str) -> None:
    if DEBUG:
        API.SysMsg(f"[Debug] {msg}", HUE_INFO)


def update_status(text: str) -> None:
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def get_available_instruments() -> List[Any]:
    """Returns all musical instruments found in the player's root backpack."""
    items = API.ItemsInContainer(API.Backpack, recursive=False) or []
    return [it for it in items if it.Graphic in ALL_INSTRUMENT_GRAPHICS]


def count_instruments() -> int:
    return len(get_available_instruments())


def get_first_instrument() -> Optional[Any]:
    insts = get_available_instruments()
    return insts[0] if insts else None

# ==============================================================================
# Target Validation
# ==============================================================================

def get_entity_info(serial: Optional[int]) -> Tuple[str, int, int]:
    """Returns (name, dist, hp_percent) for a mobile serial, or ('Not Set'/'Dead', 99, 0)."""
    if not serial:
        return ("Not Set", 99, 0)
    mob = API.FindMobile(serial)
    if not mob:
        return ("Not Found", 99, 0)
    if getattr(mob, "IsDead", False):
        return (f"{mob.Name or 'Creature'} (Dead)", mob.Distance, 0)

    name = mob.Name or f"0x{serial:X}"
    dist = mob.Distance if mob.Distance is not None else 99
    max_hp = getattr(mob, "HitsMax", 0) or 100
    cur_hp = getattr(mob, "Hits", 0) or 0
    pct = int((cur_hp / max_hp) * 100) if max_hp > 0 else 0
    return (name, dist, pct)


def validate_targets() -> bool:
    """Verifies that both targets are valid, alive, and within range."""
    global target1_name, target2_name

    if not target1_serial or not target2_serial:
        update_status("Needs Targets")
        return False

    mob1 = API.FindMobile(target1_serial)
    mob2 = API.FindMobile(target2_serial)

    if not mob1:
        API.SysMsg(f"[Trainer] Target 1 (0x{target1_serial:X}) not found in range! Pausing.", HUE_ALERT)
        update_status("Target 1 Missing")
        on_pause_clicked()
        return False

    if not mob2:
        API.SysMsg(f"[Trainer] Target 2 (0x{target2_serial:X}) not found in range! Pausing.", HUE_ALERT)
        update_status("Target 2 Missing")
        on_pause_clicked()
        return False

    if getattr(mob1, "IsDead", False):
        API.SysMsg(f"[Trainer] Target 1 '{mob1.Name or 'Target 1'}' died! Pausing.", HUE_ALERT)
        update_status("Target 1 Dead")
        on_pause_clicked()
        return False

    if getattr(mob2, "IsDead", False):
        API.SysMsg(f"[Trainer] Target 2 '{mob2.Name or 'Target 2'}' died! Pausing.", HUE_ALERT)
        update_status("Target 2 Dead")
        on_pause_clicked()
        return False

    if mob1.Distance > MAX_TARGET_DISTANCE or mob2.Distance > MAX_TARGET_DISTANCE:
        API.SysMsg(f"[Trainer] Targets are too far away (Dist: T1={mob1.Distance}, T2={mob2.Distance})! Pausing.", HUE_WARN)
        update_status("Out of Range")
        on_pause_clicked()
        return False

    target1_name = mob1.Name or target1_name
    target2_name = mob2.Name or target2_name
    return True

# ==============================================================================
# UI & Control Gump
# ==============================================================================

def update_stats() -> None:
    """Refreshes all Gump labels, mobile info, and announces skill gains."""
    global last_prov_skill, last_peace_skill, last_music_skill
    global lbl_prov_skill, lbl_peace_skill, lbl_music_skill
    global lbl_target1, lbl_target2, lbl_counts, lbl_delay

    # 1. Provocation
    p_skill = API.GetSkill("Provocation")
    if p_skill and lbl_prov_skill:
        val = float(p_skill.Value)
        cap = float(p_skill.Cap)
        lbl_prov_skill.Text = f"Provoke: {val:.1f} / {cap:.1f}"
        if last_prov_skill is not None and val > last_prov_skill:
            gain = val - last_prov_skill
            API.SysMsg(f"[Provocation] Skill gain +{gain:.1f}! New skill: {val:.1f}", HUE_SUCCESS)
        last_prov_skill = val

    # 2. Peacemaking
    peace_sk = API.GetSkill("Peacemaking")
    if peace_sk and lbl_peace_skill:
        val = float(peace_sk.Value)
        cap = float(peace_sk.Cap)
        lbl_peace_skill.Text = f"Peace: {val:.1f} / {cap:.1f}"
        if last_peace_skill is not None and val > last_peace_skill:
            gain = val - last_peace_skill
            API.SysMsg(f"[Peacemaking] Skill gain +{gain:.1f}! New skill: {val:.1f}", HUE_SUCCESS)
        last_peace_skill = val

    # 3. Musicianship
    m_skill = API.GetSkill("Musicianship")
    if m_skill and lbl_music_skill:
        val = float(m_skill.Value)
        cap = float(m_skill.Cap)
        lbl_music_skill.Text = f"Music: {val:.1f} / {cap:.1f}"
        if last_music_skill is not None and val > last_music_skill:
            gain = val - last_music_skill
            API.SysMsg(f"[Musicianship] Skill gain +{gain:.1f}! New skill: {val:.1f}", HUE_INFO)
        last_music_skill = val

    # 4. Target 1 & 2
    n1, d1, hp1 = get_entity_info(target1_serial)
    if lbl_target1:
        lbl_target1.Text = f"T1: {n1} (HP: {hp1}%, Dist: {d1})"

    n2, d2, hp2 = get_entity_info(target2_serial)
    if lbl_target2:
        lbl_target2.Text = f"T2: {n2} (HP: {hp2}%, Dist: {d2})"

    # 5. Counters
    inst_count = count_instruments()
    if lbl_counts:
        lbl_counts.Text = f"Provokes: {provoke_attempts} | Peaces: {peace_attempts} | Inst: {inst_count}"

    # 6. Delay
    if lbl_delay:
        lbl_delay.Text = f"{BARDING_COOLDOWN:.1f}s"


def on_pause_clicked() -> None:
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Trainer paused." if is_paused else "Trainer resumed.", HUE_WARN if is_paused else HUE_INFO)


def on_target1_clicked() -> None:
    global target1_serial, target1_name
    API.SysMsg("[Trainer] Target FIRST creature to provoke/peace...", HUE_INFO)
    t = API.RequestTarget(timeout=8.0)
    if t and t != API.Player.Serial:
        target1_serial = t
        mob = API.FindMobile(target1_serial)
        target1_name = (mob.Name if mob else "") or f"0x{target1_serial:X}"
        API.SysMsg(f"[Trainer] Target 1 locked to: {target1_name}", HUE_SUCCESS)
    update_stats()


def on_target2_clicked() -> None:
    global target2_serial, target2_name
    API.SysMsg("[Trainer] Target SECOND creature to provoke/peace...", HUE_INFO)
    t = API.RequestTarget(timeout=8.0)
    if t and t != API.Player.Serial:
        target2_serial = t
        mob = API.FindMobile(target2_serial)
        target2_name = (mob.Name if mob else "") or f"0x{target2_serial:X}"
        API.SysMsg(f"[Trainer] Target 2 locked to: {target2_name}", HUE_SUCCESS)
    update_stats()


def on_delay_dec() -> None:
    global BARDING_COOLDOWN, lbl_delay
    if BARDING_COOLDOWN > 3.0:
        BARDING_COOLDOWN = round(BARDING_COOLDOWN - 0.5, 1)
        if lbl_delay:
            lbl_delay.Text = f"{BARDING_COOLDOWN:.1f}s"
        API.SysMsg(f"[Trainer] Cooldown delay set to {BARDING_COOLDOWN:.1f}s", HUE_INFO)


def on_delay_inc() -> None:
    global BARDING_COOLDOWN, lbl_delay
    if BARDING_COOLDOWN < 15.0:
        BARDING_COOLDOWN = round(BARDING_COOLDOWN + 0.5, 1)
        if lbl_delay:
            lbl_delay.Text = f"{BARDING_COOLDOWN:.1f}s"
        API.SysMsg(f"[Trainer] Cooldown delay set to {BARDING_COOLDOWN:.1f}s", HUE_INFO)


def on_stop_clicked() -> None:
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.SysMsg("[Trainer] Stop requested.", HUE_WARN)
    API.Stop()


def on_gump_disposed() -> None:
    global is_stopped
    if not is_stopped and not API.StopRequested:
        is_stopped = True
        API.Stop()


def create_control_gump() -> None:
    """Initializes and renders the Provoke & Peace Control Gump."""
    global gump, lbl_status, lbl_prov_skill, lbl_peace_skill, lbl_music_skill
    global lbl_target1, lbl_target2, lbl_counts, lbl_delay
    global btn_pause, btn_target1, btn_target2, btn_delay_dec, btn_delay_inc, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(520, 80, 350, 275)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 350, 275)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("Provoke & Peace Trainer", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    lbl_author = API.Gumps.CreateGumpLabel(f"by FesterHead v{SCRIPT_VERSION}", 996)
    lbl_author.SetPos(220, 8)
    gump.Add(lbl_author)

    # Status
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Skills: Provoke, Peace, Music
    lbl_prov_skill = API.Gumps.CreateGumpLabel("Provoke: -- / --", 68)
    lbl_prov_skill.SetPos(10, 48)
    gump.Add(lbl_prov_skill)

    lbl_peace_skill = API.Gumps.CreateGumpLabel("Peace: -- / --", 68)
    lbl_peace_skill.SetPos(180, 48)
    gump.Add(lbl_peace_skill)

    lbl_music_skill = API.Gumps.CreateGumpLabel("Music: -- / --", 996)
    lbl_music_skill.SetPos(10, 70)
    gump.Add(lbl_music_skill)

    # Target Info
    lbl_target1 = API.Gumps.CreateGumpLabel("T1: Not Set", 996)
    lbl_target1.SetPos(10, 92)
    gump.Add(lbl_target1)

    lbl_target2 = API.Gumps.CreateGumpLabel("T2: Not Set", 996)
    lbl_target2.SetPos(10, 114)
    gump.Add(lbl_target2)

    # Running Counters
    lbl_counts = API.Gumps.CreateGumpLabel("Provokes: 0 | Peaces: 0 | Inst: 0", 53)
    lbl_counts.SetPos(10, 136)
    gump.Add(lbl_counts)

    # Delay Stepper: Delay: [-] 6.0s [+]
    lbl_delay_title = API.Gumps.CreateGumpLabel("Cooldown Delay:", 88)
    lbl_delay_title.SetPos(10, 162)
    gump.Add(lbl_delay_title)

    btn_delay_dec = API.Gumps.CreateSimpleButton("-", 22, 20)
    btn_delay_dec.SetPos(125, 160)
    API.Gumps.AddControlOnClick(btn_delay_dec, on_delay_dec)
    gump.Add(btn_delay_dec)

    lbl_delay = API.Gumps.CreateGumpLabel(f"{BARDING_COOLDOWN:.1f}s", 53)
    lbl_delay.SetPos(155, 162)
    gump.Add(lbl_delay)

    btn_delay_inc = API.Gumps.CreateSimpleButton("+", 22, 20)
    btn_delay_inc.SetPos(200, 160)
    API.Gumps.AddControlOnClick(btn_delay_inc, on_delay_inc)
    gump.Add(btn_delay_inc)

    # Buttons Row 1: Target 1 / Target 2
    btn_target1 = API.Gumps.CreateSimpleButton("Set Target 1", 160, 25)
    btn_target1.SetPos(10, 195)
    API.Gumps.AddControlOnClick(btn_target1, on_target1_clicked)
    gump.Add(btn_target1)

    btn_target2 = API.Gumps.CreateSimpleButton("Set Target 2", 160, 25)
    btn_target2.SetPos(180, 195)
    API.Gumps.AddControlOnClick(btn_target2, on_target2_clicked)
    gump.Add(btn_target2)

    # Buttons Row 2: Pause / Stop
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 160, 26)
    btn_pause.SetPos(10, 230)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 160, 26)
    btn_stop.SetPos(180, 230)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)
    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    global gump
    if gump and not getattr(gump, "IsDisposed", False):
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes UI callbacks, pauses, and checks for stop requests."""
    global is_paused, is_stopped
    API.ProcessCallbacks()
    update_stats()

    if is_stopped or API.StopRequested:
        return False

    while is_paused and not API.StopRequested and not is_stopped:
        API.Pause(0.2)
        API.ProcessCallbacks()
        update_stats()

    return not (is_stopped or API.StopRequested)


def wait_with_ui(seconds: float) -> bool:
    """Pauses for a duration while keeping the UI responsive and showing live status."""
    elapsed = 0.0
    step = 0.2
    while elapsed < seconds:
        if not check_ui_events():
            return False
        remaining = max(0.0, seconds - elapsed)
        update_status(f"Waiting cooldown ({remaining:.1f}s)...")
        API.Pause(step)
        elapsed += step
    return check_ui_events()

# ==============================================================================
# Barding Engine (Provocation & Peacemaking)
# ==============================================================================

def handle_instrument_breakage() -> None:
    """Checks recent journal entries for broken instrument messages."""
    global total_instruments_broken
    entries = API.GetJournalEntries(2.0)
    j_text = [str(e.Text).lower() for e in entries] if entries else []
    if any(any(pat in t for pat in BROKEN_PATTERNS) for t in j_text):
        total_instruments_broken += 1
        API.SysMsg(f"[Trainer] Instrument broke! Spare instruments remaining: {count_instruments()}", HUE_WARN)


def execute_provocation() -> bool:
    """
    Executes a Provocation cycle:
    1. Invokes Provocation skill.
    2. Targets Creature 1 (or selects an instrument if prompted).
    3. Targets Creature 2 to incite combat.
    """
    global provoke_attempts

    if not validate_targets():
        return False

    if count_instruments() == 0:
        API.SysMsg("[Trainer] Out of musical instruments in backpack! Pausing.", HUE_ALERT)
        update_status("No Instruments")
        on_pause_clicked()
        return False

    update_status("Provoking...")
    API.ClearJournal()

    # Cancel any hanging target cursor
    if API.HasTarget():
        API.CancelTarget()
        API.Pause(0.2)

    API.UseSkill("Provocation")

    # Step 1: Wait for first target cursor
    if not API.WaitForTarget(timeout=TARGET_TIMEOUT):
        debug_msg("Provocation target cursor 1 did not appear.")
        return False

    # Check if server asked to select an instrument first
    if API.InJournal("what instrument") or API.InJournal("instrument to play"):
        inst = get_first_instrument()
        if inst:
            debug_msg(f"Targeting instrument 0x{inst.Serial:X}...")
            API.Target(inst.Serial)
            API.Pause(0.3)
            if not API.WaitForTarget(timeout=TARGET_TIMEOUT):
                return False

    # Target first creature
    API.Target(target1_serial)
    API.Pause(0.2)

    # Step 2: Wait for second target cursor
    if not API.WaitForTarget(timeout=TARGET_TIMEOUT):
        debug_msg("Provocation target cursor 2 did not appear.")
        return False

    # Target second creature
    API.Target(target2_serial)
    API.Pause(0.4)

    provoke_attempts += 1
    handle_instrument_breakage()
    update_stats()

    # Inspect results
    entries = API.GetJournalEntries(1.5)
    j_text = [str(e.Text).lower() for e in entries] if entries else []
    if any("succeeds in inciting" in t or "enraged" in t or "begin to fight" in t for t in j_text):
        API.SysMsg(f"[Trainer] Provocation successful! ({target1_name} vs {target2_name})", HUE_SUCCESS)
    elif any("fail to incite" in t for t in j_text):
        debug_msg("Provocation attempt failed.")

    return True


def execute_peacemaking() -> bool:
    """
    Executes a Peacemaking cycle:
    1. Invokes Peacemaking skill.
    2. Targets Creature 1 (or Creature 2, alternating) to calm them down and stop fighting.
    """
    global peace_attempts, peace_toggle

    if not validate_targets():
        return False

    if count_instruments() == 0:
        API.SysMsg("[Trainer] Out of musical instruments in backpack! Pausing.", HUE_ALERT)
        update_status("No Instruments")
        on_pause_clicked()
        return False

    # Alternate target between Target 1 and Target 2
    peace_target = target1_serial if not peace_toggle else target2_serial
    peace_target_name = target1_name if not peace_toggle else target2_name
    peace_toggle = not peace_toggle

    update_status(f"Peacing {peace_target_name}...")
    API.ClearJournal()

    if API.HasTarget():
        API.CancelTarget()
        API.Pause(0.2)

    API.UseSkill("Peacemaking")

    if not API.WaitForTarget(timeout=TARGET_TIMEOUT):
        debug_msg("Peacemaking target cursor did not appear.")
        return False

    # Check if server asked to select an instrument first
    if API.InJournal("what instrument") or API.InJournal("instrument to play"):
        inst = get_first_instrument()
        if inst:
            API.Target(inst.Serial)
            API.Pause(0.3)
            if not API.WaitForTarget(timeout=TARGET_TIMEOUT):
                return False

    API.Target(peace_target)
    API.Pause(0.4)

    peace_attempts += 1
    handle_instrument_breakage()
    update_stats()

    # Inspect results
    entries = API.GetJournalEntries(1.5)
    j_text = [str(e.Text).lower() for e in entries] if entries else []
    if any("calms down" in t or "soothed" in t or "stop fighting" in t or "peace" in t for t in j_text):
        API.SysMsg(f"[Trainer] Peacemaking successful on {peace_target_name}!", HUE_SUCCESS)
    elif any("fail to calm" in t or "fails" in t for t in j_text):
        debug_msg("Peacemaking attempt failed.")

    return True

# ==============================================================================
# Main Orchestration Loop
# ==============================================================================

def main():
    global target1_serial, target2_serial, target1_name, target2_name

    API.SysMsg(f"=== FesterUO Provoke & Peace Trainer v{SCRIPT_VERSION} ===", HUE_INFO)

    # 1. Check instruments
    insts = get_available_instruments()
    if not insts:
        API.SysMsg("[Trainer] WARNING: No musical instruments found in your backpack! Please acquire instruments.", HUE_ALERT)

    # 2. Initialize Gump & stats
    create_control_gump()
    update_stats()

    # 3. Prompt for targets if not already set
    if not target1_serial:
        API.SysMsg("[Trainer] Target FIRST creature to provoke/peace (or ESC to set via Gump)...", HUE_INFO)
        t1 = API.RequestTarget(timeout=8.0)
        if t1 and t1 != API.Player.Serial:
            target1_serial = t1
            mob1 = API.FindMobile(target1_serial)
            target1_name = (mob1.Name if mob1 else "") or f"0x{target1_serial:X}"
            API.SysMsg(f"[Trainer] Target 1 set: {target1_name}", HUE_SUCCESS)

    if not target2_serial:
        API.SysMsg("[Trainer] Target SECOND creature to provoke/peace (or ESC to set via Gump)...", HUE_INFO)
        t2 = API.RequestTarget(timeout=8.0)
        if t2 and t2 != API.Player.Serial:
            target2_serial = t2
            mob2 = API.FindMobile(target2_serial)
            target2_name = (mob2.Name if mob2 else "") or f"0x{target2_serial:X}"
            API.SysMsg(f"[Trainer] Target 2 set: {target2_name}", HUE_SUCCESS)

    update_stats()

    if not target1_serial or not target2_serial:
        API.SysMsg("[Trainer] Both targets must be set before training can begin. Click 'Set Target 1' and 'Set Target 2' on the Gump.", HUE_WARN)
        update_status("Needs Targets")
        on_pause_clicked()
    else:
        update_status("Running")
        API.SysMsg(f"[Trainer] Ready! Targets: {target1_name} and {target2_name}. Cooldown: {BARDING_COOLDOWN:.1f}s", HUE_SUCCESS)

    # Initial breather
    API.Pause(0.8)

    # 4. Core Provoke & Peace Loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Check target skill limits
        p_skill = API.GetSkill("Provocation")
        peace_sk = API.GetSkill("Peacemaking")
        m_skill = API.GetSkill("Musicianship")

        p_done = TARGET_PROVOKING_SKILL and p_skill and float(p_skill.Value) >= TARGET_PROVOKING_SKILL
        peace_done = TARGET_PEACEMAKING_SKILL and peace_sk and float(peace_sk.Value) >= TARGET_PEACEMAKING_SKILL
        music_done = TARGET_MUSICIANSHIP_SKILL and m_skill and float(m_skill.Value) >= TARGET_MUSICIANSHIP_SKILL

        if p_done and peace_done and music_done:
            API.SysMsg("[Trainer] Target skill goals reached! Congratulations!", HUE_SUCCESS)
            update_status("Target Reached")
            break

        # Step A: Execute Provocation
        if not p_done:
            execute_provocation()
            if not wait_with_ui(BARDING_COOLDOWN):
                break

        # Step B: Execute Peacemaking
        if not peace_done:
            execute_peacemaking()
            if not wait_with_ui(BARDING_COOLDOWN):
                break

    update_status("Stopped")
    dispose_gump()
    API.SysMsg(f"[Trainer] Finished. Total provokes: {provoke_attempts}, peaces: {peace_attempts}.", HUE_INFO)


def on_stop_hook():
    """Cleanup hook registered with API.OnStop."""
    global is_stopped
    is_stopped = True
    dispose_gump()


API.OnStop(on_stop_hook)

main()
