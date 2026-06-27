"""
Heavenly Demon Heir class data and helper utilities.

This module contains the data tables, level tables, and helper functions
for the Heavenly Demon Heir class. The slash commands have been replaced
by the automatic ability detection system in services/ability_detector.py.

Ability keywords in proxy messages are now automatically detected and resolved.
"""

import discord
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
import random
import math

from database.session import get_db
from database.models import Character

# ── Level tables ─────────────────────────────────────────────────────────────

_TAO_MAX_TABLE = {
    1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10,
    10: 12, 11: 14, 12: 16, 13: 18, 14: 20, 15: 25,
    16: 30, 17: 35, 18: 40, 19: 45, 20: 50,
}
_SWORD_MAX_TABLE = {
    1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5,
    10: 5, 11: 6, 12: 6, 13: 7, 14: 7, 15: 8,
    16: 8, 17: 10, 18: 12, 19: 15, 20: 20,
}
_PROF_BONUS = {1:2,2:2,3:2,4:2,5:3,6:3,7:3,8:3,9:4,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:6,18:6,19:6,20:6}

# ── Utility functions ────────────────────────────────────────────────────────

def _mod(score: int) -> int:
    return math.floor((score - 10) / 2)


def _sword_die(level: int) -> tuple[int, int]:
    if level <= 4:   return (1, 8)
    if level <= 10:  return (1, 10)
    if level <= 16:  return (1, 12)
    return (2, 6)


def _roll_die(sides: int) -> int:
    return random.randint(1, sides)


def _roll(count: int, sides: int) -> int:
    return sum(random.randint(1, sides) for _ in range(count))


def _roll_attack(char: Character) -> tuple[int, int]:
    pb = _PROF_BONUS.get(char.level, 2)
    dex = _mod(char.dexterity)
    d20 = _roll_die(20)
    return d20, d20 + pb + dex


def _is_crit(char: Character, roll: int) -> bool:
    if char.level >= 20:
        return roll >= 18
    return roll == 20


def _sword_dmg(char: Character) -> int:
    cnt, sides = _sword_die(char.level)
    return _roll(cnt, sides) + _mod(char.dexterity)


def _tao_max(char: Character) -> int:
    base = _TAO_MAX_TABLE.get(char.level, 2)
    wis = _mod(char.wisdom)
    intel = _mod(char.intelligence)
    return max(base, char.level + wis + intel)

# ── Path descriptions with level upgrades ──────────────────────────────────────

PATH_FULL = {
    "Heavenly Demon": {
        "flavor": "You command blades as extensions of your will. Telekinetic sword control, orbital defense, and Sword Storm become your signature. The sword does not merely obey — it anticipates.",
        "level_6": "**Sword Orbit (Passive):** While controlling 1+ flying swords, gain **+2 AC** and a reaction to strike attackers who hit you.",
        "level_11": "**Sword Storm (Action, 4 Tao):** All controlled swords strike every enemy in a 30-ft radius. Each sword deals full damage and your AC bonus doubles to +4.",
        "level_17": "**Hundred Blade Domain (Active, 8 Tao, 1/rest):** Fill a 60-ft radius with orbiting blades. You automatically hit every enemy in the domain for **3d10** slashing at the start of your turn. Domain lasts 1 minute.",
    },
    "Blood Demon": {
        "flavor": "You chain Demonic Forms at terrifying speed — turning combat into a seamless massacre. Each strike births the next. Your enemies cannot find a gap between your attacks.",
        "level_6": "**Form Cascade (Passive):** When you use a Demonic Form that makes 3+ attacks, you may chain it into another form by paying its Tao cost. Chain up to **2 forms** per turn.",
        "level_11": "**Form Torrent (Passive):** Increase chain limit to **5 forms** per turn. Each form in a chain deals +1d6 bonus damage.",
        "level_17": "**Blood Moon Massacre (Active, 10 Tao, 1/rest):** Chain up to **10 forms** in a single turn. Every 5th attack in the chain is an automatic critical hit.",
    },
    "Elemental Demon": {
        "flavor": "Your Tao takes elemental form — fire, lightning, wind, or cold. Every strike ignites the air, freezes the ground, or tears the sky. The elements obey the Heavenly Demon.",
        "level_6": "**Elemental Burst (Active, 3 Tao):** Release a 20-ft radius explosion of your element. Creatures take full damage (DEX save halves) and are pushed 15 ft + knocked prone on failure.",
        "level_11": "**Elemental Aura (Passive):** While Tao ≥ 4, elemental damage radiates 15 ft around you. Creatures entering or starting turn there take **2d6** elemental damage. Your weapon attacks deal +1d8 elemental damage.",
        "level_17": "**Heavenly Demon Manifestation (Active, 8 Tao, 1/rest, 1 min):** Your body becomes elemental energy. +3 AC, advantage on all attacks, +1 extra action per turn, +3 martial arts dice per hit. When it ends: 1 level of exhaustion.",
    },
}

