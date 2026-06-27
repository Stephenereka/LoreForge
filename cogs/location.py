import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, or_, and_
from database.session import get_db
from database.models import Location, LocationConnection, CharacterLocation, GuildConfig, Character, GuildMapCache, GuildMapAnnotation, NPC, Faction, Quest, LoreEntry, BossTemplate
from services.utils import gm_only, is_gm
from services.time_service import get_world_time, get_time_flavor
from services.weather_service import get_weather, get_weather_flavor, set_weather
from services.map_service import generate_world_map_overlay, fetch_world_map, fetch_world_map_async
from cogs.character import resolve_character
import io
import random
import urllib.request
import urllib.parse

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
    await ctx.defer()
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
    await ctx.defer()
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
    try:
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

        # Fetch base map: GuildMapCache bytes first (set via /world set-map or auto-seed),
        # then fall back to Pollinations. Never re-download Discord CDN URLs (they expire).
        async with get_db() as db:
            base_bytes = await fetch_world_map_async(world_name, ctx.guild.id, db)

            # Fetch annotations for overlay
            ann_result = await db.execute(
                select(GuildMapAnnotation).where(
                    GuildMapAnnotation.guild_id == ctx.guild.id
                )
            )
            annotations = [
                dict(
                    annotation_type=a.annotation_type,
                    x=a.x, y=a.y,
                    color=a.color,
                    label=a.label,
                )
                for a in list(ann_result.scalars().all())
            ]

        img_bytes = generate_world_map_overlay(
            base_bytes, loc_data,
            player_location_id=player_loc_id,
            annotations=annotations or None,
        )
        file = discord.File(img_bytes, filename="world_map.png")
        embed = discord.Embed(title=f"🗺️ {world_name}", color=0x22C55E)
        if player_loc_id:
            current = next((l for l in all_locs if l.id == player_loc_id), None)
            if current:
                embed.set_footer(text=f"⭐ You are in {current.name}")
        embed.set_image(url="attachment://world_map.png")

        # Categorised location dropdowns — scalable to 100+ locations (25 per category)
        _LOC_EMOJI = {
            'city': '🏙️', 'town': '🏘️', 'village': '🏡', 'tavern': '🍺',
            'shrine': '⛩️', 'temple': '🛕', 'dungeon': '💀', 'ruins': '🏚️',
            'cave': '🕳️', 'fortress': '🏰', 'tower': '🗼', 'library': '📚',
            'arena': '⚔️', 'market': '🛒', 'port': '⚓', 'bridge': '🌉',
            'forest': '🌲', 'mountain': '⛰️', 'lake': '🌊', 'wilderness': '🗺️',
        }
        _CATEGORIES = [
            ('🏙️ Settlements',     {'city', 'town', 'village', 'tavern'}),
            ('⚔️ Danger Zones',    {'dungeon', 'ruins', 'cave', 'arena', 'fortress'}),
            ('🌿 Wilderness',      {'forest', 'mountain', 'lake', 'wilderness', 'bridge'}),
            ('🏛️ Points of Interest', {'shrine', 'temple', 'market', 'library', 'port', 'tower'}),
        ]

        async def _map_select_callback(interaction: discord.Interaction):
            loc_id = int(interaction.data["values"][0])
            async with get_db() as db:
                loc_result = await db.execute(
                    select(Location).where(Location.id == loc_id, Location.guild_id == interaction.guild_id)
                )
                loc = loc_result.scalar_one_or_none()
                if not loc:
                    await interaction.response.send_message("Location not found.", ephemeral=True)
                    return
                npc_result = await db.execute(
                    select(NPC).where(
                        NPC.guild_id == interaction.guild_id,
                        NPC.location_id == loc.id,
                        NPC.is_dead == False,
                    )
                )
                npcs = list(npc_result.scalars().all())
            exits = await get_exits(loc.id, interaction.guild_id)
            time_info = await get_world_time(interaction.guild_id)
            weather_info = await get_weather(interaction.guild_id)
            loc_embed = location_embed(loc, exits, time_info, weather_info, loc.is_indoors)
            if npcs:
                npc_lines = [f"**{n.name}**" + (f" — *{n.title}*" if n.title else "") for n in npcs[:5]]
                loc_embed.add_field(name="👥 People Here", value="\n".join(npc_lines), inline=False)
            await interaction.response.send_message(embed=loc_embed, ephemeral=True)

        discovered_locs = [l for l in all_locs if not l.is_hidden and l.map_x is not None and l.map_y is not None]
        map_view = None
        if discovered_locs:
            map_view = discord.ui.View(timeout=120)
            row_idx = 0
            for cat_label, cat_types in _CATEGORIES:
                bucket = [l for l in discovered_locs if l.location_type in cat_types][:25]
                if not bucket or row_idx >= 5:
                    continue
                options = [
                    discord.SelectOption(
                        label=l.name[:100],
                        value=str(l.id),
                        emoji=_LOC_EMOJI.get(l.location_type, '📍'),
                        description=l.location_type.capitalize(),
                    )
                    for l in bucket
                ]
                select = discord.ui.Select(
                    placeholder=cat_label,
                    options=options,
                    row=row_idx,
                )
                select.callback = _map_select_callback
                map_view.add_item(select)
                row_idx += 1

        await ctx.send(embed=embed, file=file, view=map_view)
    except Exception as e:
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Failed to render map: `{type(e).__name__}: {e}`", ephemeral=True)


