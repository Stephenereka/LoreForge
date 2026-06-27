"""World map — interactive location explorer with detail panel."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from database.models import GuildConfig, Location, LocationConnection, NPC, CharacterLocation, Character
from database.session import get_db
from dashboard.auth import require_guild
from dashboard.main import templates

router = APIRouter()

DANGER_COLORS = {
    (0, 2): "green",
    (3, 4): "blue",
    (5, 6): "yellow",
    (7, 8): "orange",
    (9, 10): "red",
}

TYPE_ICONS = {
    "city": "🏙️", "dungeon": "☠️", "wilderness": "🌲", "tavern": "🍺",
    "shop": "🛒", "room": "🚪", "landmark": "⭐", "quest_instance": "📜",
    "ruins": "🏚️", "port": "⚓", "mountain": "⛰️", "forest": "🌳",
    "cave": "🕳️", "castle": "🏰", "village": "🏘️", "temple": "⛪",
}

def danger_color(level: int) -> str:
    if level <= 2: return "green"
    if level <= 4: return "blue"
    if level <= 6: return "yellow"
    if level <= 8: return "orange"
    return "red"


@router.get("/dashboard/map", response_class=HTMLResponse)
async def map_page(request: Request):
    session = require_guild(request)
    guild_id = session["guild_id"]
    is_gm = session.get("is_gm", False)

    try:
        async with get_db() as db:
            config_result = await db.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild_id)
            )
            guild_config = config_result.scalar_one_or_none()

            # Locations
            if is_gm:
                loc_result = await db.execute(
                    select(Location).where(Location.guild_id == guild_id).order_by(Location.name)
                )
            else:
                loc_result = await db.execute(
                    select(Location).where(
                        Location.guild_id == guild_id,
                        Location.is_hidden == False,
                        Location.parent_id == None,
                    ).order_by(Location.name)
                )
            locations = loc_result.scalars().all()
            location_ids = [loc.id for loc in locations]

            # Connections for all locations
            connections_result = await db.execute(
                select(LocationConnection).where(
                    LocationConnection.guild_id == guild_id,
                    LocationConnection.from_location_id.in_(location_ids),
                )
            )
            all_connections = connections_result.scalars().all()

            # NPCs per location
            npc_result = await db.execute(
                select(NPC).where(
                    NPC.guild_id == guild_id,
                    NPC.location_id.in_(location_ids),
                    NPC.is_dead == False,
                ).order_by(NPC.name)
            )
            all_npcs = npc_result.scalars().all()
            npcs_by_location: dict[int, list] = {}
            for npc in all_npcs:
                npcs_by_location.setdefault(npc.location_id, []).append({
                    "name": npc.name,
                    "title": npc.title or "",
                    "disposition": npc.disposition or "neutral",
                    "is_hostile": npc.is_hostile,
                })

            # Characters currently at each location (via CharacterLocation)
            char_loc_result = await db.execute(
                select(CharacterLocation, Character.name).join(
                    Character, CharacterLocation.character_id == Character.id
                ).where(
                    CharacterLocation.guild_id == guild_id,
                    CharacterLocation.location_id.in_(location_ids),
                )
            )
            chars_by_location: dict[int, list] = {}
            for row in char_loc_result.all():
                cl, char_name = row
                chars_by_location.setdefault(cl.location_id, []).append(char_name)

            # Build connection map: location_id → list of {direction, name, locked}
            conn_by_location: dict[int, list] = {}
            loc_name_map = {loc.id: loc.name for loc in locations}
            for conn in all_connections:
                if is_gm or not conn.is_secret:
                    conn_by_location.setdefault(conn.from_location_id, []).append({
                        "direction": conn.direction,
                        "to_name": loc_name_map.get(conn.to_location_id, f"Location #{conn.to_location_id}"),
                        "to_id": conn.to_location_id,
                        "is_locked": conn.is_locked,
                        "is_secret": conn.is_secret,
                        "label": conn.label or "",
                    })

    except Exception as e:
        return templates.TemplateResponse(
            request, "error.html",
            {"session": session, "title": "Cartography Error",
             "message": f"The map could not be loaded: {str(e)}", "code": 0},
        )

    world_map_url = guild_config.world_map_url if guild_config else None
    world_name = guild_config.world_name if guild_config else "LoreForge World"

    loc_list = []
    for loc in locations:
        dc = danger_color(loc.danger_level)
        loc_list.append({
            "id": loc.id,
            "name": loc.name,
            "description": loc.description or "",
            "short_description": loc.short_description or "",
            "location_type": loc.location_type,
            "type_icon": TYPE_ICONS.get(loc.location_type, "📍"),
            "biome": (loc.biome or "unknown").replace("_", " ").title(),
            "danger_level": loc.danger_level,
            "danger_color": dc,
            "is_safe": loc.is_safe,
            "is_hidden": loc.is_hidden,
            "is_indoors": loc.is_indoors,
            "map_x": loc.map_x,
            "map_y": loc.map_y,
            "image_url": loc.image_url or "",
            "population_density": (loc.population_density or "sparse").replace("_", " ").title(),
            "lighting": (loc.lighting or "bright").title(),
            "ambient_sounds": loc.ambient_sounds or "",
            "connections": conn_by_location.get(loc.id, []),
            "npcs": npcs_by_location.get(loc.id, []),
            "characters_here": chars_by_location.get(loc.id, []),
            "parent_id": loc.parent_id,
        })

    return templates.TemplateResponse(
        request, "map.html",
        {
            "session": session,
            "world_map_url": world_map_url,
            "world_name": world_name,
            "locations": loc_list,
            "is_gm": is_gm,
        },
    )
