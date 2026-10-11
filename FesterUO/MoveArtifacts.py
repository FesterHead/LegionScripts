"""
MoveArtifacts.py - Targeted Weapon, Armor & Jewelry Artifact and Magic Item Mover for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Prompts the player to target a SOURCE container, then a DESTINATION container,
    and automatically transfers qualifying Weapons, Armor, Shields, and Jewelry that meet
    configured Rarity / Artifact tiers:
    - Artifact Tiers (All Levels):
        * Legendary Artifact
        * Major Artifact
        * Greater Artifact
        * Lesser Artifact
        * Minor Artifact
        * Artifact Rarity (Doom, Tokuno, Stealable, and Paragon artifacts)
    - Magic Item Tiers:
        * Greater Magic Item
        * Major Magic Item (configurable toggle)
        * Lesser Magic Item (configurable toggle, disabled by default)
    - Equipment Categories Covered:
        * Weapons: Swords, blades, axes, maces, hammers, spears, polearms, staves, bows, crossbows, wands.
        * Armor & Shields: Helmets, gorgets, tunics, breastplates, arms, sleeves, gloves, leggings, shields.
        * Jewelry: Rings, bracelets, necklaces, earrings, and talismans.
    - Exclusions & Preservation:
        * Strictly preserves non-qualifying mundane items, low-tier magic items, resources,
          reagents, gems, spell scrolls, maps, and books in the source container.
    - Interactive Control Gump:
        * Real-time status display and live counters for Weapons, Armor/Shields, Jewelry,
          Total Moved, and Skipped items.
        * Interactive Pause / Resume and Stop buttons.
    - Safety & Reliability:
        * Pre-opens source and destination containers to ensure full server synchronization.
        * Utilizes active OPL tooltip parsing (API.ItemNameAndProps) to evaluate exact item rarities.
        * Respects classic drag/drop delays (MOVE_DELAY) and immediate UI cancellation (API.StopRequested).

Usage:
    1. Start the script in TazUO.
    2. Target the SOURCE container when prompted (or press ESC to cancel).
    3. Target the DESTINATION container when prompted (or press ESC to cancel).
    4. The script opens containers to load contents, inspects each item's properties,
       and moves all qualifying artifacts and magic items with drag/drop delay protection.
"""

from typing import List, Tuple, Optional, Set
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Delay in seconds between moving items (prevents server packet drops or floods)
MOVE_DELAY: float = 0.65

# Timeout in seconds to wait for player target cursor selections
TARGET_TIMEOUT: float = 12.0

# When True, searches nested subcontainers inside the source container
# and moves qualifying equipment out into the destination container.
# When False, only moves items residing at the top level of the source container.
RECURSIVE_SOURCE_SCAN: bool = False

# ==============================================================================
# Filter & Tier Configuration
# ==============================================================================

# Equipment category toggles
MOVE_WEAPONS: bool = True
MOVE_ARMOR: bool = True
MOVE_SHIELDS: bool = True
MOVE_JEWELRY: bool = True

# Artifact tiers to move (True = move)
MOVE_ALL_ARTIFACTS: bool = True         # Matches Legendary, Major, Greater, Lesser, Minor, and Artifact Rarity

# Magic item tiers to move
MOVE_GREATER_MAGIC: bool = True        # Greater Magic Item
MOVE_MAJOR_MAGIC: bool = True          # Major Magic Item
MOVE_LESSER_MAGIC: bool = False        # Lesser Magic Item (set to True if desired)

# Enable verbose debug messages in the client console/journal
DEBUG: bool = False

# System message colors (hues)
HUE_INFO: int = 68      # Cyan / Light Green
HUE_WARN: int = 53      # Yellow
HUE_ERROR: int = 32     # Red
HUE_SUCCESS: int = 63   # Bright Green

# ==============================================================================
# Equipment Identification Definitions
# ==============================================================================

