"""
SmeltOreUOAlive.py - Automated Pack Pet Ore Smelter for UOAlive

Author: FesterHead
Target Client: TazUO (Legion Scripting Engine)
Target Shard: UOAlive

Description:
    Automates extracting raw ore from your Pack Llama, Pack Horse, or Giant Beetle
    and smelting it into ingots at a nearby forge:
    - Automatically detects nearby pack animals and connects to their backpack.
    - Automatically detects nearby forges (ground items, map statics, or Fire Beetles).
    - Features smart batch weight protection and Dual Smelting Modes:
        * Skill Gain Mode (Default): Extracts minimum smeltable amounts (1 medium/large ore,
          2 small ore) per attempt to maximize Mining skill gain checks. Any existing bulk
          ore stacks in the backpack are automatically offloaded to the pack pet.
        * Bulk Mode: Moves safe bulk batches (default: 25-30 ore) based on remaining
          character weight capacity for rapid ingot smelting.
        * Interactive Gump toggle button allows switching modes on the fly.
    - All completed ingots remain neatly in your backpack.
    - Features an interactive control Gump (330x215) displaying:
        * Status, Pet Ore remaining, Backpack Ingots & Smelted counters (with active mode)
        * Live Mining skill tracking with gain announcements
        * Player STR, DEX, and Weight capacity monitoring
        * Interactive Mode Toggle, Set Forge, Pause/Resume, Pack Pet, and Stop buttons.

Usage:
    1. Stand next to a Forge (or Fire Beetle) with your Pack Llama nearby.
    2. Start the script in TazUO.
    3. (Optional) Use "Set Forge" if standing near an unusual forge addon.
    4. Watch the script automatically extract and smelt all ore into ingots!
"""

from typing import List, Optional, Tuple
import API

# ==============================================================================
# Configuration
# ==============================================================================

# Enable verbose logging in the client console/journal
DEBUG: bool = False

# Maximum distance in tiles to interact with the pack animal
PACK_ANIMAL_MAX_DISTANCE: int = 3

# Maximum distance in tiles to interact with the forge
FORGE_MAX_DISTANCE: int = 3

# Skill Gain Mode: when True, smelts in minimum pieces (1 medium/large ore, 2 small ore)
# for maximum Mining skill checks. When False, smelts in bulk batches (up to MAX_BATCH_ORE).
SKILL_GAIN_MODE: bool = True

# Maximum ore pieces to pull per batch when in Bulk Mode (clamped by free weight)
MAX_BATCH_ORE: int = 30

# Weight buffer below maximum capacity to prevent overburdening
WEIGHT_BUFFER: int = 15

# Delay in seconds between drag/drop and smelting actions
ACTION_DELAY: float = 0.6

# Alert sound played when paused or completed (0x1F8 = classic system notice chime)
ALERT_SOUND: int = 0x1F8

# ==============================================================================
# Graphics Definitions
# ==============================================================================

# Ore graphics (small, medium, large, small pile)
ORE_GRAPHICS: List[int] = [
    0x19B7, 0x19B8, 0x19B9, 0x19BA
]

# Ingot graphics (all metal varieties)
INGOT_GRAPHICS: List[int] = [
    0x1BF2, 0x1BEF, 0x1BF0, 0x1BF1
]

# Pack animals (Pack Horse, Pack Llama, Giant Beetle)
PACK_ANIMAL_GRAPHICS: List[int] = [
    0x0123,  # Pack Horse
    0x0124,  # Pack Llama
    0x0317,  # Giant Beetle
]

# All classic and modern forge graphics in Ultima Online
FORGE_GRAPHICS: List[int] = [
    0x0FB1,  # Small stone/round forge (classic circular hearth)
    0x197A, 0x197B, 0x197C, 0x197D, 0x197E, 0x197F,
    0x1980, 0x1981, 0x1982, 0x1983, 0x1984, 0x1985,
    0x1986, 0x1987, 0x1988, 0x1989, 0x198A, 0x198B,
    0x198C, 0x198D, 0x198E, 0x198F, 0x1990, 0x1991,
    0x1992, 0x1993, 0x1994, 0x1995, 0x1996, 0x1997,
    0x1998, 0x1999, 0x199A, 0x199B, 0x199C, 0x199D,
    0x199E, 0x199F, 0x19A0, 0x19A1, 0x19A2,
    0x2DD8,  # Elven / Soul Forge
    0x398C, 0x3996,  # Gargish forges
    0x4017,  # Alternate stone forge ID
]

# ==============================================================================
# Global Gump & State Management
# ==============================================================================

