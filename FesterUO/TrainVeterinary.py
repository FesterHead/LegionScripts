"""
TrainVeterinary.py - Automated Veterinary Skill Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Autonomous and interactive Veterinary skill training script designed for TazUO.
    Supports two dedicated training architectures:
    1. Dual Pet Sparring Mode (Default): Prompts the player to target two sparring pets
       (e.g., horses, polar bears, ostards, or dragons). Commands them to spar, continuously
       monitors both health pools, and applies bandages to whichever pet has lower HP or is poisoned.
       Includes automatic emergency combat separation ("all stop" / "all follow me") if either
       pet falls below the emergency health threshold.
    2. Single Pet / Patient Mode: Prompts to target a single pet or creature. Continuously monitors
       its health, poison status, and resurrection needs, applying bandages whenever damaged.

Features:
    - Interactive Modern Dark Gump UI:
      * Live status updates (Idle, Healing Pet 1, Healing Pet 2, Curing Poison, Emergency Pause, Paused)
      * Real-time skill monitoring (Current skill, Cap, and total Skill Gains)
      * Live pet health gauges (HP %, Current/Max Hits)
      * Backpack bandage inventory counter with low-supply warnings
      * Running statistics counters (Total Heals, Cures, Resurrections)
      * Interactive Mode Toggle button (Sparring <-> Single Pet)
      * Interactive Pause / Resume and Stop buttons
    - Dual Pet Sparring Safety System:
      * Emergency Stop Threshold (default 30% HP): Disengages combat immediately if either pet drops low.
      * Safe Resume Threshold (default 85% HP): Automatically resumes sparring once both pets are fully healed.
    - Automatic Poison Curing & Ghost Pet Resurrection:
      * Prioritizes curing poisoned pets immediately before standard healing.
      * Detects bonded pet ghosts and applies bandages to resurrect (requires 80+ Veterinary & Lore).
    - Intelligent Bandage Timer:
      * Automatically calculates UO Dexterity-based bandage application delays or respects user overrides.
    - Full Loop & Lifecycle Safety:
      * Safe loops respecting API.StopRequested and client UI callbacks.
"""

import math
import time
from typing import Optional
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Primary training mode:
# "SPARRING"   - Coordinates two pets fighting each other, healing both continuously.
# "SINGLE"     - Monitors and heals a single pet or patient whenever damaged.
DEFAULT_MODE: str = "SPARRING"

# Skill targets:
# Set to a specific float (e.g. 100.0 or 120.0), or None to use your character's cap.
TARGET_CAP: Optional[float] = None

# Bandage delay configuration:
# If AUTO_BANDAGE_DELAY is True, calculates classic UO Dexterity-based delay.
# If False, uses FIXED_BANDAGE_DELAY (seconds).
AUTO_BANDAGE_DELAY: bool = True
FIXED_BANDAGE_DELAY: float = 2.0

# Minimum pause (seconds) between consecutive bandage applications
BANDAGE_COOLDOWN: float = 0.5

# Sparring Safety Thresholds (Percentage of Max HP):
# EMERGENCY_HP_PERCENT: If either pet drops below this, combat is stopped immediately.
# RESUME_HP_PERCENT: Sparring resumes once BOTH pets are healed back above this percentage.
EMERGENCY_HP_PERCENT: int = 30
RESUME_HP_PERCENT: int = 85

# Low bandage warning threshold in backpack
LOW_BANDAGE_THRESHOLD: int = 20

# Proximity threshold: UO requires being within 2 tiles of the pet to apply bandages
MAX_BANDAGE_DISTANCE: int = 2

# Pathfinding timeout in seconds (must be int)
PATHFIND_TIMEOUT: int = 4

# Bandage item graphic
BANDAGE_GRAPHIC: int = 0x0E21

# Enable verbose debug output to client console
DEBUG: bool = False


# ==============================================================================
# Runtime State
# ==============================================================================

current_mode: str = DEFAULT_MODE
is_paused: bool = False
is_stopped: bool = False
current_status: str = "Initializing..."

# Selected pet serials
pet1_serial: Optional[int] = None
pet2_serial: Optional[int] = None

# Sparring state
sparring_active: bool = False
emergency_holding: bool = False

# Statistics
total_heals: int = 0
total_cures: int = 0
total_resurrections: int = 0
start_skill_value: float = 0.0
last_skill_value: float = 0.0

# Gump control references
gump = None
lbl_status = None
lbl_skill = None
lbl_pet1 = None
lbl_pet2 = None
lbl_bandages = None
lbl_stats = None
btn_mode = None
btn_pause = None
btn_stop = None