# Equipment layer numbers in Ultima Online
WEAPON_LAYERS: Set[int] = {
    1,   # OneHanded (Swords, maces, fencing, axes, wands)
    2,   # TwoHanded (Bows, crossbows, 2H axes, staves, halberds - note: shields also share layer 2)
}

SHIELD_LAYERS: Set[int] = {
    2,   # TwoHanded (Shields occupy layer 2 in classic UO)
}

ARMOR_LAYERS: Set[int] = {
    3,   # Shoes / Boots
    4,   # Pants / Leggings
    6,   # Helm
    7,   # Gloves
    10,  # Neck (Gorget)
    13,  # InnerTorso (Chest / Tunic)
    17,  # MiddleTorso
    19,  # Arms / Sleeves
    23,  # OuterLegs (Kilt / Skirt)
    24,  # InnerLegs (Leggings)
}

JEWELRY_LAYERS: Set[int] = {
    8,   # Ring
    9,   # Talisman
    14,  # Bracelet
    18,  # Earrings
}

WEAPON_KEYWORDS: List[str] = [
    "sword", "blade", "katana", "scimitar", "broadsword", "longsword",
    "viking sword", "cutlass", "kryss", "dagger", "axe", "hatchet",
    "halberd", "bardiche", "scythe", "mace", "hammer", "maul", "club",
    "spear", "fork", "pike", "lance", "staff", "stave", "bow",
    "crossbow", "yumi", "wand", "scepter", "cleaver", "knife",
    "bludgeon", "war hammer", "war axe", "executioner", "two-handed",
    "one-handed", "weapon damage", "weapon speed",
]

SHIELD_KEYWORDS: List[str] = [
    "shield", "buckler", "heater", "kite shield", "metal shield",
    "wooden shield", "bronze shield", "tear kite", "order shield",
    "chaos shield",
]

ARMOR_KEYWORDS: List[str] = [
    "helm", "helmet", "coif", "cap", "mask", "gorget", "tunic",
    "breastplate", "chest", "armor", "armour", "arms", "sleeves",
    "gloves", "gauntlets", "leggings", "greaves", "pants", "kilt",
    "skirt", "platemail", "chainmail", "ringmail", "studded",
    "leather", "bone armor", "dragon armor",
]

JEWELRY_KEYWORDS: List[str] = [
    "ring", "bracelet", "earrings", "necklace", "beads", "talisman",
]

# Non-equipment exclusions (crafting resources, books, tools, potions, deeds)
EXCLUDED_KEYWORDS: List[str] = [
    "scroll", "recipe", "map", "spellbook", "runebook", "tome", "book",
    "deed", "contract", "bulk order", "ingot", "ore", "board", "log",
    "potion", "bottle", "reagent", "gem", "satchel", "bag", "pouch",
    "box", "chest", "crate", "barrel",
]

# ==============================================================================
# Global Gump & Transfer State
# ==============================================================================

gump = None
lbl_status = None
lbl_weapons = None
lbl_armor = None
lbl_jewelry = None
lbl_total = None
lbl_skipped = None
btn_pause = None
btn_stop = None

is_paused: bool = False
is_stopped: bool = False

count_weapons: int = 0
count_armor: int = 0
count_jewelry: int = 0
count_skipped: int = 0


def debug_msg(message: str) -> None:
    if DEBUG:
        API.SysMsg(f"[DEBUG] {message}")


