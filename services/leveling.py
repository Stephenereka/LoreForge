import random

# XP required to REACH each level (index = level - 1)
XP_THRESHOLDS = [
    0,        # level 1
    300,      # level 2
    900,      # level 3
    2_700,    # level 4
    6_500,    # level 5
    14_000,   # level 6
    23_000,   # level 7
    34_000,   # level 8
    48_000,   # level 9
    64_000,   # level 10
    85_000,   # level 11
    100_000,  # level 12
    120_000,  # level 13
    140_000,  # level 14
    165_000,  # level 15
    195_000,  # level 16
    225_000,  # level 17
    265_000,  # level 18
    305_000,  # level 19
    355_000,  # level 20
]

MAX_LEVEL = 20

# Levels where Ability Score Improvements occur (most classes)
ASI_LEVELS = [4, 8, 12, 16, 19]

# Hit dice by class
_HIT_DICE: dict[str, int] = {
    "barbarian": 12,
    "fighter": 10, "paladin": 10, "ranger": 10,
    "bard": 8, "cleric": 8, "druid": 8, "monk": 8, "rogue": 8, "warlock": 8,
    "sorcerer": 6, "wizard": 6,
    "heavenly demon": 10, "murim warrior": 10, "cultivator": 8, "arcane scholar": 6,
}

# Class features by level — used by /character sheet
CLASS_FEATURES: dict[str, dict[int, list[str]]] = {
    "fighter": {
        1: ["Fighting Style", "Second Wind"],
        2: ["Action Surge"],
        3: ["Martial Archetype"],
        4: ["ASI"],
        5: ["Extra Attack"],
        6: ["ASI"],
        7: ["Archetype Feature"],
        8: ["ASI"],
        9: ["Indomitable"],
        10: ["Archetype Feature"],
        11: ["Extra Attack (2)"],
        12: ["ASI"],
        13: ["Indomitable (2)"],
        14: ["ASI"],
        15: ["Archetype Feature"],
        16: ["ASI"],
        17: ["Action Surge (2)", "Indomitable (3)"],
        18: ["Archetype Feature"],
        19: ["ASI"],
        20: ["Extra Attack (3)"],
    },
    "rogue": {
        1: ["Expertise", "Sneak Attack", "Thieves' Cant"],
        2: ["Cunning Action"],
        3: ["Roguish Archetype"],
        4: ["ASI"],
        5: ["Uncanny Dodge"],
        6: ["Expertise"],
        7: ["Evasion"],
        8: ["ASI"],
        9: ["Archetype Feature"],
        10: ["ASI"],
        11: ["Reliable Talent"],
        12: ["ASI"],
        14: ["Blindsense"],
        15: ["Slippery Mind"],
        16: ["ASI"],
        18: ["Elusive"],
        19: ["ASI"],
        20: ["Stroke of Luck"],
    },
    "wizard": {
        1: ["Spellcasting", "Arcane Recovery"],
        2: ["Arcane Tradition"],
        4: ["ASI"],
        8: ["ASI"],
        12: ["ASI"],
        16: ["ASI"],
        18: ["Spell Mastery"],
        19: ["ASI"],
        20: ["Signature Spells"],
    },
    "barbarian": {
        1: ["Rage", "Unarmored Defense"],
        2: ["Reckless Attack", "Danger Sense"],
        3: ["Primal Path"],
        4: ["ASI"],
        5: ["Extra Attack", "Fast Movement"],
        6: ["Path Feature"],
        7: ["Feral Instinct"],
        8: ["ASI"],
        9: ["Brutal Critical (1)"],
        10: ["Path Feature"],
        11: ["Relentless Rage"],
        12: ["ASI"],
        13: ["Brutal Critical (2)"],
        14: ["Path Feature"],
        15: ["Persistent Rage"],
        16: ["ASI"],
        17: ["Brutal Critical (3)"],
        18: ["Indomitable Might"],
        19: ["ASI"],
        20: ["Primal Champion"],
    },
    "monk": {
        1: ["Unarmored Defense", "Martial Arts"],
        2: ["Ki", "Unarmored Movement"],
        3: ["Monastic Tradition", "Deflect Missiles"],
        4: ["ASI", "Slow Fall"],
        5: ["Extra Attack", "Stunning Strike"],
        6: ["Ki-Empowered Strikes", "Tradition Feature"],
        7: ["Evasion", "Stillness of Mind"],
        8: ["ASI"],
        9: ["Unarmored Movement Improvement"],
        10: ["Purity of Body"],
        11: ["Tradition Feature"],
        12: ["ASI"],
        13: ["Tongue of the Sun and Moon"],
        14: ["Diamond Soul"],
        15: ["Timeless Body"],
        16: ["ASI"],
        17: ["Tradition Feature"],
        18: ["Empty Body"],
        19: ["ASI"],
        20: ["Perfect Self"],
    },
}

_GENERIC_FEATURES: dict[int, list[str]] = {
    4: ["ASI"], 8: ["ASI"], 12: ["ASI"], 16: ["ASI"], 19: ["ASI"],
}


def xp_to_level(xp: int) -> int:
    """Return the level a character with `xp` XP has reached."""
    level = 1
    for i, threshold in enumerate(XP_THRESHOLDS):
        if xp >= threshold:
            level = i + 1
    return min(level, MAX_LEVEL)


def xp_for_next_level(xp: int) -> int:
    """XP still needed to reach the next level (0 if max level)."""
    current = xp_to_level(xp)
    if current >= MAX_LEVEL:
        return 0
    return XP_THRESHOLDS[current] - xp


def check_level_up(xp: int, current_level: int) -> int | None:
    """Return the new level if XP qualifies for a level-up, else None."""
    new_level = xp_to_level(xp)
    return new_level if new_level > current_level else None


def xp_bar(xp: int, width: int = 10) -> str:
    """Visual XP progress bar toward the next level."""
    current = xp_to_level(xp)
    if current >= MAX_LEVEL:
        return "█" * width + " MAX"
    prev_threshold = XP_THRESHOLDS[current - 1]
    next_threshold = XP_THRESHOLDS[current]
    progress = (xp - prev_threshold) / max(1, next_threshold - prev_threshold)
    filled = round(progress * width)
    return "█" * filled + "░" * (width - filled)


def hp_gain_on_level(char_class: str, constitution_modifier: int, average: bool = False) -> int:
    """HP gained on level-up for a given class and CON modifier."""
    die = _HIT_DICE.get(char_class.lower(), 8)
    rolled = die // 2 + 1 if average else random.randint(1, die)
    return max(1, rolled + constitution_modifier)


def feature_at_level(char_class: str, level: int) -> list[str]:
    """Features gained at this level for the given class."""
    features_map = CLASS_FEATURES.get(char_class.lower(), _GENERIC_FEATURES)
    return features_map.get(level, [])


def pvp_xp_reward(winner_level: int, loser_level: int) -> int:
    """XP reward for defeating another player in PvP."""
    base = 50 * loser_level
    if loser_level > winner_level:
        base = int(base * 1.5)
    return base