ELEMENT_DETAILS = {
    "Fire": {
        "desc": "Burning damage over time. Targets hit take 1d6 fire at start of your next turn (stacks up to 3 times).",
        "burst_extra": "Creatures that fail the save are also **Burning** (1d6 at start of their turn, save ends).",
    },
    "Lightning": {
        "desc": "Stun chance on hit. Targets hit must make CON save (DC = your save DC) or be Stunned until end of your next turn.",
        "burst_extra": "Creatures that fail the save are **Stunned** until the end of your next turn.",
    },
    "Wind": {
        "desc": "Extra attack per turn. After using a Demonic Form, make 1 additional basic attack against a different target. +10 ft movement.",
        "burst_extra": "Creatures that fail the save are knocked **Prone** and pushed an additional **30 ft**.",
    },
    "Cold": {
        "desc": "Slow on hit. Target's speed is halved until end of your next turn (save ends). Stacking slows can freeze.",
        "burst_extra": "Creatures that fail the save have their **speed reduced to 0** and cannot take reactions until the end of your next turn.",
    },
}

# ── 24 Forms data ────────────────────────────────────────────────────────────

FORMS = {
    # Basic — level 1
    "Demonic Strike":    {"tier": "Basic", "tao": 1, "unlock": 1,
        "desc": "After hitting, make 1 additional attack vs same target. +1d6 damage.",
        "attacks": 2, "bonus_dice": (1,6)},
    "Bloody Sequence":   {"tier": "Basic", "tao": 2, "unlock": 1,
        "desc": "Make 2 additional attacks after your original attack. +1d6 damage each.",
        "attacks": 3, "bonus_dice": (1,6)},
    "Phantom Cut":       {"tier": "Basic", "tao": 1, "unlock": 1,
        "desc": "Attack ignores half target's AC (rounded down). +1d6 damage.",
        "attacks": 1, "bonus_dice": (1,6), "ignore_half_ac": True},
    "Shadow Step":       {"tier": "Basic", "tao": 1, "unlock": 1,
        "desc": "Teleport up to 15 ft before attacking.",
        "attacks": 1, "teleport": 15},
    "Demonic Fang":      {"tier": "Basic", "tao": 2, "unlock": 1,
        "desc": "Single powerful strike. +1d8 damage.",
        "attacks": 1, "bonus_dice": (1,8)},
    "Black Moon Strike": {"tier": "Basic", "tao": 2, "unlock": 1,
        "desc": "Attack all enemies within 15 ft. +1d8 damage each.",
        "attacks": 1, "bonus_dice": (1,8), "aoe": True},

    # Intermediate — level 5
    "Cross Slash":       {"tier": "Intermediate", "tao": 3, "unlock": 5,
        "desc": "Make 2 attacks. In Dual Wield Stance: make 4 instead. +1d8 each.",
        "attacks": 2, "dual_attacks": 4, "bonus_dice": (1,8)},
    "Demon Beast Strike":{"tier": "Intermediate", "tao": 3, "unlock": 5,
        "desc": "Single devastating strike. +2d8 damage.",
        "attacks": 1, "bonus_dice": (2,8)},
    "Demonic Dance":     {"tier": "Intermediate", "tao": 2, "unlock": 5,
        "desc": "Make 4 consecutive attacks. +1d8 each.",
        "attacks": 4, "bonus_dice": (1,8)},
    "Demonic Pressure":  {"tier": "Intermediate", "tao": 2, "unlock": 5,
        "desc": "Enemies within 30 ft make WIS save (DC=8+prof+WIS mod) or become frightened.",
        "attacks": 0, "save_effect": "frightened"},
    "Demonic Tempest":   {"tier": "Intermediate", "tao": 3, "unlock": 5,
        "desc": "Make 3 attacks instantly. In Dual Wield Stance: 6 attacks. +1d8 each.",
        "attacks": 3, "dual_attacks": 6, "bonus_dice": (1,8)},
    "Lightning Cut":     {"tier": "Intermediate", "tao": 2, "unlock": 5,
        "desc": "Make 2 attacks. If both hit same target, make 1 additional attack. +1d8 each.",
        "attacks": 2, "lightning_cut": True, "bonus_dice": (1,8)},

    # Advanced — level 9
    "Abyss Cut":         {"tier": "Advanced", "tao": 3, "unlock": 9,
        "desc": "Attack ignores resistance. +2d10 damage.",
        "attacks": 1, "bonus_dice": (2,10), "ignore_resistance": True},
    "Demonic Domain":    {"tier": "Advanced", "tao": 4, "unlock": 9,
        "desc": "Your next attack deals +2d6 damage. All allies gain 1 extra attack this turn (+1d6).",
        "attacks": 1, "bonus_dice": (2,6), "ally_bonus": True},
    "Demonic Fury":      {"tier": "Advanced", "tao": 3, "unlock": 9,
        "desc": "Gain 2 additional attacks this turn.",
        "attacks": 3, "bonus_dice": None},
    "Demonic Massacre":  {"tier": "Advanced", "tao": 4, "unlock": 9,
        "desc": "Make 5 attacks instantly. +2d6 each.",
        "attacks": 5, "bonus_dice": (2,6)},
    "Heavenly Demon Dance":{"tier": "Advanced", "tao": 4, "unlock": 9,
        "desc": "All attacks this turn generate 1 additional attack.",
        "attacks": 2, "bonus_dice": None, "chain": True},
    "Invisible Cut":     {"tier": "Advanced", "tao": 3, "unlock": 9,
        "desc": "Attack cannot be reacted to (no opportunity attacks, no Shield spell). +2d6 damage.",
        "attacks": 1, "bonus_dice": (2,6), "no_reaction": True},

    # Supreme — level 15
    "Absolute Demonic Destruction": {"tier": "Supreme", "tao": 8, "unlock": 15,
        "desc": "Make 12 attacks instantly. +1d10 per hit.",
        "attacks": 12, "bonus_dice": (1,10)},
    "Bloody Tempest":    {"tier": "Supreme", "tao": 5, "unlock": 15,
        "desc": "Make 8 consecutive attacks.",
        "attacks": 8, "bonus_dice": None},
    "Heavenly Demon Slash":{"tier": "Supreme", "tao": 5, "unlock": 15,
        "desc": "Single strike. +1d6 per Tao spent (including base 5). Spend extra Tao for more damage.",
        "attacks": 1, "per_tao": True},
    "Heavenly Demon Domain":{"tier": "Supreme", "tao": 6, "unlock": 15,
        "desc": "Attack ALL enemies within 45 ft. +3d10 damage each.",
        "attacks": 1, "bonus_dice": (3,10), "aoe": True},
    "Hundred Blade Massacre":{"tier": "Supreme", "tao": 6, "unlock": 15,
        "desc": "Make 10 attacks instantly.",
        "attacks": 10, "bonus_dice": None},
    "Void Slash":        {"tier": "Supreme", "tao": 5, "unlock": 15,
        "desc": "Ignores ALL defenses (treat AC as 10, ignore resistance and immunity). +1d10 damage.",
        "attacks": 1, "bonus_dice": (1,10), "void": True},
}

