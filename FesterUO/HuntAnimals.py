"""
HuntAnimals.py - Automated Animal & Bird Hunting Script for TazUO

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)

Description:
    Autonomous wildlife and bird hunting script designed to locate and hunt wild
    animals, birds, and predators to gather crafting and survival resources
    (feathers, poultry, hides/leather, raw ribs/meat, and wool). Operates as a
    completely standalone script.

    Key Features:
    - Multi-Category Wildlife Detection:
        * HUNT_BIRDS (default True): Targets wild Birds (crow, raven, magpie), Eagles,
          Chickens, Turkeys, and Cranes to generate feathers and poultry.
        * HUNT_PASSIVE_ANIMALS (default True): Targets wild Hinds, Great Harts (deer),
          Cows, Bulls, Pigs, Boars, Sheep, Goats, Llamas, Horses, and Rabbits to
          generate hides/leather, raw ribs/meat, and wool.
        * HUNT_PREDATORS (default False): Optional toggle to also hunt wild Wolves,
          Bears, Cougars, and Panthers for additional hides and meat.
        * Explicitly ignores the player, friends, guildmates, and tamed player pets.
    - Automated Combat Engagement:
        * Equips the configured dress profile (default 'Fighting') to arm your weapon.
        * Enters War Mode (API.SetWarMode(True)) and commands your character to attack.
        * Intelligently pathfinds to and pursues hopping, fleeing, or wandering animals until in melee range.
    - TazUO AutoLoot & Corpse Processing:
        * Upon kill, locates the animal corpse and carves it with your weapon/tool to yield
          leather/hides, feathers, raw meat, and wool.
        * Automatically opens the corpse and triggers TazUO's native AutoLoot agent
          (API.AutoLootContainer) to collect loot according to your client settings.
    - Interactive Control Gump:
        * Semi-transparent dark background with live status updates.
        * Running counter: Animals Defeated.
        * Interactive toggle checkboxes: Birds, Passives, Predators, and Defend Threats.
        * Interactive Pause/Resume and Stop buttons.
"""

import time
from typing import List, Optional, Set
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Search radius in tiles around the player to locate wildlife
SEARCH_RADIUS: int = 15

# Animal hunting category toggles
HUNT_BIRDS: bool = True             # Birds, Eagles, Chickens, Turkeys, Cranes (feathers & poultry)
HUNT_PASSIVE_ANIMALS: bool = True   # Deer/Harts, Cows/Bulls, Pigs/Boars, Sheep, Goats, Llamas, Horses, Rabbits (leather & ribs)
HUNT_PREDATORS: bool = False        # Wolves, Bears, Cougars, Panthers (predator hunting)
AUTO_DEFEND_AGGRESSORS: bool = True # Always attack hostile/aggressive creatures and predators targeting player immediately

# Dress profile configured in TazUO to equip before attacking (e.g. "Fighting")
DRESS_PROFILE: str = "Fighting"
DRESS_DELAY: float = 1.25

# Max combat engagement timeout in seconds (to prevent getting stuck chasing unreachable animals)
COMBAT_TIMEOUT: float = 25.0

# Scan interval in seconds when no target animals are nearby
SCAN_INTERVAL: float = 0.5

# Corpse processing & TazUO AutoLoot integration
AUTO_CARVE_CORPSE: bool = True           # Carves corpse with blade/axe to yield leather/feathers/ribs
OPEN_CORPSE_FOR_AUTOLOOT: bool = True    # Opens corpse container for client autoloot
TRIGGER_TAZUO_AUTOLOOT: bool = True      # Calls API.AutoLootContainer on the corpse
CORPSE_PROCESSING_DELAY: float = 0.35

# Safety exclusions
IGNORE_TAMED_PETS: bool = True           # Ignore renamable mobiles (player pets/mounts)
IGNORE_FRIENDS: bool = True              # Ignore friends and guildmates

# Enable verbose debug logging to client console
DEBUG: bool = False

