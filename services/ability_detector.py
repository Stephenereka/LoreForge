"""
Ability Detector — automatically triggers class abilities from proxy message keywords.

When a player sends a proxy message as their character, this scans the message for
ability keywords and triggers the appropriate class-specific effects.

Heavenly Demon Heir: keyword detection for Phantom Step, Sword Control, Forms, etc.
Other classes: generic attack keyword detection from STARTER_ATTACKS.
"""

import discord
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
import random
import math

from database.session import get_db
from database.models import Character

# ── Constants ─────────────────────────────────────────────────────────────────

ABILITIES_BY_CLASS: dict[str, list[dict]] = {
    "Heavenly Demon Heir": [
        {
            "key": "phantom_step",
            "name": "Phantom Step",
            "keywords": ["phantom step", "step through shadows", "phase through",
                        "teleport", "blink", "shadow step", "vanish and reappear",
                        "step out of shadow", "flicker step"],
            "cost": {"tao": 1},
            "min_level": 4,
            "description": "Spend 1 Tao to teleport up to 30 ft.",
            "embed_color": 0x8B0000,
            "embed_icon": "💨",
        },
        {
            "key": "sword_attack",
            "name": "Sword Strike",
            "keywords": ["swords strike", "blade flies", "sword darts", "blade thrusts",
                        "flying blade", "sword spears", "sword lances", "sword slashes",
                        "flying sword", "sword rises", "blade orbits", "sword circles",
                        "telekinetic sword"],
            "cost": {"tao_per_sword": 2},
            "min_level": 7,
            "description": "Command telekinetic swords to strike a target.",
            "embed_color": 0x8B0000,
            "embed_icon": "⚔️",
        },
        {
            "key": "elemental_burst",
            "name": "Elemental Burst",
            "keywords": ["elemental burst", "burst of qi", "erupt with power",
                        "elemental eruption", "burst of energy", "qi detonates",
                        "power detonates", "element explodes", "qi burst"],
            "cost": {"tao": 3},
            "min_level": 6,
            "description": "Spend 3 Tao for a 20-ft radius elemental explosion.",
            "required_path": "Elemental Demon",
            "embed_color": 0x8B0000,
            "embed_icon": "🌪️",
        },
        {
            "key": "manifestation",
            "name": "Heavenly Demon Manifestation",
            "keywords": ["heavenly demon manifestation", "manifest my true form",
                        "demonic manifestation", "true form awakens",
                        "unleash my power", "ascend true form"],
            "cost": {"tao": 8},
            "min_level": 17,
            "description": "Spend 8 Tao to enter true demonic form for 1 minute.",
            "required_path": "Elemental Demon",
            "embed_color": 0x8B0000,
            "embed_icon": "🌌",
        },
        {
            "key": "absolute_state",
            "name": "Absolute Heavenly Demon State",
            "keywords": ["absolute heavenly demon", "absolute state", "heavenly demon ascension",
                        "peak of cultivation", "absolute power"],
            "cost": {"long_rest": True},
            "min_level": 20,
            "description": "Enter Absolute Heavenly Demon State for 1 minute (1/long rest).",
            "embed_color": 0x8B0000,
            "embed_icon": "🌌",
        },
    ],
}

# ── Heavenly Demon specific helpers ──────────────────────────────────────────

_TAO_MAX_TABLE = {
    1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10,
    10: 12, 11: 14, 12: 16, 13: 18, 14: 20, 15: 25,
    16: 30, 17: 35, 18: 40, 19: 45, 20: 50,
}
_PROF_BONUS = {1:2,2:2,3:2,4:2,5:3,6:3,7:3,8:3,9:4,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:6,18:6,19:6,20:6}


def _mod(score: int) -> int:
    return math.floor((score - 10) / 2)


def _tao_max(char: Character) -> int:
    base = _TAO_MAX_TABLE.get(char.level, 2)
    wis = _mod(char.wisdom)
    intel = _mod(char.intelligence)
    return max(base, char.level + wis + intel)


def _roll_die(sides: int) -> int:
    return random.randint(1, sides)


def _roll(count: int, sides: int) -> int:
    return sum(random.randint(1, sides) for _ in range(count))


# ── Main detection entrypoint ────────────────────────────────────────────────

