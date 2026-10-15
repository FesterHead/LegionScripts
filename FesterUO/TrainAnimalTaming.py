"""
TrainAnimalTaming.py - Automated Animal Taming Skill Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Autonomous and interactive Animal Taming training script designed for TazUO.
    Supports two primary training workflows selectable via configuration or in-game Gump:
    1. Wild Roam Mode: Autonomously scans the surrounding wilderness for valid tamable
       creatures matching the player's skill level, pathfinds to them, actively follows
       them during the taming process to maintain the 2-tile proximity requirement,
       and automatically releases them upon success.
    2. Target Trainer Mode: Continuously tames, releases, and retames a designated or trapped
       creature (such as a bull, bear, or horse penned in a house or corral) until the
       target skill cap is reached.

Features:
    - Interactive Modern Dark Gump UI:
      * Live status updates (Scanning, Approaching, Taming, Releasing, Paused, Complete)
      * Real-time skill monitoring (Current skill, Cap, and total Skill Gains)
      * Statistics counters (Successful Tames, Total Attempts)
      * Runtime Mode toggle button (Wild Roam <-> Target Trainer)
      * Runtime Auto-Release toggle button (ON <-> OFF)
      * Interactive Pause / Resume and Stop buttons
    - Active Range Pursuit:
      * Intelligently tracks moving/fleeing animals during the 10-12s taming countdown
        and issues micro-pathfinding steps to keep the player within the 2-tile limit.
    - Comprehensive Tamable Creature Database:
      * Built-in graphic and name mappings covering low, mid, and high tier tamables
        with baseline minimum skill thresholds.
    - Automatic Pet Release & Gump Handling:
      * Dispatches context menu release or command release, automatically confirming
        any client release verification gump.
    - Safety & Peacemaking Support:
      * Optional Peacemaking integration to pacify hostile or agitated wildlife.
      * Emergency self-healing checks (Bandages / Greater Heal) if damaged.
    - Strict Loop Safety:
      * Safe loops respecting API.StopRequested and client lifecycle callbacks.
"""

import math
import time
from typing import Dict, List, Optional, Set, Tuple
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Primary training mode:
# "WILD_ROAM"     - Scans for and hunts wild animals in the area to tame and release.
# "TARGET_TRAIN"  - Prompts to target a single trapped/penned animal to tame & retame.
DEFAULT_MODE: str = "WILD_ROAM"

# Skill targets:
# Set to a specific float (e.g. 100.0 or 120.0), or None to use your character's cap.
TARGET_CAP: Optional[float] = None

# Automatically release creature upon successful taming (standard skill training).
AUTO_RELEASE: bool = True

# Wild scan radius in tiles around the player
SEARCH_RADIUS: int = 18

# Max duration (seconds) to wait for a single taming cycle to conclude
TAME_DELAY: float = 12.0

# General delay (seconds) between actions / retries
ACTION_DELAY: float = 0.8

# Proximity threshold: UO requires being within 2 tiles to start and maintain taming
MAX_APPROACH_DISTANCE: int = 2

# Pathfinding timeout in seconds (must be int)
PATHFIND_TIMEOUT: int = 6

# Optional Peacemaking:
# If True, attempts to use Peacemaking on hostile or angry animals before taming.
USE_PEACEMAKING: bool = True

# Optional Animal Lore:
# If True, inspects the target with Animal Lore before taming for dual training.
USE_ANIMAL_LORE: bool = True

# Integrated Veterinary:
# If True, automatically applies bandages to damaged or poisoned creatures using
# Veterinary skill to train Veterinary concurrently with Animal Taming.
ENABLE_VETERINARY: bool = True
VET_BANDAGE_DELAY: float = 2.0  # Bandage application timer in seconds

# Emergency Self-Healing:
# Automatically uses bandages or Greater Heal if player hits drop below this percent.
ENABLE_SAFETY_HEAL: bool = True
HEAL_HP_PERCENT: int = 50

# Bandage graphic for self-healing and veterinary
BANDAGE_GRAPHIC: int = 0x0E21

# Enable verbose debug output to client console
DEBUG: bool = False


# ==============================================================================
# Tamable Creatures Database & Baseline Skill Levels
# ==============================================================================

