import discord
from sqlalchemy import select
from database.session import get_db
from database.models import NotificationConfig


async def notify_player(
    bot,
    user_id: int,
    guild_id: int,
    event_type: str,
    embed: discord.Embed,
) -> None:
    """DM a player if they have this notification type enabled."""
    async with get_db() as db:
        result = await db.execute(
            select(NotificationConfig).where(
                NotificationConfig.user_id == user_id,
                NotificationConfig.guild_id == guild_id,
            )
        )
        config = result.scalar_one_or_none()
        if not config:
            return  # No config = no notifications

        field_map = {
            "faction_changes": config.faction_changes,
            "quest_objectives": config.quest_objectives,
            "world_events": config.world_events,
            "npc_movements": config.npc_movements,
            "lore_unlocks": config.lore_unlocks,
        }
        if not field_map.get(event_type, False):
            return

    try:
        user = await bot.fetch_user(user_id)
        await user.send(embed=embed)
    except (discord.Forbidden, discord.NotFound):
        pass