# ==============================================================================
# Logging & Debugging
# ==============================================================================

def debug_msg(message: str) -> None:
    """Outputs debug message if DEBUG is enabled."""
    if DEBUG:
        API.SysMsg(f"[Veterinary:DEBUG] {message}")


# ==============================================================================
# Lifecycle Callbacks
# ==============================================================================

def on_stop() -> None:
    """Invoked when the script is stopped from the client UI."""
    dispose_gump()
    # Safety stop any active pet combat
    if current_mode == "SPARRING":
        API.Msg("all stop")
        API.Msg("all follow me")
    API.SysMsg("[Veterinary] Training script stopped.")

API.OnStop(on_stop)


def on_gump_disposed() -> None:
    """Invoked if the player closes the Gump by right-clicking."""
    global is_stopped, gump
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


# ==============================================================================
# Helper Utilities
# ==============================================================================

def get_bandage_count() -> int:
    """Counts total bandages in the player's main backpack and subcontainers."""
    try:
        bandages = API.FindType(BANDAGE_GRAPHIC, API.Backpack)
        if not bandages:
            return 0
        total = 0
        all_items = API.ItemsInContainer(API.Backpack) or []
        for item in all_items:
            if getattr(item, "Graphic", 0) == BANDAGE_GRAPHIC:
                total += getattr(item, "Amount", 1)
        return total if total > 0 else getattr(bandages, "Amount", 1)
    except Exception:
        bandage = API.FindType(BANDAGE_GRAPHIC, API.Backpack)
        return getattr(bandage, "Amount", 0) if bandage else 0


def calculate_bandage_delay() -> float:
    """Calculates bandage application timer based on player Dexterity."""
    if not AUTO_BANDAGE_DELAY:
        return FIXED_BANDAGE_DELAY

    dex = getattr(API.Player, "Dex", 100)
    # Standard UO Veterinary delay formula: max(2.0, (11.0 - floor(dex / 20)) * 0.5)
    calc_delay = max(2.0, (11.0 - math.floor(dex / 20.0)) * 0.5)
    return calc_delay


def get_mobile_distance(mob) -> int:
    """Calculates distance in tiles between player and mobile."""
    if not mob:
        return 999
    dist = getattr(mob, "Distance", None)
    if isinstance(dist, (int, float)):
        return int(dist)
    try:
        dx = abs(mob.X - API.Player.X)
        dy = abs(mob.Y - API.Player.Y)
        return max(dx, dy)
    except Exception:
        return 999


def ensure_range(mob, max_distance: int = MAX_BANDAGE_DISTANCE) -> bool:
    """Navigates player within max_distance tiles of the pet."""
    if not mob:
        return False

    dist = get_mobile_distance(mob)
    if dist <= max_distance:
        return True

    debug_msg(f"Approaching pet 0x{mob.Serial:X} (distance {dist} > {max_distance})...")
    API.PathfindEntity(mob.Serial, distance=max_distance, wait=False, timeout=PATHFIND_TIMEOUT, run=True)

    start_time = time.time()
    while not API.StopRequested and not is_stopped:
        if not process_ui_events():
            return False

        dist = get_mobile_distance(mob)
        if dist <= max_distance:
            return True

        if time.time() - start_time > PATHFIND_TIMEOUT:
            break

        API.Pause(0.2)

    return get_mobile_distance(mob) <= max_distance


def get_pet_health_info(serial: Optional[int]) -> Tuple[int, int, int, bool, bool]:
    """
    Returns (hits, hits_max, hp_percent, is_poisoned, is_dead) for a pet serial.
    """
    if not serial:
        return (0, 0, 100, False, False)

    mob = API.FindMobile(serial)
    if not mob:
        return (0, 0, 0, False, True)

    is_dead = getattr(mob, "IsDead", False) or getattr(mob, "IsGhost", False)
    is_poisoned = getattr(mob, "Poisoned", False)
    hits = getattr(mob, "Hits", 0)
    hits_max = getattr(mob, "HitsMax", 0)

    if hits_max > 0:
        pct = int((hits / hits_max) * 100)
    else:
        pct = 100

    return (hits, hits_max, pct, is_poisoned, is_dead)


# ==============================================================================
# Gump UI Implementation
# ==============================================================================

