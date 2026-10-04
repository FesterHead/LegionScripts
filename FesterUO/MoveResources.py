"""
MoveResources.py - Targeted Resource, Reagent & Gem Mover for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Prompts the player to target a SOURCE container, then a DESTINATION container,
    and automatically transfers all Reagents, Gems, and Crafting Resources while
    strictly excluding and leaving behind all scrolls, weapons, armor, and equipment.

    Features:
    - Filters and moves:
        * Reagents: Full Magery (8 standard), Necromancy (5), Mysticism, and Pagan reagents.
        * Gems: All standard gems (Amber, Amethyst, Citrine, Diamond, Emerald, Ruby,
          Sapphire, Star Sapphire, Tourmaline) and Mondain's Legacy / Stygian Abyss special gems.
        * Resources: Ingots, Ore, Boards, Logs, Shafts, Feathers, Arrows, Bolts, Leather,
          Hides, Cloth, Bolts of Cloth, Wool, Cotton, Scales, Bones, Granite, Sand, Bandages,
          Empty Bottles, and raw cooking staples.
        * Gold / Silver coins (optional toggle, enabled by default).
    - Strict Exclusions (leaves untouched in source container):
        * Scrolls: All spell scrolls (1st-8th circle, Necro, Chivalry, Weaving, Mysticism),
          blank scrolls, recipe scrolls, power/stat scrolls, and maps.
        * Weapons: All melee, ranged, and throwing weapons, staves, and wands.
        * Equipment & Armor: Helmets, gorgets, tunics, arms, gloves, leggings, robes,
          cloaks, footwear, shields, and wearable jewelry (rings, bracelets, necklaces).
        * Books: Spellbooks, runebooks, BOD books.
    - Interactive control Gump:
        * Real-time status display and live counters for Reagents, Gems, Resources,
          Total Moved, and Skipped items.
        * Pause / Resume and Stop buttons.
    - Safe execution with container content auto-loading, responsive cancellation,
      and loop safety (API.StopRequested).

Usage:
    1. Start the script in TazUO.
    2. Target the SOURCE container when prompted (or press ESC to cancel).
    3. Target the DESTINATION container when prompted (or press ESC to cancel).
    4. The script opens containers to load contents, then filters and moves qualifying
       items with drag/drop delay protection.
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

# Transfer gold and silver coins
MOVE_CURRENCY: bool = True

# When True, searches nested subcontainers inside the source container
# and moves qualifying items out into the destination container.
# When False, only moves items residing at the top level of the source container.
RECURSIVE_SOURCE_SCAN: bool = False

# Enable verbose debug messages in the client console/journal
DEBUG: bool = False

# System message colors (hues)
HUE_INFO: int = 68     # Cyan / Light Green
HUE_WARN: int = 53     # Yellow
HUE_ERROR: int = 32    # Red
HUE_SUCCESS: int = 63   # Bright Green

# ==============================================================================
# Graphics & Definitions: Reagents, Gems & Resources
# ==============================================================================

# Standard Magery Reagents
MAGERY_REAGENT_GRAPHICS: Set[int] = {
    0x0F7A,  # Black Pearl
    0x0F7B,  # Bloodmoss
    0x0F84,  # Garlic
    0x0F85,  # Ginseng
    0x0F86,  # Mandrake Root
    0x0F88,  # Nightshade
    0x0F8C,  # Sulfurous Ash
    0x0F8D,  # Spiders' Silk
}

# Necromancy Reagents
NECRO_REAGENT_GRAPHICS: Set[int] = {
    0x0F78,  # Bat Wing
    0x0F8F,  # Grave Dust
    0x0F7D,  # Daemon Blood
    0x0F8E,  # Nox Crystal
    0x0F8A,  # Pig Iron
}

# Mysticism, Pagan & Special Reagents
PAGAN_REAGENT_GRAPHICS: Set[int] = {
    0x0F7E,  # Bone
    0x0F80,  # Daemon Bone
    0x0F81,  # Fertile Dirt
    0x0F82,  # Dragon's Blood
    0x0F83,  # Executioner's Cap
    0x0F79,  # Blackmoor
    0x0F7C,  # Bloodspawn
    0x0F7F,  # Brimstone
    0x0F87,  # Eye of Newt
    0x0F89,  # Obsidian
    0x0F8B,  # Pumice
    0x0F90,  # Volcanic Ash
    0x0F91,  # Wyrm's Heart
}

ALL_REAGENT_GRAPHICS: Set[int] = (
    MAGERY_REAGENT_GRAPHICS | NECRO_REAGENT_GRAPHICS | PAGAN_REAGENT_GRAPHICS
)

REAGENT_NAME_KEYWORDS: List[str] = [
    "black pearl", "bloodmoss", "blood moss", "garlic", "ginseng",
    "mandrake", "nightshade", "spiders' silk", "spider silk",
    "sulfurous ash", "sulphurous ash", "bat wing", "grave dust",
    "daemon blood", "demon blood", "nox crystal", "pig iron",
    "fertile dirt", "dragon's blood", "daemon bone", "demon bone",
    "brimstone", "pumice", "volcanic ash", "executioner's cap",
    "eye of newt", "blackmoor", "bloodspawn", "wyrm's heart",
]

# Standard and Mondain's Legacy / Stygian Abyss Gems
STANDARD_GEM_GRAPHICS: Set[int] = {
    0x0F25,          # Amber
    0x0F16, 0x0F17,  # Amethyst
    0x0F15, 0x0F23, 0x0F24,  # Citrine
    0x0F26, 0x0F27, 0x0F28, 0x0F29, 0x0F30,  # Diamond
    0x0F10, 0x0F14,  # Emerald
    0x0F13, 0x0F19, 0x0F1A, 0x0F1B,  # Ruby
    0x0F11, 0x0F12,  # Sapphire
    0x0F0F, 0x0F21, 0x0F22,  # Star Sapphire
    0x0F18, 0x0F20,  # Tourmaline
}

SPECIAL_GEM_GRAPHICS: Set[int] = {
    0x3192,  # Perfect Emerald
    0x3193,  # Dark Sapphire
    0x3194,  # Turquoise
    0x3195,  # Ecru Citrine
    0x3196,  # White Pearl
    0x3197,  # Fire Ruby
    0x3198,  # Blue Diamond
    0x3199,  # Brilliant Amber
}

ALL_GEM_GRAPHICS: Set[int] = STANDARD_GEM_GRAPHICS | SPECIAL_GEM_GRAPHICS

GEM_NAME_KEYWORDS: List[str] = [
    "amber", "amethyst", "citrine", "diamond", "emerald",
    "ruby", "sapphire", "star sapphire", "tourmaline", "turquoise",
    "white pearl", "fire ruby", "dark sapphire", "perfect emerald",
    "blue diamond", "ecru citrine", "brilliant amber",
]

# Raw & Crafting Resources
RESOURCE_GRAPHICS: Set[int] = {
    # Metals & Ore
    0x1BEF, 0x1BF2,          # Ingots (iron and all colored metals)
    0x19B7, 0x19B8, 0x19B9, 0x19BA,  # Ore piles
    0x1779,                  # Granite / Stone
    0x423A,                  # Sand
    # Woods & Lumber
    0x1BDD, 0x1BE0,          # Logs
    0x1BD7, 0x1BD8, 0x1BD9, 0x1BDA, 0x1BDB, 0x1BDC, 0x1BE1, 0x1BE2,  # Boards
    0x1BD4,                  # Shafts
    0x0DE1, 0x0DE2,          # Kindling
    0x318F,                  # Bark fragments
    0x2F5F,                  # Switch
    0x3191,                  # Luminescent fungi
    0x3190,                  # Parasitic plant
    # Tailoring & Leather
    0x1078, 0x1079,          # Hides
    0x1067, 0x1081,          # Cut Leather
    0x0DF8,                  # Wool
    0x0DF9,                  # Cotton
    0x1A9C, 0x1A9D,          # Flax
    0x0FA0,                  # Spool of Thread
    0x0E1D, 0x0E1E, 0x0E1F,  # Ball of Yarn
    0x0F95,                  # Bolt of Cloth
    0x1766, 0x1767,          # Cut Cloth
    0x1BD1,                  # Feathers
    0x26B4,                  # Dragon Scales
    # Fletching & Ammo
    0x0F3F,                  # Arrows
    0x1BFB,                  # Crossbow Bolts
    # Alchemy & Healing Supplies
    0x0F0E,                  # Empty Bottles
    0x0E21,                  # Clean Bandages
    0x0E20,                  # Bloody Bandages
    # Cooking Staples & Raw Meat
    0x097A, 0x097B,          # Raw Fish Steaks
    0x0979,                  # Raw Whole Fish
    0x09F1, 0x09F2,          # Raw Ribs
    0x09B9, 0x09BA,          # Raw Bird / Poultry
    0x0976, 0x0977,          # Raw Slab of Bacon
    0x097D,                  # Raw Lamb Leg
    0x1039, 0x1045,          # Sack of Flour
    0x103D,                  # Dough
    0x103E,                  # Sweet Dough
    0x09EC,                  # Jar of Honey
    0x09B5,                  # Eggs
}

# Currency
CURRENCY_GRAPHICS: Set[int] = {
    0x0EED,  # Gold Coins
    0x0EF0,  # Silver Coins
}

RESOURCE_NAME_KEYWORDS: List[str] = [
    "ingot", "ore", "board", "log", "shaft", "feather", "arrow",
    "bolt", "hide", "leather", "cut cloth", "bolt of cloth", "wool",
    "cotton", "yarn", "thread", "dragon scale", "scale", "granite",
    "sand", "bandage", "empty bottle", "raw fish", "fish steak",
    "raw rib", "raw bird", "raw meat", "dough", "flour",
]

# ==============================================================================
# Graphics & Definitions: Explicit Exclusions (Scrolls, Equipment, Weapons, Books)
# ==============================================================================

# Spell Scrolls & Maps
SCROLL_GRAPHIC_RANGES: Set[int] = (
    set(range(0x1F2D, 0x1F6D)) |  # Magery 1st-8th Circle Scrolls
    set(range(0x2260, 0x2271)) |  # Necromancy Scrolls
    set(range(0x2D73, 0x2D81)) |  # Spellweaving Scrolls
    set(range(0x2DA0, 0x2DB1)) |  # Mysticism Scrolls
    {
        0x0EF3,  # Blank Scroll
        0x283E,  # Recipe Scroll
        0x14F0,  # Power Scroll / Deed
        0x14EB, 0x14EC,  # Maps
    }
)

# Spellbooks & Textbooks
BOOK_GRAPHICS: Set[int] = {
    0x0EFA,  # Spellbook
    0x2253,  # Necromancer Spellbook
    0x2252,  # Book of Chivalry
    0x238C,  # Book of Bushido
    0x23A0,  # Book of Ninjitsu
    0x2D9D,  # Spellweaving Book
    0x2D9E,  # Mysticism Book
    0x22C5,  # Runebook
    0x2259,  # Bulk Order Book
    0x0FF0, 0x0FF1, 0x0FF2, 0x0FF3, 0x0FF4,  # Standard Books
}

# Wearable Jewelry (Rings, Bracelets, Necklaces, Earrings)
JEWELRY_GRAPHICS: Set[int] = {
    0x108A, 0x1F09,  # Ring
    0x1086,          # Bracelet
    0x1085, 0x1088, 0x1089,  # Necklaces / Beads
    0x1087,          # Earrings
    0x2F58, 0x2F59, 0x2F5A, 0x2F5B,  # Talismans
}

EXCLUDED_NAME_KEYWORDS: List[str] = [
    # Scrolls & Literature
    "scroll", "recipe", "map", "spellbook", "runebook", "tome", "book",
    "deed", "contract", "bulk order",
    # Weapons
    "sword", "blade", "katana", "scimitar", "broadsword", "longsword",
    "viking sword", "cutlass", "kryss", "dagger", "axe", "hatchet",
    "halberd", "bardiche", "scythe", "mace", "hammer", "maul", "club",
    "spear", "fork", "pike", "lance", "staff", "stave", "bow",
    "crossbow", "yumi", "wand", "scepter", "cleaver", "knife",
    # Armor & Shields
    "shield", "buckler", "helm", "helmet", "coif", "cap", "hat", "mask",
    "gorget", "tunic", "breastplate", "chest", "armor", "armour", "arms",
    "sleeves", "gloves", "gauntlets", "leggings", "greaves", "pants",
    "skirt", "kilt", "robe", "cloak", "dress", "shirt", "doublet",
    "surcoat", "boots", "shoes", "sandals", "belt", "sash", "apron",
    # Wearable Jewelry
    "ring", "bracelet", "necklace", "earrings", "beads", "talisman",
]

# ==============================================================================
# Global Gump & Transfer State
# ==============================================================================

gump = None
lbl_status = None
lbl_reagents = None
lbl_gems = None
lbl_resources = None
lbl_total = None
lbl_skipped = None
btn_pause = None
btn_stop = None

is_paused: bool = False
is_stopped: bool = False

count_reagents: int = 0
count_gems: int = 0
count_resources: int = 0
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
    global lbl_reagents, lbl_gems, lbl_resources, lbl_total, lbl_skipped
    total_moved = count_reagents + count_gems + count_resources
    if lbl_reagents:
        lbl_reagents.Text = f"Reagents Moved: {count_reagents}"
    if lbl_gems:
        lbl_gems.Text = f"Gems Moved: {count_gems}"
    if lbl_resources:
        lbl_resources.Text = f"Resources Moved: {count_resources}"
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
        API.SysMsg("Resource Mover resumed.", HUE_INFO)
    else:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused")
        API.SysMsg("Resource Mover paused.", HUE_WARN)


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
    global gump, lbl_status, lbl_reagents, lbl_gems, lbl_resources, lbl_total, lbl_skipped, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 250, 185)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 250, 185)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("FesterUO Resource Mover", 53)
    title.SetPos(10, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Reagents counter
    lbl_reagents = API.Gumps.CreateGumpLabel("Reagents Moved: 0", 68)
    lbl_reagents.SetPos(10, 48)
    gump.Add(lbl_reagents)

    # Gems counter
    lbl_gems = API.Gumps.CreateGumpLabel("Gems Moved: 0", 63)
    lbl_gems.SetPos(10, 68)
    gump.Add(lbl_gems)

    # Resources counter
    lbl_resources = API.Gumps.CreateGumpLabel("Resources Moved: 0", 88)
    lbl_resources.SetPos(10, 88)
    gump.Add(lbl_resources)

    # Total moved counter
    lbl_total = API.Gumps.CreateGumpLabel("Total Moved: 0", 53)
    lbl_total.SetPos(10, 108)
    gump.Add(lbl_total)

    # Skipped items counter
    lbl_skipped = API.Gumps.CreateGumpLabel("Items Skipped: 0", 996)
    lbl_skipped.SetPos(10, 128)
    gump.Add(lbl_skipped)

    # Action button (Pause / Resume)
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 75, 22)
    btn_pause.SetPos(15, 152)
    API.Gumps.AddControlOnClick(btn_pause, on_action_clicked)
    gump.Add(btn_pause)

    # Stop button
    btn_stop = API.Gumps.CreateSimpleButton("Stop", 75, 22)
    btn_stop.SetPos(160, 152)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Handle gump right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely cleans up and disposes the Gump."""
    global gump
    if gump and not gump.IsDisposed:
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes UI callbacks and handles pause states."""
    API.ProcessCallbacks()

    if is_stopped or API.StopRequested:
        return False

    if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
        on_stop_clicked()
        return False

    if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
        on_action_clicked()

    while is_paused and not API.StopRequested and not is_stopped:
        API.Pause(0.2)
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
    API.SysMsg("Resource Mover stopped.", HUE_WARN)


API.OnStop(on_script_stop)

# ==============================================================================
# Item Classification & Filter Logic
# ==============================================================================

def is_explicitly_excluded(item) -> bool:
    """
    Checks if an item must be strictly preserved in the source container:
    - All scrolls (spell scrolls, blank scrolls, maps, recipe scrolls, deeds)
    - All weapons, armor, shields, and wearable clothing
    - All jewelry and spellbooks
    """
    graphic = getattr(item, "Graphic", 0)
    name = str(getattr(item, "Name", "")).lower()

    # 1. Check graphic exclusions
    if graphic in SCROLL_GRAPHIC_RANGES:
        return True
    if graphic in BOOK_GRAPHICS:
        return True
    if graphic in JEWELRY_GRAPHICS:
        return True

    # 2. Check name keywords for scrolls, weapons, equipment, and jewelry
    for kw in EXCLUDED_NAME_KEYWORDS:
        if kw in name:
            return True

    return False


def classify_item(item) -> Optional[str]:
    """
    Determines if an item is a Reagent, Gem, or Resource to move.
    Returns 'reagent', 'gem', 'resource', or None if it should be skipped.
    """
    if is_explicitly_excluded(item):
        return None

    graphic = getattr(item, "Graphic", 0)
    name = str(getattr(item, "Name", "")).lower()

    # 1. Reagents
    if graphic in ALL_REAGENT_GRAPHICS:
        return "reagent"
    for kw in REAGENT_NAME_KEYWORDS:
        if kw in name:
            return "reagent"

    # 2. Gems
    if graphic in ALL_GEM_GRAPHICS:
        return "gem"
    for kw in GEM_NAME_KEYWORDS:
        if kw in name:
            return "gem"

    # 3. Resources
    if graphic in RESOURCE_GRAPHICS:
        return "resource"
    if MOVE_CURRENCY and graphic in CURRENCY_GRAPHICS:
        return "resource"
    for kw in RESOURCE_NAME_KEYWORDS:
        if kw in name:
            return "resource"

    return None

# ==============================================================================
# Main Execution Logic
# ==============================================================================

def main():
    global count_reagents, count_gems, count_resources, count_skipped

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

    update_status("Transferring...")
    API.SysMsg(f"Scanning {total_inspected} items in source container...", HUE_INFO)

    # 6. Process items and transfer qualifying targets
    for item in items:
        if API.StopRequested or is_stopped:
            break
        if not check_ui_events():
            break

        # Check classification
        category = classify_item(item)
        if not category:
            count_skipped += 1
            refresh_counters()
            continue

        item_serial = getattr(item, "Serial", item)
        item_name = getattr(item, "Name", "Resource")

        debug_msg(f"Moving {item_name} ({category}) -> Dest")
        # Move full stack (0 = move all / full stack)
        API.MoveItem(item_serial, dest, 0)

        if category == "reagent":
            count_reagents += 1
        elif category == "gem":
            count_gems += 1
        elif category == "resource":
            count_resources += 1

        refresh_counters()
        API.Pause(MOVE_DELAY)

    # 7. Final Completion Report
    total_moved = count_reagents + count_gems + count_resources
    update_status("Finished")
    refresh_counters()

    API.SysMsg(
        f"Transfer complete! Moved {total_moved} items ({count_reagents} reagents, "
        f"{count_gems} gems, {count_resources} resources). "
        f"Skipped {count_skipped} equipment/scrolls.",
        HUE_SUCCESS
    )


main()