gump = None
lbl_status = None
lbl_pet_ore = None
lbl_ingots = None
lbl_skill = None
lbl_stats = None
btn_mode = None
btn_pause = None
btn_forge = None
btn_pet = None
btn_stop = None

skill_gain_mode: bool = SKILL_GAIN_MODE
is_paused: bool = False
is_stopped: bool = False
total_ore_smelted: int = 0
initial_ingot_count: int = 0
unsmeltable_serials: set = set()

pack_animal_serial: Optional[int] = None
pack_container_serial: Optional[int] = None
forge_target_obj = None

last_mining_skill: Optional[float] = None
last_str: Optional[int] = None
last_dex: Optional[int] = None


def debug_msg(text: str) -> None:
    """Outputs debug message if DEBUG is enabled."""
    if DEBUG:
        API.SysMsg(f"[Smelter] {text}", 88)


def update_status(text: str) -> None:
    """Updates the status display on the Gump and prints to debug if enabled."""
    global lbl_status
    if lbl_status:
        lbl_status.Text = f"Status: {text}"
    debug_msg(text)


def update_stats() -> None:
    """Refreshes pet ore count, backpack ingots, mining skill, and character stats."""
    global last_mining_skill, last_str, last_dex
    global lbl_pet_ore, lbl_ingots, lbl_skill, lbl_stats

    # 1. Pet Ore remaining
    if lbl_pet_ore:
        p_ore = get_pack_animal_ore_count()
        pname = "Pet"
        animal = find_nearby_pack_animal(PACK_ANIMAL_MAX_DISTANCE)
        if animal:
            pname = getattr(animal, "Name", "Pet") or "Pet"
        lbl_pet_ore.Text = f"Pet Ore: {p_ore} remaining ({pname[:10]})"

    # 2. Backpack Ingots & Smelted count
    if lbl_ingots:
        cur_ingots = get_backpack_ingot_count()
        mode_str = "Skill Gain" if skill_gain_mode else "Bulk"
        lbl_ingots.Text = f"Backpack Ingots: {cur_ingots} (Smelted: {total_ore_smelted}) [{mode_str}]"

    # 3. Mining skill
    skill_obj = API.GetSkill("Mining")
    if skill_obj and lbl_skill:
        val = float(skill_obj.Value)
        cap = float(skill_obj.Cap)
        lbl_skill.Text = f"Mining: {val:.1f} / {cap:.1f}"
        if last_mining_skill is not None and val > last_mining_skill:
            gain = val - last_mining_skill
            API.SysMsg(f"Mining gained +{gain:.1f}! New: {val:.1f}", 68)
        last_mining_skill = val

    # 4. Character stats and weight
    cur_str = API.Player.Strength
    cur_dex = API.Player.Dexterity
    cur_wt = API.Player.Weight
    max_wt = API.Player.WeightMax

    if lbl_stats and cur_str is not None and cur_dex is not None:
        wt_str = f"{cur_wt}/{max_wt}" if cur_wt is not None and max_wt is not None else "--/--"
        f_name = "Forge: OK" if forge_target_obj else "Forge: None"
        lbl_stats.Text = f"STR: {cur_str} | DEX: {cur_dex} | Wt: {wt_str} | {f_name}"
        last_str = cur_str
        last_dex = cur_dex


def trigger_overweight_pause() -> None:
    """Auto-pauses the script when the player is full."""
    global is_paused, btn_pause
    if not is_paused:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused: Too Full!")
        API.HeadMsg("TOO FULL! SCRIPT PAUSED", API.Player, 32)
        API.SysMsg("Backpack weight limit reached! Please lighten your pack before resuming.", 32)
        if ALERT_SOUND > 0:
            API.PlaySound(ALERT_SOUND)


def trigger_insufficient_ore_pause(reason: str = "Not enough metal-bearing ore in pile!") -> None:
    """Auto-pauses the script when an ore pile cannot be smelted."""
    global is_paused, btn_pause
    if not is_paused:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused: Not Enough Ore")
        API.HeadMsg("NOT ENOUGH ORE!", API.Player, 32)
        API.SysMsg(f"{reason} Auto-paused for player inspection.", 32)
        if ALERT_SOUND > 0:
            API.PlaySound(ALERT_SOUND)


def on_pause_clicked() -> None:
    """Callback triggered when the Pause/Resume button is clicked on the Gump."""
    global is_paused, btn_pause
    if is_paused:
        is_paused = False
        if btn_pause:
            btn_pause.SetText("Pause")
        update_status("Resuming...")
        API.SysMsg("Ore smelter resumed.")
    else:
        is_paused = True
        if btn_pause:
            btn_pause.SetText("Resume")
        update_status("Paused")
        API.SysMsg("Ore smelter paused.")