def update_status(text: str) -> None:
    """Updates the status display on the Gump."""
    global current_status
    current_status = text
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def update_stats() -> None:
    """Updates skill progression, pet health, and counters on the Gump."""
    # Skill progress
    skill_obj = API.GetSkill("Veterinary")
    cur_val = skill_obj.Value if skill_obj else 0.0
    cap_val = TARGET_CAP if TARGET_CAP is not None else (skill_obj.Cap if skill_obj else 100.0)
    gained = max(0.0, cur_val - start_skill_value)

    if lbl_skill:
        lbl_skill.Text = f"Veterinary: {cur_val:.1f} / {cap_val:.1f} (+{gained:.1f})"

    # Pet 1 Health Gauge
    if lbl_pet1:
        if pet1_serial:
            mob1 = API.FindMobile(pet1_serial)
            name1 = mob1.Name if mob1 and mob1.Name else f"0x{pet1_serial:X}"
            h1, hm1, pct1, pois1, dead1 = get_pet_health_info(pet1_serial)
            status_tag = " [POISON]" if pois1 else (" [DEAD]" if dead1 else "")
            lbl_pet1.Text = f"{name1}: {pct1}% ({h1}/{hm1}){status_tag}"
        else:
            lbl_pet1.Text = "Pet 1: [Click Target]"

    # Pet 2 Health Gauge
    if lbl_pet2:
        if current_mode == "SPARRING":
            if pet2_serial:
                mob2 = API.FindMobile(pet2_serial)
                name2 = mob2.Name if mob2 and mob2.Name else f"0x{pet2_serial:X}"
                h2, hm2, pct2, pois2, dead2 = get_pet_health_info(pet2_serial)
                status_tag = " [POISON]" if pois2 else (" [DEAD]" if dead2 else "")
                lbl_pet2.Text = f"{name2}: {pct2}% ({h2}/{hm2}){status_tag}"
            else:
                lbl_pet2.Text = "Pet 2: [Click Target]"
        else:
            lbl_pet2.Text = "Mode: Single Pet Healing"

    # Bandage supply
    if lbl_bandages:
        b_count = get_bandage_count()
        lbl_bandages.Text = f"Bandages: {b_count}"

    # General statistics
    if lbl_stats:
        lbl_stats.Text = f"Heals: {total_heals} | Cures: {total_cures} | Rez: {total_resurrections}"


def on_mode_clicked() -> None:
    """Toggles between Sparring and Single Pet modes."""
    global current_mode, pet2_serial, sparring_active
    if current_mode == "SPARRING":
        current_mode = "SINGLE"
        pet2_serial = None
        if sparring_active:
            API.Msg("all stop")
            API.Msg("all follow me")
            sparring_active = False
        API.SysMsg("[Veterinary] Switched to Single Pet Healing mode.")
    else:
        current_mode = "SPARRING"
        API.SysMsg("[Veterinary] Switched to Dual Pet Sparring mode.")

    if btn_mode:
        btn_mode.Text = "Mode: Sparring" if current_mode == "SPARRING" else "Mode: Single Pet"
    update_status("Mode changed")


def on_pause_clicked() -> None:
    """Pauses or resumes the script."""
    global is_paused
    is_paused = not is_paused
    if btn_pause:
        btn_pause.Text = "Resume" if is_paused else "Pause"
    update_status("Paused" if is_paused else "Running")
    API.SysMsg(f"[Veterinary] {'Paused' if is_paused else 'Resumed'}.")


