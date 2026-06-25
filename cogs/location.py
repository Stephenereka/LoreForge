import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, or_, and_
from database.session import get_db
from database.models import Location, LocationConnection, CharacterLocation, GuildConfig, Character
from services.utils import gm_only, is_gm
from services.time_service import get_world_time, get_time_flavor
from services.weather_service import get_weather, get_weather_flavor, set_weather
from services.map_service import generate_world_map_overlay, fetch_world_map
from cogs.character import resolve_character
import io

# ── Constants ──────────────────────────────────────────────────────────────

LOCATION_TYPES = ['city', 'town', 'village', 'wilderness', 'dungeon', 'tavern',
                  'shrine', 'fortress', 'ruins', 'cave', 'forest', 'lake',
                  'mountain', 'bridge', 'port', 'tower', 'library', 'arena',
                  'market', 'temple']

DIRECTIONS = ['north', 'south', 'east', 'west', 'northeast', 'northwest',
              'southeast', 'southwest', 'up', 'down']

BIOMES = ['forest', 'desert', 'mountain', 'plains', 'swamp', 'tundra',
          'jungle', 'coastal', 'urban', 'underground', 'magical']


# ── Helper functions ──────────────────────────────────────────────────────

async def get_character_location(char_id: int, guild_id: int):
    async with get_db() as db:
        cl_result = await db.execute(
            select(CharacterLocation).where(
                CharacterLocation.character_id == char_id,
                CharacterLocation.guild_id == guild_id,
            )
        )
        cl = cl_result.scalar_one_or_none()
        if not cl:
            return None, None
        loc_result = await db.execute(
            select(Location).where(Location.id == cl.location_id)
        )
        loc = loc_result.scalar_one_or_none()
        return loc, cl


async def get_exits(location_id: int, guild_id: int, show_secret: bool = False):
    async with get_db() as db:
        stmt = select(LocationConnection).where(
            LocationConnection.from_location_id == location_id,
            LocationConnection.guild_id == guild_id,
        )
        if not show_secret:
            stmt = stmt.where(LocationConnection.is_secret == False)
        result = await db.execute(stmt)
        conns = list(result.scalars().all())

    exits = []
    for c in conns:
        to_result = await db.execute(
            select(Location).where(Location.id == c.to_location_id)
        )
        to_loc = to_result.scalar_one_or_none()
        if to_loc and (not to_loc.is_hidden or show_secret):
            exits.append({
                "direction": c.direction,
                "label": c.label or to_loc.name,
                "to_location_id": c.to_location_id,
                "is_locked": c.is_locked,
                "is_secret": c.is_secret,
                "travel_time": c.travel_time_minutes,
            })
    return exits


def location_embed(loc: Location, exits: list[dict],
                   time_info: dict, weather_info: dict,
                   is_indoors: bool):
    embed = discord.Embed(
        title=f"📍 {loc.name}",
        description=loc.description or "*An unremarkable place.*",
        color=0x22C55E,
    )
    if loc.short_description:
        embed.add_field(name="At a Glance", value=loc.short_description, inline=False)

    time_flavor = get_time_flavor(
        time_info["time_of_day"], is_indoors, weather_info["weather_type"]
    )
    weather_flavor = get_weather_flavor(weather_info["weather_type"], is_indoors)
    embed.add_field(
        name=f"{time_info['emoji']} {time_info['time_of_day']}  "
             f"·  {weather_info['icon']} {weather_info['weather_type'].title()}",
        value=f"{time_flavor}\n{weather_flavor}",
        inline=False,
    )
    embed.add_field(name="Type", value=loc.location_type.capitalize(), inline=True)
    if loc.biome:
        embed.add_field(name="Biome", value=loc.biome.capitalize(), inline=True)

    exit_lines = []
    for ex in exits:
        lock = " 🔒" if ex["is_locked"] else ""
        travel = f" (⏳{ex['travel_time']}m)" if ex["travel_time"] else ""
        exit_lines.append(
            f"**{ex['direction'].capitalize()}**: {ex['label']}{lock}{travel}"
        )
    if exit_lines:
        embed.add_field(name="Exits", value="\n".join(exit_lines), inline=False)
    else:
        embed.add_field(name="Exits", value="*None visible.*", inline=False)

    if loc.is_safe:
        embed.add_field(name="Safe Zone", value="Resting here is safe.", inline=False)
    if loc.danger_level:
        embed.add_field(name="Danger Level", value="⚠️" * min(loc.danger_level, 5), inline=True)
    if loc.image_url:
        embed.set_image(url=loc.image_url)
    embed.set_footer(
        text=f"Coords: ({loc.map_x:.0f}, {loc.map_y:.0f})  ·  LoreForge"
    )
    return embed