def on_mode_clicked() -> None:
    """Toggles between Skill Gain Mode and Bulk Mode."""
    global skill_gain_mode, btn_mode
    skill_gain_mode = not skill_gain_mode
    if skill_gain_mode:
        if btn_mode:
            btn_mode.SetText("Mode: Skill Gain")
        update_status("Skill Gain Mode")
        API.SysMsg("Skill Gain Mode enabled: smelting 1-2 ore per attempt for max skill gain.", 68)
        offload_excess_backpack_ore_to_pet()
    else:
        if btn_mode:
            btn_mode.SetText("Mode: Bulk")
        update_status("Bulk Mode")
        API.SysMsg("Bulk Mode enabled: smelting full batches.", 68)
    update_stats()


def on_set_forge_clicked() -> None:
    """Allows manual targeting of a Forge or Fire Beetle."""
    global forge_target_obj
    API.SysMsg("Target a Forge, Anvil addon, or Fire Beetle (or press ESC to auto-detect)...")
    target_serial = API.RequestTarget(timeout=10.0)
    if target_serial:
        item = API.FindItem(target_serial)
        mob = API.FindMobile(target_serial)
        if item:
            forge_target_obj = item
            name = getattr(item, "Name", "Forge") or "Forge"
            API.SysMsg(f"Forge set to {name} [0x{target_serial:X}].", 68)
        elif mob:
            forge_target_obj = mob
            name = getattr(mob, "Name", "Fire Beetle") or "Fire Beetle"
            API.SysMsg(f"Forge set to {name} [0x{target_serial:X}].", 68)
        else:
            forge_target_obj = target_serial
            API.SysMsg(f"Forge set to target [0x{target_serial:X}].", 68)
    else:
        forge_target_obj = find_nearby_forge()
        if forge_target_obj:
            API.SysMsg("Auto-detected nearby Forge.", 68)
        else:
            API.SysMsg("No forge detected within reach.", 53)
    update_stats()


def on_pack_pet_clicked() -> None:
    """Allows player to manually select their Pack Horse, Pack Llama, or Giant Beetle."""
    global pack_animal_serial, pack_container_serial
    API.SysMsg("Target your Pack Horse, Pack Llama, or Beetle (or press ESC to auto-detect)...")
    target_serial = API.RequestTarget(timeout=10.0)
    if target_serial and target_serial != API.Player.Serial:
        mob = API.FindMobile(target_serial)
        if mob:
            pack_animal_serial = target_serial
            pack_container_serial = None
            name = getattr(mob, "Name", "Pack Pet") or "Pack Pet"
            API.SysMsg(f"Pack animal set to {name} [0x{target_serial:X}].", 68)
            container = get_pack_animal_container(mob, open_if_needed=True)
            if container:
                pack_container_serial = getattr(container, "Serial", container)
            update_stats()
            return

    animal = find_nearby_pack_animal(max_distance=4)
    if animal:
        name = getattr(animal, "Name", "Pack Pet") or "Pack Pet"
        API.SysMsg(f"Auto-detected pack animal: {name} [0x{animal.Serial:X}].", 68)
        container = get_pack_animal_container(animal, open_if_needed=True)
        if container:
            pack_container_serial = getattr(container, "Serial", container)
    else:
        API.SysMsg("No pack animal detected within reach.", 53)
    update_stats()