async def check_ability_trigger(bot: commands.Bot, message: discord.Message, char: Character, inner_text: str):
    """
    Check a proxy message for class ability keyword triggers.

    Called from cogs/proxy.py after a successful webhook send.
    Handles both in-combat and out-of-combat ability detection.
    """
    if not char or not inner_text:
        return

    text_lower = inner_text.lower()
    guild_id = message.guild.id if message.guild else None
    if not guild_id:
        return

    # Check if the player is in combat
    in_combat = await _is_in_combat(bot, message.channel.id, char.user_id)

    # Check class-specific abilities
    class_name = char.char_class or ""
    abilities = ABILITIES_BY_CLASS.get(class_name, [])

    for ability in abilities:
        if char.level < ability.get("min_level", 1):
            continue

        # Check for required path
        required_path = ability.get("required_path")
        if required_path:
            res = dict(char.class_resources or {})
            if res.get("hd_path") != required_path:
                continue

        # Check keyword match
        matched_keyword = None
        for kw in ability["keywords"]:
            if kw in text_lower:
                matched_keyword = kw
                break

        if not matched_keyword:
            continue

        # Resolve the ability
        await _resolve_ability(bot, message, char, ability, matched_keyword, in_combat)
        return  # Only trigger one ability per message

    # Generic STARTER_ATTACKS check for any class
    if not in_combat:
        await _check_starter_attack_trigger(bot, message, char, text_lower)


async def _is_in_combat(bot: commands.Bot, channel_id: int, user_id: int) -> bool:
    """Check if a user's character is currently in active combat in a given channel."""
    from cogs import combat as _combat_module
    session = _combat_module._sessions.get(channel_id)
    if not session or session.state not in ("active", "lobby"):
        return False
    user_id_str = str(user_id)
    return any(c.id == user_id_str for c in session.players)


async def _resolve_ability(
    bot: commands.Bot,
    message: discord.Message,
    char: Character,
    ability: dict,
    matched_keyword: str,
    in_combat: bool,
):
    """Resolve an ability trigger — deduct resources and post result."""
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(Character.id == char.id)
        )
        char = result.scalar_one_or_none()
        if not char:
            return

        res = dict(char.class_resources or {})
        cur_tao = res.get("tao_current", 0)
        tao_max = _tao_max(char)

        # Check cost
        cost_tao = ability.get("cost", {}).get("tao", 0)
        if cost_tao > 0 and cur_tao < cost_tao:
            await message.channel.send(
                embed=discord.Embed(
                    description=f"*{char.name} tries to use {ability['name']} but doesn't have enough Tao ({cur_tao}/{cost_tao}).*",
                    color=0x8B0000,
                )
            )
            return

        # Deduct cost
        new_tao = cur_tao - cost_tao
        res["tao_current"] = new_tao
        if new_tao <= 0:
            res["tao_exhausted"] = True
        char.class_resources = res
        flag_modified(char, "class_resources")

        # Build result embed
        icon = ability.get("embed_icon", "⚡")
        embed = discord.Embed(
            title=f"{icon} {ability['name']}",
            description=f"*{char.name} uses {ability['name']}!*\n\n{ability.get('description', '')}",
            color=ability.get("embed_color", 0x8B0000),
        )

        if cost_tao > 0:
            embed.add_field(name="🌀 Tao", value=f"{cur_tao} → **{new_tao}**", inline=True)

        # In combat: also roll an attack
        if in_combat:
            pb = _PROF_BONUS.get(char.level, 2)
            dex_mod = _mod(char.dexterity)
            d20 = _roll_die(20)
            atk = d20 + pb + dex_mod
            dmg = _roll(1, 8) + dex_mod
            embed.add_field(
                name="⚔️ Combat Action",
                value=f"Attack: `d20={d20}` → **{atk}** | Damage: **{dmg}** slashing",
                inline=False,
            )

        await message.channel.send(embed=embed)


async def _check_starter_attack_trigger(
    bot: commands.Bot,
    message: discord.Message,
    char: Character,
    text_lower: str,
):
    """Check for generic attack keyword triggers from combat_engine.py STARTER_ATTACKS."""
    try:
        from services.combat_engine import STARTER_ATTACKS
    except ImportError:
        return

    class_name = char.char_class or ""
    class_attacks = STARTER_ATTACKS.get(class_name, [])
    if not class_attacks:
        # Fallback to all attacks across classes
        for attacks_list in STARTER_ATTACKS.values():
            class_attacks.extend(attacks_list)

    for attack in class_attacks:
        name = attack.get("name", "")
        keywords = [name.lower()]
        if attack.get("keywords"):
            keywords.extend([kw.lower() for kw in attack["keywords"]])

        for kw in keywords:
            if kw and kw in text_lower:
                embed = discord.Embed(
                    title=f"⚔️ {name}",
                    description=f"*{char.name} demonstrates {name}!*",
                    color=0xF59E0B,
                )
                dmg = attack.get("damage", "1d8")
                embed.add_field(name="Damage", value=dmg, inline=True)
                if attack.get("description"):
                    embed.add_field(name="Description", value=attack["description"], inline=False)
                await message.channel.send(embed=embed)
                return
