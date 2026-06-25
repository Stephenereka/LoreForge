import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from sqlalchemy import select
from database.session import get_db
from database.models import WorldScheduledEvent, EventRSVP
from services.utils import is_gm

events_group = app_commands.Group(name="event", description="Schedule and manage events")


@events_group.command(name="create", description="Create a new scheduled event (GM only)")
@app_commands.describe(name="Event name", datetime_str="When the event starts (e.g., '2026-07-01 19:00 UTC')")
async def event_create(interaction: discord.Interaction, name: str, datetime_str: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can create events.", ephemeral=True)
        return

    try:
        scheduled_at = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            scheduled_at = datetime.fromisoformat(datetime_str)
        except ValueError:
            await interaction.response.send_message(
                "Invalid date format. Use `YYYY-MM-DD HH:MM` or ISO format.", ephemeral=True
            )
            return

    async with get_db() as db:
        db.add(WorldScheduledEvent(
            guild_id=interaction.guild_id,
            name=name,
            event_type="session",
            scheduled_at=scheduled_at,
            created_by=interaction.user.id,
        ))

    timestamp = int(scheduled_at.timestamp())
    await interaction.response.send_message(
        f"📅 Event **{name}** created for <t:{timestamp}:F>!"
    )


@events_group.command(name="list", description="List upcoming events")
async def event_list(interaction: discord.Interaction):
    async with get_db() as db:
        result = await db.execute(
            select(WorldScheduledEvent).where(
                WorldScheduledEvent.guild_id == interaction.guild_id,
                WorldScheduledEvent.scheduled_at >= datetime.utcnow(),
            ).order_by(WorldScheduledEvent.scheduled_at)
        )
        events = result.scalars().all()

    if not events:
        await interaction.response.send_message("No upcoming events.", ephemeral=True)
        return

    embed = discord.Embed(title="📅 Upcoming Events", color=0x6366F1)
    for event in events:
        ts = int(event.scheduled_at.timestamp())
        embed.add_field(
            name=event.name,
            value=f"<t:{ts}:F>  (<t:{ts}:R>)\nType: {event.event_type}",
            inline=False,
        )

    await interaction.response.send_message(embed=embed)


@events_group.command(name="rsvp", description="RSVP for an event")
@app_commands.describe(event_id="ID of the event", status="Your response")
@app_commands.choices(status=[
    app_commands.Choice(name="Attending", value="attending"),
    app_commands.Choice(name="Maybe", value="maybe"),
    app_commands.Choice(name="Declined", value="declined"),
])
async def event_rsvp(interaction: discord.Interaction, event_id: int, status: app_commands.Choice[str]):
    async with get_db() as db:
        result = await db.execute(
            select(WorldScheduledEvent).where(WorldScheduledEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            await interaction.response.send_message("Event not found.", ephemeral=True)
            return

        existing = await db.execute(
            select(EventRSVP).where(
                EventRSVP.event_id == event_id,
                EventRSVP.user_id == interaction.user.id,
            )
        )
        rsvp = existing.scalar_one_or_none()
        if rsvp:
            rsvp.status = status.value
        else:
            db.add(EventRSVP(
                event_id=event_id,
                user_id=interaction.user.id,
                status=status.value,
            ))

    emoji = {"attending": "✅", "maybe": "❓", "declined": "❌"}.get(status.value, "✅")
    await interaction.response.send_message(
        f"{emoji} You're marked as **{status.value}** for **{event.name}**."
    )


@events_group.command(name="info", description="View event details")
@app_commands.describe(event_id="ID of the event")
async def event_info(interaction: discord.Interaction, event_id: int):
    async with get_db() as db:
        result = await db.execute(
            select(WorldScheduledEvent).where(WorldScheduledEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            await interaction.response.send_message("Event not found.", ephemeral=True)
            return

        rsvp_result = await db.execute(
            select(EventRSVP).where(EventRSVP.event_id == event_id)
        )
        rsvps = rsvp_result.scalars().all()

        attending = sum(1 for r in rsvps if r.status == "attending")
        maybe = sum(1 for r in rsvps if r.status == "maybe")

        ts = int(event.scheduled_at.timestamp())
        embed = discord.Embed(
            title=f"📅 {event.name}",
            description=event.description or "No description.",
            color=0x6366F1,
        )
        embed.add_field(name="When", value=f"<t:{ts}:F>", inline=True)
        embed.add_field(name="Type", value=event.event_type, inline=True)
        embed.add_field(name="Attending", value=f"{attending} attending, {maybe} maybe", inline=False)

        await interaction.response.send_message(embed=embed)


class EventsCog(commands.Cog, name="Events"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(events_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("event")


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