# ==============================================================================
# Mobile & Item Graphics Definitions
# ==============================================================================

# Bird creature graphics
BIRD_GRAPHICS: Set[int] = {
    0x0006,  # Small bird / Crow / Raven / Magpie
    0x0005,  # Eagle
    0x00D0,  # Chicken / Turkey
    0x011A,  # Crane / Tropical bird
}

BIRD_NAME_KEYWORDS: List[str] = [
    "bird", "eagle", "chicken", "turkey", "crane", "crow", "raven", "magpie"
]

# Passive animal graphics (Deer, Cattle, Swine, Sheep, Goats, Camelids, Equines, Leporids)
PASSIVE_ANIMAL_GRAPHICS: Set[int] = {
    0x00ED,  # Hind (female deer)
    0x00EA,  # Great Hart (male deer / stag)
    0x00D8, 0x00E7,  # Cow (black/white & brown)
    0x00E8, 0x00E9,  # Bull
    0x00CB,  # Pig
    0x0014,  # Boar
    0x00CF, 0x00DF,  # Sheep (wooly & shorn)
    0x00D1, 0x0058,  # Goat & Mountain Goat
    0x00DC,  # Llama
    0x00C8, 0x00E2, 0x00E4, 0x00CC,  # Wild Horses
    0x00CD,  # Rabbit / Jackrabbit
    0x00D2, 0x00DB, 0x00DA,  # Desert Ostard, Forest Ostard, Frenzied Ostard
    0x00DD,  # Walrus
}

PASSIVE_ANIMAL_KEYWORDS: List[str] = [
    "hind", "great hart", "hart", "deer", "stag",
    "cow", "bull", "pig", "boar", "sheep", "goat",
    "llama", "horse", "rabbit", "hare", "ostard", "walrus"
]

# Predator animal graphics (Wolves, Bears, Big Cats)
PREDATOR_GRAPHICS: Set[int] = {
    0x00E1, 0x0019, 0x001B, 0x0017,  # Timber Wolf, Gray Wolf, White Wolf, Dire Wolf
    0x00D3, 0x00A7, 0x00D4, 0x00D5,  # Black Bear, Brown Bear, Grizzly Bear, Polar Bear
    0x00D6, 0x001E,                  # Panther, Cougar
}

PREDATOR_KEYWORDS: List[str] = [
    "wolf", "bear", "grizzly", "panther", "cougar"
]

# Corpse graphic
CORPSE_GRAPHIC: int = 0x2006

# Bladed tools and weapons for corpse carving
BLADE_GRAPHICS: Set[int] = {
    0x0F51, 0x0F52,  # Dagger
    0x13F6,          # Butcher Knife
    0x0EC4,          # Skinning Knife
    0x0EC2,          # Cleaver
    0x0F43, 0x0F44,  # Hatchet
    0x0F45, 0x0F46,  # Executioner's Axe
    0x0F47, 0x0F48,  # Battle Axe
    0x0F49, 0x0F4A,  # Axe
    0x0F4B, 0x0F4C,  # Double Axe
    0x0F4D, 0x0F4E,  # Bardiche
    0x13AF, 0x13B0,  # War Axe
    0x13FA, 0x13FB,  # Large Battle Axe
    0x1442, 0x1443,  # Two Handed Axe
}

# ==============================================================================
# State Variables
# ==============================================================================

is_paused: bool = False
is_stopped: bool = False
current_status: str = "Ready"

total_spotted: int = 0
total_killed: int = 0

# Interactive Gump controls
gump = None
lbl_status = None
lbl_stats = None
cb_birds = None
cb_passives = None
cb_predators = None
cb_defend = None
btn_pause = None
btn_stop = None

# ==============================================================================
# Logging & Debugging
# ==============================================================================

def debug_msg(message: str) -> None:
    """Outputs debug message to the client log if DEBUG is enabled."""
    if DEBUG:
        API.SysMsg(f"[HuntAnimals:DEBUG] {message}")


