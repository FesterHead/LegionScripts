"""
TrainMusicianship.py - Automated Musicianship Skill Training Script with Interactive Control Gump

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Fully automated Musicianship skill training script for TazUO featuring:
    - Multi-Instrument Auto-Detection:
        * Automatically scans the player's backpack for any valid musical instrument:
          Lute, Lap Harp, Standing Harp, Drum, Tambourine, Bamboo Flute, Fire Horn, Aud-Char.
        * Displays the current active instrument name and total spare instruments in backpack.
    - Seamless Instrument Recycling & Breakage Recovery:
        * Actively monitors journal messages and backpack contents for broken or exhausted instruments.
        * Immediately switches to the next available instrument in the backpack without interrupting training.
    - Automated Restock Container Integration:
        * Allows setting a restock container (chest, satchel, crate, or pouch) via script config
          or dynamically in-game via the "Set Restock" button on the Gump.
        * When backpack instrument reserves drop to zero, automatically opens the restock container
          and pulls fresh instruments into the backpack.
        * If all instruments are depleted, safely pauses and prompts the player to restock,
          keeping the Gump alive and ready to resume.
    - Skill Progression & Milestone Gain Tracking:
        * Displays real-time Musicianship skill level, character skill cap, and session gain (+X.X).
        * Announces skill gains with in-game system messages.
        * Stops cleanly upon reaching the configured TARGET_SKILL or character cap.
    - Intelligent Cooldown & Anti-Spam Management:
        * Uses standard UO instrument cooldown delay (PLAY_DELAY, default 6.0s).
        * Detects server "must wait" journal cooldown responses and dynamically handles delays.
    - Interactive Control Gump:
        * Real-time training status (Playing, Waiting, Restocking, Paused, Out of Instruments, Complete).
        * Live Musicianship skill and total session gain.
        * Current instrument type and backpack count.
        * Played and Broken counters.
        * Restock Container status indicator.
        * Interactive Pause / Resume, Set Restock, and Stop buttons.
"""

from typing import Optional, List, Any
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Script version
SCRIPT_VERSION: str = "1.0.1"

# Target skill level to stop training (e.g. 100.0 for GM, 120.0 for Legendary).
# Set to None to automatically train until your character's skill cap.
TARGET_SKILL: Optional[float] = None

# Delay in seconds between playing instruments.
# Standard OSI/UO instrument cooldown is ~5.0 - 6.0 seconds.
PLAY_DELAY: float = 6.0

# Number of instruments to maintain in backpack when restocking from a container
RESTOCK_AMOUNT: int = 5

# Optional default serial for an instrument restock container (e.g. 0x4012ABCD).
# Set to None to configure in-game using the "Set Restock" button on the Gump.
RESTOCK_CONTAINER_SERIAL: Optional[int] = None

# System message hues
HUE_INFO: int = 68      # Cyan / Light Blue
HUE_GAIN: int = 63      # Bright Green
HUE_WARN: int = 53      # Yellow / Gold
HUE_ERROR: int = 32     # Red

# Enable verbose debug logging to client console
DEBUG: bool = False

# ==============================================================================
# Musical Instrument Definitions
# ==============================================================================

