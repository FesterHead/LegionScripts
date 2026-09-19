"""
TrainChivalry.py - Chivalry Skill Training Script with Interactive Control Gump

Target Client: TazUO (Legion Scripting Engine)
Author: FesterHead
Source Reference: https://github.com/PlayTazUO/PublicLegionScripts/blob/main/Skills/Any/Train%20Chiv.py

Description:
    Automatically trains Chivalry by casting the appropriate spell based on current skill level:
    - 0 to 44.9: Consecrate Weapon (requires weapon in hand)
    - 45.0 to 59.9: Divine Fury
    - 60.0 to 69.9: Enemy Of One
    - 70.0 to 89.9: Holy Light
    - 90.0 to 115.0+: Noble Sacrifice


Features:
    - Startup validation: Verifies mana and tithing requirements for the initial spell before
      starting, displaying informative status messages on the Gump and in client chat before
      safely stopping if requirements are not met.
    - Interactive control Gump showing:
      * Training status (Casting, Meditating, Waiting for Mana, Low Tithe, Paused)
      * Chivalry skill level and cap with automatic gain announcements
      * Current Mana / Max Mana
      * Tithing Points
      * Pause / Resume button
      * Stop button
    - Low tithing alert and auto-stop when points are depleted
    - Optional auto-meditation when mana is insufficient during training
"""

import API

# ==============================================================================
# Configuration
# ==============================================================================

DRESS_PROFILE = "Archery" # Dress profile to equip weapon/gear automatically
USE_MEDITATION = True     # Automatically use Meditation when mana is low during training
CAST_DELAY = 3.0          # Delay in seconds after casting a spell
MEDITATE_DELAY = 10.0     # Duration to wait while meditating
TARGET_SKILL = 115.0      # Stop when reaching this skill or cap


# ==============================================================================
# Global Gump & State Management
# ==============================================================================

gump = None
lbl_status = None
lbl_skill = None
lbl_mana = None
lbl_tithe = None
btn_pause = None
btn_stop = None

is_paused = False
is_stopped = False
last_skill = None