# Format: graphic -> (name, min_skill)
TAMABLE_DATABASE: Dict[int, Tuple[str, float]] = {
    # 0.0 - 30.0 (Low tier / Passives)
    0x00D0: ("Chicken", 0.0),
    0x0006: ("Bird", 0.0),
    0x00CD: ("Rabbit", 0.0),
    0x00CF: ("Sheep", 11.1),
    0x00DF: ("Sheep", 11.1),
    0x00CB: ("Pig", 11.1),
    0x00D1: ("Goat", 17.1),
    0x0058: ("Mountain Goat", 17.1),
    0x00ED: ("Hind", 23.1),
    0x0014: ("Boar", 29.1),
    0x00D8: ("Cow", 11.1),
    0x00E7: ("Cow", 11.1),

    # 30.0 - 60.0 (Mid tier)
    0x00E1: ("Timber Wolf", 23.1),
    0x00C8: ("Horse", 29.1),
    0x00E2: ("Horse", 29.1),
    0x00E4: ("Horse", 29.1),
    0x00CC: ("Horse", 29.1),
    0x00D2: ("Desert Ostard", 29.1),
    0x00DB: ("Forest Ostard", 29.1),
    0x00DC: ("Llama", 35.1),
    0x00D3: ("Black Bear", 35.1),
    0x00D5: ("Polar Bear", 35.1),
    0x00DD: ("Walrus", 35.1),
    0x00A7: ("Brown Bear", 41.1),
    0x001E: ("Cougar", 41.1),
    0x00D6: ("Panther", 53.1),
    0x0019: ("Gray Wolf", 53.1),
    0x00D4: ("Grizzly Bear", 59.1),
    0x001C: ("Giant Spider", 59.1),
    0x00EA: ("Great Hart", 59.1),

    # 60.0 - 90.0+ (High tier)
    0x001B: ("White Wolf", 65.1),
    0x00E8: ("Bull", 71.1),
    0x00E9: ("Bull", 71.1),
    0x00DA: ("Frenzied Ostard", 77.1),
    0x0050: ("Giant Toad", 77.1),
    0x00BB: ("Ridgeback", 83.1),
    0x003C: ("Drake", 84.3),
    0x003D: ("Drake", 84.3),
    0x000C: ("Dragon", 93.9),
    0x003B: ("Dragon", 93.9),
    0x00B4: ("White Wyrm", 96.3),
    0x0114: ("Cu Sidhe", 101.1),
    0x0074: ("Nightmare", 95.1),
}

# Substring matches for custom shards or unnamed mobiles
TAMABLE_KEYWORDS: List[Tuple[str, float]] = [
    ("chicken", 0.0),
    ("bird", 0.0),
    ("rabbit", 0.0),
    ("sheep", 11.1),
    ("pig", 11.1),
    ("goat", 17.1),
    ("hind", 23.1),
    ("boar", 29.1),
    ("cow", 11.1),
    ("timber wolf", 23.1),
    ("horse", 29.1),
    ("ostard", 29.1),
    ("llama", 35.1),
    ("black bear", 35.1),
    ("polar bear", 35.1),
    ("walrus", 35.1),
    ("brown bear", 41.1),
    ("cougar", 41.1),
    ("panther", 53.1),
    ("gray wolf", 53.1),
    ("grizzly", 59.1),
    ("great hart", 59.1),
    ("white wolf", 65.1),
    ("bull", 71.1),
    ("ridgeback", 83.1),
    ("drake", 84.3),
    ("dragon", 93.9),
    ("white wyrm", 96.3),
    ("cu sidhe", 101.1),
    ("nightmare", 95.1),
]

# Taming Journal Triggers
JOURNAL_SUCCESS = [
    "accept you as master",
    "accept you as its master",
    "you tame the creature",
    "seems to accept",
    "it seems to accept you",
    "looks tame",
]

JOURNAL_FAIL = [
    "you fail to tame",
    "failed to tame",
    "fail to tame the creature",
]

JOURNAL_ANGRY = [
    "too angry to continue taming",
    "animal looks angry",
    "lost its trust",
    "has lost its trust",
    "the creature is too angry",
    "cannot be tamed in its current state",
]

JOURNAL_TOO_FAR = [
    "too far away to continue taming",
    "you are too far away",
    "too far away",
    "that is too far away",
]

JOURNAL_CANNOT_TAME = [
    "that is not something you can tame",
    "already tame",
    "someone else is already taming",
    "have no chance of taming",
    "cannot be tamed",
]

JOURNAL_BUSY = [
    "must wait to perform another action",
    "wait a few moments",
    "you must wait",
]


# ==============================================================================
# Script Runtime State
# ==============================================================================

current_mode: str = DEFAULT_MODE
auto_release_enabled: bool = AUTO_RELEASE
is_paused: bool = False
is_stopped: bool = False
current_status: str = "Initializing..."

total_tamed: int = 0
total_attempts: int = 0
total_vet_heals: int = 0
start_skill_value: float = 0.0
last_skill_value: float = 0.0
start_vet_value: float = 0.0
last_vet_value: float = 0.0

# Set of mobile serials to ignore (already tamed & released this session)
ignored_mobiles: Set[int] = set()

# Targeted creature serial for TARGET_TRAIN mode
target_trainer_serial: Optional[int] = None

# Gump control references
gump = None
lbl_status = None
lbl_skill = None
lbl_vet = None
lbl_stats = None
btn_mode = None
btn_release = None
btn_pause = None
btn_stop = None


# ==============================================================================
# Logging and Debugging
# ==============================================================================