INSTRUMENT_GRAPHICS = {
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

ALL_INSTRUMENT_GRAPHICS = set(INSTRUMENT_GRAPHICS.keys())

# Journal patterns indicating instrument breakage
BROKEN_PATTERNS = [
    "broke your instrument",
    "instrument broke",
    "your instrument has broken",
    "broke into pieces",
    "worn out",
    "destroyed",
]

# Journal patterns indicating skill / action cooldown wait
WAIT_PATTERNS = [
    "must wait to perform another action",
    "must wait to use another skill",
    "must wait a few moments to play again",
    "must wait to play again",
    "wait a few moments",
]

# ==============================================================================
# Global State
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_instrument = None
lbl_counts = None
lbl_restock = None

btn_pause = None
btn_restock = None
btn_stop = None

restock_serial: Optional[int] = RESTOCK_CONTAINER_SERIAL
active_instrument_serial: Optional[int] = None

is_paused: bool = False
is_stopped: bool = False

total_played: int = 0
total_broken: int = 0

initial_skill: Optional[float] = None
last_reported_skill: Optional[float] = None

# ==============================================================================
# UI & Gump Management
# ==============================================================================

def update_status(text: str) -> None:
    """Updates the Gump status display."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def update_stats() -> None:
    """Refreshes skill, instrument count, counters, and restock indicators on the Gump."""
    global last_reported_skill, initial_skill
    global lbl_skill, lbl_instrument, lbl_counts, lbl_restock

    # 1. Musicianship Skill
    skill_obj = API.GetSkill("Musicianship")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        if initial_skill is None:
            initial_skill = val

        gain_total = val - initial_skill
        gain_str = f" (+{gain_total:.1f})" if gain_total > 0.0 else ""
        lbl_skill.Text = f"Musicianship: {val:.1f} / {cap:.1f}{gain_str}"

        if last_reported_skill is not None and val > last_reported_skill:
            gain_step = val - last_reported_skill
            API.SysMsg(f"[Musicianship] Skill gain +{gain_step:.1f}! New skill: {val:.1f} / {cap:.1f}", HUE_GAIN)

        last_reported_skill = val

    # 2. Instruments in Backpack
    bp_instruments = get_backpack_instruments()
    bp_count = len(bp_instruments)
    current_name = "None"
    if active_instrument_serial:
        for inst in bp_instruments:
            if inst.Serial == active_instrument_serial:
                current_name = INSTRUMENT_GRAPHICS.get(inst.Graphic, "Instrument")
                break
        if current_name == "None" and bp_count > 0:
            current_name = INSTRUMENT_GRAPHICS.get(bp_instruments[0].Graphic, "Instrument")

    if lbl_instrument:
        lbl_instrument.Text = f"Instrument: {current_name} (BP: {bp_count})"

    # 3. Counters
    if lbl_counts:
        lbl_counts.Text = f"Played: {total_played:,} | Broken: {total_broken:,}"

    # 4. Restock Container indicator
    if lbl_restock:
        if restock_serial:
            lbl_restock.Text = f"Restock Box: Set (0x{restock_serial:X})"
        else:
            lbl_restock.Text = "Restock Box: Not Set"


def on_pause_clicked() -> None:
    """Callback when the Pause/Resume button is clicked."""
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("[Musicianship] Trainer paused." if is_paused else "[Musicianship] Trainer resumed.", HUE_WARN)


def on_restock_clicked() -> None:
    """Allows the player to target an instrument restock container."""
    global restock_serial
    API.SysMsg("[Musicianship] Target container with spare instruments (or press ESC to clear)...", HUE_INFO)
    target = API.RequestTarget(timeout=10.0)
    if target and target != API.Player.Serial and target != API.Backpack:
        restock_serial = target
        API.SysMsg(f"[Musicianship] Restock container set to: 0x{restock_serial:X}", HUE_INFO)
    else:
        restock_serial = None
        API.SysMsg("[Musicianship] Restock container cleared.", HUE_WARN)
    update_stats()


def on_stop_clicked() -> None:
    """Callback when the Stop button is clicked."""
    global is_stopped
    is_stopped = True
    update_status("Stopping...")
    API.Stop()


def on_gump_disposed() -> None:
    """Callback when the Gump window is closed by right-click."""
    global is_stopped
    if not is_stopped and not API.StopRequested:
        is_stopped = True
        API.Stop()


def create_control_gump() -> None:
    """Initializes and renders the interactive Musicianship Trainer Gump."""
    global gump, lbl_status, lbl_skill, lbl_instrument, lbl_counts, lbl_restock
    global btn_pause, btn_restock, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(120, 120, 285, 175)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 285, 175)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("Musicianship Trainer", 53)
    title.SetPos(10, 8)
    gump.Add(title)
    lbl_author = API.Gumps.CreateGumpLabel(f"by FesterHead v{SCRIPT_VERSION}", 996)
    lbl_author.SetPos(150, 8)
    gump.Add(lbl_author)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 30)
    gump.Add(lbl_status)

    # Skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Musicianship: -- / --", 996)
    lbl_skill.SetPos(10, 50)
    gump.Add(lbl_skill)

    # Active Instrument label
    lbl_instrument = API.Gumps.CreateGumpLabel("Instrument: Searching...", 996)
    lbl_instrument.SetPos(10, 70)
    gump.Add(lbl_instrument)

    # Counts label
    lbl_counts = API.Gumps.CreateGumpLabel("Played: 0 | Broken: 0", 996)
    lbl_counts.SetPos(10, 90)
    gump.Add(lbl_counts)

    # Restock Box label
    lbl_restock = API.Gumps.CreateGumpLabel("Restock Box: Not Set", 996)
    lbl_restock.SetPos(10, 110)
    gump.Add(lbl_restock)

    # Pause button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 72, 22)
    btn_pause.SetPos(10, 138)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Set Restock button
    btn_restock = API.Gumps.CreateSimpleButton("Restock", 76, 22)
    btn_restock.SetPos(92, 138)
    API.Gumps.AddControlOnClick(btn_restock, on_restock_clicked)
    gump.Add(btn_restock)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 72, 22)
    btn_stop.SetPos(178, 138)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Handle right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely cleans up the Gump window upon script stop."""
    global gump
    if gump and not getattr(gump, "IsDisposed", False):
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes UI clicks, stats updates, and handles pause loops."""
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

    if btn_restock and getattr(btn_restock, "HasBeenClicked", lambda: False)():
        on_restock_clicked()

    while is_paused and not API.StopRequested and not is_stopped:
        API.ProcessCallbacks()
        API.Pause(0.1)
        update_stats()

        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            on_pause_clicked()
            break
        if btn_restock and getattr(btn_restock, "HasBeenClicked", lambda: False)():
            on_restock_clicked()

    return not is_stopped and not API.StopRequested


def wait_with_ui(seconds: float) -> bool:
    """Waits for specified seconds in small slices while processing UI events."""
    elapsed = 0.0
    step = 0.1
    while elapsed < seconds:
        if not check_ui_events():
            return False
        API.Pause(step)
        elapsed += step
    return check_ui_events()


# ==============================================================================
# Helper Functions - Instruments & Restocking
# ==============================================================================

def debug_msg(message: str) -> None:
    """Prints debug message if DEBUG is enabled."""
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def get_backpack_instruments() -> List[Any]:
    """Finds all musical instruments in the player's backpack."""
    if not API.Backpack:
        return []
    items = API.ItemsInContainer(API.Backpack, recursive=True) or []
    return [item for item in items if item.Graphic in ALL_INSTRUMENT_GRAPHICS]


def get_current_or_next_instrument() -> Optional[Any]:
    """Retrieves the active instrument, or selects the first available instrument in backpack."""
    global active_instrument_serial

    instruments = get_backpack_instruments()
    if not instruments:
        active_instrument_serial = None
        return None

    # If the active instrument still exists in backpack, continue using it
    if active_instrument_serial:
        for inst in instruments:
            if inst.Serial == active_instrument_serial:
                return inst

    # Pick the next instrument in backpack
    next_inst = instruments[0]
    active_instrument_serial = next_inst.Serial
    inst_name = INSTRUMENT_GRAPHICS.get(next_inst.Graphic, "Instrument")
    API.SysMsg(f"[Musicianship] Now using {inst_name} (Serial: 0x{next_inst.Serial:X}).", HUE_INFO)
    return next_inst


def check_for_breakage() -> bool:
    """Inspects recent journal entries to determine if an instrument broke."""
    global active_instrument_serial, total_broken

    for pattern in BROKEN_PATTERNS:
        if API.InJournal(pattern):
            total_broken += 1
            API.SysMsg("[Musicianship] An instrument broke! Switching to next instrument...", HUE_WARN)
            active_instrument_serial = None
            return True
    return False


def restock_instruments_from_container() -> bool:
    """
    Attempts to pull fresh instruments from the designated restock container
    into the player's backpack.
    """
    global restock_serial
    if not restock_serial or not API.Backpack:
        return False

    update_status("Restocking instruments...")
    API.SysMsg(f"[Musicianship] Restocking instruments from container 0x{restock_serial:X}...", HUE_INFO)

    # Open container to sync contents
    API.UseObject(restock_serial)
    API.Pause(0.5)

    if not check_ui_events():
        return False

    container_items = API.ItemsInContainer(restock_serial, recursive=False) or []
    restock_candidates = [item for item in container_items if item.Graphic in ALL_INSTRUMENT_GRAPHICS]

    if not restock_candidates:
        API.SysMsg("[Musicianship] No instruments found in restock container!", HUE_WARN)
        return False

    needed = RESTOCK_AMOUNT - len(get_backpack_instruments())
    if needed <= 0:
        return True

    moved_count = 0
    for item in restock_candidates[:needed]:
        if not check_ui_events():
            return False

        API.MoveItem(item.Serial, API.Backpack, 0)
        moved_count += 1
        API.Pause(0.65)

    API.SysMsg(f"[Musicianship] Restocked {moved_count} instrument(s) into backpack.", HUE_INFO)
    update_stats()
    return moved_count > 0


# ==============================================================================
# Lifecycle Callbacks
# ==============================================================================

def on_stop() -> None:
    """Invoked when the script is stopped manually or finishes."""
    dispose_gump()
    API.SysMsg("[Musicianship] Training script stopped.", HUE_WARN)

API.OnStop(on_stop)

# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    global total_played, is_paused

    skill_obj = API.GetSkill("Musicianship")
    if not skill_obj:
        API.SysMsg("[Musicianship] Error: Could not retrieve Musicianship skill information.", HUE_ERROR)
        return

    cap = TARGET_SKILL if TARGET_SKILL is not None else float(skill_obj.Cap)
    current_val = float(skill_obj.Value)

    if current_val >= cap:
        API.SysMsg(f"[Musicianship] Skill already at or above goal ({current_val:.1f} / {cap:.1f}). Nothing to train!", HUE_INFO)
        return

    create_control_gump()
    update_stats()
    update_status("Starting...")

    API.SysMsg(f"[Musicianship v{SCRIPT_VERSION}] Training started (Current: {current_val:.1f}, Goal: {cap:.1f}, Delay: {PLAY_DELAY}s).", HUE_INFO)

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Check skill completion
        skill_obj = API.GetSkill("Musicianship")
        if not skill_obj:
            API.SysMsg("[Musicianship] Lost skill reference.", HUE_ERROR)
            break

        current_val = float(skill_obj.Value)
        if current_val >= cap:
            update_status("Complete!")
            update_stats()
            API.SysMsg(f"[Musicianship] *** Training complete! Reached {current_val:.1f} / {cap:.1f} ***", HUE_GAIN)
            break

        # Locate instrument
        instrument = get_current_or_next_instrument()

        # If backpack has no instruments, attempt restock
        if not instrument and restock_serial:
            restock_instruments_from_container()
            instrument = get_current_or_next_instrument()

        # If still no instruments, pause and prompt player
        if not instrument:
            update_status("Out of Instruments")
            update_stats()
            API.SysMsg("[Musicianship] Out of instruments! Add instruments to backpack (or set Restock Box) and click Resume.", HUE_WARN)
            is_paused = True
            if btn_pause:
                btn_pause.SetText("Resume")
            if not check_ui_events():
                break
            continue

        inst_name = INSTRUMENT_GRAPHICS.get(instrument.Graphic, "Instrument")
        update_status(f"Playing {inst_name}...")
        debug_msg(f"Double-clicking {inst_name} (0x{instrument.Serial:X})...")

        API.ClearJournal()
        API.UseObject(instrument.Serial)
        total_played += 1
        update_stats()

        # Brief pause to register server response in journal
        if not wait_with_ui(0.5):
            break

        # Check if the instrument broke on this play
        check_for_breakage()

        # Check for skill cooldown wait messages
        cooldown_extra = 0.0
        for pattern in WAIT_PATTERNS:
            if API.InJournal(pattern):
                debug_msg("Cooldown wait message detected in journal. Adding 1.0s delay...")
                cooldown_extra = 1.0
                break

        # Wait remaining cooldown while keeping UI responsive
        remaining_delay = max(0.0, PLAY_DELAY - 0.5) + cooldown_extra
        update_status("Waiting cooldown...")
        if not wait_with_ui(remaining_delay):
            break

    update_status("Finished")
    update_stats()
    API.SysMsg(f"[Musicianship] Training ended. Total Played: {total_played:,} | Broken: {total_broken:,}.", HUE_INFO)


main()
