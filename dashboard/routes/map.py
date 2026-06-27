"""World map viewer — location pins on a world map image."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from database.models import GuildConfig, Location
from database.session import get_db
from dashboard.auth import require_guild
from dashboard.main import templates

router = APIRouter()


@router.get("/dashboard/map", response_class=HTMLResponse)
async def map_page(request: Request):
    """Show the world map with location pins."""
    session = require_guild(request)
    guild_id = session["guild_id"]
    is_gm = session.get("is_gm", False)

    try:
        async with get_db() as db:
            # Get guild config
            config_result = await db.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild_id)
            )
            guild_config = config_result.scalar_one_or_none()

            # Get locations
            if is_gm:
                # GMs see all locations
                loc_result = await db.execute(
                    select(Location).where(
                        Location.guild_id == guild_id,
                    ).order_by(Location.name)
                )
            else:
                # Players only see non-hidden locations
                loc_result = await db.execute(
                    select(Location).where(
                        Location.guild_id == guild_id,
                        Location.is_hidden == False,
                    ).order_by(Location.name)
                )
            locations = loc_result.scalars().all()

    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "session": session,
                "title": "Cartography Error",
                "message": f"The map could not be loaded: {str(e)}",
                "code": 0,
            },
        )

    world_map_url = guild_config.world_map_url if guild_config else None

    # Build location data for template
    loc_list = []
    for loc in locations:
        danger_color = "green-500"
        if loc.danger_level >= 8:
            danger_color = "red-500"
        elif loc.danger_level >= 5:
            danger_color = "yellow-500"
        elif loc.danger_level >= 3:
            danger_color = "orange-500"

        loc_list.append({
            "id": loc.id,
            "name": loc.name,
            "description": loc.description,
            "short_description": loc.short_description or "",
            "location_type": loc.location_type,
            "biome": loc.biome or "Unknown",
            "danger_level": loc.danger_level,
            "danger_color": danger_color,
            "is_safe": loc.is_safe,
            "is_hidden": loc.is_hidden,
            "map_x": loc.map_x,
            "map_y": loc.map_y,
        })

    return templates.TemplateResponse(
        "map.html",
        {
            "request": request,
            "session": session,
            "world_map_url": world_map_url,
            "world_name": guild_config.world_name if guild_config else "LoreForge World",
            "locations": loc_list,
            "is_gm": is_gm,
        },
    )