def on_stop_clicked() -> None:
    """Callback triggered when the Stop button is clicked on the Gump."""
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
    """Initializes and renders the interactive UOAlive Auto Ore Smelter Gump."""
    global gump, lbl_status, lbl_pet_ore, lbl_ingots, lbl_skill, lbl_stats
    global btn_mode, btn_pause, btn_forge, btn_pet, btn_stop

    gump = API.Gumps.CreateGump(acceptMouseInput=True, canMove=True, keepOpen=False)
    gump.SetRect(100, 100, 330, 215)

    # Semi-transparent dark background
    bg = API.Gumps.CreateGumpColorBox(0.8, "#1A1A1A")
    bg.SetRect(0, 0, 330, 215)
    gump.Add(bg)

    # Title label (gold hue 53)
    title = API.Gumps.CreateGumpLabel("UOAlive Auto Ore Smelter", 53)
    title.SetPos(12, 8)
    gump.Add(title)

    # Status label
    lbl_status = API.Gumps.CreateGumpLabel("Status: Initializing...", 996)
    lbl_status.SetPos(12, 30)
    gump.Add(lbl_status)

    # Pet Ore remaining counter
    lbl_pet_ore = API.Gumps.CreateGumpLabel("Pet Ore: 0 remaining", 996)
    lbl_pet_ore.SetPos(12, 52)
    gump.Add(lbl_pet_ore)

    # Backpack Ingots & Smelted counter
    lbl_ingots = API.Gumps.CreateGumpLabel("Backpack Ingots: 0 (Smelted: 0)", 996)
    lbl_ingots.SetPos(12, 74)
    gump.Add(lbl_ingots)

    # Mining skill label
    lbl_skill = API.Gumps.CreateGumpLabel("Mining: --", 996)
    lbl_skill.SetPos(12, 96)
    gump.Add(lbl_skill)

    # Character stats and weight
    lbl_stats = API.Gumps.CreateGumpLabel("STR: -- | DEX: -- | Wt: --/--", 996)
    lbl_stats.SetPos(12, 118)
    gump.Add(lbl_stats)

    # Row 1 Buttons (y=146)
    mode_text = "Mode: Skill Gain" if skill_gain_mode else "Mode: Bulk"
    btn_mode = API.Gumps.CreateSimpleButton(mode_text, 150, 24)
    btn_mode.SetPos(10, 146)
    API.Gumps.AddControlOnClick(btn_mode, on_mode_clicked)
    gump.Add(btn_mode)

    btn_forge = API.Gumps.CreateSimpleButton("Set Forge", 150, 24)
    btn_forge.SetPos(170, 146)
    API.Gumps.AddControlOnClick(btn_forge, on_set_forge_clicked)
    gump.Add(btn_forge)

    # Row 2 Buttons (y=176)
    btn_pause = API.Gumps.CreateSimpleButton("Pause", 95, 24)
    btn_pause.SetPos(10, 176)
    API.Gumps.AddControlOnClick(btn_pause, on_pause_clicked)
    gump.Add(btn_pause)

    btn_pet = API.Gumps.CreateSimpleButton("Pack Pet", 100, 24)
    btn_pet.SetPos(115, 176)
    API.Gumps.AddControlOnClick(btn_pet, on_pack_pet_clicked)
    gump.Add(btn_pet)

    btn_stop = API.Gumps.CreateSimpleButton("Stop", 95, 24)
    btn_stop.SetPos(225, 176)
    API.Gumps.AddControlOnClick(btn_stop, on_stop_clicked)
    gump.Add(btn_stop)

    # Handle gump right-click close
    API.Gumps.AddControlOnDisposed(gump, on_gump_disposed)

    API.Gumps.AddGump(gump)


def dispose_gump() -> None:
    """Safely removes the Gump window from the screen."""
    global gump
    if gump and not gump.IsDisposed:
        gump.Dispose()


def check_ui_events() -> bool:
    """Processes Gump callbacks, updates stats, and handles pause states."""
    global is_paused, is_stopped
    API.ProcessCallbacks()
    update_stats()

    if is_stopped or API.StopRequested:
        return False

    if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
        on_stop_clicked()
        return False

    if btn_mode and getattr(btn_mode, "HasBeenClicked", lambda: False)():
        on_mode_clicked()

    if btn_forge and getattr(btn_forge, "HasBeenClicked", lambda: False)():
        on_set_forge_clicked()

    if btn_pet and getattr(btn_pet, "HasBeenClicked", lambda: False)():
        on_pack_pet_clicked()

    if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
        on_pause_clicked()

    while is_paused and not API.StopRequested and not is_stopped:
        API.Pause(0.15)
        API.ProcessCallbacks()
        update_stats()
        if btn_stop and getattr(btn_stop, "HasBeenClicked", lambda: False)():
            on_stop_clicked()
            return False
        if btn_mode and getattr(btn_mode, "HasBeenClicked", lambda: False)():
            on_mode_clicked()
        if btn_forge and getattr(btn_forge, "HasBeenClicked", lambda: False)():
            on_set_forge_clicked()
        if btn_pet and getattr(btn_pet, "HasBeenClicked", lambda: False)():
            on_pack_pet_clicked()
        if btn_pause and getattr(btn_pause, "HasBeenClicked", lambda: False)():
            on_pause_clicked()
            if not is_paused:
                break

    return not is_stopped and not API.StopRequested


def wait_with_ui(seconds: float) -> bool:
    """Time-sliced delay that continues processing UI callbacks."""
    elapsed = 0.0
    step = 0.1
    while elapsed < seconds:
        if not check_ui_events():
            return False
        API.Pause(step)
        elapsed += step
    return check_ui_events()