# ==============================================================================
# Gump UI Implementation & Interactive Toggles
# ==============================================================================

def on_toggle_birds() -> None:
    """Handles runtime toggle for Birds category."""
    global HUNT_BIRDS
    if cb_birds:
        val = getattr(cb_birds, "IsChecked", None)
        if val is None and hasattr(cb_birds, "GetIsChecked"):
            val = cb_birds.GetIsChecked()
        if val is not None and val != HUNT_BIRDS:
            HUNT_BIRDS = bool(val)
        else:
            HUNT_BIRDS = not HUNT_BIRDS
            if hasattr(cb_birds, "SetIsChecked"):
                cb_birds.SetIsChecked(HUNT_BIRDS)
            else:
                cb_birds.IsChecked = HUNT_BIRDS
        API.SysMsg(f"[HuntAnimals] Birds hunting: {'ON' if HUNT_BIRDS else 'OFF'}")


def on_toggle_passives() -> None:
    """Handles runtime toggle for Passive Animals category."""
    global HUNT_PASSIVE_ANIMALS
    if cb_passives:
        val = getattr(cb_passives, "IsChecked", None)
        if val is None and hasattr(cb_passives, "GetIsChecked"):
            val = cb_passives.GetIsChecked()
        if val is not None and val != HUNT_PASSIVE_ANIMALS:
            HUNT_PASSIVE_ANIMALS = bool(val)
        else:
            HUNT_PASSIVE_ANIMALS = not HUNT_PASSIVE_ANIMALS
            if hasattr(cb_passives, "SetIsChecked"):
                cb_passives.SetIsChecked(HUNT_PASSIVE_ANIMALS)
            else:
                cb_passives.IsChecked = HUNT_PASSIVE_ANIMALS
        API.SysMsg(f"[HuntAnimals] Passive Animals: {'ON' if HUNT_PASSIVE_ANIMALS else 'OFF'}")


def on_toggle_predators() -> None:
    """Handles runtime toggle for Predators category."""
    global HUNT_PREDATORS
    if cb_predators:
        val = getattr(cb_predators, "IsChecked", None)
        if val is None and hasattr(cb_predators, "GetIsChecked"):
            val = cb_predators.GetIsChecked()
        if val is not None and val != HUNT_PREDATORS:
            HUNT_PREDATORS = bool(val)
        else:
            HUNT_PREDATORS = not HUNT_PREDATORS
            if hasattr(cb_predators, "SetIsChecked"):
                cb_predators.SetIsChecked(HUNT_PREDATORS)
            else:
                cb_predators.IsChecked = HUNT_PREDATORS
        API.SysMsg(f"[HuntAnimals] Predators: {'ON' if HUNT_PREDATORS else 'OFF'}")


def on_toggle_defend() -> None:
    """Handles runtime toggle for Aggressive Threat Auto-Defense."""
    global AUTO_DEFEND_AGGRESSORS
    if cb_defend:
        val = getattr(cb_defend, "IsChecked", None)
        if val is None and hasattr(cb_defend, "GetIsChecked"):
            val = cb_defend.GetIsChecked()
        if val is not None and val != AUTO_DEFEND_AGGRESSORS:
            AUTO_DEFEND_AGGRESSORS = bool(val)
        else:
            AUTO_DEFEND_AGGRESSORS = not AUTO_DEFEND_AGGRESSORS
            if hasattr(cb_defend, "SetIsChecked"):
                cb_defend.SetIsChecked(AUTO_DEFEND_AGGRESSORS)
            else:
                cb_defend.IsChecked = AUTO_DEFEND_AGGRESSORS
        API.SysMsg(f"[HuntAnimals] Auto Defend Threats: {'ON' if AUTO_DEFEND_AGGRESSORS else 'OFF'}")


