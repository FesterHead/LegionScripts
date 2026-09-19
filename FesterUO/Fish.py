"""
Fish.py - Automated Fishing Script with Interactive Gump for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Automates fishing with an on-screen interactive control Gump:
    - Provides a "Start" button to initiate the water targeting selector.
    - Locks onto target water coordinates and repeatedly fishes until the spot is depleted.
    - Tracks and displays:
        - Current fishing status (Ready, Click water to fish, Fishing, Spot Depleted, Stopped)
        - Cast count for the current spot (resets to 0 whenever Start is clicked)
        - Running total of regular Fish caught while the Gump is open
        - Running total of Small Fish caught while the Gump is open
        - Running total of Junk caught while the Gump is open
        - Live Fishing skill (value and cap) with skill gain announcements
    - Clicking the button while fishing acts as a "Stop" to cancel the current spot.
    - Right-clicking / closing the Gump safely halts the script.

Usage:
    1. Equip a fishing pole (or have one in your backpack).
    2. Start the script in TazUO.
    3. Click "Start" on the Gump, then click the desired water tile when prompted.
"""

from typing import List, Tuple, Optional
import API

# ==============================================================================
# Configuration
# ==============================================================================

DEBUG: bool = False

# Delay in seconds between casts. FesterUO allows fast harvesting (1.0s–2.0s).
# For standard / default UO shards, set this to 6.0–8.0s.
FISHING_DELAY: float = 2.0

# Optional dress configuration profile to load at startup (set to None or "" to disable)
DRESS_PROFILE: str = ""

# Fishing pole item graphic ID
FISHING_POLE_GRAPHIC: int = 0x0DC0

# Fish and catch graphic IDs
FISH_GRAPHICS: List[int] = [
    0x09CC,  # Raw fish 1
    0x09CD,  # Raw fish 2
    0x09CE,  # Raw fish 3
    0x09CF,  # Raw fish 4
]

SMALL_FISH_GRAPHICS: List[int] = [
    0x0DD6,  # Small fish / Mess of small fish
    0x0DD7,  # Small fish variant
]

JUNK_GRAPHICS: List[int] = [
    0x170F,  # Shoes
    0x1708,  # Boots
    0x170B,  # Leather Boots / Thigh Boots
    0x1711,  # Thigh Boots
    0x170D,  # Sandals
    0x0DC1,  # Seaweed / Turnip / Kelp
    0x0DC2,  # Fish bones / Twigs
]

JUNK_KEYWORDS: List[str] = [
    "shoes", "shoe", "boots", "boot", "sandals", "sandal",
    "seaweed", "kelp", "twigs", "twig", "bones", "footwear"
]

# Journal messages indicating that the current fishing spot is depleted or unreachable.
DEPLETED_MESSAGES: List[str] = [
    "biting here",
    "Biting here",
    "The fish don't seem to be biting here",
    "the fish don't seem to be biting here",
    "The fish don’t seem to be biting here",
    "the fish don’t seem to be biting here",
    "There are no fish here to bite",
    "there are no fish here to bite",
    "There are no fish here",
    "there are no fish here",
    "no fish here",
    "No fish here",
    "cannot see that",
    "Cannot see that",
    "can't reach that",
    "Can't reach that",
    "too far away",
    "Too far away",
    "that is too far away",
    "That is too far away",
    "closer to the water",
    "Closer to the water"
]

# ==============================================================================
# Global Gump & State Management
# ==============================================================================

gump = None
lbl_status = None
lbl_casts = None
lbl_fish = None
lbl_small_fish = None
lbl_junk = None
lbl_skill = None
btn_action = None

is_stopped: bool = False
is_fishing: bool = False
start_requested: bool = False
stop_fishing_requested: bool = False

current_casts: int = 0
total_fish: int = 0
total_small_fish: int = 0
total_junk: int = 0
last_skill: Optional[float] = None


