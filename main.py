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
    "cogs.ai_config",
    "cogs.sessions",
    "cogs.titles",
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


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    import traceback
    print(f"[CMD ERROR] {interaction.command} — {error}")
    traceback.print_exc()
    msg = f"Something went wrong: `{type(error).__name__}: {error}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

async def _auto_seed_murim_template():
    """On startup, load the murim_magic template for any guild that has 0 locations."""
    import json, pathlib
    from sqlalchemy import select, func
    from database.session import get_db
    from database.models import Location, Faction, NPC, Quest, LoreEntry, BossTemplate, LocationConnection

    bot_root = pathlib.Path(__file__).parent
    template_path = bot_root / "data" / "templates" / "murim_magic.json"
    if not template_path.exists():
        print("[AutoSeed] murim_magic.json not found, skipping.")
        return

    with open(template_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    REVERSE_DIR = {
        "north": "south", "south": "north", "east": "west", "west": "east",
        "northeast": "southwest", "southwest": "northeast",
        "northwest": "southeast", "southeast": "northwest",
        "up": "down", "down": "up", "surrounding": "center",
    }

    for guild in bot.guilds:
        guild_id = guild.id
        async with get_db() as db:
            loc_count = await db.scalar(select(func.count()).select_from(Location).where(Location.guild_id == guild_id))
        if loc_count and loc_count > 0:
            print(f"[AutoSeed] Guild {guild_id} already has {loc_count} locations — skipping template.")
            continue

        print(f"[AutoSeed] Guild {guild_id} has 0 locations — loading murim_magic template...")
        bot_user_id = bot.user.id

        loc_name_to_id: dict[str, int] = {}
        faction_name_to_id: dict[str, int] = {}
        locs_created = npc_created = factions_created = quests_created = lore_created = bosses_created = 0

        async with get_db() as db:
            for loc_data in data.get("locations", []):
                existing = await db.execute(select(Location).where(Location.guild_id == guild_id, Location.name == loc_data["name"]))
                existing = existing.scalar_one_or_none()
                if existing:
                    loc_name_to_id[existing.name] = existing.id
                    continue
                loc = Location(
                    guild_id=guild_id, name=loc_data["name"], description=loc_data.get("description", ""),
                    short_description=loc_data.get("short_description", ""), location_type=loc_data.get("location_type", "wilderness"),
                    biome=loc_data.get("biome"), map_x=loc_data.get("map_x", 50.0), map_y=loc_data.get("map_y", 50.0),
                    is_safe=loc_data.get("is_safe", False), is_indoors=loc_data.get("is_indoors", False),
                    is_hidden=False, danger_level=loc_data.get("danger_level", 1), resources={}, created_by=bot_user_id,
                )
                db.add(loc)
                await db.flush()
                loc_name_to_id[loc.name] = loc.id
                locs_created += 1

        async with get_db() as db:
            for loc_data in data.get("locations", []):
                from_id = loc_name_to_id.get(loc_data["name"])
                if not from_id:
                    continue
                for conn_data in loc_data.get("connections", []):
                    target = conn_data.get("target_name")
                    direction = conn_data.get("direction", "north")
                    to_id = loc_name_to_id.get(target)
                    if not to_id:
                        continue
                    existing_conn = await db.execute(select(LocationConnection).where(
                        LocationConnection.guild_id == guild_id, LocationConnection.from_location_id == from_id, LocationConnection.to_location_id == to_id))
                    if existing_conn.scalar_one_or_none():
                        continue
                    db.add(LocationConnection(guild_id=guild_id, from_location_id=from_id, to_location_id=to_id, direction=direction, is_locked=False, is_secret=False, travel_time_minutes=conn_data.get("travel_time_minutes", 10)))
                    rev = REVERSE_DIR.get(direction, direction)
                    existing_rev = await db.execute(select(LocationConnection).where(
                        LocationConnection.guild_id == guild_id, LocationConnection.from_location_id == to_id, LocationConnection.to_location_id == from_id))
                    if not existing_rev.scalar_one_or_none():
                        db.add(LocationConnection(guild_id=guild_id, from_location_id=to_id, to_location_id=from_id, direction=rev, is_locked=False, is_secret=False, travel_time_minutes=conn_data.get("travel_time_minutes", 10)))

        async with get_db() as db:
            for f_data in data.get("factions", []):
                existing = await db.execute(select(Faction).where(Faction.guild_id == guild_id, Faction.name == f_data["name"]))
                existing = existing.scalar_one_or_none()
                if existing:
                    faction_name_to_id[existing.name] = existing.id
                    continue
                faction = Faction(guild_id=guild_id, name=f_data["name"], description=f_data.get("description", ""), faction_type=f_data.get("faction_type", "guild"), color=f_data.get("color", "#6366F1"), icon_emoji=f_data.get("icon_emoji"), starting_rep=f_data.get("starting_rep", 0), created_by=bot_user_id)
                db.add(faction)
                await db.flush()
                faction_name_to_id[faction.name] = faction.id
                factions_created += 1

        async with get_db() as db:
            for npc_data in data.get("npcs", []):
                existing = await db.execute(select(NPC).where(NPC.guild_id == guild_id, NPC.name == npc_data["name"]))
                if existing.scalar_one_or_none():
                    continue
                loc_id = loc_name_to_id.get(npc_data.get("location_name", ""))
                if not loc_id:
                    continue
                db.add(NPC(guild_id=guild_id, name=npc_data["name"], title=npc_data.get("title"), race=npc_data.get("race"), description=npc_data.get("description", ""), appearance=npc_data.get("appearance"), location_id=loc_id, disposition=npc_data.get("disposition", "neutral"), greeting=npc_data.get("greeting"), dialogue_topics=npc_data.get("dialogue_topics", {}), image_url=npc_data.get("image_url") or None, proxy_name=npc_data.get("proxy_name") or npc_data.get("name"), proxy_mode=npc_data.get("proxy_mode", "automatic"), faction_id=faction_name_to_id.get(npc_data.get("faction_name", "")), hp_max=npc_data.get("hp_max", 30), hp_current=npc_data.get("hp_max", 30), created_by=bot_user_id))
                npc_created += 1

        async with get_db() as db:
            for q_data in data.get("quests", []):
                existing = await db.execute(select(Quest).where(Quest.guild_id == guild_id, Quest.name == q_data["name"]))
                if existing.scalar_one_or_none():
                    continue
                db.add(Quest(guild_id=guild_id, name=q_data["name"], description=q_data.get("description", ""), quest_type=q_data.get("quest_type", "standard"), reward_xp=q_data.get("reward_xp", 0), reward_gold=q_data.get("reward_gold", 0), reward_items=q_data.get("reward_items", []), is_active=True, created_by=bot_user_id))
                quests_created += 1

        async with get_db() as db:
            for l_data in data.get("lore_entries", []):
                existing = await db.execute(select(LoreEntry).where(LoreEntry.guild_id == guild_id, LoreEntry.title == l_data["title"]))
                if existing.scalar_one_or_none():
                    continue
                db.add(LoreEntry(guild_id=guild_id, title=l_data["title"], content=l_data.get("content", ""), category=l_data.get("category", "lore"), tags=l_data.get("tags", []), is_canon=l_data.get("is_canon", True), visibility=l_data.get("visibility", "public"), importance=l_data.get("importance", 5), created_by=bot_user_id))
                lore_created += 1

        async with get_db() as db:
            for b_data in data.get("bosses", []):
                existing = await db.execute(select(BossTemplate).where(BossTemplate.guild_id == guild_id, BossTemplate.name == b_data["name"]))
                if existing.scalar_one_or_none():
                    continue
                db.add(BossTemplate(guild_id=guild_id, name=b_data["name"], title=b_data.get("title"), description=b_data.get("description", ""), hp_max=b_data.get("hp_max", 100), armor_class=b_data.get("armor_class", 15), attack_bonus=b_data.get("attack_bonus", 6), damage_dice=b_data.get("damage_dice", "2d8"), damage_bonus=b_data.get("damage_bonus", 0), xp_value=b_data.get("xp_value", 1000), gold_drop=b_data.get("gold_drop", 0), loot_table=b_data.get("loot_table", []), phase_count=b_data.get("phase_count", 1), phase_thresholds=b_data.get("phase_thresholds", []), phase_abilities=b_data.get("phase_abilities", {}), legendary_actions=b_data.get("legendary_actions", []), legendary_action_count=b_data.get("legendary_action_count", 3), is_lair_boss=b_data.get("is_lair_boss", False), lair_actions=b_data.get("lair_actions", []), created_by=bot_user_id))
                bosses_created += 1

        print(f"[AutoSeed] Done — {locs_created} locations, {factions_created} factions, {npc_created} NPCs, {quests_created} quests, {lore_created} lore, {bosses_created} bosses.")


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
    await _auto_seed_murim_template()

async def main():
    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            print(f"Loaded: {cog}")
        await bot.start(os.getenv("DISCORD_TOKEN"))

asyncio.run(main())
