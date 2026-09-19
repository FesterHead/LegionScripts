"""
TrainAnatomy.py - Automated Anatomy Skill Training Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Automates Anatomy skill training by repeatedly using the Anatomy skill
    on yourself (or a chosen target) using the standard UO skill delay timer.
    Monitors skill progression and automatically terminates when the skill cap
    (or configured target) is reached.

Usage:
    1. Configure TARGET_SELF and SKILL_DELAY as desired.
    2. Start the script in TazUO.
    3. If TARGET_SELF is False, click the creature/player to inspect when prompted.
"""

import API

# ==============================================================================
# Configuration
# ==============================================================================

# Standard UO skill wait timer in seconds.
# Default is 10.0s (classic OSI / standard shard skill cooldown).
# Can be reduced (e.g., 1.0s–5.0s) on fast custom shards.
SKILL_DELAY: float = 10.0

# Target selection:
# Set to True to target yourself automatically (API.Player).
# Set to False to prompt for a target (e.g. pet, horse, training dummy) on start.
TARGET_SELF: bool = True

# Target skill goal:
# Set to a specific float (e.g., 100.0 or 120.0), or None to use your character's cap.
TARGET_CAP: float | None = None

# Enable verbose progress and status messages in the client console
DEBUG: bool = False

# ==============================================================================
# Lifecycle Callbacks
# ==============================================================================

def on_stop() -> None:
    """Invoked when the script is stopped from the client UI."""
    API.SysMsg("Anatomy training stopped.")

API.OnStop(on_stop)


def debug_msg(message: str) -> None:
    """Prints debug message if DEBUG is enabled."""
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")

# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    skill_obj = API.GetSkill("Anatomy")
    if not skill_obj:
        API.SysMsg("Could not retrieve Anatomy skill information.")
        return

    cap = TARGET_CAP if TARGET_CAP is not None else skill_obj.Cap
    current_val = skill_obj.Value

    if current_val >= cap:
        API.SysMsg(f"Anatomy already at or above goal ({current_val:.1f} / {cap:.1f}). Nothing to train!")
        return

    # Determine target serial
    target_serial = API.Player
    if not TARGET_SELF:
        API.SysMsg("Target the creature or player to train Anatomy on...")
        target_serial = API.RequestTarget(timeout=10)
        if not target_serial or target_serial == 0:
            API.SysMsg("Target selection timed out or cancelled.")
            return

    API.SysMsg(f"Starting Anatomy training on serial 0x{target_serial:X} (Current: {current_val:.1f}, Goal: {cap:.1f}, Delay: {SKILL_DELAY}s)...")

    attempts = 0
    last_reported_val = current_val

    while not API.StopRequested:
        skill_obj = API.GetSkill("Anatomy")
        if not skill_obj:
            API.SysMsg("Lost skill reference.")
            break

        current_val = skill_obj.Value

        # Check completion
        if current_val >= cap:
            API.SysMsg(f"Anatomy training complete! Reached {current_val:.1f} / {cap:.1f}.")
            break

        # Log skill gains
        if current_val > last_reported_val:
            gain = current_val - last_reported_val
            API.SysMsg(f"Anatomy gained +{gain:.1f}! New skill: {current_val:.1f} / {cap:.1f}")
            last_reported_val = current_val

        attempts += 1
        debug_msg(f"Attempt #{attempts}: Using Anatomy...")

        API.ClearJournal()
        API.UseSkill("Anatomy")

        if API.WaitForTarget(timeout=5):
            API.Target(target_serial)
            API.Pause(SKILL_DELAY)
        else:
            debug_msg("Target cursor timed out. Retrying...")
            API.Pause(1.0)

        # Check for skill busy / wait journal messages
        if API.InJournal("must wait to perform another action") or API.InJournal("wait a few moments"):
            debug_msg("Skill cooldown active, pausing 1 second...")
            API.Pause(1.0)

    API.SysMsg("Anatomy training script ended.")


main()