def on_stop_clicked() -> None:
    """Stops the script execution."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.SysMsg("[Veterinary] Stop requested via Gump.")
    API.Stop()


def create_control_gump() -> None:
    """Constructs the interactive dark Gump UI."""
    global gump, lbl_status, lbl_skill, lbl_pet1, lbl_pet2, lbl_bandages, lbl_stats, btn_mode, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(True, True, False)
    gump.SetPos(60, 420)

    # Dark background panel
    bg = API.Gumps.CreateGumpColorBox(0.85, "#151515")
    bg.SetRect(0, 0, 310, 230)
    gump.Add(bg)

    # Title & Author
    lbl_title = API.Gumps.CreateGumpLabel("Veterinary Trainer", 68)
    lbl_title.SetPos(12, 8)
    gump.Add(lbl_title)

    lbl_author = API.Gumps.CreateGumpLabel("by FesterHead", 996)
    lbl_author.SetPos(215, 8)
    gump.Add(lbl_author)

    # Status Label
    lbl_status = API.Gumps.CreateGumpLabel(f"Status: {current_status}", 53)
    lbl_status.SetPos(12, 28)
    gump.Add(lbl_status)

    # Skill Progress Label
    lbl_skill = API.Gumps.CreateGumpLabel("Veterinary: 0.0 / 0.0 (+0.0)", 88)
    lbl_skill.SetPos(12, 48)
    gump.Add(lbl_skill)

    # Pet 1 & 2 Gauges
    lbl_pet1 = API.Gumps.CreateGumpLabel("Pet 1: [Not Set]", 64)
    lbl_pet1.SetPos(12, 68)
    gump.Add(lbl_pet1)

    lbl_pet2 = API.Gumps.CreateGumpLabel("Pet 2: [Not Set]", 64)
    lbl_pet2.SetPos(12, 88)
    gump.Add(lbl_pet2)

    # Bandages and Stats
    lbl_bandages = API.Gumps.CreateGumpLabel("Bandages: 0", 996)
    lbl_bandages.SetPos(12, 108)
    gump.Add(lbl_bandages)

    lbl_stats = API.Gumps.CreateGumpLabel("Heals: 0 | Cures: 0 | Rez: 0", 996)
    lbl_stats.SetPos(12, 128)
    gump.Add(lbl_stats)

    # Mode Selector Button
    btn_mode = API.Gumps.CreateSimpleButton("Mode: Sparring" if current_mode == "SPARRING" else "Mode: Single Pet", 140, 26)
    btn_mode.SetPos(10, 154)
    API.Gumps.AddControlOnClick(btn_mode, on_mode_clicked)
    gump.Add(btn_mode)

    # Pause / Resume Button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 70, 26)
    btn_pause.SetPos(155, 154)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Stop Button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 70, 26)
    btn_stop.SetPos(230, 154)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Hint text
    lbl_hint = API.Gumps.CreateGumpLabel("Maintains healing, cures poison & manages sparring", 900)
    lbl_hint.SetPos(12, 192)
    gump.Add(lbl_hint)

    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)
    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely closes and disposes the Gump."""
    global gump
    if gump and not getattr(gump, "IsDisposed", False):
        try:
            gump.Dispose()
        except Exception:
            pass


def process_ui_events() -> bool:
    """Processes UI callbacks and handles pause states."""
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


# ==============================================================================
# Bandaging & Veterinary Logic
# ==============================================================================

def apply_bandage_to_pet(target_serial: int) -> bool:
    """
    Applies a bandage to the designated pet, monitoring the application timer
    and updating heals/cures/resurrections.
    """
    global total_heals, total_cures, total_resurrections, last_skill_value

    mob = API.FindMobile(target_serial)
    if not mob:
        return False

    # Ensure player is within reach
    if not ensure_range(mob, MAX_BANDAGE_DISTANCE):
        debug_msg(f"Could not reach pet 0x{target_serial:X} to bandage.")
        return False

    bandage = API.FindType(BANDAGE_GRAPHIC, API.Backpack)
    if not bandage:
        update_status("OUT OF BANDAGES!")
        API.SysMsg("[Veterinary] ERROR: Out of bandages in backpack!")
        API.Pause(2.0)
        return False

    mob_name = mob.Name or "Pet"
    is_dead = getattr(mob, "IsDead", False) or getattr(mob, "IsGhost", False)
    is_poisoned = getattr(mob, "Poisoned", False)

    if is_dead:
        update_status(f"Resurrecting {mob_name}...")
        debug_msg(f"Resurrecting {mob_name} (0x{target_serial:X})...")
    elif is_poisoned:
        update_status(f"Curing {mob_name}...")
        debug_msg(f"Curing poison on {mob_name} (0x{target_serial:X})...")
    else:
        update_status(f"Healing {mob_name}...")
        debug_msg(f"Applying bandage to {mob_name} (0x{target_serial:X})...")

    # Clear journal and start bandaging
    API.ClearJournal()
    API.UseObject(bandage.Serial)

    if not API.WaitForTarget(timeout=2):
        debug_msg("Bandage target cursor timed out.")
        return False

    API.Target(target_serial)

    # Wait for the bandage timer to conclude
    app_delay = calculate_bandage_delay()
    start_time = time.time()

    while (time.time() - start_time) < app_delay:
        if not process_ui_events():
            return False

        # Check early finishes in journal
        if API.InJournal("You apply the bandages") or API.InJournal("You finish applying"):
            break
        if API.InJournal("You heal") or API.InJournal("You cure") or API.InJournal("resurrect"):
            break
        if API.InJournal("That being is not damaged") or API.InJournal("does not appear"):
            break

        API.Pause(0.2)

    # Inspect outcomes
    if is_dead:
        total_resurrections += 1
    elif is_poisoned:
        total_cures += 1
    else:
        total_heals += 1

    # Check for Veterinary skill gain
    skill_obj = API.GetSkill("Veterinary")
    if skill_obj and skill_obj.Value > last_skill_value:
        gain = skill_obj.Value - last_skill_value
        API.SysMsg(f"[Veterinary] Skill Gain: +{gain:.1f}! New Value: {skill_obj.Value:.1f} / {skill_obj.Cap:.1f}")
        last_skill_value = skill_obj.Value

    update_stats()
    API.Pause(BANDAGE_COOLDOWN)
    return True