def update_status(text: str) -> None:
    """Updates the status label on the Gump."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"
    debug_msg(text)


def refresh_counters() -> None:
    """Refreshes all numerical counters displayed on the Gump."""
    global lbl_weapons, lbl_armor, lbl_jewelry, lbl_total, lbl_skipped
    total_moved = count_weapons + count_armor + count_jewelry
    if lbl_weapons:
        lbl_weapons.Text = f"Weapons Moved: {count_weapons}"
    if lbl_armor:
        lbl_armor.Text = f"Armor & Shields: {count_armor}"
    if lbl_jewelry:
        lbl_jewelry.Text = f"Jewelry Moved: {count_jewelry}"
    if lbl_total:
        lbl_total.Text = f"Total Moved: {total_moved}"
    if lbl_skipped:
        lbl_skipped.Text = f"Items Skipped: {count_skipped}"


def on_action_clicked() -> None:
    """Callback when Pause / Resume button is clicked."""
    global is_paused, btn_pause
    if is_paused:
        is_paused = False
        if btn_pause:
            btn_pause.SetText("Pause")
        update_status("Transferring...")
        API.SysMsg("[MoveArtifacts] Resumed.", HUE_INFO)
    else:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused")
        API.SysMsg("[MoveArtifacts] Paused.", HUE_WARN)


def on_stop_clicked() -> None:
    """Callback when Stop button is clicked."""
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


def create_control_gump() -> None:
    """Initializes and displays the interactive control Gump."""
    global gump, lbl_status, lbl_weapons, lbl_armor, lbl_jewelry, lbl_total, lbl_skipped, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 260, 205)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 260, 205)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Artifact Mover", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Weapons counter
    lbl_weapons = API.Gumps.CreateGumpLabel("Weapons Moved: 0", 68)
    lbl_weapons.SetPos(10, 48)
    gump.Add(lbl_weapons)

    # Armor & Shields counter
    lbl_armor = API.Gumps.CreateGumpLabel("Armor & Shields: 0", 63)
    lbl_armor.SetPos(10, 68)
    gump.Add(lbl_armor)

    # Jewelry counter
    lbl_jewelry = API.Gumps.CreateGumpLabel("Jewelry Moved: 0", 88)
    lbl_jewelry.SetPos(10, 88)
    gump.Add(lbl_jewelry)

    # Total Moved counter
    lbl_total = API.Gumps.CreateGumpLabel("Total Moved: 0", 53)
    lbl_total.SetPos(10, 108)
    gump.Add(lbl_total)

    # Items Skipped counter
    lbl_skipped = API.Gumps.CreateGumpLabel("Items Skipped: 0", 996)
    lbl_skipped.SetPos(10, 128)
    gump.Add(lbl_skipped)

    # Pause button
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 72, 22)
    btn_pause.SetPos(15, 160)
    API.Gumps.AddControlOnClick(btn_pause, on_action_clicked)
    gump.Add(btn_pause)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 72, 22)
    btn_stop.SetPos(170, 160)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Handle right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely disposes of the Gump control."""
    global gump
    if gump and not getattr(gump, "IsDisposed", False):
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes UI clicks, stats updates, and handles pause loops."""
    global is_paused, is_stopped
    API.ProcessCallbacks()

    if is_stopped or API.StopRequested:
        return False

    if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
        on_stop_clicked()
        return False

    if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
        on_action_clicked()

    while is_paused and not API.StopRequested and not is_stopped:
        API.Pause(0.1)
        API.ProcessCallbacks()
        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            on_action_clicked()
            break

    return not (is_stopped or API.StopRequested)


def on_script_stop() -> None:
    """Cleanup callback when the script halts."""
    dispose_gump()
    API.SysMsg("[MoveArtifacts] Script stopped.", HUE_WARN)


API.OnStop(on_script_stop)

# ==============================================================================
# Equipment Classification & Filter Logic
# ==============================================================================

def get_item_properties(item) -> str:
    """Retrieves full lowercase tooltip properties for an item."""
    serial = getattr(item, "Serial", None)
    if not serial:
        return str(getattr(item, "Name", "") or "").lower()

    # Fast path: check cached properties without blocking
    props = API.ItemNameAndProps(serial, wait=False)
    if props:
        return str(props).lower()

    # Query with short timeout
    props = API.ItemNameAndProps(serial, wait=True, timeout=1)
    if props:
        return str(props).lower()

    return str(getattr(item, "Name", "") or "").lower()


def get_equipment_category(item, props: str) -> Optional[str]:
    """
    Determines if an item is a Weapon, Armor/Shield, or Jewelry.
    Returns 'weapon', 'armor', 'jewelry', or None if not recognized equipment.
    """
    # 1. Check non-equipment exclusions
    for kw in EXCLUDED_KEYWORDS:
        if kw in props:
            return None

    # 2. Layer-based check from ItemData if available
    item_data = item.GetItemData() if hasattr(item, "GetItemData") else None
    layer = getattr(item_data, "Layer", 0) if item_data else 0

    if layer in JEWELRY_LAYERS and MOVE_JEWELRY:
        return "jewelry"

    if layer in ARMOR_LAYERS and MOVE_ARMOR:
        return "armor"

    # Layer 2 can be a two-handed weapon or a shield
    if layer == 2:
        if any(kw in props for kw in SHIELD_KEYWORDS) and MOVE_SHIELDS:
            return "armor"
        if MOVE_WEAPONS:
            return "weapon"

    if layer == 1 and MOVE_WEAPONS:
        return "weapon"

    # 3. Tooltip keyword and stat checks
    # Jewelry
    if MOVE_JEWELRY:
        for kw in JEWELRY_KEYWORDS:
            if kw in props:
                return "jewelry"

    # Shields
    if MOVE_SHIELDS:
        for kw in SHIELD_KEYWORDS:
            if kw in props:
                return "armor"

    # Armor (Resistances, defense stats, armor names)
    if MOVE_ARMOR:
        has_resists = (
            "physical resist" in props
            or "fire resist" in props
            or "cold resist" in props
            or "poison resist" in props
            or "energy resist" in props
            or "mage armor" in props
        )
        if has_resists:
            return "armor"

        for kw in ARMOR_KEYWORDS:
            if kw in props:
                return "armor"

    # Weapons (Damage stats, speed, weapon names)
    if MOVE_WEAPONS:
        has_weapon_stats = (
            "weapon damage" in props
            or "weapon speed" in props
            or "damage increase" in props
            or "swing speed increase" in props
            or "hit chance increase" in props
            or "hit lightning" in props
            or "hit fireball" in props
            or "hit lower defense" in props
            or "hit lower attack" in props
            or "use best weapon skill" in props
            or "spell channeling" in props
        )
        if has_weapon_stats:
            return "weapon"

        for kw in WEAPON_KEYWORDS:
            if kw in props:
                return "weapon"

    return None


def matches_rarity_tier(props: str) -> bool:
    """
    Checks if item properties match any of the configured Artifact or Magic Item tiers:
    - Legendary Artifact
    - Major Artifact
    - Greater Artifact
    - Lesser Artifact
    - Minor Artifact
    - Artifact Rarity (Doom/Tokuno/Stealables)
    - Greater Magic Item
    - Major Magic Item (optional)
    - Lesser Magic Item (optional)
    """
    # 1. Artifact Tiers
    if MOVE_ALL_ARTIFACTS:
        if "legendary artifact" in props:
            return True
        if "major artifact" in props:
            return True
        if "greater artifact" in props:
            return True
        if "lesser artifact" in props:
            return True
        if "minor artifact" in props:
            return True
        if "artifact rarity" in props:
            return True
        if "artifact" in props and ("rarity" in props or "item" in props):
            return True

    # 2. Magic Item Tiers
    if MOVE_GREATER_MAGIC and "greater magic item" in props:
        return True

    if MOVE_MAJOR_MAGIC and "major magic item" in props:
        return True

    if MOVE_LESSER_MAGIC and "lesser magic item" in props:
        return True

    return False


def classify_equipment(item) -> Tuple[Optional[str], str]:
    """
    Evaluates an item.
    Returns (category, item_title) if it matches equipment filters and rarity tiers,
    or (None, item_title) if it should be skipped.
    """
    props = get_item_properties(item)
    if not props:
        return None, "Unknown Item"

    item_title = str(getattr(item, "Name", None) or props.split("\n")[0]).strip()

    # Verify equipment category
    category = get_equipment_category(item, props)
    if not category:
        return None, item_title

    # Verify rarity / artifact tier
    if not matches_rarity_tier(props):
        return None, item_title

    return category, item_title

# ==============================================================================
# Main Execution Logic
# ==============================================================================

def main():
    global count_weapons, count_armor, count_jewelry, count_skipped

    create_control_gump()
    update_status("Targeting containers...")

    # 1. Prompt for SOURCE container
    API.SysMsg("Target the SOURCE container (or press ESC to cancel)...", HUE_INFO)
    source = API.RequestTarget(timeout=TARGET_TIMEOUT)

    if API.StopRequested or is_stopped:
        dispose_gump()
        return

    if not source:
        API.SysMsg("Source container selection cancelled or timed out.", HUE_ERROR)
        update_status("Cancelled")
        dispose_gump()
        return

    # 2. Prompt for DESTINATION container
    API.SysMsg("Target the DESTINATION container (or press ESC to cancel)...", HUE_INFO)
    dest = API.RequestTarget(timeout=TARGET_TIMEOUT)

    if API.StopRequested or is_stopped:
        dispose_gump()
        return

    if not dest:
        API.SysMsg("Destination container selection cancelled or timed out.", HUE_ERROR)
        update_status("Cancelled")
        dispose_gump()
        return

    # 3. Validation: Source and destination must not be identical
    if source == dest:
        API.SysMsg("Error: Source and Destination cannot be the same container!", HUE_ERROR)
        update_status("Error: Same Container")
        dispose_gump()
        return

    # 4. Open containers so the client receives current contents from server
    update_status("Loading container contents...")
    API.UseObject(source)
    API.Pause(0.5)

    if API.StopRequested or is_stopped:
        dispose_gump()
        return

    API.UseObject(dest)
    API.Pause(0.5)

    if API.StopRequested or is_stopped:
        dispose_gump()
        return

    # 5. Fetch items in source container
    items = API.ItemsInContainer(source, recursive=RECURSIVE_SOURCE_SCAN) or []
    total_inspected = len(items)

    if total_inspected == 0:
        API.SysMsg("No items found in the source container!", HUE_WARN)
        update_status("Container empty")
        return

    update_status("Scanning equipment...")
    API.SysMsg(f"[MoveArtifacts] Scanning {total_inspected} items in source container...", HUE_INFO)

    # 6. Process items and transfer qualifying artifacts
    for idx, item in enumerate(items, start=1):
        if API.StopRequested or is_stopped:
            break
        if not check_ui_events():
            break

        # Check classification
        category, item_title = classify_equipment(item)
        if not category:
            count_skipped += 1
            refresh_counters()
            continue

        item_serial = getattr(item, "Serial", item)
        update_status(f"Moving {item_title}...")
        debug_msg(f"Moving {item_title} ({category}) -> Dest")

        # Move item (0 = move all / full stack)
        API.MoveItem(item_serial, dest, 0)

        if category == "weapon":
            count_weapons += 1
        elif category == "armor":
            count_armor += 1
        elif category == "jewelry":
            count_jewelry += 1

        refresh_counters()
        API.Pause(MOVE_DELAY)

    # 7. Final Completion Report
    total_moved = count_weapons + count_armor + count_jewelry
    update_status("Finished")
    refresh_counters()

    API.SysMsg(
        f"[MoveArtifacts] Complete! Moved {total_moved} items ({count_weapons} weapons, "
        f"{count_armor} armor/shields, {count_jewelry} jewelry). "
        f"Skipped {count_skipped} items.",
        HUE_SUCCESS
    )


main()
