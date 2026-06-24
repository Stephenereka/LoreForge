import math

XP_THRESHOLDS = [0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
                 85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000]

HIT_DICE = {
    "Fighter": 10, "Barbarian": 12, "Rogue": 8,
    "Cleric": 8, "Wizard": 6, "Warlock": 8,
}

CLASS_FEATURES: dict[str, dict[int, str]] = {
    "Fighter":   {5: "Extra Attack (2 attacks per turn)", 11: "Triple Attack (3 attacks per turn)"},
    "Rogue":     {5: "Uncanny Dodge — halve one attack's damage once per turn", 11: "Reliable Talent — min 10 on skill checks"},
    "Cleric":    {5: "Destroy Undead — upgraded Turn Undead"},
    "Wizard":    {5: "Extra spell slot"},
    "Barbarian": {5: "Extra Attack + Fast Movement", 11: "Relentless Rage — survive 0 HP once per rage"},
    "Warlock":   {5: "Third spell slot + 3rd level spells"},
}

ASI_LEVELS: set[int] = {4, 8, 12, 16, 19}


def xp_to_reach(level: int) -> int:
    """Total XP needed to reach `level`. Level 1 = 0 XP."""
    if level <= 1:
        return 0
    if level >= len(XP_THRESHOLDS):
        return XP_THRESHOLDS[-1]
    return XP_THRESHOLDS[level - 1]


def xp_for_next_level(current_level: int) -> int:
    """Total XP needed to level up from current_level."""
    return xp_to_reach(current_level + 1)


def check_level_up(current_xp: int, current_level: int) -> int | None:
    """Return new level if XP qualifies for a level-up, else None."""
    if current_level >= 20:
        return None
    if current_xp >= xp_for_next_level(current_level):
        return current_level + 1
    return None


def hp_gain_on_level(char_class: str, con_score: int) -> int:
    """HP gained when levelling up (average roll + CON mod, min 1)."""
    hit_die = HIT_DICE.get(char_class, 8)
    avg_roll = math.ceil(hit_die / 2) + 1
    return max(1, avg_roll + math.floor((con_score - 10) / 2))


def proficiency_bonus(level: int) -> int:
    return math.ceil(level / 4) + 1


def feature_at_level(char_class: str, level: int) -> str | None:
    return CLASS_FEATURES.get(char_class, {}).get(level)


def pvp_xp_reward(loser_level: int, winner_count: int) -> int:
    """XP each winner earns after defeating a player in PvP."""
    return (loser_level * 50) // max(winner_count, 1)


def xp_bar(current_xp: int, current_level: int, bar_width: int = 10) -> str:
    """Return a text XP progress bar string."""
    if current_level >= 20:
        return f"XP `{current_xp}` — **MAX LEVEL**"
    needed = xp_for_next_level(current_level)
    start = xp_to_reach(current_level)
    progress = current_xp - start
    span = needed - start
    pct = min(progress / span, 1.0) if span > 0 else 1.0
    filled = round(pct * bar_width)
    bar = "▓" * filled + "░" * (bar_width - filled)
    return f"XP `{current_xp}/{needed}` {bar} → Lv{current_level + 1}"