@commands.hybrid_command(name="search", description="Search the area for secrets")
async def cmd_search(ctx):
    if not ctx.guild:
        return
    await ctx.defer()
    char, _ = await resolve_character(ctx.author.id, ctx.guild.id)
    if not char:
        return
    loc, _ = await get_character_location(char.id, ctx.guild.id)
    if not loc:
        return
    search_roll = random.randint(1, 20) + (char.wisdom - 10) // 2
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
    await ctx.defer()
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
    gather_roll = random.randint(1, 20) + 2
    gathered = []
    for res_name, res_data in resources.items():
        dc = res_data.get("dc", 10)
        if gather_roll >= dc:
            qty = random.randint(1, res_data.get("max_qty", 3))
            gathered.append(f"{res_name} x{qty}")
    if gathered:
        await ctx.send(f"🌿 You gather: {', '.join(gathered)} (Roll: {gather_roll})")
    else:
        await ctx.send(f"🌿 You find nothing useful. (Roll: {gather_roll})")


@commands.hybrid_command(name="discoveries", description="View discovered locations")
async def cmd_discoveries(ctx):
    if not ctx.guild:
        return
    await ctx.defer()
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
    await ctx.defer()
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


async def _location_name_autocomplete(interaction: discord.Interaction, current: str):
    async with get_db() as db:
        result = await db.execute(
            select(Location).where(
                Location.guild_id == interaction.guild_id,
                Location.is_hidden == False,
                Location.name.ilike(f"%{current}%"),
            ).limit(25)
        )
        locs = result.scalars().all()
    return [app_commands.Choice(name=loc.name, value=loc.name) for loc in locs]


@location_group.command(name="view", description="View a location's details and who's there")
@app_commands.describe(name="Location name")
@app_commands.autocomplete(name=_location_name_autocomplete)
async def loc_view(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    async with get_db() as db:
        loc_result = await db.execute(
            select(Location).where(
                Location.guild_id == interaction.guild_id,
                Location.name.ilike(name),
                Location.is_hidden == False,
            )
        )
        loc = loc_result.scalar_one_or_none()
        if not loc:
            await interaction.followup.send(
                f"Location **{name}** not found or not yet discovered.", ephemeral=True
            )
            return

        npc_result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.location_id == loc.id,
                NPC.is_dead == False,
            )
        )
        npcs = npc_result.scalars().all()

    exits = await get_exits(loc.id, interaction.guild_id)
    time_info = await get_world_time(interaction.guild_id)
    weather_info = await get_weather(interaction.guild_id)
    embed = location_embed(loc, exits, time_info, weather_info, loc.is_indoors)

    if npcs:
        npc_lines = []
        for n in npcs:
            title_str = f" — *{n.title}*" if n.title else ""
            npc_lines.append(f"**{n.name}**{title_str}")
        embed.add_field(name="👥 People Here", value="\n".join(npc_lines), inline=False)
    else:
        embed.add_field(name="👥 People Here", value="*No one notable is here right now.*", inline=False)

    await interaction.followup.send(embed=embed)


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