def debug_msg(message: str) -> None:
    """Outputs debug message if DEBUG is enabled."""
    if DEBUG:
        API.SysMsg(f"[Taming:DEBUG] {message}")


# ==============================================================================
# Lifecycle Callbacks
# ==============================================================================

def on_stop() -> None:
    """Invoked when the script is stopped from the client UI."""
    dispose_gump()
    API.SysMsg("[Animal Taming] Training script stopped.")

API.OnStop(on_stop)


def on_gump_disposed() -> None:
    """Invoked if the player closes the Gump by right-clicking."""
    global is_stopped, gump
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


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
    """Updates skill progression and taming stats on the Gump."""
    skill_obj = API.GetSkill("Animal Taming")
    cur_val = skill_obj.Value if skill_obj else 0.0
    cap_val = TARGET_CAP if TARGET_CAP is not None else (skill_obj.Cap if skill_obj else 100.0)
    gained = max(0.0, cur_val - start_skill_value)

    if lbl_skill:
        lbl_skill.Text = f"Taming: {cur_val:.1f} / {cap_val:.1f} (+{gained:.1f})"

    if lbl_vet:
        vet_obj = API.GetSkill("Veterinary")
        cur_vet = vet_obj.Value if vet_obj else 0.0
        cap_vet = vet_obj.Cap if vet_obj else 100.0
        vet_gained = max(0.0, cur_vet - start_vet_value)
        lbl_vet.Text = f"Vet: {cur_vet:.1f} / {cap_vet:.1f} (+{vet_gained:.1f}) | Heals: {total_vet_heals}"

    if lbl_stats:
        lbl_stats.Text = f"Tamed: {total_tamed} | Attempts: {total_attempts}"


def on_mode_clicked() -> None:
    """Switches between Wild Roam and Target Trainer modes."""
    global current_mode, target_trainer_serial
    if current_mode == "WILD_ROAM":
        current_mode = "TARGET_TRAIN"
        target_trainer_serial = None
        API.SysMsg("[Animal Taming] Switched to Target Trainer mode.")
    else:
        current_mode = "WILD_ROAM"
        API.SysMsg("[Animal Taming] Switched to Wild Roam mode.")

    if btn_mode:
        btn_mode.Text = "Mode: Wild Roam" if current_mode == "WILD_ROAM" else "Mode: Target Trainer"
    update_status("Mode changed")


def on_release_clicked() -> None:
    """Toggles automatic release behavior."""
    global auto_release_enabled
    auto_release_enabled = not auto_release_enabled
    if btn_release:
        btn_release.Text = f"Auto-Release: {'ON' if auto_release_enabled else 'OFF'}"
    API.SysMsg(f"[Animal Taming] Auto-Release: {'Enabled' if auto_release_enabled else 'Disabled'}")


def on_pause_clicked() -> None:
    """Pauses or resumes the script."""
    global is_paused
    is_paused = not is_paused
    if btn_pause:
        btn_pause.Text = "Resume" if is_paused else "Pause"
    update_status("Paused" if is_paused else "Running")
    API.SysMsg(f"[Animal Taming] {'Paused' if is_paused else 'Resumed'}.")