def sync_checkboxes() -> None:
    """Synchronizes boolean variables with Gump checkbox states."""
    global HUNT_BIRDS, HUNT_PASSIVE_ANIMALS, HUNT_PREDATORS, AUTO_DEFEND_AGGRESSORS
    if cb_birds:
        val = getattr(cb_birds, "IsChecked", None)
        if val is None and hasattr(cb_birds, "GetIsChecked"):
            val = cb_birds.GetIsChecked()
        if val is not None and val != HUNT_BIRDS:
            HUNT_BIRDS = bool(val)
            API.SysMsg(f"[HuntAnimals] Birds hunting: {'ON' if HUNT_BIRDS else 'OFF'}")

    if cb_passives:
        val = getattr(cb_passives, "IsChecked", None)
        if val is None and hasattr(cb_passives, "GetIsChecked"):
            val = cb_passives.GetIsChecked()
        if val is not None and val != HUNT_PASSIVE_ANIMALS:
            HUNT_PASSIVE_ANIMALS = bool(val)
            API.SysMsg(f"[HuntAnimals] Passive Animals: {'ON' if HUNT_PASSIVE_ANIMALS else 'OFF'}")

    if cb_predators:
        val = getattr(cb_predators, "IsChecked", None)
        if val is None and hasattr(cb_predators, "GetIsChecked"):
            val = cb_predators.GetIsChecked()
        if val is not None and val != HUNT_PREDATORS:
            HUNT_PREDATORS = bool(val)
            API.SysMsg(f"[HuntAnimals] Predators: {'ON' if HUNT_PREDATORS else 'OFF'}")

    if cb_defend:
        val = getattr(cb_defend, "IsChecked", None)
        if val is None and hasattr(cb_defend, "GetIsChecked"):
            val = cb_defend.GetIsChecked()
        if val is not None and val != AUTO_DEFEND_AGGRESSORS:
            AUTO_DEFEND_AGGRESSORS = bool(val)
            API.SysMsg(f"[HuntAnimals] Auto Defend Threats: {'ON' if AUTO_DEFEND_AGGRESSORS else 'OFF'}")


def on_pause_clicked() -> None:
    """Handles Gump Pause / Resume toggle button."""
    global is_paused
    is_paused = not is_paused
    if btn_pause:
        btn_pause.Text = "Resume" if is_paused else "Pause"
    update_status("Paused" if is_paused else "Scanning...")
    API.SysMsg(f"[HuntAnimals] {'Paused' if is_paused else 'Resumed'}.")


def on_stop_clicked() -> None:
    """Handles Gump Stop button."""
    global is_stopped
    is_stopped = True
    update_status("Stopped")
    API.SysMsg("[HuntAnimals] Stop requested via Gump.")
    API.Stop()


def on_gump_disposed() -> None:
    """Cleanup when Gump is closed by right-click."""
    global is_stopped, gump
    if not is_stopped and not API.StopRequested:
        if gump and getattr(gump, "IsDisposed", False):
            is_stopped = True
            API.Stop()