def is_ore_smeltable(ore) -> bool:
    """Checks if an ore stack has enough pieces to make an ingot."""
    graphic = getattr(ore, "Graphic", 0)
    amt = getattr(ore, "Amount", 1) or 1
    # Small ore (0x19B7) requires at least 2 pieces to smelt into an ingot
    if graphic == 0x19B7 and amt < 2:
        return False
    return True


def get_min_smelt_amount(graphic: int) -> int:
    """Returns the minimum ore units required to smelt (2 for small ore 0x19B7, 1 for other)."""
    return 2 if graphic == 0x19B7 else 1


# ==============================================================================
# Helper Functions: Inventory, Pet & Forge
# ==============================================================================

def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Calculates tile distance between two coordinates."""
    return max(abs(x1 - x2), abs(y1 - y2))


def get_all_backpack_items() -> List:
    """Safely retrieves all items inside the player's backpack using recursive=False."""
    all_items = []
    to_scan = [API.Backpack]
    visited = set()

    while to_scan:
        container_id = to_scan.pop(0)
        if not container_id or container_id in visited:
            continue
        visited.add(container_id)

        items = API.ItemsInContainer(container_id, recursive=False)
        if items is None:
            items = API.ItemsInContainer(container_id)
        if items:
            for item in items:
                all_items.append(item)
                graphic = getattr(item, "Graphic", 0)
                if getattr(item, "IsContainer", False) or graphic in [
                    0x0E75, 0x0E76, 0x0E79, 0x0E7D, 0x0E7E, 0x0E80, 0x09B0, 0x0E40, 0x0E41, 0x0E42, 0x0E43
                ]:
                    sub_serial = getattr(item, "Serial", None)
                    if sub_serial and sub_serial not in visited:
                        to_scan.append(sub_serial)

    return all_items


def get_backpack_ingot_count() -> int:
    """Counts total ingots currently inside the player's backpack."""
    total = 0
    items = get_all_backpack_items()
    for item in items:
        graphic = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()
        if graphic in INGOT_GRAPHICS or ("ingot" in name):
            total += getattr(item, "Amount", 1) or 1
    return total


def find_nearby_pack_animal(max_distance: int = PACK_ANIMAL_MAX_DISTANCE):
    """Finds a nearby Pack Horse, Pack Llama, or Giant Beetle."""
    global pack_animal_serial

    if pack_animal_serial:
        mob = API.FindMobile(pack_animal_serial)
        if mob and not getattr(mob, "IsDead", False):
            if chebyshev_distance(API.Player.X, API.Player.Y, mob.X, mob.Y) <= max_distance:
                return mob

    mobiles = API.GetAllMobiles()
    if not mobiles:
        return None

    px = API.Player.X
    py = API.Player.Y
    closest_mob = None
    min_dist = max_distance + 1

    for mob in mobiles:
        if not mob or mob.Serial == API.Player.Serial or getattr(mob, "IsDead", False):
            continue
        graphic = getattr(mob, "Graphic", 0)
        if graphic in PACK_ANIMAL_GRAPHICS:
            dist = chebyshev_distance(px, py, mob.X, mob.Y)
            if dist <= max_distance and dist < min_dist:
                min_dist = dist
                closest_mob = mob

    if closest_mob:
        pack_animal_serial = closest_mob.Serial
        return closest_mob

    return None


def get_pack_animal_container(animal, open_if_needed: bool = False):
    """Retrieves the backpack/container item for the pack animal."""
    global pack_container_serial
    if not animal:
        return None

    animal_serial = getattr(animal, "Serial", animal)

    if pack_container_serial:
        cont = API.FindItem(pack_container_serial)
        if cont:
            return cont

    if hasattr(animal, "Backpack") and animal.Backpack:
        pack_container_serial = getattr(animal.Backpack, "Serial", animal.Backpack)
        return animal.Backpack

    layer_item = API.FindLayer("Backpack", animal_serial)
    if layer_item:
        pack_container_serial = getattr(layer_item, "Serial", layer_item)
        return layer_item

    if open_if_needed:
        API.UseObject(animal_serial)
        API.Pause(0.5)

        if hasattr(animal, "Backpack") and animal.Backpack:
            pack_container_serial = getattr(animal.Backpack, "Serial", animal.Backpack)
            return animal.Backpack

        layer_item = API.FindLayer("Backpack", animal_serial)
        if layer_item:
            pack_container_serial = getattr(layer_item, "Serial", layer_item)
            return layer_item

    return None


