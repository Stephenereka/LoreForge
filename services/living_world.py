import asyncio
import random
from datetime import datetime, timezone
from sqlalchemy import select
from database.session import get_db
from database.models import NPC, Location, WorldEvent, GuildConfig, Faction


class LivingWorldService:
    """Background simulation that ticks all guilds every 15 minutes,
    creating NPC movement events and faction events."""

    def __init__(self, bot):
        self.bot = bot
        self._task = None

    def start(self):
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None

    async def _loop(self):
        await asyncio.sleep(30)  # initial delay
        while True:
            await asyncio.sleep(900)  # 15 minutes
            try:
                await self._tick_all_guilds()
            except Exception:
                pass

    async def _tick_all_guilds(self):
        async with get_db() as db:
            configs = await db.execute(select(GuildConfig))
            guild_ids = [c.guild_id for c in configs.scalars().all()]
        for guild_id in guild_ids:
            try:
                await self._tick_guild(guild_id)
            except Exception:
                pass

    async def _tick_guild(self, guild_id: int):
        async with get_db() as db:
            # 10% chance: random NPC roams to another location
            if random.random() < 0.10:
                npcs = (
                    await db.execute(select(NPC).where(NPC.guild_id == guild_id))
                ).scalars().all()
                locations = (
                    await db.execute(
                        select(Location).where(
                            Location.guild_id == guild_id, Location.is_hidden == False
                        )
                    )
                ).scalars().all()
                if npcs and locations:
                    npc = random.choice(npcs)
                    new_loc = random.choice(locations)
                    if npc.location_id != new_loc.id:
                        npc.location_id = new_loc.id
                        event = WorldEvent(
                            guild_id=guild_id,
                            event_type="npc_movement",
                            narrative=f"{npc.name} has moved to {new_loc.name}.",
                            created_at=datetime.now(timezone.utc),
                        )
                        db.add(event)

            # 5% chance: faction event
            if random.random() < 0.05:
                factions = (
                    await db.execute(
                        select(Faction).where(Faction.guild_id == guild_id)
                    )
                ).scalars().all()
                if factions:
                    faction = random.choice(factions)
                    events_pool = [
                        f"A patrol from {faction.name} was seen near the border.",
                        f"Trade caravans bearing the {faction.name} banner arrived at the capital.",
                        f"Tensions rise within {faction.name} as rumors spread.",
                        f"Messengers from {faction.name} have been spotted in multiple locations.",
                    ]
                    desc = random.choice(events_pool)
                    event = WorldEvent(
                        guild_id=guild_id,
                        event_type="faction_event",
                        narrative=desc,
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(event)

            await db.commit()