# ==============================================================================
# Sparring Management
# ==============================================================================

def start_sparring() -> None:
    """Commands Pet 1 and Pet 2 to spar against each other."""
    global sparring_active
    if not pet1_serial or not pet2_serial:
        return

    mob1 = API.FindMobile(pet1_serial)
    mob2 = API.FindMobile(pet2_serial)
    if not mob1 or not mob2:
        return

    name1 = mob1.Name or "Pet 1"
    name2 = mob2.Name or "Pet 2"

    API.SysMsg(f"[Veterinary] Initiating sparring between {name1} and {name2}...")
    update_status("Initiating Sparring...")

    # Command Pet 1 to attack Pet 2
    API.Msg(f"{name1} kill")
    if API.WaitForTarget(timeout=3):
        API.Target(pet2_serial)
        API.Pause(0.5)

    # Command Pet 2 to attack Pet 1
    API.Msg(f"{name2} kill")
    if API.WaitForTarget(timeout=3):
        API.Target(pet1_serial)
        API.Pause(0.5)

    sparring_active = True


def stop_sparring() -> None:
    """Issues safety commands to disengage pet combat immediately."""
    global sparring_active
    update_status("EMERGENCY STOP: Halting Combat...")
    API.Msg("all stop")
    API.Pause(0.3)
    API.Msg("all follow me")
    API.Pause(0.5)
    sparring_active = False


def run_sparring_cycle() -> None:
    """Executes a cycle of dual pet sparring, health monitoring, and triage."""
    global pet1_serial, pet2_serial, emergency_holding

    # Verify both pets are selected
    if not pet1_serial:
        update_status("Select Pet 1...")
        API.SysMsg("[Veterinary] Target Pet 1 for sparring...")
        sel1 = API.RequestTarget(timeout=10)
        if not sel1 or sel1 == 0:
            API.SysMsg("[Veterinary] Target 1 selection cancelled.")
            API.Pause(1.0)
            return
        pet1_serial = sel1
        update_stats()

    if not pet2_serial:
        update_status("Select Pet 2...")
        API.SysMsg("[Veterinary] Target Pet 2 for sparring...")
        sel2 = API.RequestTarget(timeout=10)
        if not sel2 or sel2 == 0:
            API.SysMsg("[Veterinary] Target 2 selection cancelled.")
            API.Pause(1.0)
            return
        pet2_serial = sel2
        update_stats()

    h1, hm1, pct1, pois1, dead1 = get_pet_health_info(pet1_serial)
    h2, hm2, pct2, pois2, dead2 = get_pet_health_info(pet2_serial)

    # 1. Emergency Safety Stop Check:
    # If either pet is below EMERGENCY_HP_PERCENT, disengage combat immediately
    if pct1 < EMERGENCY_HP_PERCENT or pct2 < EMERGENCY_HP_PERCENT or dead1 or dead2:
        if sparring_active:
            API.SysMsg(f"[Veterinary] WARNING: Pet critically low (P1: {pct1}%, P2: {pct2}%). Disengaging!")
            stop_sparring()
        emergency_holding = True

    # 2. If in emergency holding: heal both pets until above RESUME_HP_PERCENT
    if emergency_holding:
        update_status(f"Safety Healing (P1: {pct1}%, P2: {pct2}%)...")
        if pct1 >= RESUME_HP_PERCENT and pct2 >= RESUME_HP_PERCENT and not dead1 and not dead2:
            emergency_holding = False
            API.SysMsg("[Veterinary] Both pets restored above safe threshold. Resuming sparring.")
            start_sparring()
            return

    # 3. If sparring is not active and not holding: start sparring
    if not sparring_active and not emergency_holding:
        start_sparring()

    # 4. Triage Healing Selection:
    # Priority:
    #   A. Dead / Ghost pet
    #   B. Poisoned pet
    #   C. Lower HP percentage
    target_to_heal = None

    if dead1:
        target_to_heal = pet1_serial
    elif dead2:
        target_to_heal = pet2_serial
    elif pois1:
        target_to_heal = pet1_serial
    elif pois2:
        target_to_heal = pet2_serial
    elif pct1 < 100 or pct2 < 100:
        target_to_heal = pet1_serial if pct1 <= pct2 else pet2_serial

    if target_to_heal:
        apply_bandage_to_pet(target_to_heal)
    else:
        update_status("Sparring in progress...")
        API.Pause(0.3)


