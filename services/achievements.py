"""
Achievement system for LoreForge.
Manages achievement definitions, granting, and tracking.
"""

import discord
from sqlalchemy import select
from database.session import get_db
from database.models import Achievement, Character

ACHIEVEMENTS = {
    "first_blood": {"name": "First Blood", "desc": "Win your first combat", "icon": "⚔️", "xp": 50},
    "explorer_5": {"name": "Wanderer", "desc": "Discover 5 locations", "icon": "🗺️", "xp": 75},
    "explorer_10": {"name": "Pathfinder", "desc": "Discover 10 locations", "icon": "🧭", "xp": 150},
    "quest_first": {"name": "Quest Accepted", "desc": "Complete your first quest", "icon": "📜", "xp": 100},
    "quest_10": {"name": "Adventurer", "desc": "Complete 10 quests", "icon": "🏆", "xp": 300},
    "level_5": {"name": "Rising Star", "desc": "Reach level 5", "icon": "⭐", "xp": 200},
    "level_10": {"name": "Veteran", "desc": "Reach level 10", "icon": "🌟", "xp": 500},
    "level_20": {"name": "Legend", "desc": "Reach max level 20", "icon": "👑", "xp": 2000},
    "rich": {"name": "Wealthy", "desc": "Accumulate 10,000 Spirit Stones", "icon": "💰", "xp": 250},
    "pvp_5": {"name": "Duelist", "desc": "Win 5 PvP combats", "icon": "🥊", "xp": 300},
    "boss_first": {"name": "Boss Slayer", "desc": "Defeat your first boss", "icon": "💀", "xp": 500},
    "crafter": {"name": "Artisan", "desc": "Craft your first item", "icon": "🔨", "xp": 100},
    "trader": {"name": "Merchant", "desc": "Complete your first trade", "icon": "🤝", "xp": 75},
    "faction_friendly": {"name": "Friend of the Realm", "desc": "Reach Friendly with any faction", "icon": "🟢", "xp": 150},
    "faction_exalted": {"name": "Champion", "desc": "Reach Exalted with any faction", "icon": "🟡", "xp": 1000},
    "relationship": {"name": "Bonded", "desc": "Form your first character relationship", "icon": "❤️", "xp": 50},
    "proxy_100": {"name": "Storyteller", "desc": "Send 100 proxy messages as your character", "icon": "🎭", "xp": 200},
    "died_once": {"name": "Near Death Experience", "desc": "Survive a death saving throw", "icon": "💀", "xp": 100},
    "market_sell": {"name": "Open for Business", "desc": "Sell your first item on the market", "icon": "🏪", "xp": 75},
    "lore_found": {"name": "Scholar", "desc": "Search the lore wiki for the first time", "icon": "📚", "xp": 50},
    "scribe": {"name": "Scribe", "desc": "Have a lore submission approved", "icon": "✍️", "xp": 100},
}


async def grant_achievement(bot, character_id: int, guild_id: int, achievement_key: str, channel=None):
    """
    Grant an achievement to a character.

    Args:
        bot: The bot instance (to look up channels, users)
        character_id: Character.id to grant to
        guild_id: Guild ID for scoping
        achievement_key: Key from ACHIEVEMENTS dict
        channel: Optional discord channel to post the achievement announcement in

    Returns:
        True if the achievement was newly granted (not already earned)
    """
    ach_def = ACHIEVEMENTS.get(achievement_key)
    if not ach_def:
        return False

    async with get_db() as db:
        # Check if already earned
        existing = await db.execute(
            select(Achievement).where(
                Achievement.character_id == character_id,
                Achievement.achievement_key == achievement_key,
            )
        )
        if existing.scalar_one_or_none():
            return False

        # Get character for XP award
        char_result = await db.execute(
            select(Character).where(Character.id == character_id)
        )
        char = char_result.scalar_one_or_none()
        if not char:
            return False

        # Create achievement record
        db.add(Achievement(
            character_id=character_id,
            guild_id=guild_id,
            achievement_key=achievement_key,
        ))

        # Award XP
        xp_bonus = ach_def.get("xp", 0)
        if xp_bonus > 0:
            char.xp = (char.xp or 0) + xp_bonus

    # Post announcement
    if channel:
        icon = ach_def.get("icon", "🏆")
        name = ach_def.get("name", achievement_key)
        desc = ach_def.get("desc", "")
        embed = discord.Embed(
            title=f"{icon} Achievement Unlocked!",
            description=f"**{name}**\n*{desc}*",
            color=0xF1C40F,
        )
        if xp_bonus > 0:
            embed.add_field(name="✨ XP Bonus", value=f"+{xp_bonus} XP", inline=True)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    return True