# ── Command Groups ────────────────────────────────────────────────────────

location_group = app_commands.Group(name="location", description="GM location management")
world_group = app_commands.Group(name="world", description="World map and generation")


# ── Player Commands ───────────────────────────────────────────────────────

@commands.hybrid_command(name="look", description="See your current location")
async def cmd_look(ctx):
    if not ctx.guild:
        return
    char, _ = await resolve_character(ctx.author.id, ctx.guild.id)
    if not char:
        await ctx.send("Create a character first with /character create.", ephemeral=True)
        return
    loc, _ = await get_character_location(char.id, ctx.guild.id)
    if not loc:
        await ctx.send("You haven't discovered any locations yet.", ephemeral=True)
        return
    exits = await get_exits(loc.id, ctx.guild.id)
    time_info = await get_world_time(ctx.guild.id)
    weather_info = await get_weather(ctx.guild.id)
    embed = location_embed(loc, exits, time_info, weather_info, loc.is_indoors)
    await ctx.send(embed=embed)


@commands.hybrid_command(name="travel", description="Travel to a connected location")
async def cmd_travel(ctx, direction: str):
    if not ctx.guild:
        return
    char, _ = await resolve_character(ctx.author.id, ctx.guild.id)
    if not char:
        await ctx.send("Create a character first.", ephemeral=True)
        return
    loc, cl = await get_character_location(char.id, ctx.guild.id)
    if not loc:
        await ctx.send("You haven't discovered any locations.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(LocationConnection).where(
                LocationConnection.from_location_id == loc.id,
                LocationConnection.guild_id == ctx.guild.id,
                LocationConnection.direction.ilike(direction.strip()),
            )
        )
        conn = result.scalar_one_or_none()
    if not conn:
        await ctx.send(f"No exit **{direction}** from here.")
        return
    if conn.is_locked:
        await ctx.send("That exit is locked.")
        return
    to_result = await db.execute(
        select(Location).where(Location.id == conn.to_location_id)
    )
    to_loc = to_result.scalar_one_or_none()
    if not to_loc or to_loc.is_hidden:
        await ctx.send("You can't go that way.")
        return
    async with get_db() as db:
        cl_db = await db.execute(
            select(CharacterLocation).where(CharacterLocation.id == cl.id)
        )
        cl_db = cl_db.scalar_one_or_none()
        if cl_db:
            cl_db.location_id = to_loc.id
    # Check quest progression
    from services.quest_service import check_objective_progress
    await check_objective_progress(char.id, ctx.guild.id, "travel_to", {"location_id": to_loc.id})
    await ctx.send(f"🚶 You travel **{direction}** to **{to_loc.name}**.\nUse `/look` to see your surroundings.")


@commands.hybrid_command(name="map", description="View the world map")
async def cmd_map(ctx):
    if not ctx.guild:
        return
    await ctx.defer()
    char, _ = await resolve_character(ctx.author.id, ctx.guild.id)
    if not char:
        await ctx.send("Create a character first with `/character create`.", ephemeral=True)
        return
    loc, _ = await get_character_location(char.id, ctx.guild.id)
    async with get_db() as db:
        result = await db.execute(
            select(Location).where(
                Location.guild_id == ctx.guild.id,
                Location.is_hidden == False,
            )
        )
        all_locs = list(result.scalars().all())
        config_result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == ctx.guild.id)
        )
        config = config_result.scalar_one_or_none()
    world_name = config.world_name if config else ctx.guild.name
    loc_data = [
        dict(
            id=l.id, name=l.name, map_x=l.map_x, map_y=l.map_y,
            location_type=l.location_type, is_hidden=l.is_hidden
        ) for l in all_locs
    ]
    player_loc_id = loc.id if loc else None
    import asyncio
    base_bytes = await asyncio.get_event_loop().run_in_executor(
        None, lambda: fetch_world_map(world_name, ctx.guild.id)
    )
    img_bytes = generate_world_map_overlay(
        base_bytes, loc_data, player_location_id=player_loc_id
    )
    file = discord.File(img_bytes, filename="world_map.png")
    embed = discord.Embed(title=f"🗺️ {world_name}", color=0x22C55E)
    if player_loc_id:
        current = next((l for l in all_locs if l.id == player_loc_id), None)
        if current:
            embed.set_footer(text=f"⭐ You are in {current.name}")
    embed.set_image(url="attachment://world_map.png")
    await ctx.send(embed=embed, file=file)