def create_control_gump() -> None:
    """Constructs the interactive control Gump."""
    global gump, lbl_status, lbl_stats, cb_birds, cb_passives, cb_predators, cb_defend, btn_pause, btn_stop

    gump = API.Gumps.CreateGump(True, True, False)
    gump.SetPos(50, 480)

    # Background panel (dark aesthetic)
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1A1A1A")
    bg.SetRect(0, 0, 290, 162)
    gump.Add(bg)

    # Title
    lbl_title = API.Gumps.CreateGumpLabel("Animal Hunter", 68)
    lbl_title.SetPos(10, 8)
    gump.Add(lbl_title)

    lbl_author = API.Gumps.CreateGumpLabel("by FesterHead", 996)
    lbl_author.SetPos(200, 8)
    gump.Add(lbl_author)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 53)
    lbl_status.SetPos(10, 28)
    gump.Add(lbl_status)

    # Stats label
    lbl_stats = API.Gumps.CreateGumpLabel("Defeated: 0", 996)
    lbl_stats.SetPos(10, 48)
    gump.Add(lbl_stats)

    # Interactive Category Toggles (Checkboxes)
    cb_birds = API.Gumps.CreateGumpCheckbox("Birds", 996, HUNT_BIRDS)
    cb_birds.SetPos(10, 70)
    API.Gumps.AddControlOnClick(cb_birds, on_toggle_birds)
    gump.Add(cb_birds)

    cb_passives = API.Gumps.CreateGumpCheckbox("Passives", 996, HUNT_PASSIVE_ANIMALS)
    cb_passives.SetPos(150, 70)
    API.Gumps.AddControlOnClick(cb_passives, on_toggle_passives)
    gump.Add(cb_passives)

    cb_predators = API.Gumps.CreateGumpCheckbox("Predators", 996, HUNT_PREDATORS)
    cb_predators.SetPos(10, 94)
    API.Gumps.AddControlOnClick(cb_predators, on_toggle_predators)
    gump.Add(cb_predators)

    cb_defend = API.Gumps.CreateGumpCheckbox("Defend Threats", 996, AUTO_DEFEND_AGGRESSORS)
    cb_defend.SetPos(150, 94)
    API.Gumps.AddControlOnClick(cb_defend, on_toggle_defend)
    gump.Add(cb_defend)

    # Control buttons
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 125, 26)
    btn_pause.SetPos(10, 124)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 125, 26)
    btn_stop.SetPos(150, 124)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)
    API.Gumps.AddGump(gump)


def update_status(status_text: str) -> None:
    """Updates the status text on the Gump."""
    global current_status
    current_status = status_text
    if lbl_status:
        lbl_status.Text = f"Status: {status_text}"


def update_stats() -> None:
    """Refreshes kill counter on the Gump."""
    if lbl_stats:
        lbl_stats.Text = f"Defeated: {total_killed}"