def get_pack_animal_ores() -> List:
    """Finds all ore items inside the pack animal's backpack."""
    animal = find_nearby_pack_animal(PACK_ANIMAL_MAX_DISTANCE)
    if not animal:
        return []

    container = get_pack_animal_container(animal, open_if_needed=True)
    if not container:
        return []

    cont_serial = getattr(container, "Serial", container)
    items = API.ItemsInContainer(cont_serial, recursive=False)
    if not items:
        return []

    ores = []
    for item in items:
        graphic = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()
        if graphic in ORE_GRAPHICS or ("ore" in name and "scoreboard" not in name):
            ores.append(item)
    return ores


def get_pack_animal_ore_count() -> int:
    """Counts total ore units remaining in the pack animal."""
    ores = get_pack_animal_ores()
    total = 0
    for o in ores:
        total += getattr(o, "Amount", 1) or 1
    return total


def find_nearby_forge():
    """
    Finds a nearby forge within reach.
    Checks:
    1. Manually set forge object
    2. Dynamic ground items (placed house addons, craft tables, circular stone forges)
    3. Map statics (blacksmith shop forges)
    4. Fire Beetles (mobile forge)
    """
    global forge_target_obj

    if forge_target_obj:
        return forge_target_obj

    px = API.Player.X
    py = API.Player.Y

    # 1. Check dynamic ground items
    ground_items = API.GetItemsOnGround(distance=FORGE_MAX_DISTANCE)
    if ground_items:
        for item in ground_items:
            g = getattr(item, "Graphic", 0)
            name = str(getattr(item, "Name", "") or "").lower()
            if g in FORGE_GRAPHICS or "forge" in name:
                debug_msg(f"Forge detected on ground: 0x{item.Serial:X} Graphic 0x{g:04X} at ({item.X}, {item.Y})")
                return item

    # 2. Check map statics
    statics = API.GetStaticsInArea(px - FORGE_MAX_DISTANCE, py - FORGE_MAX_DISTANCE, px + FORGE_MAX_DISTANCE, py + FORGE_MAX_DISTANCE)
    if statics:
        for s in statics:
            sg = getattr(s, "Graphic", 0)
            name = str(getattr(s, "Name", "") or "").lower()
            if sg in FORGE_GRAPHICS or "forge" in name:
                debug_msg(f"Forge detected as static: Graphic 0x{sg:04X} at ({s.X}, {s.Y})")
                return s

    # 3. Check for nearby Fire Beetle (mobile forge)
    mobiles = API.GetAllMobiles(distance=FORGE_MAX_DISTANCE)
    if mobiles:
        for m in mobiles:
            name = str(getattr(m, "Name", "") or "").lower()
            if getattr(m, "Graphic", 0) == 0x0317 and "fire" in name:
                debug_msg(f"Fire Beetle detected as mobile forge: 0x{m.Serial:X}")
                return m

    return None


def target_forge(forge) -> bool:
    """Directs target cursor onto the forge object (item, static, or mobile)."""
    if hasattr(forge, "Serial") and getattr(forge, "Serial", 0) != 0:
        API.Target(forge.Serial)
        API.Pause(0.15)
        if not API.HasTarget():
            return True

    # If static or coordinate-based
    fx = int(getattr(forge, "X", 0))
    fy = int(getattr(forge, "Y", 0))
    fz = int(getattr(forge, "Z", 0))
    fg = int(getattr(forge, "Graphic", 0))

    API.Target(fx, fy, fz, fg)
    API.Pause(0.15)
    if not API.HasTarget():
        return True

    dx = fx - API.Player.X
    dy = fy - API.Player.Y
    API.TargetTileRel(dx, dy, fg)
    API.Pause(0.15)
    return not API.HasTarget()


# ==============================================================================
# Smelting Engine
# ==============================================================================

def offload_excess_backpack_ore_to_pet() -> int:
    """
    In Skill Gain Mode, offloads bulk ore stacks (> 1 or > 2 for small ore) from backpack
    to the pack animal so ore can be pulled and smelted in single skill-gain batches.
    Returns the number of bulk stacks offloaded.
    """
    if not skill_gain_mode:
        return 0

    animal = find_nearby_pack_animal(PACK_ANIMAL_MAX_DISTANCE)
    if not animal:
        return 0

    container = get_pack_animal_container(animal, open_if_needed=True)
    if not container:
        return 0

    cont_serial = getattr(container, "Serial", container)
    bp_items = get_all_backpack_items()
    moved_stacks = 0

    for item in bp_items:
        if API.StopRequested or is_stopped or is_paused:
            break
        g = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()
        amt = getattr(item, "Amount", 1) or 1
        item_serial = getattr(item, "Serial", None)
        if (g in ORE_GRAPHICS or ("ore" in name and "scoreboard" not in name)) and item_serial:
            min_req = get_min_smelt_amount(g)
            if amt > min_req:
                update_status(f"Offloading {amt} ore to pet...")
                debug_msg(f"Moving bulk ore stack [0x{item_serial:X}] ({amt} pieces) to pet...")
                API.MoveItem(item_serial, cont_serial, 0)
                wait_with_ui(ACTION_DELAY)
                moved_stacks += 1

    if moved_stacks > 0:
        API.SysMsg(f"Offloaded {moved_stacks} bulk ore stack(s) to pack pet for skill-gain training.", 68)
        update_stats()

    return moved_stacks


