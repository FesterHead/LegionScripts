"""
MoveItemsBetweenContainers.py - Container Item Organizer / Mover for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Prompts the player to target a SOURCE container, then a DESTINATION container,
    and transfers all items from the source container to the destination container.

Usage:
    1. Start the script in TazUO.
    2. Target the SOURCE container when prompted (or press ESC to cancel).
    3. Target the DESTINATION container when prompted (or press ESC to cancel).
    4. The script will open the source container to ensure contents are populated,
       then safely transfer each item with drag/drop delay and cancellation checks.
"""

import API

# ==============================================================================
# Configuration
# ==============================================================================

# Delay in seconds between moving items (prevents out-of-sequence drops or server flood)
MOVE_DELAY: float = 0.65

# Timeout in seconds to wait for player target cursor selections
TARGET_TIMEOUT: float = 10.0

# When False, only top-level items in the source container are moved.
# If subcontainers exist, they are moved as whole objects with their contents intact.
RECURSIVE: bool = False

# System message colors (hues)
HUE_INFO: int = 68     # Cyan / Light Green
HUE_WARN: int = 53     # Yellow
HUE_ERROR: int = 32    # Red

# ==============================================================================
# Stop Handler
# ==============================================================================

def on_stop():
    """Callback when script is stopped manually or finishes."""
    API.SysMsg("Move Items script ended.", HUE_WARN)

API.OnStop(on_stop)

# ==============================================================================
# Main Execution Logic
# ==============================================================================

def main():
    # 1. Prompt for SOURCE container
    API.SysMsg("Target the SOURCE container (or press ESC to cancel)...", HUE_INFO)
    source = API.RequestTarget(timeout=TARGET_TIMEOUT)

    if API.StopRequested:
        return

    if not source:
        API.SysMsg("Source container selection cancelled or timed out.", HUE_ERROR)
        return

    # 2. Prompt for DESTINATION container
    API.SysMsg("Target the DESTINATION container (or press ESC to cancel)...", HUE_INFO)
    dest = API.RequestTarget(timeout=TARGET_TIMEOUT)

    if API.StopRequested:
        return

    if not dest:
        API.SysMsg("Destination container selection cancelled or timed out.", HUE_ERROR)
        return

    # 3. Validation: Source and destination must not be the same container
    if source == dest:
        API.SysMsg("Error: Source and Destination cannot be the same container!", HUE_ERROR)
        return

    # 4. Ensure source container contents are loaded in client memory
    # Opening the container prompts the server to send contents if not already loaded
    API.UseObject(source)
    API.Pause(0.5)

    if API.StopRequested:
        return

    # 5. Fetch items from source container
    items = API.ItemsInContainer(source, recursive=RECURSIVE) or []
    total_items = len(items)

    if total_items == 0:
        API.SysMsg("No items found in the source container!", HUE_WARN)
        return

    API.SysMsg(f"Moving {total_items} items from source to destination...", HUE_INFO)

    # 6. Transfer loop
    moved_count = 0
    for idx, item in enumerate(items, start=1):
        if API.StopRequested:
            API.SysMsg(f"Transfer interrupted! Moved {moved_count} of {total_items} items.", HUE_WARN)
            return

        # Move item stack to destination (0 = move all / full stack)
        item_serial = item.Serial if hasattr(item, "Serial") else item
        API.MoveItem(item_serial, dest, 0)
        moved_count += 1

        API.Pause(MOVE_DELAY)

    API.SysMsg(f"Finished transferring all {moved_count} items!", HUE_INFO)

main()
