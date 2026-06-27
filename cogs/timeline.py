import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from sqlalchemy import select
from database.session import get_db
from database.models import WorldEvent, GuildConfig
from services.utils import is_gm

timeline_group = app_commands.Group(
    name="timeline", description="World timeline and history"
)


@timeline_group.command(name="view", description="View the world timeline")
@app_commands.describe(page="Page number (10 events per page)")
async def timeline_view(interaction: discord.Interaction, page: int = 1):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer()

    per_page = 10
    offset = (page - 1) * per_page

    async with get_db() as db:
        # Get current era
        config_result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
        )
        config = config_result.scalar_one_or_none()
        current_era = config.current_era if config else None

        result = await db.execute(
            select(WorldEvent)
            .where(WorldEvent.guild_id == interaction.guild_id)
            .order_by(WorldEvent.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        events = list(result.scalars().all())

        # Total count
        count_result = await db.execute(
            select(WorldEvent).where(WorldEvent.guild_id == interaction.guild_id)
        )
        total = len(list(count_result.scalars().all()))
        # Actually get count properly
        from sqlalchemy import func
        count_result = await db.execute(
            select(func.count()).select_from(WorldEvent).where(
                WorldEvent.guild_id == interaction.guild_id
            )
        )
        total = count_result.scalar()

    if not events:
        await interaction.followup.send("No world events recorded yet. Things will change over time...")
        return

    total_pages = max(1, (total + per_page - 1) // per_page)
    embed = discord.Embed(
        title="📜 World Timeline",
        color=0xB8860B,
    )
    if current_era:
        embed.add_field(name="Current Era", value=current_era, inline=False)

    # Map event types to emoji
    type_emoji = {
        "npc_movement": "🚶",
        "faction_event": "🏛️",
        "manual": "📝",
        "combat": "⚔️",
        "quest": "📜",
        "discovery": "🔍",
    }

    for event in events:
        emoji = type_emoji.get(event.event_type, "📌")
        date_str = event.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(event.created_at, 'strftime') else str(event.created_at)[:16]
        embed.add_field(
            name=f"{emoji} {date_str}",
            value=f"**{event.event_type.replace('_', ' ').title()}**\n{event.narrative[:200] if event.narrative else ''}",
            inline=False,
        )

    embed.set_footer(text=f"Page {page}/{total_pages} • {total} total events")
    await interaction.followup.send(embed=embed)


@timeline_group.command(name="add", description="GM only: Add an event to the timeline")
@app_commands.describe(title="Event title", description="What happened", era="Optional era tag")
async def timeline_add(interaction: discord.Interaction, title: str, description: str, era: str = None):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer()
    if not await is_gm(interaction):
        await interaction.followup.send("Only GMs can add timeline events.", ephemeral=True)
        return

    desc = f"{title}: {description}"
    async with get_db() as db:
        event = WorldEvent(
            guild_id=interaction.guild_id,
            event_type="manual",
            narrative=desc,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        await db.commit()

    embed = discord.Embed(
        title="📝 Timeline Event Added",
        description=desc,
        color=0xB8860B,
    )
    if era:
        embed.add_field(name="Era", value=era, inline=True)
    await interaction.followup.send(embed=embed)


@timeline_group.command(name="era", description="GM only: Set the current world era")
@app_commands.describe(era_name="Name of the current era (e.g. Age of Shadows)")
async def timeline_era(interaction: discord.Interaction, era_name: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer()
    if not await is_gm(interaction):
        await interaction.followup.send("Only GMs can set the current era.", ephemeral=True)
        return

    async with get_db() as db:
        config_result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
        )
        config = config_result.scalar_one_or_none()
        if config:
            config.current_era = era_name
        else:
            config = GuildConfig(guild_id=interaction.guild_id, current_era=era_name)
            db.add(config)
        await db.commit()

    await interaction.followup.send(f"🌍 Current era set to **{era_name}**!")


class TimelineCog(commands.Cog, name="Timeline"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(timeline_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("timeline")


async def setup(bot):
    await bot.add_cog(TimelineCog(bot))