def smelt_backpack_ore(forge) -> int:
    """
    Smelts any ore stacks currently in the player's backpack at the forge.
    In Skill Gain Mode, offloads any bulk stacks to the pet first to ensure single-piece smelting.
    Returns the number of ore units successfully smelted.
    """
    global total_ore_smelted, unsmeltable_serials
    if not forge:
        return 0

    if skill_gain_mode:
        offload_excess_backpack_ore_to_pet()

    bp_items = get_all_backpack_items()
    bp_ores = []
    for item in bp_items:
        graphic = getattr(item, "Graphic", 0)
        name = str(getattr(item, "Name", "") or "").lower()
        if graphic in ORE_GRAPHICS or ("ore" in name and "scoreboard" not in name):
            serial = getattr(item, "Serial", None)
            if serial and serial not in unsmeltable_serials:
                bp_ores.append(item)

    if not bp_ores:
        return 0

    smelted_units = 0
    for ore in bp_ores:
        if not check_ui_events():
            break

        ore_serial = getattr(ore, "Serial", ore)
        if not API.FindItem(ore_serial):
            continue

        amt = getattr(ore, "Amount", 1) or 1
        graphic = getattr(ore, "Graphic", 0)

        # Check if single small ore piece which cannot be smelted
        if graphic == 0x19B7 and amt < 2:
            debug_msg(f"Small ore [0x{ore_serial:X}] has only {amt} piece (requires 2). Skipping.")
            unsmeltable_serials.add(ore_serial)
            trigger_insufficient_ore_pause("There is not enough metal-bearing ore in this pile to make an ingot.")
            break

        mode_tag = " (Skill Gain)" if skill_gain_mode else ""
        update_status(f"Smelting {amt} ore{mode_tag}...")
        API.CancelTarget()
        API.ClearJournal()
        API.UseObject(ore_serial)

        if API.WaitForTarget(timeout=2.0):
            target_forge(forge)
            wait_with_ui(ACTION_DELAY)

            # Check journal for server failure messages
            if API.InJournal("not enough metal-bearing ore", clearMatches=True):
                unsmeltable_serials.add(ore_serial)
                API.SysMsg("There is not enough metal-bearing ore in this pile to make an ingot.", 53)
                trigger_insufficient_ore_pause("There is not enough metal-bearing ore in this pile to make an ingot.")
                break

            # Verify actual consumption
            cur_item = API.FindItem(ore_serial)
            if not cur_item:
                consumed = amt
            else:
                new_amt = getattr(cur_item, "Amount", 0) or 0
                consumed = max(0, amt - new_amt)

            if consumed > 0:
                smelted_units += consumed
                total_ore_smelted += consumed
                update_stats()
            else:
                debug_msg(f"Ore [0x{ore_serial:X}] amount did not change after smelting.")
        else:
            API.CancelTarget()
            wait_with_ui(0.3)

    return smelted_units


