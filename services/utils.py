import discord
from sqlalchemy import select


async def is_gm(interaction: discord.Interaction) -> bool:
    """Return True if user is server owner, has the GM role, or is in the GuildGM table."""
    if not interaction.guild:
        return False
    if interaction.user.id == interaction.guild.owner_id:
        return True
    from database.session import get_db
    from database.models import GuildConfig, GuildGM
    async with get_db() as db:
        # Check DB-registered GMs
        gm_row = await db.execute(
            select(GuildGM).where(
                GuildGM.guild_id == interaction.guild_id,
                GuildGM.user_id == interaction.user.id,
            )
        )
        if gm_row.scalar_one_or_none():
            return True
        # Check role-based GM
        config_row = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
        )
        config = config_row.scalar_one_or_none()
    if not config or not config.gm_role_id:
        return False
    return any(role.id == config.gm_role_id for role in interaction.user.roles)


async def gm_only(interaction: discord.Interaction) -> bool:
    """Gate check: sends an error and returns False if the user is not a GM."""
    if await is_gm(interaction):
        return True
    await interaction.response.send_message(
        "You need the GM role to use this command.", ephemeral=True
    )
    return False


async def owner_only(interaction: discord.Interaction) -> bool:
    """Gate check: only the server owner can proceed."""
    if interaction.guild and interaction.user.id == interaction.guild.owner_id:
        return True
    await interaction.response.send_message(
        "Only the server owner can use this command.", ephemeral=True
    )
    return False
