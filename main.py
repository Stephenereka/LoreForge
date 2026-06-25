import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
from database.session import init_db

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

COGS = [
    "cogs.admin",
    "cogs.character",
    "cogs.combat",
    "cogs.gm",
    "cogs.shop",
    "cogs.inventory",
    "cogs.proxy",
    "cogs.rest",
    "cogs.location",
    "cogs.npc",
    "cogs.quest",
    "cogs.faction",
    "cogs.lore",
    "cogs.tutorial",
    "cogs.party",
    "cogs.training",
    "cogs.housing",
    "cogs.economy",
    "cogs.market",
    "cogs.trade",
    "cogs.events",
    "cogs.dice",
    "cogs.embed_builder",
    "cogs.heavenly_demon",
]

async def _weather_task():
    """Change weather for all active guilds every 45 minutes."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            from services.weather_service import random_weather_change
            from sqlalchemy import select
            from database.session import get_db
            from database.models import GuildConfig
            async with get_db() as db:
                result = await db.execute(select(GuildConfig))
                for config in result.scalars().all():
                    try:
                        await random_weather_change(config.guild_id)
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(2700)  # 45 minutes


async def _event_reminder_task():
    """Check every 5 minutes for events starting in the next 60 minutes."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import select
            from database.session import get_db
            from database.models import WorldScheduledEvent, GuildConfig
            now = datetime.utcnow()
            soon = now + timedelta(hours=1)
            async with get_db() as db:
                result = await db.execute(
                    select(WorldScheduledEvent).where(
                        WorldScheduledEvent.scheduled_at.between(now, soon)
                    )
                )
                for event in result.scalars().all():
                    try:
                        guild_config = await db.execute(
                            select(GuildConfig).where(GuildConfig.guild_id == event.guild_id)
                        )
                        config = guild_config.scalar_one_or_none()
                        if config and config.gm_channel_id:
                            channel = bot.get_channel(config.gm_channel_id)
                            if channel:
                                await channel.send(
                                    f"📅 **Upcoming Event: {event.name}**\n"
                                    f"{event.description or ''}\n"
                                    f"Starts <t:{int(event.scheduled_at.timestamp())}:R>"
                                )
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(300)  # 5 minutes


async def _time_update_task():
    """Every 60 seconds, recalculate world time for all guilds in automatic mode."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            from services.time_service import recalc_automatic_time
            from sqlalchemy import select
            from database.session import get_db
            from database.models import WorldTime
            async with get_db() as db:
                result = await db.execute(select(WorldTime).where(WorldTime.mode == "automatic"))
                for wt in result.scalars().all():
                    try:
                        await recalc_automatic_time(wt.guild_id)
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(60)


@bot.event
async def on_ready():
    await init_db()
    print(f"{bot.user} is online!")

    # Start background tasks
    bot.loop.create_task(_weather_task())
    bot.loop.create_task(_event_reminder_task())
    bot.loop.create_task(_time_update_task())

    try:
        guild = discord.Object(id=1519154137017614427)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} slash commands to guild")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="LoreForge | /ping")
    )

async def main():
    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            print(f"Loaded: {cog}")
        await bot.start(os.getenv("DISCORD_TOKEN"))

asyncio.run(main())