TIER_EMOJI = {"Basic": "⚪", "Intermediate": "🟡", "Advanced": "🔴", "Supreme": "🌌"}
PATH_NAMES = ["Heavenly Demon", "Blood Demon", "Elemental Demon"]
ELEMENTS = ["Fire", "Lightning", "Wind", "Cold"]
ELEMENT_EMOJI = {"Fire": "🔥", "Lightning": "⚡", "Wind": "🌪️", "Cold": "❄️"}

# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_hd_char(user_id: int, guild_id: int) -> Character | None:
    """Get the active Heavenly Demon Heir character for a user."""
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == user_id,
                Character.guild_id == guild_id,
                Character.char_class == "Heavenly Demon Heir",
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        char = result.scalar_one_or_none()
        if char is None:
            result2 = await db.execute(
                select(Character).where(
                    Character.user_id == user_id,
                    Character.guild_id == guild_id,
                    Character.char_class == "Heavenly Demon Heir",
                    Character.is_dead == False,
                ).limit(1)
            )
            char = result2.scalar_one_or_none()
    return char


async def _update_resources(char_id: int, updates: dict):
    """Update class_resources JSON for a character."""
    async with get_db() as db:
        result = await db.execute(select(Character).where(Character.id == char_id))
        char = result.scalar_one_or_none()
        if char is None:
            return
        res = dict(char.class_resources or {})
        res.update(updates)
        char.class_resources = res
        flag_modified(char, "class_resources")


def _res(char: Character) -> dict:
    return dict(char.class_resources or {})


def _tao(char: Character) -> int:
    return _res(char).get("tao_current", 0)


def _hd_embed(title: str, desc: str = "") -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=0x8B0000)
    return e


# ── Minimal cog for setup (no slash commands) ────────────────────────────────

class HeavenlyDemonCog(commands.Cog, name="Heavenly Demon"):
    """Heavenly Demon Heir class data and helpers — abilities now detected automatically from proxy messages."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    await bot.add_cog(HeavenlyDemonCog(bot))