def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def update_status(text: str) -> None:
    """Updates the status line displayed on the Gump."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"
    debug_msg(text)


def update_totals_display() -> None:
    """Refreshes cast count and running catch totals on the Gump."""
    global lbl_casts, lbl_fish, lbl_small_fish, lbl_junk
    if lbl_casts:
        lbl_casts.Text = f"Casts: {current_casts}"
    if lbl_fish:
        lbl_fish.Text = f"Fish: {total_fish}"
    if lbl_small_fish:
        lbl_small_fish.Text = f"Small Fish: {total_small_fish}"
    if lbl_junk:
        lbl_junk.Text = f"Junk: {total_junk}"


def update_skill_display() -> None:
    """Updates Fishing skill on the Gump and announces skill gains."""
    global last_skill, lbl_skill

    skill_obj = API.GetSkill("Fishing")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        lbl_skill.Text = f"Fishing: {val:.1f} / {cap:.1f}"
        if last_skill is not None and val > last_skill:
            gain = val - last_skill
            API.SysMsg(f"Fishing gained +{gain:.1f}! New skill: {val:.1f}")
        last_skill = val


def on_action_clicked() -> None:
    """Callback triggered when the Start / Stop button is clicked."""
    global is_fishing, start_requested, stop_fishing_requested
    if is_fishing:
        stop_fishing_requested = True
        update_status("Stopping...")
    else:
        start_requested = True


def on_gump_disposed() -> None:
    """Callback triggered if the Gump window is closed by right-click."""
    global is_stopped
    if not is_stopped and not API.StopRequested:
        is_stopped = True
        API.Stop()


def create_control_gump() -> None:
    """Initializes and displays the interactive control Gump."""
    global gump, lbl_status, lbl_casts, lbl_fish, lbl_small_fish, lbl_junk, lbl_skill, btn_action

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 240, 200)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 240, 200)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Fisher", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Ready", 996)
    lbl_status.SetPos(10, 30)
    gump.Add(lbl_status)

    # Cast count label (restarts at 0 on Start)
    lbl_casts = API.Gumps.CreateGumpLabel("Casts: 0", 996)
    lbl_casts.SetPos(10, 52)
    gump.Add(lbl_casts)

    # Running totals (persist while Gump is open)
    lbl_fish = API.Gumps.CreateGumpLabel(f"Fish: {total_fish}", 996)
    lbl_fish.SetPos(10, 74)
    gump.Add(lbl_fish)

    lbl_small_fish = API.Gumps.CreateGumpLabel(f"Small Fish: {total_small_fish}", 996)
    lbl_small_fish.SetPos(10, 96)
    gump.Add(lbl_small_fish)

    lbl_junk = API.Gumps.CreateGumpLabel(f"Junk: {total_junk}", 996)
    lbl_junk.SetPos(10, 118)
    gump.Add(lbl_junk)

    # Live Fishing skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Fishing: --", 996)
    lbl_skill.SetPos(10, 140)
    gump.Add(lbl_skill)

    # Start / Stop action button
    btn_action = API.Gumps.CreateSimpleButton("Start", 80, 22)
    btn_action.SetPos(80, 166)
    API.Gumps.AddControlOnClick(btn_action, on_action_clicked)
    gump.Add(btn_action)

    # Handle gump right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely cleans up and disposes the Gump."""
    global gump
    if gump and not gump.IsDisposed:
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes UI callbacks and polls button state."""
    global is_stopped
    API.ProcessCallbacks()
    update_skill_display()

    if is_stopped or API.StopRequested:
        return False

    if btn_action and getattr(btn_action, "HasBeenClicked", lambda: False)():
        on_action_clicked()

    return True


def pause_with_ui(seconds: float) -> bool:
    """Pauses for the specified duration while pumping UI events."""
    elapsed = 0.0
    step = 0.1
    while elapsed < seconds:
        if API.StopRequested or is_stopped or stop_fishing_requested:
            return False
        API.Pause(step)
        elapsed += step
        check_ui_events()
    return True


def on_script_stop() -> None:
    """Clean-up callback when script halts."""
    dispose_gump()
    API.SysMsg("Fishing stopped.")


API.OnStop(on_script_stop)

# ==============================================================================
# Helper Functions: Equipment, Inventory & Depletion
# ==============================================================================

def get_fishing_pole():
    """Finds an equipped fishing pole or one in the backpack."""
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and (item.Graphic == FISHING_POLE_GRAPHIC or "pole" in str(item.Name).lower()):
            return item

    pole = API.FindType(FISHING_POLE_GRAPHIC, API.Backpack)
    if pole:
        return pole

    return None


def get_backpack_counts() -> Tuple[int, int, int]:
    """Returns a tuple of (fish_count, small_fish_count, junk_count) currently in backpack."""
    items = API.ItemsInContainer(API.Backpack)
    if not items:
        return 0, 0, 0

    fish = 0
    small_fish = 0
    junk = 0

    for item in items:
        g = item.Graphic
        amt = item.Amount if item.Amount else 1
        name = str(item.Name).lower() if item.Name else ""

        if g in SMALL_FISH_GRAPHICS or "small fish" in name:
            small_fish += amt
        elif g in FISH_GRAPHICS or (name == "fish" or name == "raw fish"):
            fish += amt
        elif g in JUNK_GRAPHICS or any(k in name for k in JUNK_KEYWORDS):
            junk += amt

    return fish, small_fish, junk


def process_catch(before_counts: Tuple[int, int, int]) -> None:
    """Detects fish, small fish, or junk caught using backpack delta and journal inspection."""
    global total_fish, total_small_fish, total_junk
    after_counts = get_backpack_counts()

    delta_fish = max(0, after_counts[0] - before_counts[0])
    delta_small = max(0, after_counts[1] - before_counts[1])
    delta_junk = max(0, after_counts[2] - before_counts[2])

    if delta_fish > 0 or delta_small > 0 or delta_junk > 0:
        total_fish += delta_fish
        total_small_fish += delta_small
        total_junk += delta_junk
        debug_msg(f"Backpack delta: Fish=+{delta_fish}, Small=+{delta_small}, Junk=+{delta_junk}")
    else:
        # Check journal entries from the cast
        entries = API.GetJournalEntries(FISHING_DELAY + 1.0)
        if entries:
            for entry in entries:
                text = str(entry.Text).lower()
                # Ignore non-catch failure and ambient messages
                if "fail to catch" in text or "fish a while" in text or "biting here" in text or "no fish" in text:
                    continue

                if "pull out" in text or "fished up" in text or "you catch" in text:
                    if any(k in text for k in ["small fish", "tiny fish", "mess of small fish"]):
                        total_small_fish += 1
                        debug_msg(f"Journal caught small fish: {entry.Text}")
                        break
                    elif any(k in text for k in ["boot", "shoe", "sandal", "seaweed", "kelp", "twig", "stick", "bones", "footwear"]):
                        total_junk += 1
                        debug_msg(f"Journal caught junk: {entry.Text}")
                        break
                    elif "fish" in text:
                        total_fish += 1
                        debug_msg(f"Journal caught fish: {entry.Text}")
                        break

    update_totals_display()


def is_spot_depleted() -> Tuple[bool, str]:
    """
    Checks if the current fishing spot is depleted.
    Combines direct InJournal checks with case-insensitive journal entry scanning
    to guard against capitalizations or unicode apostrophe (' vs ’) discrepancies.
    """
    # 1. Direct API.InJournal check
    for msg in DEPLETED_MESSAGES:
        if API.InJournal(msg):
            return True, msg

    # 2. Case-insensitive inspection of recent journal entries
    entries = API.GetJournalEntries(4.0)
    if entries:
        for entry in entries:
            text = str(entry.Text).lower()
            if "biting here" in text:
                return True, entry.Text
            if "no fish here" in text:
                return True, entry.Text
            if "cannot see that" in text or "can't reach" in text or "too far away" in text:
                return True, entry.Text
            if "closer to the water" in text:
                return True, entry.Text

    return False, ""


# ==============================================================================
# Fishing Execution Session
# ==============================================================================

def run_fishing_session() -> None:
    """Executes a fishing session for a targeted water spot until depleted or stopped."""
    global is_fishing, stop_fishing_requested, current_casts, btn_action

    is_fishing = True
    stop_fishing_requested = False
    current_casts = 0
    update_totals_display()

    if btn_action:
        btn_action.SetText("Stop")

    pole = get_fishing_pole()
    if not pole:
        API.SysMsg("No fishing pole found in hands or backpack!")
        update_status("No fishing pole!")
        is_fishing = False
        if btn_action:
            btn_action.SetText("Start")
        return

    # 1. Pop targeting cursor to select water
    update_status("Click water to fish...")
    API.SysMsg("Click the water where you want to fish...")
    if API.HasTarget():
        API.CancelTarget()
        API.Pause(0.2)

    API.ClearJournal()
    API.UseObject(pole)

    old_pos = API.LastTargetPos

    # Wait for user to target water
    targeted = False
    for _ in range(150):  # 15 second timeout
        if API.StopRequested or is_stopped or stop_fishing_requested:
            if API.HasTarget():
                API.CancelTarget()
            update_status("Cancelled")
            is_fishing = False
            if btn_action:
                btn_action.SetText("Start")
            return

        check_ui_events()
        pos = API.LastTargetPos
        graphic = API.LastTargetGraphic
        if pos and (pos != old_pos or API.InJournal("You pull out") or API.InJournal("You fish a while") or API.InJournal("You reel in")):
            targeted = True
            break
        API.Pause(0.1)

    if not targeted:
        pos = API.LastTargetPos
        graphic = API.LastTargetGraphic
        if pos:
            targeted = True

    if not targeted or not pos:
        API.SysMsg("Target selection timed out.")
        update_status("Target timed out")
        is_fishing = False
        if btn_action:
            btn_action.SetText("Start")
        return

    tx = int(pos.X)
    ty = int(pos.Y)
    tz = int(pos.Z)
    tg = int(graphic) if graphic else 0

    debug_msg(f"Locked water tile: ({tx}, {ty}, {tz}) graphic={tg}. Starting loop...")
    update_status("Fishing...")

    # Wait for initial manual cast to finish
    before_counts = get_backpack_counts()
    if not pause_with_ui(FISHING_DELAY):
        update_status("Stopped")
        is_fishing = False
        if btn_action:
            btn_action.SetText("Start")
        return

    current_casts = 1
    process_catch(before_counts)

    depleted, reason = is_spot_depleted()
    if depleted:
        API.SysMsg(f"Fishing spot finished: '{reason}'")
        update_status("Spot Depleted")
        is_fishing = False
        if btn_action:
            btn_action.SetText("Start")
        return

    # Automated casting loop continues from cast #2 onward
    while not API.StopRequested and not is_stopped and not stop_fishing_requested:
        check_ui_events()
        if stop_fishing_requested:
            break

        current_casts += 1
        debug_msg(f"=== Cast #{current_casts} ===")
        update_status(f"Fishing (Cast #{current_casts})...")
        update_totals_display()

        before_counts = get_backpack_counts()
        API.ClearJournal()

        # Cancel any dangling cursor before using pole
        if API.HasTarget():
            API.CancelTarget()
            API.Pause(0.2)

        API.UseObject(pole)

        if API.WaitForTarget(timeout=5):
            API.Target(tx, ty, tz, tg)
            if not pause_with_ui(FISHING_DELAY):
                break
        else:
            debug_msg(f"Cast #{current_casts}: Retrying target...")
            if not pause_with_ui(0.8):
                break
            API.UseObject(pole)
            if API.WaitForTarget(timeout=5):
                API.Target(tx, ty, tz, tg)
                if not pause_with_ui(FISHING_DELAY):
                    break
            else:
                debug_msg(f"Cast #{current_casts}: Target timed out.")
                update_status("Target timed out")
                break

        # Process caught items
        process_catch(before_counts)

        # Check depletion
        depleted, reason = is_spot_depleted()
        if depleted:
            API.SysMsg(f"Fishing spot finished: '{reason}'")
            update_status("Spot Depleted")
            break

    if stop_fishing_requested:
        update_status("Stopped")
    elif not depleted:
        update_status("Ready")

    is_fishing = False
    if btn_action:
        btn_action.SetText("Start")


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    global start_requested, is_stopped, is_fishing

    create_control_gump()
    update_status("Ready")
    update_skill_display()

    if DRESS_PROFILE:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE}'...")
        API.Dress(DRESS_PROFILE)
        API.Pause(1.0)

    # Main event loop while Gump is open
    while not API.StopRequested and not is_stopped:
        check_ui_events()

        if start_requested and not is_fishing:
            start_requested = False
            run_fishing_session()

        API.Pause(0.1)

    dispose_gump()


main()