@commands.hybrid_command(name="search", description="Search the area for secrets")
async def cmd_search(ctx):
    if not ctx.guild:
        return
    char, _ = await resolve_character(ctx.author.id, ctx.guild.id)
    if not char:
        return
    loc, _ = await get_character_location(char.id, ctx.guild.id)
    if not loc:
        return
    from services.combat_engine import roll
    search_roll = roll("1d20") + (char.wisdom - 10) // 2
    secret_exits = await get_exits(loc.id, ctx.guild.id, show_secret=True)
    secret_exits = [e for e in secret_exits if e["is_secret"]]
    if not secret_exits:
        await ctx.send(f"🔍 You search the area but find nothing unusual. (Wisdom: {search_roll})")
        return
    found_any = False
    for se in secret_exits:
        async with get_db() as db:
            conn_result = await db.execute(
                select(LocationConnection).where(
                    LocationConnection.from_location_id == loc.id,
                    LocationConnection.guild_id == ctx.guild.id,
                    LocationConnection.direction == se["direction"],
                )
            )
            conn = conn_result.scalar_one_or_none()
            dc = conn.search_dc if conn else 15
        if search_roll >= dc:
            found_any = True
            if conn:
                conn.is_secret = False
                label = se["label"] or se["direction"]
                await ctx.send(
                    f"🔍 You find a hidden path! 👁️ **{label}** is now visible.\n"
                    f"(Wisdom: {search_roll} vs DC {dc})"
                )
    if not found_any:
        await ctx.send(f"🔍 You search but find nothing. (Wisdom: {search_roll})")


@commands.hybrid_command(name="gather", description="Gather resources")
async def cmd_gather(ctx):
    if not ctx.guild:
        return
    char, _ = await resolve_character(ctx.author.id, ctx.guild.id)
    if not char:
        return
    loc, _ = await get_character_location(char.id, ctx.guild.id)
    if not loc:
        return
    resources = loc.resources or {}
    if not resources:
        await ctx.send("🌿 Nothing worth gathering here.")
        return
    from services.combat_engine import roll
    gather_roll = roll("1d20") + 2
    gathered = []
    for res_name, res_data in resources.items():
        dc = res_data.get("dc", 10)
        if gather_roll >= dc:
            qty = roll(f"1d{res_data.get('max_qty', 3)}")
            gathered.append(f"{res_name} x{qty}")
    if gathered:
        await ctx.send(f"🌿 You gather: {', '.join(gathered)} (Roll: {gather_roll})")
    else:
        await ctx.send(f"🌿 You find nothing useful. (Roll: {gather_roll})")


@commands.hybrid_command(name="discoveries", description="View discovered locations")
async def cmd_discoveries(ctx):
    if not ctx.guild:
        return
    char, _ = await resolve_character(ctx.author.id, ctx.guild.id)
    if not char:
        return
    async with get_db() as db:
        result = await db.execute(
            select(CharacterLocation).where(
                CharacterLocation.character_id == char.id,
                CharacterLocation.guild_id == ctx.guild.id,
            ).order_by(CharacterLocation.arrived_at.desc())
        )
        cls = list(result.scalars().all())
    locs = []
    for cl in cls:
        loc_result = await db.execute(
            select(Location).where(Location.id == cl.location_id)
        )
        l = loc_result.scalar_one_or_none()
        if l:
            ts = int(cl.arrived_at.timestamp())
            locs.append(f"📍 **{l.name}** — {l.location_type}\n   *Visited <t:{ts}:R>*")
    if not locs:
        await ctx.send("No locations discovered yet.")
        return
    embed = discord.Embed(
        title="🗺️ Discovered Locations",
        description="\n".join(locs),
        color=0x22C55E,
    )
    await ctx.send(embed=embed)