@location_group.command(name="set-image", description="[GM] Set a custom image for a location")
@app_commands.describe(
    location_id="Location ID to set the image for",
    image="Upload an image to use as the location's picture (optional — attach a file)",
)
async def location_set_image(interaction: discord.Interaction,
                              location_id: int,
                              image: discord.Attachment = None):
    if not await gm_only(interaction):
        return
    if not image:
        await interaction.response.send_message(
            "Please attach an image file to set as the location picture.", ephemeral=True
        )
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
        loc.image_url = image.url
    await interaction.response.send_message(
        f"✅ Set image for **{loc.name}** — it will appear in `/look` and `/location info`.", ephemeral=True
    )


# ── World Generation Commands ─────────────────────────────────────────────

@world_group.command(name="validate", description="[GM] Validate a world JSON file before importing")
@app_commands.describe(json_file="Attach a .json file to validate")
async def world_validate(interaction: discord.Interaction, json_file: discord.Attachment):
    if not await gm_only(interaction):
        return
    if not json_file.filename.endswith(".json"):
        await interaction.response.send_message("Attached file must be a `.json` file.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    try:
        content = await json_file.read()
        import json
        data = json.loads(content)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to parse JSON: {e}", ephemeral=True)
        return

    errors = []

    # Check required top-level fields
    if "version" not in data:
        errors.append("Missing required field: `version`")
    if "world_name" not in data:
        errors.append("Missing required field: `world_name`")

    # Collect location names/ids
    locations = data.get("locations", [])
    location_names = {loc.get("name"): loc.get("id") for loc in locations}
    location_ids = {loc.get("id"): loc.get("name") for loc in locations}

    # Validate each location has required fields
    for i, loc in enumerate(locations):
        loc_name = loc.get("name", f"locations[{i}]")
        if "name" not in loc:
            errors.append(f"locations[{i}]: Missing required field `name`")
        if "location_type" not in loc:
            errors.append(f"locations[{i}] (`{loc_name}`): Missing required field `location_type`")

    # Validate NPC location references
    npcs = data.get("npcs", [])
    for i, npc in enumerate(npcs):
        npc_name = npc.get("name", f"npcs[{i}]")
        loc_id = npc.get("location_id")
        loc_name_ref = npc.get("location_name")
        if loc_id:
            if loc_id not in location_ids:
                errors.append(f"npcs[{i}] (`{npc_name}`): `location_id` {loc_id} not found in locations")
        elif loc_name_ref:
            if loc_name_ref not in location_names:
                errors.append(f"npcs[{i}] (`{npc_name}`): `location_name` \"{loc_name_ref}\" not found in locations")

    # Validate quest NPC references
    quests = data.get("quests", [])
    for i, quest in enumerate(quests):
        quest_name = quest.get("name", f"quests[{i}]")
        giver_npc_id = quest.get("giver_npc_id")
        turnin_npc_id = quest.get("turnin_npc_id")
        npc_ids = [npc.get("id") for npc in npcs]
        if giver_npc_id and giver_npc_id not in npc_ids:
            errors.append(f"quests[{i}] (`{quest_name}`): `giver_npc_id` {giver_npc_id} not found in npcs array")
        if turnin_npc_id and turnin_npc_id not in npc_ids:
            errors.append(f"quests[{i}] (`{quest_name}`): `turnin_npc_id` {turnin_npc_id} not found in npcs array")

    # Validate boss template minion references
    boss_templates = data.get("boss_templates", [])
    bt_ids = {bt.get("id"): bt.get("name") for bt in boss_templates}
    for i, bt in enumerate(boss_templates):
        bt_name = bt.get("name", f"boss_templates[{i}]")
        minion_id = bt.get("minion_template_id")
        if minion_id and minion_id not in bt_ids:
            errors.append(f"boss_templates[{i}] (`{bt_name}`): `minion_template_id` {minion_id} not found in boss_templates array")

    if errors:
        error_list = "\n".join(f"• {e}" for e in errors[:20])
        if len(errors) > 20:
            error_list += f"\n*...and {len(errors)-20} more errors*"
        embed = discord.Embed(
            title="❌ Validation Failed",
            description=f"Found **{len(errors)}** error(s):\n\n{error_list}",
            color=0xEF4444,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        loc_count = len(locations)
        npc_count = len(npcs)
        quest_count = len(quests)
        bt_count = len(boss_templates)
        embed = discord.Embed(
            title="✅ Validation Passed",
            description=f"The world JSON is valid and ready to import!\n\n"
                        f"📍 **{loc_count}** locations\n"
                        f"👤 **{npc_count}** NPCs\n"
                        f"📜 **{quest_count}** quests\n"
                        f"🗡️ **{bt_count}** boss templates",
            color=0x22C55E,
        )
        embed.set_footer(text="Use /world import to load this data")
        await interaction.followup.send(embed=embed, ephemeral=True)


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


@world_group.command(name="set-map", description="[GM] Upload a custom world map image")
@app_commands.describe(image="Upload an image to use as the custom world map")
async def world_set_map(interaction: discord.Interaction, image: discord.Attachment):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    import base64
    # Download bytes now — Discord CDN URLs expire and can't be fetched later
    img_bytes = await image.read()
    img_b64 = base64.b64encode(img_bytes).decode("ascii")
    async with get_db() as db:
        config_result = await db.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
        config = config_result.scalar_one_or_none()
        if not config:
            config = GuildConfig(guild_id=interaction.guild_id)
            db.add(config)
        config.world_map_url = image.url
        # Store bytes in GuildMapCache so /map can use them directly
        cache_result = await db.execute(select(GuildMapCache).where(GuildMapCache.guild_id == interaction.guild_id))
        cache = cache_result.scalar_one_or_none()
        if not cache:
            cache = GuildMapCache(guild_id=interaction.guild_id)
            db.add(cache)
        cache.map_bytes_b64 = img_b64
        cache.map_url = image.url
    await interaction.followup.send(
        f"🗺️ Custom world map set! Use `/map` to see it.", ephemeral=True
    )


@world_group.command(name="clear-map", description="[GM] Reset to the AI-generated world map")
async def world_clear_map(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    async with get_db() as db:
        result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
        )
        config = result.scalar_one_or_none()
        if not config or not config.world_map_url:
            await interaction.response.send_message(
                "No custom map is currently set.", ephemeral=True
            )
            return
        config.world_map_url = None
    await interaction.response.send_message(
        "🗺️ Custom map cleared — `/map` will now use the AI-generated world map.", ephemeral=True
    )


@world_group.command(name="load-template", description="[GM] Load a built-in world template (locations, NPCs, factions, quests, lore, bosses)")
@app_commands.describe(
    template_name="Choose a world template",
    purge_stale="Delete locations/NPCs/factions NOT in the template (removes old placeholder data)",
)
@app_commands.choices(template_name=[
    app_commands.Choice(name="Murim / Magic World (The Merged Realms)", value="murim_magic"),
])
async def world_load_template(interaction: discord.Interaction, template_name: str = "murim_magic", purge_stale: bool = False):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    import json, pathlib, os
    bot_root = pathlib.Path(__file__).parent.parent
    # Normalize: "murim/magic" or "murim magic" → "murim_magic"
    safe_name = template_name.replace("/", "_").replace(" ", "_").replace("-", "_")
    template_path = bot_root / "data" / "templates" / f"{safe_name}.json"
    if not template_path.exists():
        await interaction.followup.send(
            f"❌ Template `{safe_name}` not found. Available: `murim_magic`", ephemeral=True
        )
        return

    with open(template_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    guild_id = interaction.guild_id
    bot_user_id = interaction.client.user.id

    # ── Optional purge of stale data not in this template ─────────────────────
    locs_purged = npcs_purged = factions_purged = 0
    if purge_stale:
        template_loc_names   = {l["name"] for l in data.get("locations", [])}
        template_npc_names   = {n["name"] for n in data.get("npcs", [])}
        template_faction_names = {f["name"] for f in data.get("factions", [])}
        async with get_db() as db:
            # Delete locations not in template
            loc_result = await db.execute(select(Location).where(Location.guild_id == guild_id))
            for loc in loc_result.scalars().all():
                if loc.name not in template_loc_names:
                    await db.delete(loc)
                    locs_purged += 1
            # Delete NPCs not in template
            npc_result = await db.execute(select(NPC).where(NPC.guild_id == guild_id))
            for npc in npc_result.scalars().all():
                if npc.name not in template_npc_names:
                    await db.delete(npc)
                    npcs_purged += 1
            # Delete factions not in template
            fac_result = await db.execute(select(Faction).where(Faction.guild_id == guild_id))
            for fac in fac_result.scalars().all():
                if fac.name not in template_faction_names:
                    await db.delete(fac)
                    factions_purged += 1

    locs_created = locs_skipped = 0
    npc_created = npc_skipped = 0
    factions_created = factions_skipped = 0
    quests_created = quests_skipped = 0
    lore_created = lore_skipped = 0
    bosses_created = bosses_skipped = 0

    # ── Step 0: GuildConfig ────────────────────────────────────────────────
    _MERGED_REALMS_MAP_URL = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(
            "fantasy political territory map, soft watercolor colored faction territories, "
            "dark teal ocean background, parchment texture overlay, fantasy cartography art, "
            "Inkarnate style, highly detailed, professional TTRPG world map, "
            "title The Merged Realms, faction territories: jade green Murim Alliance center-north, "
            "deep crimson Heavenly Demon Cult far northeast, indigo Arcane Council center-north, "
            "silver purple Silverwood Dominion far west, golden Southern Kingdoms south, "
            "orange Ebon Scale Covenant far southeast, dark grey Pale Hand northeast, "
            "neutral Rift Wardens center crossroads"
        )
        + "?width=1792&height=1008&model=flux&seed=1000&nologo=true&enhance=true"
    )
    gc_data = data.get("guild_config", {})
    async with get_db() as db:
        gc_result = await db.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
        gc = gc_result.scalar_one_or_none()
        if not gc:
            gc = GuildConfig(guild_id=guild_id)
            db.add(gc)
        if not gc.world_name or gc.world_name == "LoreForge World":
            gc.world_name = gc_data.get("world_name", "The Merged Realms")
        if gc_data.get("world_data"):
            gc.world_data = {**(gc.world_data or {}), **gc_data["world_data"]}
        if not gc.world_map_url:
            gc.world_map_url = _MERGED_REALMS_MAP_URL

    # ── Step 1: Locations ──────────────────────────────────────────────────
    loc_name_to_id: dict[str, int] = {}
    async with get_db() as db:
        for loc_data in data.get("locations", []):
            existing = await db.execute(
                select(Location).where(
                    Location.guild_id == guild_id,
                    Location.name == loc_data["name"],
                )
            )
            existing = existing.scalar_one_or_none()
            if existing:
                loc_name_to_id[existing.name] = existing.id
                locs_skipped += 1
                continue
            loc = Location(
                guild_id=guild_id,
                name=loc_data["name"],
                description=loc_data.get("description", ""),
                short_description=loc_data.get("short_description", ""),
                location_type=loc_data.get("location_type", "wilderness"),
                biome=loc_data.get("biome"),
                map_x=loc_data.get("map_x", 50.0),
                map_y=loc_data.get("map_y", 50.0),
                is_safe=loc_data.get("is_safe", False),
                is_indoors=loc_data.get("is_indoors", False),
                is_hidden=False,
                danger_level=loc_data.get("danger_level", 1),
                resources=loc_data.get("resources", {}),
                created_by=bot_user_id,
            )
            db.add(loc)
            await db.flush()
            loc_name_to_id[loc.name] = loc.id
            locs_created += 1

    # ── Step 2: Connections ────────────────────────────────────────────────
    REVERSE_DIR = {
        "north": "south", "south": "north", "east": "west", "west": "east",
        "northeast": "southwest", "southwest": "northeast",
        "northwest": "southeast", "southeast": "northwest",
        "up": "down", "down": "up", "surrounding": "center",
    }
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
                existing_conn = await db.execute(
                    select(LocationConnection).where(
                        LocationConnection.guild_id == guild_id,
                        LocationConnection.from_location_id == from_id,
                        LocationConnection.to_location_id == to_id,
                    )
                )
                if existing_conn.scalar_one_or_none():
                    continue
                db.add(LocationConnection(
                    guild_id=guild_id,
                    from_location_id=from_id,
                    to_location_id=to_id,
                    direction=direction,
                    is_locked=False,
                    is_secret=False,
                    travel_time_minutes=conn_data.get("travel_time_minutes", 10),
                ))
                rev = REVERSE_DIR.get(direction, direction)
                existing_rev = await db.execute(
                    select(LocationConnection).where(
                        LocationConnection.guild_id == guild_id,
                        LocationConnection.from_location_id == to_id,
                        LocationConnection.to_location_id == from_id,
                    )
                )
                if not existing_rev.scalar_one_or_none():
                    db.add(LocationConnection(
                        guild_id=guild_id,
                        from_location_id=to_id,
                        to_location_id=from_id,
                        direction=rev,
                        is_locked=False,
                        is_secret=False,
                        travel_time_minutes=conn_data.get("travel_time_minutes", 10),
                    ))

    # ── Step 3: Factions ───────────────────────────────────────────────────
    faction_name_to_id: dict[str, int] = {}
    async with get_db() as db:
        for f_data in data.get("factions", []):
            existing = await db.execute(
                select(Faction).where(
                    Faction.guild_id == guild_id,
                    Faction.name == f_data["name"],
                )
            )
            existing = existing.scalar_one_or_none()
            if existing:
                faction_name_to_id[existing.name] = existing.id
                factions_skipped += 1
                continue
            faction = Faction(
                guild_id=guild_id,
                name=f_data["name"],
                description=f_data.get("description", ""),
                faction_type=f_data.get("faction_type", "guild"),
                color=f_data.get("color", "#6366F1"),
                icon_emoji=f_data.get("icon_emoji"),
                starting_rep=f_data.get("starting_rep", 0),
                created_by=bot_user_id,
            )
            db.add(faction)
            await db.flush()
            faction_name_to_id[faction.name] = faction.id
            factions_created += 1

    # ── Step 4: NPCs ───────────────────────────────────────────────────────
    async with get_db() as db:
        for npc_data in data.get("npcs", []):
            existing = await db.execute(
                select(NPC).where(
                    NPC.guild_id == guild_id,
                    NPC.name == npc_data["name"],
                )
            )
            if existing.scalar_one_or_none():
                npc_skipped += 1
                continue
            loc_id = loc_name_to_id.get(npc_data.get("location_name", ""))
            if not loc_id:
                npc_skipped += 1
                continue
            faction_id = faction_name_to_id.get(npc_data.get("faction_name", ""))
            npc = NPC(
                guild_id=guild_id,
                name=npc_data["name"],
                title=npc_data.get("title"),
                race=npc_data.get("race"),
                description=npc_data.get("description", ""),
                appearance=npc_data.get("appearance"),
                location_id=loc_id,
                disposition=npc_data.get("disposition", "neutral"),
                is_hostile=npc_data.get("is_hostile", False),
                is_killable=npc_data.get("is_killable", True),
                greeting=npc_data.get("greeting"),
                dialogue_topics=npc_data.get("dialogue_topics", {}),
                image_url=npc_data.get("image_url") or None,
                proxy_name=npc_data.get("proxy_name") or npc_data.get("name"),
                proxy_mode=npc_data.get("proxy_mode", "automatic"),
                faction_id=faction_id,
                hp_max=npc_data.get("hp_max", 30),
                hp_current=npc_data.get("hp_max", 30),
                armor_class=npc_data.get("armor_class", 10),
                attack_bonus=npc_data.get("attack_bonus", 2),
                damage_dice=npc_data.get("damage_dice", "1d6"),
                damage_bonus=npc_data.get("damage_bonus", 0),
                xp_value=npc_data.get("xp_value", 50),
                gold=npc_data.get("gold", 0),
                shop_inventory=npc_data.get("shop_inventory", {}),
                created_by=bot_user_id,
            )
            db.add(npc)
            npc_created += 1

    # ── Step 5: Quests ─────────────────────────────────────────────────────
    async with get_db() as db:
        for q_data in data.get("quests", []):
            existing = await db.execute(
                select(Quest).where(
                    Quest.guild_id == guild_id,
                    Quest.name == q_data["name"],
                )
            )
            if existing.scalar_one_or_none():
                quests_skipped += 1
                continue
            quest = Quest(
                guild_id=guild_id,
                name=q_data["name"],
                description=q_data.get("description", ""),
                quest_type=q_data.get("quest_type", "standard"),
                reward_xp=q_data.get("reward_xp", 0),
                reward_gold=q_data.get("reward_gold", 0),
                reward_items=q_data.get("reward_items", []),
                is_active=True,
                created_by=bot_user_id,
            )
            db.add(quest)
            quests_created += 1

    # ── Step 6: Lore entries ───────────────────────────────────────────────
    async with get_db() as db:
        for l_data in data.get("lore_entries", []):
            existing = await db.execute(
                select(LoreEntry).where(
                    LoreEntry.guild_id == guild_id,
                    LoreEntry.title == l_data["title"],
                )
            )
            if existing.scalar_one_or_none():
                lore_skipped += 1
                continue
            lore = LoreEntry(
                guild_id=guild_id,
                title=l_data["title"],
                content=l_data.get("content", ""),
                category=l_data.get("category", "lore"),
                tags=l_data.get("tags", []),
                is_canon=l_data.get("is_canon", True),
                visibility=l_data.get("visibility", "public"),
                importance=l_data.get("importance", 5),
                created_by=bot_user_id,
            )
            db.add(lore)
            lore_created += 1

    # ── Step 7: Boss templates ─────────────────────────────────────────────
    async with get_db() as db:
        for b_data in data.get("bosses", []):
            existing = await db.execute(
                select(BossTemplate).where(
                    BossTemplate.guild_id == guild_id,
                    BossTemplate.name == b_data["name"],
                )
            )
            if existing.scalar_one_or_none():
                bosses_skipped += 1
                continue
            boss = BossTemplate(
                guild_id=guild_id,
                name=b_data["name"],
                title=b_data.get("title"),
                description=b_data.get("description", ""),
                hp_max=b_data.get("hp_max", 100),
                armor_class=b_data.get("armor_class", 15),
                attack_bonus=b_data.get("attack_bonus", 6),
                damage_dice=b_data.get("damage_dice", "2d8"),
                damage_bonus=b_data.get("damage_bonus", 0),
                xp_value=b_data.get("xp_value", 1000),
                gold_drop=b_data.get("gold_drop", 0),
                loot_table=b_data.get("loot_table", []),
                phase_count=b_data.get("phase_count", 1),
                phase_thresholds=b_data.get("phase_thresholds", []),
                phase_abilities=b_data.get("phase_abilities", {}),
                legendary_actions=b_data.get("legendary_actions", []),
                legendary_action_count=b_data.get("legendary_action_count", 3),
                is_lair_boss=b_data.get("is_lair_boss", False),
                lair_actions=b_data.get("lair_actions", []),
                created_by=bot_user_id,
            )
            db.add(boss)
            bosses_created += 1

    embed = discord.Embed(
        title=f"🗺️ Template Loaded — {data.get('template_name', template_name)}",
        description=data.get("description", ""),
        color=0x22C55E,
    )
    if purge_stale and (locs_purged or npcs_purged or factions_purged):
        embed.add_field(
            name="🗑️ Purged (stale)",
            value=f"{locs_purged} locations, {npcs_purged} NPCs, {factions_purged} factions",
            inline=False,
        )
    embed.add_field(name="📍 Locations", value=f"+{locs_created} created, {locs_skipped} skipped", inline=True)
    embed.add_field(name="👤 NPCs", value=f"+{npc_created} created, {npc_skipped} skipped", inline=True)
    embed.add_field(name="⚔️ Factions", value=f"+{factions_created} created, {factions_skipped} skipped", inline=True)
    embed.add_field(name="📜 Quests", value=f"+{quests_created} created, {quests_skipped} skipped", inline=True)
    embed.add_field(name="📚 Lore", value=f"+{lore_created} created, {lore_skipped} skipped", inline=True)
    embed.add_field(name="🗡️ Bosses", value=f"+{bosses_created} created, {bosses_skipped} skipped", inline=True)
    embed.set_footer(text="Run /location list and /npc list to see all created entities.")
    await interaction.followup.send(embed=embed, ephemeral=True)


# ── Map Annotation Commands (GM only) ─────────────────────────────────────

ANNOTATION_TYPES = ["road_block", "danger_zone", "icon", "label"]


@world_group.command(name="annotate", description="[GM] Add an annotation to the world map overlay")
@app_commands.describe(
    type_="Annotation type (road_block, danger_zone, icon, label)",
    x="Map X coordinate (0–100)",
    y="Map Y coordinate (0–100)",
    color="Hex color code (default: #EF4444 for red)",
    label="Text label (only shown for 'label' and 'icon' types)",
)
async def world_annotate(interaction: discord.Interaction,
                          type_: str,
                          x: float,
                          y: float,
                          color: str = "#EF4444",
                          label: str = None):
    if not await gm_only(interaction):
        return
    if type_ not in ANNOTATION_TYPES:
        await interaction.response.send_message(
            f"Invalid type. Options: {', '.join(ANNOTATION_TYPES)}", ephemeral=True
        )
        return
    x = max(0.0, min(100.0, x))
    y = max(0.0, min(100.0, y))
    # Validate hex color
    if not color.startswith("#") or len(color) not in (4, 7):
        color = "#EF4444"
    async with get_db() as db:
        ann = GuildMapAnnotation(
            guild_id=interaction.guild_id,
            annotation_type=type_,
            x=x,
            y=y,
            color=color,
            label=label,
            created_by=interaction.user.id,
        )
        db.add(ann)
    type_labels = {
        "road_block": "🚧 Road Block",
        "danger_zone": "⚠️ Danger Zone",
        "icon": "📍 Icon",
        "label": "🏷️ Label",
    }
    desc_parts = [f"**Type:** {type_labels.get(type_, type_)}"]
    desc_parts.append(f"**Coords:** ({x:.0f}, {y:.0f})")
    desc_parts.append(f"**Color:** {color}")
    if label:
        desc_parts.append(f"**Label:** {label}")
    embed = discord.Embed(
        title="🗺️ Annotation Added",
        description="\n".join(desc_parts),
        color=0x22C55E,
    )
    embed.set_footer(text=f"Annotation ID: {ann.id}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@world_group.command(name="annotations", description="[GM] List all map overlay annotations")
async def world_annotations(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    async with get_db() as db:
        result = await db.execute(
            select(GuildMapAnnotation).where(
                GuildMapAnnotation.guild_id == interaction.guild_id
            ).order_by(GuildMapAnnotation.created_at.desc())
        )
        anns = list(result.scalars().all())
    if not anns:
        await interaction.response.send_message(
            "No annotations on the world map yet.", ephemeral=True
        )
        return
    lines = []
    type_emoji = {"road_block": "🚧", "danger_zone": "⚠️", "icon": "📍", "label": "🏷️"}
    for a in anns:
        emoji = type_emoji.get(a.annotation_type, "📌")
        coords = f"({a.x:.0f}, {a.y:.0f})"
        label_str = f" — *{a.label}*" if a.label else ""
        lines.append(f"`{a.id:3d}` {emoji} **{a.annotation_type}** @ {coords} {label_str}")
    await interaction.response.send_message(
        f"**Map Annotations ({len(anns)}):**\n" + "\n".join(lines),
        ephemeral=True,
    )


@world_group.command(name="remove-annotation", description="[GM] Remove a map overlay annotation")
@app_commands.describe(annotation_id="ID of the annotation to remove")
async def world_remove_annotation(interaction: discord.Interaction, annotation_id: int):
    if not await gm_only(interaction):
        return
    async with get_db() as db:
        result = await db.execute(
            select(GuildMapAnnotation).where(
                GuildMapAnnotation.id == annotation_id,
                GuildMapAnnotation.guild_id == interaction.guild_id,
            )
        )
        ann = result.scalar_one_or_none()
        if not ann:
            await interaction.response.send_message(
                "Annotation not found.", ephemeral=True
            )
            return
        ann_type = ann.annotation_type
        ann_id = ann.id
        await db.delete(ann)
    await interaction.response.send_message(
        f"🗑️ Removed annotation **{ann_id}** ({ann_type}).", ephemeral=True
    )


# ── Standalone Player Commands ────────────────────────────────────────────

@commands.hybrid_command(name="weather", description="Check the current weather")
async def cmd_weather(ctx):
    """Check the current weather conditions."""
    if not ctx.guild:
        return
    await ctx.defer()
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
    await ctx.defer()
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
    await ctx.defer()
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
    await ctx.defer()
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