def dispose_gump() -> None:
    """Safely disposes the Gump."""
    global gump
    if gump and not getattr(gump, "IsDisposed", False):
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes UI events and checks pause state."""
    global is_paused, is_stopped
    API.ProcessCallbacks()
    sync_checkboxes()
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
        sync_checkboxes()
        update_stats()
        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            on_pause_clicked()
            break

    return not (is_stopped or API.StopRequested)


# ==============================================================================
# Wildlife Identification & Targeting
# ==============================================================================

def is_aggressive_mobile(mob) -> bool:
    """
    Checks if a mobile is an actual hostile/aggressive threat targeting or threatening the player.
    Passive wildlife (cows, deer, sheep, birds, llamas, pigs, rabbits) are NEVER considered aggressive threats.
    """
    if not mob or mob.Serial == API.Player.Serial:
        return False
    if getattr(mob, "IsDead", False) or getattr(mob, "IsGhost", False):
        return False
    if getattr(mob, "IsYellowHits", False):
        return False

    graphic = mob.Graphic
    name = (mob.Name or "").lower()

    # Passive wildlife and birds are NEVER aggressive threats
    if graphic in PASSIVE_ANIMAL_GRAPHICS or graphic in BIRD_GRAPHICS:
        return False
    if any(kw in name for kw in PASSIVE_ANIMAL_KEYWORDS) or any(kw in name for kw in BIRD_NAME_KEYWORDS):
        return False

    dist = get_mobile_distance(mob)

    # 1. Any non-passive mobile actively in War Mode within combat proximity (actively attacking or targeting player)
    if getattr(mob, "InWarMode", False) and dist <= 10:
        return True

    # 2. Explicitly Hostile Notoriety: Enemy or Murderer (Orange/Red)
    if mob.Notoriety in (API.Notoriety.Enemy, API.Notoriety.Murderer):
        return True

    return False


def is_target_animal(mob) -> bool:
    """Checks if a given mobile matches active animal hunting categories."""
    try:
        if not mob:
            return False

        # Ignore player
        if mob.Serial == API.Player.Serial:
            return False

        # Ignore dead or ghosts
        if getattr(mob, "IsDead", False) or getattr(mob, "IsGhost", False):
            return False
        # In UO network protocol, Hits is 0 for ambient wildlife until status is requested.
        # Only treat as dead by health if HitsMax is known (> 0) and Hits is depleted (<= 0).
        if getattr(mob, "HitsMax", 0) > 0 and getattr(mob, "Hits", 0) <= 0:
            return False

        # Ignore invulnerable / yellow hits mobiles (e.g. blessed vendors or protected creatures)
        if getattr(mob, "IsYellowHits", False):
            return False

        # Aggressive threat self-defense: always a valid target
        if AUTO_DEFEND_AGGRESSORS and is_aggressive_mobile(mob):
            return True

        graphic = mob.Graphic
        name = (mob.Name or "").lower()
        matched = False

        # 1. Birds category
        if HUNT_BIRDS:
            if graphic in BIRD_GRAPHICS or any(kw in name for kw in BIRD_NAME_KEYWORDS):
                matched = True

        # 2. Passive animals category (Deer, Cows, Pigs, Sheep, Goats, Llamas, Horses, Rabbits)
        if not matched and HUNT_PASSIVE_ANIMALS:
            if graphic in PASSIVE_ANIMAL_GRAPHICS or any(kw in name for kw in PASSIVE_ANIMAL_KEYWORDS):
                matched = True

        # 3. Predators category (Wolves, Bears, Cougars, Panthers)
        if not matched and HUNT_PREDATORS:
            if graphic in PREDATOR_GRAPHICS or any(kw in name for kw in PREDATOR_KEYWORDS):
                matched = True

        return matched
    except Exception as ex:
        debug_msg(f"Exception in is_target_animal: {ex}")
        return False


def get_mobile_distance(mob) -> int:
    """Safely calculates the distance to a mobile in tiles."""
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


def find_nearby_animals() -> List:
    """Finds all living wild animals matching active categories, sorted with aggressive threats first."""
    try:
        all_mobiles = API.GetAllMobiles()
        if not all_mobiles:
            all_mobiles = API.NearestMobiles(
                [
                    API.Notoriety.Innocent,
                    API.Notoriety.Gray,
                    API.Notoriety.Unknown,
                    API.Notoriety.Enemy,
                    API.Notoriety.Criminal,
                ],
                maxDistance=SEARCH_RADIUS,
            ) or []

        targets = []
        for m in all_mobiles:
            if not m or m.Serial == API.Player.Serial:
                continue
            dist = get_mobile_distance(m)
            if dist > SEARCH_RADIUS:
                continue
            if is_target_animal(m):
                is_aggro = 0 if is_aggressive_mobile(m) else 1
                targets.append((is_aggro, dist, m))

        # Sort: aggressive threats first (0 before 1), then closest distance first
        targets.sort(key=lambda t: (t[0], t[1]))
        return [t[2] for t in targets]
    except Exception as ex:
        API.SysMsg(f"[HuntAnimals] Error in find_nearby_animals: {ex}")
        return []


# ==============================================================================
# Corpse Carving & AutoLoot Processing
# ==============================================================================

def find_bladed_tool():
    """Finds an equipped or backpack bladed tool or axe to carve corpses."""
    # Check hands
    for layer in ["OneHanded", "TwoHanded"]:
        item = API.FindLayer(layer)
        if item and item.Graphic in BLADE_GRAPHICS:
            return item

    # Check backpack
    for graphic in BLADE_GRAPHICS:
        found = API.FindType(graphic, API.Backpack)
        if found:
            return found

    return None


def process_corpse(corpse_serial: int) -> None:
    """Carves animal corpse (to yield hides/feathers/ribs/wool) and invokes TazUO AutoLoot."""
    # 1. Carve corpse if enabled
    if AUTO_CARVE_CORPSE:
        blade = find_bladed_tool()
        if blade:
            debug_msg(f"Carving corpse 0x{corpse_serial:X} with tool 0x{blade.Serial:X}...")
            update_status("Carving corpse...")
            API.ClearJournal()
            API.UseObject(blade.Serial)
            if API.WaitForTarget(timeout=1.5):
                API.Target(corpse_serial)
                API.Pause(0.5)
        else:
            debug_msg("No bladed tool or axe found to carve corpse.")

    # 2. Open corpse container for client autoloot
    if OPEN_CORPSE_FOR_AUTOLOOT:
        debug_msg(f"Opening corpse 0x{corpse_serial:X} for TazUO AutoLoot...")
        update_status("Opening corpse...")
        API.UseObject(corpse_serial)
        API.Pause(CORPSE_PROCESSING_DELAY)

    # 3. Explicitly trigger TazUO native AutoLoot agent on corpse
    if TRIGGER_TAZUO_AUTOLOOT:
        debug_msg(f"Triggering AutoLootContainer on 0x{corpse_serial:X}...")
        update_status("AutoLooting...")
        API.AutoLootContainer(corpse_serial)
        API.Pause(CORPSE_PROCESSING_DELAY)


# ==============================================================================
# Combat Loop
# ==============================================================================

def equip_dress_profile() -> bool:
    """Equips the configured dress profile with validation, case-insensitive lookup, and War Mode safety."""
    global DRESS_PROFILE
    if not DRESS_PROFILE:
        return True

    try:
        available = API.GetAvailableDressOutfits() or []
        target_profile = DRESS_PROFILE

        if available:
            match = next((o for o in available if o.lower() == DRESS_PROFILE.lower()), None)
            if match:
                target_profile = match
            else:
                API.SysMsg(f"[HuntAnimals] WARNING: Dress profile '{DRESS_PROFILE}' not found in TazUO! Available: {', '.join(available)}")
                return False

        # In UO, equipment changes are rejected if currently in War Mode
        if API.Player.InWarMode:
            API.SetWarMode(False)
            API.Pause(0.3)

        API.SysMsg(f"[HuntAnimals] Equipping '{target_profile}' dress profile...")
        API.Dress(target_profile)
        # Give TazUO client and server sufficient time to unequip tool and equip weapon (drag/drop delays)
        API.Pause(max(DRESS_DELAY, 1.25))

        # Verification check: did a weapon equip in either hand?
        has_weapon = API.FindLayer("OneHanded") or API.FindLayer("TwoHanded")
        if not has_weapon:
            debug_msg("Hand layers still empty after dress, retrying Dress...")
            API.Dress(target_profile)
            API.Pause(0.6)

        return True
    except Exception as ex:
        API.SysMsg(f"[HuntAnimals] Error equipping dress profile: {ex}")
        return False


def engage_animal(animal, is_defense: bool = False) -> bool:
    """
    Arms weapon, enters War Mode, and hunts the target animal until defeated.
    Returns True if animal was killed, False if timeout or escaped.
    """
    global total_killed

    target_name = animal.Name or ("Hostile Threat" if is_defense else "Animal")
    target_serial = animal.Serial
    dist = get_mobile_distance(animal)
    action_type = "DEFENDING against" if is_defense else "Engaging"
    API.SysMsg(f"[HuntAnimals] {action_type} '{target_name}' (0x{target_serial:X}) at dist {dist}...")
    update_status(f"{'Defending: ' if is_defense else 'Hunting '}{target_name}...")

    # 1. Equip combat dress profile to arm weapon
    equip_dress_profile()

    # 2. Enter War Mode
    API.SetWarMode(True)
    API.Pause(0.25)

    # 3. Command attack
    API.Attack(target_serial)

    # 4. Chase and attack loop
    start_time = time.time()
    killed = False

    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Check combat timeout
        elapsed = time.time() - start_time
        if elapsed > COMBAT_TIMEOUT:
            API.SysMsg(f"[HuntAnimals] Combat timeout ({COMBAT_TIMEOUT}s) for '{target_name}'. Target escaped.")
            break

        # Check if mobile still exists in game world
        current_mob = API.FindMobile(target_serial)
        if not current_mob:
            debug_msg(f"Target 0x{target_serial:X} no longer exists. Mobile eliminated!")
            killed = True
            break

        # Check if dead
        if getattr(current_mob, "IsDead", False) or getattr(current_mob, "IsGhost", False):
            debug_msg(f"Target 0x{target_serial:X} marked dead. Mobile eliminated!")
            killed = True
            break

        if getattr(current_mob, "HitsMax", 0) > 0 and getattr(current_mob, "Hits", 0) <= 0:
            debug_msg(f"Target 0x{target_serial:X} hits depleted. Mobile eliminated!")
            killed = True
            break

        # If animal moved or fled, follow it
        dist = get_mobile_distance(current_mob)
        if dist > 1:
            update_status(f"Chasing {target_name} ({dist}t)...")
            API.PathfindEntity(target_serial, distance=1, wait=False, run=True)
            API.Attack(target_serial)

        API.Pause(0.4)

    # 5. Clean up combat state
    API.SetWarMode(False)

    if killed:
        total_killed += 1
        API.SysMsg(f"[HuntAnimals] '{target_name}' defeated! (Total Kills: {total_killed})")

        # 6. Corpse processing for TazUO AutoLoot
        if AUTO_CARVE_CORPSE or OPEN_CORPSE_FOR_AUTOLOOT or TRIGGER_TAZUO_AUTOLOOT:
            API.Pause(0.3)
            corpse = API.NearestCorpse(distance=6)
            if corpse:
                cdist = get_mobile_distance(corpse)
                if cdist > 2:
                    API.PathfindEntity(corpse.Serial, distance=1, wait=True, timeout=3)
                process_corpse(corpse.Serial)

    update_status("Scanning...")
    API.Pause(1.0)
    return killed


# ==============================================================================
# Lifecycle Callbacks
# ==============================================================================

def on_stop() -> None:
    """Invoked when the script is stopped from the client UI."""
    # Ensure war mode is off
    API.SetWarMode(False)

    dispose_gump()
    API.SysMsg("[HuntAnimals] Script stopped.")

API.OnStop(on_stop)


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    global total_spotted

    create_control_gump()
    update_status("Scanning...")
    update_stats()

    cats = []
    if HUNT_BIRDS:
        cats.append("Birds")
    if HUNT_PASSIVE_ANIMALS:
        cats.append("Passives")
    if HUNT_PREDATORS:
        cats.append("Predators")

    # Validate dress profile against available outfits in TazUO
    global DRESS_PROFILE
    available_outfits = API.GetAvailableDressOutfits() or []
    if DRESS_PROFILE and available_outfits:
        match = next((o for o in available_outfits if o.lower() == DRESS_PROFILE.lower()), None)
        if match:
            DRESS_PROFILE = match
        else:
            API.SysMsg(f"[HuntAnimals] WARNING: Dress profile '{DRESS_PROFILE}' not found in TazUO! Available: {', '.join(available_outfits)}")

    API.SysMsg(f"[HuntAnimals] Animal Hunter initialized (Radius: {SEARCH_RADIUS}t, Categories: {', '.join(cats)}, Dress: '{DRESS_PROFILE}').")

    # Main detection loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        animals = find_nearby_animals()
        if animals:
            target = animals[0]
            is_aggro = is_aggressive_mobile(target)
            total_spotted += 1
            engage_animal(target, is_defense=is_aggro)
        else:
            update_status("Scanning...")
            API.Pause(SCAN_INTERVAL)

    update_status("Finished")
    API.SysMsg(f"[HuntAnimals] Hunting ended. Total Defeated: {total_killed}.")


main()
