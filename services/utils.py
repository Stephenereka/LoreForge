import discord
from sqlalchemy import select


async def is_gm(interaction: discord.Interaction) -> bool:
    """Return True if the user is the server owner or has the configured GM role."""
    if not interaction.guild:
        return False
    if interaction.user.id == interaction.guild.owner_id:
        return True
    from database.session import get_db
    from database.models import GuildConfig
    async with get_db() as db:
        result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
        )
        config = result.scalar_one_or_none()
    if not config or not config.gm_role_id:
        return False
    return any(role.id == config.gm_role_id for role in interaction.user.roles)


async def gm_only(interaction: discord.Interaction) -> bool:
    """Use as a check: sends an error and returns False if not GM."""
    if await is_gm(interaction):
        return True
    await interaction.response.send_message(
        "You need the GM role to use this command.", ephemeral=True
    )
    return False