@commands.hybrid_command(name="players-here", description="Who's at your location")
async def cmd_players_here(ctx):
    if not ctx.guild:
        return
    char, _ = await resolve_character(ctx.author.id, ctx.guild.id)
    if not char:
        return
    loc, _ = await get_character_location(char.id, ctx.guild.id)
    if not loc:
        return
    async with get_db() as db:
        result = await db.execute(
            select(CharacterLocation).where(
                CharacterLocation.location_id == loc.id,
                CharacterLocation.guild_id == ctx.guild.id,
            )
        )
        cls = list(result.scalars().all())
    names = []
    for cl in cls:
        char_result = await db.execute(
            select(Character).where(Character.id == cl.character_id)
        )
        c = char_result.scalar_one_or_none()
        if c and not c.is_dead:
            names.append(c.name)
    if not names:
        await ctx.send(f"You are alone at **{loc.name}**.")
    else:
        await ctx.send(f"👥 At **{loc.name}**: {', '.join(names)}")


# ── GM Location Commands ──────────────────────────────────────────────────

@location_group.command(name="create", description="[GM] Create a new location")
@app_commands.describe(
    name="Location name",
    type_="Location type (city, town, village, etc.)",
    description="Full description",
    biome="Biome type",
    x="Map X coordinate",
    y="Map Y coordinate",
    is_safe="Is this a safe zone?",
)
async def loc_create(interaction: discord.Interaction,
                      name: str,
                      type_: str,
                      description: str = "",
                      biome: str = "",
                      x: float = 0.0,
                      y: float = 0.0,
                      is_safe: bool = False):
    if not await gm_only(interaction):
        return
    if type_ not in LOCATION_TYPES:
        await interaction.response.send_message(
            f"Invalid type. Options: {', '.join(LOCATION_TYPES)}", ephemeral=True
        )
        return
    async with get_db() as db:
        loc = Location(
            guild_id=interaction.guild_id,
            name=name,
            location_type=type_,
            description=description or f"A {type_} in the world.",
            short_description="",
            biome=biome if biome else None,
            map_x=x,
            map_y=y,
            is_safe=is_safe,
            is_indoors=False,
            is_hidden=False,
            danger_level=1,
            resources={},
            created_by=interaction.user.id,
        )
        db.add(loc)
    await interaction.response.send_message(
        f"✅ Created location **{name}** (ID: {loc.id})", ephemeral=True
    )


@location_group.command(name="edit", description="[GM] Edit a location")
@app_commands.describe(
    location_id="Location ID to edit",
    name="New name",
    description="New description",
    biome="New biome",
    is_safe="Is this a safe zone?",
    danger_level="Danger level (1-5)",
)
async def loc_edit(interaction: discord.Interaction,
                    location_id: int,
                    name: str = None,
                    description: str = None,
                    biome: str = None,
                    is_safe: bool = None,
                    danger_level: int = None):
    if not await gm_only(interaction):
        return
    async with get_db() as db:
        result = await db.execute(
            select(Location).where(
                Location.id == location_id,
                Location.guild_id == interaction.guild_id,
            )
        )
        loc = result.scalar_one_or_none()
        if not loc:
            await interaction.response.send_message("Location not found.", ephemeral=True)
            return
        if name is not None:
            loc.name = name
        if description is not None:
            loc.description = description
        if biome is not None:
            loc.biome = biome
        if is_safe is not None:
            loc.is_safe = is_safe
        if danger_level is not None:
            loc.danger_level = max(1, min(5, danger_level))
    await interaction.response.send_message(f"✅ Updated **{loc.name}**.", ephemeral=True)