def update_status(text: str) -> None:
    """Updates the status display on the Gump."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"


def update_stats() -> None:
    """Updates Chivalry skill, Mana, and Tithing points on the Gump and announces gains."""
    global last_skill, lbl_skill, lbl_mana, lbl_tithe

    # Update Chivalry skill
    skill_obj = API.GetSkill("Chivalry")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        lbl_skill.Text = f"Chivalry: {val:.1f} / {cap:.1f}"
        if last_skill is not None and val > last_skill:
            gain = val - last_skill
            API.SysMsg(f"Chivalry gained +{gain:.1f}! New skill: {val:.1f}")
        last_skill = val

    # Update Mana
    if lbl_mana and API.Player:
        cur_mana = API.Player.Mana if API.Player.Mana is not None else 0
        max_mana = API.Player.ManaMax if API.Player.ManaMax is not None else 0
        lbl_mana.Text = f"Mana: {cur_mana} / {max_mana}"

    # Update Tithe Points
    if lbl_tithe and API.Player:
        tithe = getattr(API.Player, "TithingPoints", None)
        if tithe is None:
            tithe = getattr(API.Player, "Tithing", None)
        tithe_str = str(tithe) if tithe is not None else "--"
        lbl_tithe.Text = f"Tithe Points: {tithe_str}"


def on_pause_clicked() -> None:
    """Callback triggered when the Pause/Resume button is clicked."""
    global is_paused, btn_pause
    is_paused = not is_paused
    if btn_pause:
        btn_pause.SetText("Resume" if is_paused else "Pause")
    update_status("Paused" if is_paused else "Resuming...")
    API.SysMsg("Chivalry trainer paused." if is_paused else "Chivalry trainer resumed.")


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
    """Initializes and renders the interactive Chivalry Trainer Gump."""
    global gump, lbl_status, lbl_skill, lbl_mana, lbl_tithe, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 240, 150)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 240, 150)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("Chivalry Trainer", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 30)
    gump.Add(lbl_status)

    # Skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Chivalry: -- / --", 996)
    lbl_skill.SetPos(10, 50)
    gump.Add(lbl_skill)

    # Mana label
    lbl_mana = API.Gumps.CreateGumpLabel("Mana: -- / --", 996)
    lbl_mana.SetPos(10, 70)
    gump.Add(lbl_mana)

    # Tithe Points label
    lbl_tithe = API.Gumps.CreateGumpLabel("Tithe Points: --", 996)
    lbl_tithe.SetPos(10, 90)
    gump.Add(lbl_tithe)

    # Pause button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 70, 22)
    btn_pause.SetPos(15, 116)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 70, 22)
    btn_stop.SetPos(155, 116)
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


def get_spell_info(skill, cap):
    """
    Determines spell name, mana cost, and tithe cost based on current skill level.
    Returns None if skill has reached TARGET_SKILL or cap.
    """
    if skill < 45.0:
        return ("Consecrate Weapon", 10, 10)
    elif skill < 60.0:
        return ("Divine Fury", 15, 10)
    elif skill < 70.0:
        return ("Enemy Of One", 20, 10)
    elif skill < 90.0:
        return ("Holy Light", 10, 10)
    elif skill < TARGET_SKILL and skill < cap:
        return ("Noble Sacrifice", 20, 30)
    else:
        return None


def ensure_weapon_equipped():
    """Checks if a weapon is in hand; automatically re-dresses DRESS_PROFILE if hands are empty."""
    has_weapon = API.FindLayer("OneHanded") or API.FindLayer("TwoHanded")
    if not has_weapon and DRESS_PROFILE:
        API.SysMsg(f"Equipping dress profile '{DRESS_PROFILE}'...")
        API.Dress(DRESS_PROFILE)
        API.Pause(0.8)
        has_weapon = API.FindLayer("OneHanded") or API.FindLayer("TwoHanded")
    return has_weapon



# ==============================================================================
# Lifecycle Callbacks
# ==============================================================================

def on_stop() -> None:
    dispose_gump()
    API.SysMsg("Chivalry training stopped.")

API.OnStop(on_stop)


# ==============================================================================
# Main Training Loop
# ==============================================================================

def main():
    API.SysMsg("Starting Chivalry training...")
    if DRESS_PROFILE:
        API.SysMsg(f"Loading dress profile '{DRESS_PROFILE}'...")
        API.Dress(DRESS_PROFILE)
        API.Pause(0.8)

    create_control_gump()
    update_status("Checking requirements...")
    update_stats()


    try:
        # Initial skill retrieval
        skill_obj = API.GetSkill("Chivalry")
        if not skill_obj:
            update_status("Error: Skill not found")
            API.SysMsg("Cannot start training: Could not retrieve Chivalry skill.")
            wait_with_ui(3.0)
            return

        # Check if Chivalry skill is locked or set to down
        lock_val = getattr(skill_obj, "Lock", 0)
        if lock_val != 0 and lock_val != "Up":
            API.SysMsg("Notice: Chivalry skill arrow is not set to Up (▲) in your Skills list!")


        skill = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        spell_info = get_spell_info(skill, cap)

        if not spell_info:
            update_status(f"Finished ({skill:.1f})")
            API.SysMsg(f"Chivalry is already at or above target skill ({skill:.1f} / {TARGET_SKILL:.1f}).")
            wait_with_ui(3.0)
            return

        spell_name, mana_cost, tithe_cost = spell_info

        # Initial Tithing Points check
        cur_tithe = getattr(API.Player, "TithingPoints", None)
        if cur_tithe is None:
            cur_tithe = getattr(API.Player, "Tithing", None)

        if cur_tithe is not None and cur_tithe < tithe_cost:
            update_status(f"No Tithe ({cur_tithe}/{tithe_cost})")
            API.SysMsg(f"Cannot start training: Insufficient tithing points ({cur_tithe}/{tithe_cost} required for {spell_name}). Please tithe gold at a shrine.")
            wait_with_ui(3.5)
            return

        # Initial Mana check
        cur_mana = API.Player.Mana if (API.Player and API.Player.Mana is not None) else 0
        max_mana = API.Player.ManaMax if (API.Player and API.Player.ManaMax is not None) else 0

        if max_mana < mana_cost:
            update_status(f"Max Mana Low ({max_mana}/{mana_cost})")
            API.SysMsg(f"Cannot start training: Maximum mana ({max_mana}) is below {spell_name} cost ({mana_cost}).")
            wait_with_ui(3.5)
            return

        if cur_mana < mana_cost:
            update_status(f"Low Mana ({cur_mana}/{mana_cost})")
            API.SysMsg(f"Cannot start training: Insufficient mana ({cur_mana}/{mana_cost} required for {spell_name}). Please restore mana before starting.")
            wait_with_ui(3.5)
            return

        # Main training loop
        while not API.StopRequested and not is_stopped:
            if not check_ui_events():
                break

            skill_obj = API.GetSkill("Chivalry")
            if not skill_obj:
                update_status("Error: Chivalry skill not found")
                API.SysMsg("Could not retrieve Chivalry skill.")
                break

            skill = float(skill_obj.Value)
            cap = float(skill_obj.Cap)
            spell_info = get_spell_info(skill, cap)

            if not spell_info:
                update_status(f"Finished ({skill:.1f})")
                API.SysMsg(f"Chivalry training complete ({skill:.1f})!")
                wait_with_ui(3.0)
                break

            spell_name, mana_cost, tithe_cost = spell_info

            # Check Tithing Points during training
            cur_tithe = getattr(API.Player, "TithingPoints", None)
            if cur_tithe is None:
                cur_tithe = getattr(API.Player, "Tithing", None)

            if cur_tithe is not None and cur_tithe < tithe_cost:
                update_status(f"Out of Tithe ({cur_tithe}/{tithe_cost})")
                API.SysMsg(f"Training stopped: Insufficient tithing points ({cur_tithe}/{tithe_cost} required for {spell_name}). Please tithe gold at a shrine.")
                wait_with_ui(3.5)
                break

            # Check Mana during training
            cur_mana = API.Player.Mana if (API.Player and API.Player.Mana is not None) else 0
            if cur_mana < mana_cost:
                if USE_MEDITATION:
                    update_status(f"Meditating ({cur_mana}/{mana_cost})...")
                    API.UseSkill("Meditation")
                    if not wait_with_ui(MEDITATE_DELAY):
                        break
                    # Re-equip weapon if unequipped by meditation
                    ensure_weapon_equipped()
                else:
                    update_status(f"Low Mana ({cur_mana}/{mana_cost})...")
                    if not wait_with_ui(2.0):
                        break
                continue

            # Consecrate Weapon requires a weapon equipped in hands
            if spell_name == "Consecrate Weapon":
                if not ensure_weapon_equipped():
                    update_status("Equip a weapon!")
                    API.SysMsg("Notice: Consecrate Weapon requires a weapon equipped in your hand.")
                    if not wait_with_ui(3.0):
                        break
                    continue


            # Cast Spell
            update_status(f"Casting {spell_name}...")
            API.CastSpell(spell_name)


            # Wait after cast while remaining responsive
            if not wait_with_ui(CAST_DELAY):
                break

            # Small slice pause
            API.Pause(0.1)

    finally:
        dispose_gump()
        API.SysMsg("Chivalry training finished.")


main()