def on_stop_clicked() -> None:
    """Stops the script execution."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.SysMsg("[Animal Taming] Stop requested via Gump.")
    API.Stop()


def create_control_gump() -> None:
    """Builds the interactive modern dark Gump UI."""
    global gump, lbl_status, lbl_skill, lbl_vet, lbl_stats, btn_mode, btn_release, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(True, True, False)
    gump.SetPos(60, 420)

    # Background panel (dark aesthetic with rounded look)
    bg = API.Gumps.CreateGumpColorBox(0.85, "#151515")
    bg.SetRect(0, 0, 310, 215)
    gump.Add(bg)

    # Title & Author
    lbl_title = API.Gumps.CreateGumpLabel("Animal Tamer", 68)
    lbl_title.SetPos(12, 8)
    gump.Add(lbl_title)

    lbl_author = API.Gumps.CreateGumpLabel("by FesterHead", 996)
    lbl_author.SetPos(215, 8)
    gump.Add(lbl_author)

    # Status Label
    lbl_status = API.Gumps.CreateGumpLabel(f"Status: {current_status}", 53)
    lbl_status.SetPos(12, 28)
    gump.Add(lbl_status)

    # Skill Progress Labels
    lbl_skill = API.Gumps.CreateGumpLabel("Taming: 0.0 / 0.0 (+0.0)", 88)
    lbl_skill.SetPos(12, 48)
    gump.Add(lbl_skill)

    lbl_vet = API.Gumps.CreateGumpLabel("Vet: 0.0 / 0.0 (+0.0) | Heals: 0", 64)
    lbl_vet.SetPos(12, 66)
    gump.Add(lbl_vet)

    # Statistics Label
    lbl_stats = API.Gumps.CreateGumpLabel("Tamed: 0 | Attempts: 0", 996)
    lbl_stats.SetPos(12, 86)
    gump.Add(lbl_stats)

    # Mode Selector Button
    btn_mode = API.Gumps.CreateSimpleButton("Mode: Wild Roam" if current_mode == "WILD_ROAM" else "Mode: Target Trainer", 140, 26)
    btn_mode.SetPos(10, 114)
    API.Gumps.AddControlOnClick(btn_mode, on_mode_clicked)
    gump.Add(btn_mode)

    # Auto-Release Toggle Button
    btn_release = API.Gumps.CreateSimpleButton(f"Auto-Release: {'ON' if auto_release_enabled else 'OFF'}", 140, 26)
    btn_release.SetPos(160, 114)
    API.Gumps.AddControlOnClick(btn_release, on_release_clicked)
    gump.Add(btn_release)

    # Pause / Resume Button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 140, 26)
    btn_pause.SetPos(10, 146)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Stop Button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 140, 26)
    btn_stop.SetPos(160, 146)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Help text
    lbl_hint = API.Gumps.CreateGumpLabel("Maintains 2-tile range, vet heals & releases", 900)
    lbl_hint.SetPos(14, 182)
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
    """Processes Gump events and handles paused execution."""
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
# Helper Utilities & Combat Defense
# ==============================================================================

def get_mobile_distance(mob) -> int:
    """Calculates Chebyshev distance in tiles between player and mobile."""
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


def check_emergency_healing() -> None:
    """Applies emergency healing if player health falls below threshold."""
    if not ENABLE_SAFETY_HEAL:
        return

    player = API.Player
    if not player or getattr(player, "HitsMax", 0) <= 0:
        return

    hp_pct = (player.Hits / player.HitsMax) * 100
    if hp_pct < HEAL_HP_PERCENT:
        debug_msg(f"Low health ({hp_pct:.1f}%). Attempting emergency heal...")
        # Check bandages first
        bandage = API.FindType(BANDAGE_GRAPHIC, API.Backpack)
        if bandage:
            API.ClearJournal()
            API.UseObject(bandage.Serial)
            if API.WaitForTarget(timeout=2):
                API.TargetSelf()
                API.Pause(0.5)
                return

        # Fallback to Greater Heal if player has Magery
        magery = API.GetSkill("Magery")
        if magery and magery.Value >= 40.0 and player.Mana >= 11:
            API.ClearJournal()
            API.CastSpell("Greater Heal")
            if API.WaitForTarget(timeout=3):
                API.TargetSelf()
                API.Pause(1.0)


def attempt_peacemaking(target_serial: int) -> None:
    """Uses Peacemaking on the target if configured and available."""
    if not USE_PEACEMAKING:
        return

    peace_skill = API.GetSkill("Peacemaking")
    if not peace_skill or peace_skill.Value < 20.0:
        return

    debug_msg(f"Attempting Peacemaking on 0x{target_serial:X}...")
    API.ClearJournal()
    API.UseSkill("Peacemaking")
    if API.WaitForTarget(timeout=2):
        API.Target(target_serial)
        API.Pause(1.0)


def attempt_animal_lore(target_serial: int) -> None:
    """Uses Animal Lore on the target for dual skill training."""
    if not USE_ANIMAL_LORE:
        return

    lore_skill = API.GetSkill("Animal Lore")
    if not lore_skill or lore_skill.Value >= lore_skill.Cap:
        return

    debug_msg(f"Using Animal Lore on 0x{target_serial:X}...")
    API.ClearJournal()
    API.UseSkill("Animal Lore")
    if API.WaitForTarget(timeout=2):
        API.Target(target_serial)
        API.Pause(1.0)
        # Close any animal lore gump if opened
        if API.WaitForGump(delay=1.0):
            API.CloseGump()


def attempt_veterinary(target_serial: int) -> bool:
    """
    Applies bandages to an injured or poisoned creature using Veterinary skill.
    Returns True if a bandage was applied, False otherwise.
    """
    global total_vet_heals, last_vet_value
    if not ENABLE_VETERINARY:
        return False

    mob = API.FindMobile(target_serial)
    if not mob or getattr(mob, "IsDead", False):
        return False

    # Check if creature is damaged or poisoned
    is_damaged = (getattr(mob, "HitsMax", 0) > 0 and getattr(mob, "Hits", 0) < getattr(mob, "HitsMax", 0))
    is_poisoned = getattr(mob, "Poisoned", False)

    if not is_damaged and not is_poisoned:
        return False

    # Ensure in range
    if get_mobile_distance(mob) > MAX_APPROACH_DISTANCE:
        approach_target(mob, MAX_APPROACH_DISTANCE)

    bandage = API.FindType(BANDAGE_GRAPHIC, API.Backpack)
    if not bandage:
        debug_msg("No bandages in backpack for Veterinary.")
        return False

    mob_name = mob.Name or "Creature"
    update_status(f"Vet Healing {mob_name}...")
    debug_msg(f"Applying bandage to {mob_name} (0x{target_serial:X})...")

    API.ClearJournal()
    API.UseObject(bandage.Serial)
    if API.WaitForTarget(timeout=2):
        API.Target(target_serial)
        API.Pause(VET_BANDAGE_DELAY)
        total_vet_heals += 1
        update_stats()

        # Check for Veterinary skill gain
        vet_skill = API.GetSkill("Veterinary")
        if vet_skill and vet_skill.Value > last_vet_value:
            gain = vet_skill.Value - last_vet_value
            API.SysMsg(f"[Veterinary] Skill Gain: +{gain:.1f}! New Value: {vet_skill.Value:.1f} / {vet_skill.Cap:.1f}")
            last_vet_value = vet_skill.Value
            update_stats()

        return True

    return False


# ==============================================================================
# Wildlife Discovery & Validation
# ==============================================================================

def get_creature_min_skill(mob) -> float:
    """Returns the baseline minimum taming skill required for the mobile."""
    if not mob:
        return 0.0

    graphic = getattr(mob, "Graphic", 0)
    if graphic in TAMABLE_DATABASE:
        return TAMABLE_DATABASE[graphic][1]

    name = (getattr(mob, "Name", "") or "").lower()
    for kw, min_skill in TAMABLE_KEYWORDS:
        if kw in name:
            return min_skill

    # Default to 0.0 if unknown
    return 0.0


def is_valid_tame_target(mob, player_taming_val: float) -> bool:
    """Checks whether a mobile is a valid target for wild taming."""
    if not mob or mob.Serial == API.Player.Serial:
        return False

    # Ignore dead or ghost mobiles
    if getattr(mob, "IsDead", False) or getattr(mob, "IsGhost", False):
        return False

    # Ignore invulnerable / vendor mobiles
    if getattr(mob, "IsYellowHits", False):
        return False

    # Ignore already tamed player pets / mounts
    if getattr(mob, "IsRenamable", False):
        return False

    # Ignore mobiles tamed/released earlier this session
    if mob.Serial in ignored_mobiles:
        return False

    graphic = getattr(mob, "Graphic", 0)
    name = (getattr(mob, "Name", "") or "").lower()

    # Verify if creature is in our tamable database
    is_tamable = graphic in TAMABLE_DATABASE or any(kw in name for kw, _ in TAMABLE_KEYWORDS)
    if not is_tamable:
        return False

    # Skill level eligibility check: creature min skill must be reachable by player
    # (Allow creatures up to 10 points above current skill for training challenge)
    min_skill = get_creature_min_skill(mob)
    if min_skill > (player_taming_val + 10.0):
        return False

    return True


def find_wild_taming_target(player_taming_val: float) -> Optional[object]:
    """Scans for the closest valid wild creature to tame."""
    try:
        all_mobiles = API.GetAllMobiles(distance=SEARCH_RADIUS)
        if not all_mobiles:
            all_mobiles = API.NearestMobiles(
                [
                    API.Notoriety.Innocent,
                    API.Notoriety.Gray,
                    API.Notoriety.Unknown,
                    API.Notoriety.Criminal,
                ],
                maxDistance=SEARCH_RADIUS,
            ) or []

        candidates = []
        for m in all_mobiles:
            if not m or m.Serial == API.Player.Serial:
                continue

            dist = get_mobile_distance(m)
            if dist > SEARCH_RADIUS:
                continue

            if is_valid_tame_target(m, player_taming_val):
                candidates.append((dist, m))

        if not candidates:
            return None

        # Sort closest first
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]
    except Exception as ex:
        debug_msg(f"Error scanning for wild target: {ex}")
        return None


# ==============================================================================
# Approach & Range Maintenance
# ==============================================================================

def approach_target(mob, max_distance: int = MAX_APPROACH_DISTANCE) -> bool:
    """
    Approaches the target mobile until within max_distance tiles.
    Returns True if successfully in range, False otherwise.
    """
    if not mob:
        return False

    dist = get_mobile_distance(mob)
    if dist <= max_distance:
        return True

    debug_msg(f"Approaching target 0x{mob.Serial:X} (distance {dist} > {max_distance})...")
    update_status(f"Approaching {mob.Name or 'Creature'}...")

    # Issue pathfinding towards entity
    API.PathfindEntity(mob.Serial, distance=max_distance, wait=False, timeout=PATHFIND_TIMEOUT, run=True)

    start_time = time.time()
    while not API.StopRequested and not is_stopped:
        if not process_ui_events():
            return False

        dist = get_mobile_distance(mob)
        if dist <= max_distance:
            return True

        if time.time() - start_time > PATHFIND_TIMEOUT:
            debug_msg("Approach timed out.")
            break

        API.Pause(0.2)

    return get_mobile_distance(mob) <= max_distance


# ==============================================================================
# Pet Release Automation
# ==============================================================================

def release_pet(target_serial: int) -> bool:
    """
    Releases a newly tamed pet via context menu or speech commands,
    confirming any release verification dialog.
    """
    mob = API.FindMobile(target_serial)
    if not mob:
        return True

    mob_name = mob.Name or "Pet"
    update_status(f"Releasing {mob_name}...")
    debug_msg(f"Attempting to release pet {mob_name} (0x{target_serial:X})...")

    # Command pet to stop and come adjacent so we are well within context menu range
    API.Msg("all stop")
    API.Pause(0.2)
    API.Msg("all follow me")
    API.Pause(0.4)

    # Ensure player is adjacent (1 tile) to pet
    approach_target(mob, 1)

    for attempt in range(1, 4):
        if API.StopRequested or is_stopped:
            return False

        # Check if already released
        mob = API.FindMobile(target_serial)
        if not mob or not getattr(mob, "IsRenamable", False):
            API.SysMsg(f"[Animal Taming] Pet {mob_name} successfully released.")
            return True

        API.ClearJournal()

        # Method 1: Context Menu "Release"
        debug_msg(f"Release attempt #{attempt}: sending context menu 'Release'...")
        context_sent = False
        try:
            context_sent = API.ContextMenu(target_serial, "Release", timeout=2.5)
        except Exception as ex:
            debug_msg(f"ContextMenu exception: {ex}")

        # Method 2: If context menu failed or not available, try speech
        if not context_sent:
            debug_msg(f"Release attempt #{attempt}: sending speech command...")
            if mob_name and mob_name != "Wild Animal" and mob_name != "Creature":
                API.Msg(f"{mob_name} release")
            else:
                API.Msg("all release")

            # In case the server responds with a target cursor for "all release"
            if API.WaitForTarget(timeout=1.0):
                API.Target(target_serial)

        # Handle release confirmation dialog
        if API.WaitForGump(delay=2.0):
            debug_msg("Release confirmation gump detected.")
            gump_content = API.GetGumpContents()
            debug_msg(f"Gump text: {gump_content}")

            # Standard RunUO / ServUO / ModernUO / OSI PetReleaseGump:
            # Button 2 = OK / Confirm (AddButton(..., 2, GumpButtonType.Reply, 0))
            # Button 1 = Cancel
            debug_msg("Sending confirm response (button 2)...")
            API.ReplyGump(2)
            API.Pause(0.6)

            # Check if gump is still open (some custom shards use button 1 for OK)
            if API.WaitForGump(delay=0.6):
                debug_msg("Gump still open, attempting button 1...")
                API.ReplyGump(1)
                API.Pause(0.6)

        # Wait and verify journal or mobile state
        API.Pause(0.5)

        for msg in [
            "you have released your pet",
            "has been released",
            "released",
            "decides to take its chances",
            "looks up at you with sadness",
            "returns to the wild",
            "no longer following you",
        ]:
            if API.InJournal(msg):
                API.SysMsg(f"[Animal Taming] Pet {mob_name} successfully released.")
                return True

        mob = API.FindMobile(target_serial)
        if not mob or not getattr(mob, "IsRenamable", False):
            API.SysMsg(f"[Animal Taming] Pet {mob_name} successfully released.")
            return True

        debug_msg(f"Release attempt #{attempt} did not complete. Retrying...")
        API.Pause(0.5)

    mob = API.FindMobile(target_serial)
    if not mob or not getattr(mob, "IsRenamable", False):
        API.SysMsg(f"[Animal Taming] Pet {mob_name} successfully released.")
        return True

    API.SysMsg(f"[Animal Taming] WARNING: Could not release {mob_name}. Check if your shard uses a custom gump or command.")
    return False


# ==============================================================================
# Core Taming Cycle
# ==============================================================================

def execute_tame_attempt(target_serial: int) -> str:
    """
    Executes a single Animal Taming attempt on the given mobile serial.
    Actively tracks target position to maintain the 2-tile requirement.

    Returns one of:
      "SUCCESS", "FAIL", "ANGRY", "TOO_FAR", "CANNOT_TAME", "COOLDOWN", "DEAD", "ABORT"
    """
    global total_attempts

    mob = API.FindMobile(target_serial)
    if not mob or getattr(mob, "IsDead", False):
        return "DEAD"

    # Pre-taming preparation
    check_emergency_healing()

    if USE_ANIMAL_LORE:
        attempt_animal_lore(target_serial)

    # Ensure in range before starting
    if not approach_target(mob, MAX_APPROACH_DISTANCE):
        return "TOO_FAR"

    mob_name = mob.Name or "Creature"
    update_status(f"Taming {mob_name}...")
    debug_msg(f"Initiating taming on {mob_name} (0x{target_serial:X})...")

    API.ClearJournal()
    API.UseSkill("Animal Taming")

    if not API.WaitForTarget(timeout=5):
        debug_msg("Taming target cursor timed out.")
        if API.InJournal("must wait to perform another action") or API.InJournal("wait a few moments"):
            return "COOLDOWN"
        return "FAIL"

    API.Target(target_serial)
    total_attempts += 1
    update_stats()

    # Active monitoring loop: wait for taming resolution while pursuing moving animals
    start_time = time.time()
    last_pursuit_time = 0.0

    while (time.time() - start_time) < TAME_DELAY:
        if not process_ui_events():
            return "ABORT"

        check_emergency_healing()

        # Check if mobile is dead or gone
        mob = API.FindMobile(target_serial)
        if not mob or getattr(mob, "IsDead", False):
            return "DEAD"

        # Check if mobile became tamed (renamable flag changed)
        if getattr(mob, "IsRenamable", False):
            return "SUCCESS"

        # Active pursuit: ensure player remains within 2 tiles of hopping / fleeing animal
        dist = get_mobile_distance(mob)
        if dist > MAX_APPROACH_DISTANCE:
            now = time.time()
            if (now - last_pursuit_time) > 0.8:
                debug_msg(f"Animal moving away (dist {dist}). Pursuing...")
                API.PathfindEntity(target_serial, distance=1, wait=False, timeout=3, run=True)
                last_pursuit_time = now

        # Journal Inspections
        for msg in JOURNAL_SUCCESS:
            if API.InJournal(msg):
                return "SUCCESS"

        for msg in JOURNAL_ANGRY:
            if API.InJournal(msg):
                return "ANGRY"

        for msg in JOURNAL_TOO_FAR:
            if API.InJournal(msg):
                return "TOO_FAR"

        for msg in JOURNAL_CANNOT_TAME:
            if API.InJournal(msg):
                return "CANNOT_TAME"

        for msg in JOURNAL_FAIL:
            if API.InJournal(msg):
                return "FAIL"

        if API.InJournal("must wait to perform another action"):
            return "COOLDOWN"

        API.Pause(0.25)

    # If taming delay expired without specific journal response, inspect mobile state
    mob = API.FindMobile(target_serial)
    if mob and getattr(mob, "IsRenamable", False):
        return "SUCCESS"

    return "FAIL"


# ==============================================================================
# Main Training Loops
# ==============================================================================

def run_wild_roam_cycle(player_taming_val: float) -> None:
    """Executes one cycle of wild animal scanning and taming."""
    update_status("Searching for Wildlife...")
    target_mob = find_wild_taming_target(player_taming_val)

    if not target_mob:
        update_status("No wild targets nearby. Waiting...")
        debug_msg(f"No valid wild targets found within {SEARCH_RADIUS} tiles.")
        API.Pause(1.5)
        return

    mob_serial = target_mob.Serial
    mob_name = target_mob.Name or "Wild Animal"
    API.SysMsg(f"[Animal Taming] Spotted {mob_name} (0x{mob_serial:X}). Approaching...")

    # Approach
    if not approach_target(target_mob, MAX_APPROACH_DISTANCE):
        debug_msg(f"Could not reach {mob_name}. Skipping...")
        ignored_mobiles.add(mob_serial)
        return

    # Attempt Tame
    outcome = execute_tame_attempt(mob_serial)
    debug_msg(f"Tame outcome for 0x{mob_serial:X}: {outcome}")

    if outcome == "SUCCESS":
        global total_tamed
        total_tamed += 1
        update_stats()
        API.SysMsg(f"[Animal Taming] Successfully tamed {mob_name}!")

        # Apply Veterinary healing if creature was damaged before releasing
        if ENABLE_VETERINARY:
            attempt_veterinary(mob_serial)

        if auto_release_enabled:
            API.Pause(0.5)
            release_pet(mob_serial)

        # Mark as handled so we don't immediately re-target it
        ignored_mobiles.add(mob_serial)
        API.Pause(ACTION_DELAY)

    elif outcome == "ANGRY":
        API.SysMsg(f"[Animal Taming] {mob_name} is too angry!")
        attempt_peacemaking(mob_serial)
        API.Pause(2.0)

    elif outcome == "TOO_FAR":
        debug_msg("Animal escaped out of range.")
        API.Pause(0.5)

    elif outcome == "CANNOT_TAME":
        API.SysMsg(f"[Animal Taming] Cannot tame {mob_name}. Skipping...")
        ignored_mobiles.add(mob_serial)
        API.Pause(0.5)

    elif outcome == "COOLDOWN":
        debug_msg("Skill cooldown active. Pausing...")
        API.Pause(1.5)

    elif outcome == "FAIL":
        debug_msg(f"Failed tame attempt on {mob_name}. Retrying or continuing...")
        API.Pause(ACTION_DELAY)


def run_target_trainer_cycle() -> None:
    """Executes repetitive taming and releasing on a single designated target."""
    global target_trainer_serial

    # Verify target selection
    if not target_trainer_serial:
        update_status("Select Target...")
        API.SysMsg("[Animal Taming] Please target the creature you wish to train on...")
        selected = API.RequestTarget(timeout=10)
        if not selected or selected == 0:
            API.SysMsg("[Animal Taming] Target selection cancelled or timed out. Returning to Wild Roam.")
            on_mode_clicked()
            return
        target_trainer_serial = selected
        mob = API.FindMobile(target_trainer_serial)
        name = mob.Name if mob and mob.Name else f"0x{target_trainer_serial:X}"
        API.SysMsg(f"[Animal Taming] Target locked: {name}.")

    mob = API.FindMobile(target_trainer_serial)
    if not mob or getattr(mob, "IsDead", False):
        API.SysMsg("[Animal Taming] Target creature is dead or missing.")
        target_trainer_serial = None
        API.Pause(1.0)
        return

    # Check for Veterinary healing before taming if damaged
    if ENABLE_VETERINARY:
        attempt_veterinary(target_trainer_serial)

    # Approach if needed
    if not approach_target(mob, MAX_APPROACH_DISTANCE):
        debug_msg("Target creature out of range.")
        API.Pause(1.0)
        return

    # Attempt Tame
    outcome = execute_tame_attempt(target_trainer_serial)
    debug_msg(f"Target trainer outcome: {outcome}")

    if outcome == "SUCCESS":
        global total_tamed
        total_tamed += 1
        update_stats()
        API.SysMsg("[Animal Taming] Successfully tamed target creature!")

        # Apply Veterinary healing if creature was damaged
        if ENABLE_VETERINARY:
            attempt_veterinary(target_trainer_serial)

        if auto_release_enabled:
            API.Pause(0.5)
            release_pet(target_trainer_serial)
            # Brief delay for server state synchronization
            API.Pause(1.5)

    elif outcome == "ANGRY":
        API.SysMsg("[Animal Taming] Creature is angry! Waiting for anger to subside...")
        attempt_peacemaking(target_trainer_serial)
        API.Pause(3.0)

    elif outcome == "COOLDOWN":
        API.Pause(1.5)

    elif outcome == "FAIL":
        API.Pause(ACTION_DELAY)


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    global start_skill_value, last_skill_value, start_vet_value, last_vet_value, is_stopped

    skill_obj = API.GetSkill("Animal Taming")
    if not skill_obj:
        API.SysMsg("[Animal Taming] Could not retrieve Animal Taming skill information.")
        return

    cap = TARGET_CAP if TARGET_CAP is not None else skill_obj.Cap
    start_skill_value = skill_obj.Value
    last_skill_value = start_skill_value

    vet_obj = API.GetSkill("Veterinary")
    if vet_obj:
        start_vet_value = vet_obj.Value
        last_vet_value = start_vet_value

    if start_skill_value >= cap:
        API.SysMsg(f"[Animal Taming] Skill already at cap ({start_skill_value:.1f} / {cap:.1f}). Nothing to train!")
        return

    # Check skill lock direction
    if skill_obj.Lock != 0:
        API.SysMsg("[Animal Taming] WARNING: Animal Taming skill lock is not set to UP (▲)!")

    # Initialize Gump UI
    create_control_gump()
    update_stats()
    update_status("Starting...")

    API.SysMsg(
        f"[Animal Taming] Starting training (Current: {start_skill_value:.1f}, Goal: {cap:.1f}, Mode: {current_mode})..."
    )

    while not API.StopRequested and not is_stopped:
        if not process_ui_events():
            break

        # Check current skill progress
        skill_obj = API.GetSkill("Animal Taming")
        if not skill_obj:
            break

        cur_val = skill_obj.Value

        # Check for skill gain announcements
        if cur_val > last_skill_value:
            gain = cur_val - last_skill_value
            API.SysMsg(f"[Animal Taming] Skill Gain: +{gain:.1f}! New Value: {cur_val:.1f} / {cap:.1f}")
            last_skill_value = cur_val
            update_stats()

        # Check for Veterinary skill gain announcements
        vet_obj = API.GetSkill("Veterinary")
        if vet_obj and vet_obj.Value > last_vet_value:
            vet_gain = vet_obj.Value - last_vet_value
            API.SysMsg(f"[Veterinary] Skill Gain: +{vet_gain:.1f}! New Value: {vet_obj.Value:.1f} / {vet_obj.Cap:.1f}")
            last_vet_value = vet_obj.Value
            update_stats()

        # Check completion
        if cur_val >= cap:
            update_status("Goal Reached!")
            API.SysMsg(f"[Animal Taming] Congratulations! Reached goal of {cur_val:.1f} / {cap:.1f}.")
            break

        # Execute training mode cycle
        if current_mode == "WILD_ROAM":
            run_wild_roam_cycle(cur_val)
        else:
            run_target_trainer_cycle()

        API.Pause(0.1)

    update_status("Finished")
    dispose_gump()
    API.SysMsg(f"[Animal Taming] Script ended. Total Tamed: {total_tamed}, Total Attempts: {total_attempts}, Total Vet Heals: {total_vet_heals}.")


main()