@location_group.command(name="delete", description="[GM] Delete a location")
@app_commands.describe(location_id="Location ID to delete")
async def loc_delete(interaction: discord.Interaction, location_id: int):
    if not await gm_only(interaction):
        return
    async with get_db() as db:
        result = await db.execute(
            select(Location).where(
                Location.id == location_id,
                Location.guild_id == interaction.guild_id,
            )
        )
        loc = result.scalar_one_or_none()
        if not loc:
            await interaction.response.send_message("Location not found.", ephemeral=True)
            return
        name = loc.name
        # Delete connections
        await db.execute(
            LocationConnection.__table__.delete().where(
                or_(
                    LocationConnection.from_location_id == location_id,
                    LocationConnection.to_location_id == location_id,
                )
            )
        )
        # Delete character locations
        await db.execute(
            CharacterLocation.__table__.delete().where(
                CharacterLocation.location_id == location_id
            )
        )
        await db.delete(loc)
    await interaction.response.send_message(f"🗑️ Deleted location **{name}**.", ephemeral=True)


@location_group.command(name="connect", description="[GM] Connect two locations")
@app_commands.describe(
    from_id="Source location ID",
    to_id="Destination location ID",
    direction="Direction (north, south, etc.)",
    label="Exit label (defaults to destination name)",
    is_locked="Is this exit locked?",
    is_secret="Is this exit secret?",
    travel_time="Travel time in minutes",
)
async def loc_connect(interaction: discord.Interaction,
                      from_id: int,
                      to_id: int,
                      direction: str,
                      label: str = None,
                      is_locked: bool = False,
                      is_secret: bool = False,
                      travel_time: int = None):
    if not await gm_only(interaction):
        return
    if direction.lower() not in DIRECTIONS:
        await interaction.response.send_message(
            f"Invalid direction. Options: {', '.join(DIRECTIONS)}", ephemeral=True
        )
        return
    async with get_db() as db:
        # Verify both exist
        from_loc = await db.get(Location, from_id)
        to_loc = await db.get(Location, to_id)
        if not from_loc or not to_loc:
            await interaction.response.send_message("One or both locations not found.", ephemeral=True)
            return
        conn = LocationConnection(
            guild_id=interaction.guild_id,
            from_location_id=from_id,
            to_location_id=to_id,
            direction=direction.lower(),
            label=label,
            is_locked=is_locked,
            is_secret=is_secret,
            travel_time_minutes=travel_time or 5,
            search_dc=15 if is_secret else None,
        )
        db.add(conn)
        # Also add reverse connection
        rev_dir = {"north": "south", "south": "north", "east": "west", "west": "east",
                    "northeast": "southwest", "southwest": "northeast",
                    "northwest": "southeast", "southeast": "northwest",
                    "up": "down", "down": "up"}
        rev_direction = rev_dir.get(direction.lower(), direction.lower())
        conn_rev = LocationConnection(
            guild_id=interaction.guild_id,
            from_location_id=to_id,
            to_location_id=from_id,
            direction=rev_direction,
            label=label or to_loc.name,
            is_locked=is_locked,
            is_secret=False,
            travel_time_minutes=travel_time or 5,
            search_dc=None,
        )
        db.add(conn_rev)
    await interaction.response.send_message(
        f"✅ Connected **{from_loc.name}** → **{to_loc.name}** ({direction})", ephemeral=True
    )


@location_group.command(name="disconnect", description="[GM] Remove a connection")
@app_commands.describe(from_id="Source location ID", to_id="Destination location ID")
async def loc_disconnect(interaction: discord.Interaction, from_id: int, to_id: int):
    if not await gm_only(interaction):
        return
    async with get_db() as db:
        await db.execute(
            LocationConnection.__table__.delete().where(
                and_(
                    LocationConnection.from_location_id == from_id,
                    LocationConnection.to_location_id == to_id,
                    LocationConnection.guild_id == interaction.guild_id,
                )
            )
        )
        await db.execute(
            LocationConnection.__table__.delete().where(
                and_(
                    LocationConnection.from_location_id == to_id,
                    LocationConnection.to_location_id == from_id,
                    LocationConnection.guild_id == interaction.guild_id,
                )
            )
        )
    await interaction.response.send_message("✅ Connections removed.", ephemeral=True)