def pull_ore_batch_from_pet(batch_size: int = MAX_BATCH_ORE) -> bool:
    """
    Pulls a safe batch amount of ore from the pack animal into the player's backpack.
    In Skill Gain Mode, pulls the minimum pieces (1 for large/med, 2 for small) to maximize skill gain.
    In Bulk Mode, pulls up to batch_size based on player free weight.
    Returns True if an ore batch was moved, False if no ore remains.
    """
    pet_ores = get_pack_animal_ores()
    if not pet_ores:
        return False

    # Check player weight room
    cur_wt = API.Player.Weight or 0
    max_wt = API.Player.WeightMax or 400
    free_room = max_wt - cur_wt - WEIGHT_BUFFER
    if free_room <= 15:
        API.SysMsg("Backpack too heavy to pull more ore! Auto-pausing.", 32)
        trigger_overweight_pause()
        return False

    # Find the first smeltable ore stack in the pet
    target_ore = None
    for ore in pet_ores:
        ore_s = getattr(ore, "Serial", None)
        if ore_s in unsmeltable_serials:
            continue
        g = getattr(ore, "Graphic", 0)
        amt = getattr(ore, "Amount", 1) or 1
        min_req = get_min_smelt_amount(g)
        if amt < min_req:
            # Single small ore that cannot be smelted alone
            unsmeltable_serials.add(ore_s)
            continue
        target_ore = ore
        break

    if not target_ore:
        return False

    ore_serial = getattr(target_ore, "Serial", target_ore)
    ore_amount = getattr(target_ore, "Amount", 1) or 1
    ore_graphic = getattr(target_ore, "Graphic", 0)

    if skill_gain_mode:
        needed = get_min_smelt_amount(ore_graphic)
        move_amt = min(ore_amount, needed)
    else:
        # Large ore weighs 12 stones each. Calculate safe quantity
        safe_qty = max(2, min(batch_size, free_room // 12))
        move_amt = min(ore_amount, safe_qty)

    update_status(f"Pulling {move_amt} ore from pet...")
    debug_msg(f"Moving {move_amt} ore [0x{ore_serial:X}] from pet to backpack...")

    API.MoveItem(ore_serial, API.Backpack, amt=move_amt)
    wait_with_ui(ACTION_DELAY)
    return True


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    global forge_target_obj, initial_ingot_count

    # Settle any lingering UI action delays
    API.CancelTarget()
    wait_with_ui(0.5)

    # Render on-screen control Gump
    create_control_gump()
    update_stats()

    initial_ingot_count = get_backpack_ingot_count()

    update_status("Detecting pack pet & forge...")
    API.SysMsg("Auto Ore Smelter started.")

    # 1. Verify pack animal
    animal = find_nearby_pack_animal(PACK_ANIMAL_MAX_DISTANCE)
    if animal:
        pname = getattr(animal, "Name", "Pack Pet") or "Pack Pet"
        API.SysMsg(f"Connected to pack animal: {pname} [0x{animal.Serial:X}].", 68)
        get_pack_animal_container(animal, open_if_needed=True)
    else:
        API.SysMsg("No pack animal detected within reach! Click 'Pack Pet' to select.", 53)

    # 2. Verify forge
    forge_target_obj = find_nearby_forge()
    if forge_target_obj:
        fname = getattr(forge_target_obj, "Name", "Forge") or "Forge"
        API.SysMsg(f"Connected to forge: {fname}.", 68)
    else:
        API.SysMsg("No forge detected within 3 tiles! Stand near a forge or click 'Set Forge'.", 53)

    update_stats()

    # Main extraction and smelting loop
    while not API.StopRequested and not is_stopped:
        if not check_ui_events():
            break

        # Check if forge is set
        if not forge_target_obj:
            forge_target_obj = find_nearby_forge()
            if not forge_target_obj:
                update_status("Waiting for Forge...")
                wait_with_ui(1.0)
                continue

        # Step 1: Smelt any ore already sitting in the backpack
        smelted_now = smelt_backpack_ore(forge_target_obj)
        if not check_ui_events():
            break

        # Step 2: Check remaining ore in pack pet
        pet_ores = get_pack_animal_ores()
        # Filter for smeltable, non-excluded backpack ores
        bp_items = get_all_backpack_items()
        smeltable_bp_ores = [
            i for i in bp_items
            if (getattr(i, "Graphic", 0) in ORE_GRAPHICS or ("ore" in str(getattr(i, "Name", "") or "").lower() and "scoreboard" not in str(getattr(i, "Name", "") or "").lower()))
            and getattr(i, "Serial", None) not in unsmeltable_serials
            and is_ore_smeltable(i)
        ]

        has_smeltable_pet_ore = any(
            getattr(o, "Serial", None) not in unsmeltable_serials and is_ore_smeltable(o)
            for o in pet_ores
        )

        if not has_smeltable_pet_ore and not smeltable_bp_ores:
            update_status("Finished! All ore smelted.")
            API.SysMsg(f"All ore from pack animal successfully smelted! Total ore processed: {total_ore_smelted}.", 68)
            if unsmeltable_serials:
                API.SysMsg(f"{len(unsmeltable_serials)} unsmeltable small ore pile(s) (< 2 pieces) remaining in pack.", 53)
            if ALERT_SOUND > 0:
                API.PlaySound(ALERT_SOUND)
            break

        # Step 3: Pull a safe batch of ore from the pack animal
        if not pull_ore_batch_from_pet(MAX_BATCH_ORE):
            if is_paused:
                continue
            wait_with_ui(0.5)

    update_status("Finished")
    update_stats()
    wait_with_ui(2.0)
    dispose_gump()


main()