# ==============================================================================
# Single Pet Healing Management
# ==============================================================================

def run_single_pet_cycle() -> None:
    """Monitors and applies bandages to a single patient pet."""
    global pet1_serial

    if not pet1_serial:
        update_status("Select Patient...")
        API.SysMsg("[Veterinary] Target the pet or creature you wish to monitor & heal...")
        sel = API.RequestTarget(timeout=10)
        if not sel or sel == 0:
            API.SysMsg("[Veterinary] Target selection cancelled.")
            API.Pause(1.0)
            return
        pet1_serial = sel
        mob = API.FindMobile(pet1_serial)
        name = mob.Name if mob and mob.Name else f"0x{pet1_serial:X}"
        API.SysMsg(f"[Veterinary] Patient locked: {name}.")
        update_stats()

    mob = API.FindMobile(pet1_serial)
    if not mob:
        API.SysMsg("[Veterinary] Patient missing or out of radar.")
        pet1_serial = None
        API.Pause(1.0)
        return

    h, hm, pct, pois, dead = get_pet_health_info(pet1_serial)

    # Check if healing is needed
    if pct < 100 or pois or dead:
        apply_bandage_to_pet(pet1_serial)
    else:
        update_status(f"Patient {mob.Name or 'Pet'} healthy (100%)")
        API.Pause(0.5)


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    global start_skill_value, last_skill_value, is_stopped

    skill_obj = API.GetSkill("Veterinary")
    if not skill_obj:
        API.SysMsg("[Veterinary] Could not retrieve Veterinary skill information.")
        return

    cap = TARGET_CAP if TARGET_CAP is not None else skill_obj.Cap
    start_skill_value = skill_obj.Value
    last_skill_value = start_skill_value

    if start_skill_value >= cap:
        API.SysMsg(f"[Veterinary] Skill already at cap ({start_skill_value:.1f} / {cap:.1f}). Nothing to train!")
        return

    # Check skill lock direction
    if skill_obj.Lock != 0:
        API.SysMsg("[Veterinary] WARNING: Veterinary skill lock is not set to UP (▲)!")

    # Check bandages
    initial_bandages = get_bandage_count()
    if initial_bandages == 0:
        API.SysMsg("[Veterinary] WARNING: No bandages detected in backpack! Restock before starting.")

    # Initialize Gump UI
    create_control_gump()
    update_stats()
    update_status("Ready")

    API.SysMsg(
        f"[Veterinary] Starting Veterinary training (Current: {start_skill_value:.1f}, Goal: {cap:.1f}, Mode: {current_mode})..."
    )

    while not API.StopRequested and not is_stopped:
        if not process_ui_events():
            break

        # Check current skill progress
        skill_obj = API.GetSkill("Veterinary")
        if not skill_obj:
            break

        cur_val = skill_obj.Value

        # Check completion
        if cur_val >= cap:
            update_status("Goal Reached!")
            API.SysMsg(f"[Veterinary] Congratulations! Reached goal of {cur_val:.1f} / {cap:.1f}.")
            break

        # Check bandage supply warning
        b_count = get_bandage_count()
        if b_count == 0:
            update_status("NO BANDAGES!")
            API.SysMsg("[Veterinary] Out of bandages! Halting.")
            break
        elif b_count < LOW_BANDAGE_THRESHOLD:
            debug_msg(f"Low bandages warning: {b_count} left.")

        # Execute training mode cycle
        if current_mode == "SPARRING":
            run_sparring_cycle()
        else:
            run_single_pet_cycle()

        API.Pause(0.1)

    # Cleanup
    if current_mode == "SPARRING" and sparring_active:
        API.Msg("all stop")
        API.Msg("all follow me")

    update_status("Finished")
    dispose_gump()
    API.SysMsg(
        f"[Veterinary] Script ended. Total Heals: {total_heals}, Cures: {total_cures}, Resurrections: {total_resurrections}."
    )


main()