@location_group.command(name="list", description="[GM] List all locations")
async def loc_list(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    async with get_db() as db:
        result = await db.execute(
            select(Location).where(
                Location.guild_id == interaction.guild_id
            ).order_by(Location.name)
        )
        locs = list(result.scalars().all())
    if not locs:
        await interaction.response.send_message("No locations.", ephemeral=True)
        return
    lines = []
    for l in locs:
        hidden = " 👁️" if l.is_hidden else ""
        safe = " 🛡️" if l.is_safe else ""
        lines.append(f"`{l.id:3d}` **{l.name}** ({l.location_type}){hidden}{safe}")
    await interaction.response.send_message(
        f"**Locations ({len(locs)}):**\n" + "\n".join(lines), ephemeral=True
    )


@location_group.command(name="info", description="[GM] View a location's details")
@app_commands.describe(location_id="Location ID")
async def loc_info(interaction: discord.Interaction, location_id: int):
    if not await gm_only(interaction):
        return
    async with get_db() as db:
        result = await db.execute(
            select(Location).where(Location.id == location_id)
        )
        loc = result.scalar_one_or_none()
    if not loc:
        await interaction.response.send_message("Location not found.", ephemeral=True)
        return
    exits = await get_exits(location_id, interaction.guild_id, show_secret=True)
    time_info = await get_world_time(interaction.guild_id)
    weather_info = await get_weather(interaction.guild_id)
    embed = location_embed(loc, exits, time_info, weather_info, loc.is_indoors)
    await interaction.response.send_message(embed=embed)


@location_group.command(name="teleport", description="[GM] Teleport a player")
@app_commands.describe(
    member="Player to teleport",
    location_id="Target location ID",
)
async def loc_teleport(interaction: discord.Interaction,
                        member: discord.Member,
                        location_id: int):
    if not await gm_only(interaction):
        return
    char, _ = await resolve_character(member.id, interaction.guild_id)
    if not char:
        await interaction.response.send_message(
            f"{member.mention} has no character.", ephemeral=True
        )
        return
    async with get_db() as db:
        result = await db.execute(
            select(CharacterLocation).where(
                CharacterLocation.character_id == char.id,
                CharacterLocation.guild_id == interaction.guild_id,
            )
        )
        cl = result.scalar_one_or_none()
        loc = await db.get(Location, location_id)
        if not loc:
            await interaction.response.send_message("Location not found.", ephemeral=True)
            return
        if cl:
            cl.location_id = location_id
        else:
            cl = CharacterLocation(
                character_id=char.id,
                guild_id=interaction.guild_id,
                location_id=location_id,
            )
            db.add(cl)
    await interaction.response.send_message(
        f"✨ Teleported {member.mention} to **{loc.name}**.", ephemeral=True
    )


@location_group.command(name="set-weather", description="[GM] Override weather")
@app_commands.describe(
    weather_type="Weather type (clear, rain, storm, fog, snow)",
)
async def loc_set_weather(interaction: discord.Interaction, weather_type: str):
    if not await gm_only(interaction):
        return
    await set_weather(interaction.guild_id, weather_type)
    await interaction.response.send_message(f"☁️ Weather set to **{weather_type}**.", ephemeral=True)


# ── World Generation Commands ─────────────────────────────────────────────

@world_group.command(name="generate", description="[GM] Generate random world locations")
@app_commands.describe(count="How many locations to generate")
async def world_generate(interaction: discord.Interaction, count: int = 10):
    if not await gm_only(interaction):
        return
    if count > 50:
        await interaction.response.send_message("Max 50 locations at once.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    import random
    guild_id = interaction.guild_id
    created = 0

    prefixes = ["Ancient", "Misty", "Crimson", "Silver", "Broken",
                 "Whispering", "Sunken", "Golden", "Shadow", "Crystal"]
    suffixes = ["Vale", "Peak", "Hollow", "Gate", "Falls",
                "Spire", "March", "Reach", "Pass", "Glen"]

    x_offset = random.randint(0, 100)
    y_offset = random.randint(0, 100)

    async with get_db() as db:
        # Get starting location as anchor
        first_result = await db.execute(
            select(Location).where(
                Location.guild_id == guild_id,
            ).order_by(Location.id).limit(1)
        )
        first = first_result.scalar_one_or_none()
        anchor_x = first.map_x if first else 0
        anchor_y = first.map_y if first else 0

        for i in range(count):
            loc_type = random.choice(LOCATION_TYPES)
            name = f"{random.choice(prefixes)} {random.choice(suffixes)}"
            biome = random.choice(BIOMES)
            loc = Location(
                guild_id=guild_id,
                name=name,
                location_type=loc_type,
                description=f"A {loc_type} in the {biome}.",
                short_description=f"A {biome} {loc_type}.",
                biome=biome,
                map_x=anchor_x + random.randint(-20, 20),
                map_y=anchor_y + random.randint(-20, 20),
                is_safe=loc_type in ("city", "town", "village", "tavern", "shrine"),
                is_indoors=loc_type in ("dungeon", "cave", "tavern", "library"),
                is_hidden=False,
                danger_level=random.randint(1, 5),
                resources={},
                created_by=interaction.user.id,
            )
            db.add(loc)
            created += 1

    await interaction.followup.send(
        f"🗺️ Generated **{created}** new locations.", ephemeral=True
    )


@world_group.command(name="link", description="[GM] Auto-link nearby locations")
async def world_link(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    async with get_db() as db:
        result = await db.execute(
            select(Location).where(
                Location.guild_id == interaction.guild_id
            )
        )
        locs = list(result.scalars().all())

    linked = 0
    for i, loc_a in enumerate(locs):
        for loc_b in locs[i + 1:]:
            dx = loc_a.map_x - loc_b.map_x
            dy = loc_a.map_y - loc_b.map_y
            distance = (dx ** 2 + dy ** 2) ** 0.5
            if distance < 5:
                direction = "north" if dy > 0 else "south" if dy < 0 else "east"
                # Check if already connected
                async with get_db() as db_check:
                    existing = await db_check.execute(
                        select(LocationConnection).where(
                            LocationConnection.from_location_id == loc_a.id,
                            LocationConnection.to_location_id == loc_b.id,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue
                async with get_db() as db_write:
                    conn_ab = LocationConnection(
                        guild_id=interaction.guild_id,
                        from_location_id=loc_a.id,
                        to_location_id=loc_b.id,
                        direction=direction,
                        label=loc_b.name,
                        is_locked=False,
                        is_secret=False,
                        travel_time_minutes=max(1, int(distance * 2)),
                        search_dc=None,
                    )
                    db_write.add(conn_ab)
                    rev = {"north": "south", "south": "north", "east": "west", "west": "east"}
                    conn_ba = LocationConnection(
                        guild_id=interaction.guild_id,
                        from_location_id=loc_b.id,
                        to_location_id=loc_a.id,
                        direction=rev.get(direction, direction),
                        label=loc_a.name,
                        is_locked=False,
                        is_secret=False,
                        travel_time_minutes=max(1, int(distance * 2)),
                        search_dc=None,
                    )
                    db_write.add(conn_ba)
                linked += 1

    await interaction.followup.send(
        f"🔗 Created **{linked}** connections between nearby locations.", ephemeral=True
    )


@world_group.command(name="info", description="[GM] World info overview")
async def world_info(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    async with get_db() as db:
        loc_count = await db.scalar(
            select(Location.id).where(
                Location.guild_id == interaction.guild_id
            ).order_by(Location.id.desc()).limit(1)
        )
        conn_count = await db.scalar(
            select(LocationConnection.id).where(
                LocationConnection.guild_id == interaction.guild_id
            ).order_by(LocationConnection.id.desc()).limit(1)
        )
        char_count = await db.scalar(
            select(CharacterLocation.id).where(
                CharacterLocation.guild_id == interaction.guild_id
            ).order_by(CharacterLocation.id.desc()).limit(1)
        )

    embed = discord.Embed(
        title="🗺️ World Overview",
        color=0x22C55E,
    )
    embed.add_field(name="Locations", value=str(loc_count or 0), inline=True)
    embed.add_field(name="Connections", value=str(conn_count or 0), inline=True)
    embed.add_field(name="Players with locations", value=str(char_count or 0), inline=True)
    time_info = await get_world_time(interaction.guild_id)
    weather_info = await get_weather(interaction.guild_id)
    embed.add_field(name="Time", value=f"{time_info['emoji']} {time_info['time_of_day']}", inline=True)
    embed.add_field(name="Weather", value=f"{weather_info['icon']} {weather_info['weather_type'].title()}", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── Standalone Player Commands ────────────────────────────────────────────

@commands.hybrid_command(name="weather", description="Check the current weather")
async def cmd_weather(ctx):
    """Check the current weather conditions."""
    if not ctx.guild:
        return
    weather_info = await get_weather(ctx.guild.id)
    embed = discord.Embed(
        title=f"{weather_info['icon']} Current Weather",
        description=weather_info["flavor"],
        color=0x6366F1,
    )
    embed.add_field(name="Temperature", value=weather_info["temperature"].title(), inline=True)
    embed.add_field(name="Type", value=weather_info["weather_type"].title(), inline=True)
    combat_effects = weather_info.get("combat_effects", {})
    if combat_effects.get("flavor"):
        embed.add_field(name="Combat Effects", value=combat_effects["flavor"], inline=False)
    await ctx.send(embed=embed)


@commands.hybrid_command(name="announce", description="[GM] Post a world announcement")
async def cmd_announce(ctx, *, message: str):
    """Post a world announcement to the configured GM channel."""
    if not ctx.guild:
        return
    if not await is_gm(ctx.author, ctx.guild.id):
        await ctx.send("Only GMs can make announcements.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == ctx.guild.id)
        )
        config = result.scalar_one_or_none()
    if config and config.gm_channel_id:
        channel = ctx.guild.get_channel(config.gm_channel_id) or ctx.channel
    else:
        channel = ctx.channel
    embed = discord.Embed(
        title="📢 World Announcement",
        description=message,
        color=0xF59E0B,
    )
    embed.set_footer(text=f"Announced by {ctx.author.display_name}")
    await channel.send(embed=embed)
    if channel != ctx.channel:
        await ctx.send("✅ Announcement posted.", ephemeral=True)


@commands.hybrid_command(name="time", description="Check the current world time")
async def cmd_time(ctx):
    """Show current world time, season, and day."""
    if not ctx.guild:
        return
    time_info = await get_world_time(ctx.guild.id)
    embed = discord.Embed(
        title=f"{time_info['emoji']} {time_info['time_of_day']}",
        description=(
            f"{time_info['season_emoji']} Season: **{time_info['season'].title()}**\n"
            f"📅 Day {time_info['day']}, Month {time_info['month']}, Year {time_info['year']}\n"
            f"⏰ Hour: {time_info['hour']}:00 ({time_info['mode']} mode)"
        ),
        color=0x6366F1,
    )
    await ctx.send(embed=embed)


@commands.hybrid_command(name="timemode", description="[Owner] Toggle time mode (automatic/manual)")
async def cmd_timemode(ctx, mode: str):
    """Switch between automatic and manual time progression."""
    if not ctx.guild:
        return
    from services.utils import gm_only
    if not await is_gm(ctx.author, ctx.guild.id):
        await ctx.send("Only GMs can change time mode.", ephemeral=True)
        return
    if mode.lower() not in ("automatic", "manual"):
        await ctx.send("Mode must be 'automatic' or 'manual'.", ephemeral=True)
        return
    await set_time_mode(ctx.guild.id, mode.lower())
    await ctx.send(f"⏰ Time mode set to **{mode.lower()}**.", ephemeral=True)


from services.time_service import set_time_mode

# ── Cog setup ─────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    bot.add_command(cmd_look)
    bot.add_command(cmd_travel)
    bot.add_command(cmd_map)
    bot.add_command(cmd_search)
    bot.add_command(cmd_gather)
    bot.add_command(cmd_discoveries)
    bot.add_command(cmd_players_here)
    bot.add_command(cmd_weather)
    bot.add_command(cmd_announce)
    bot.add_command(cmd_time)
    bot.add_command(cmd_timemode)
    bot.tree.add_command(location_group)
    bot.tree.add_command(world_group)
