"""Character manager route — view all characters for a guild."""

import math
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func

from database.models import Character, GuildConfig
from database.session import get_db
from dashboard.auth import require_guild
from dashboard.main import templates

router = APIRouter()

PAGE_SIZE = 20


def calc_modifier(score: int) -> str:
    """Calculate ability modifier string like '+3' or '-1'."""
    mod = math.floor((score - 10) / 2)
    if mod >= 0:
        return f"+{mod}"
    return str(mod)


def calc_mod_value(score: int) -> int:
    """Calculate ability modifier as integer."""
    return math.floor((score - 10) / 2)


def get_hp_bar_color(pct: float) -> str:
    """Return a Tailwind color class for the HP bar."""
    if pct > 50:
        return "bg-green-500"
    elif pct > 25:
        return "bg-yellow-500"
    else:
        return "bg-red-500"


@router.get("/dashboard/characters", response_class=HTMLResponse)
async def characters_page(
    request: Request,
    page: int = Query(1, ge=1),
    search: str = Query("", max_length=100),
):
    """List characters for the selected guild."""
    session = require_guild(request)
    guild_id = session["guild_id"]
    user_id = session["user_id"]
    is_gm = session.get("is_gm", False)

    try:
        async with get_db() as db:
            guild_config = await db.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild_id)
            )
            guild_config = guild_config.scalar_one_or_none()

            world_name = guild_config.world_name if guild_config else "LoreForge World"

            # Build query
            if is_gm:
                # GMs see all characters
                base_query = select(Character).where(Character.guild_id == guild_id)
                count_query = select(func.count(Character.id)).where(Character.guild_id == guild_id)
                if search:
                    search_pattern = f"%{search}%"
                    base_query = base_query.where(Character.name.ilike(search_pattern))
                    count_query = count_query.where(Character.name.ilike(search_pattern))
            else:
                # Players only see their own characters
                base_query = select(Character).where(
                    Character.guild_id == guild_id,
                    Character.user_id == user_id,
                )
                count_query = select(func.count(Character.id)).where(
                    Character.guild_id == guild_id,
                    Character.user_id == user_id,
                )
                if search:
                    search_pattern = f"%{search}%"
                    base_query = base_query.where(Character.name.ilike(search_pattern))
                    count_query = count_query.where(Character.name.ilike(search_pattern))

            # Get total count
            total_result = await db.execute(count_query)
            total = total_result.scalar() or 0
            total_pages = max(1, math.ceil(total / PAGE_SIZE))
            if page > total_pages:
                page = total_pages

            # Get page of results
            offset = (page - 1) * PAGE_SIZE
            base_query = base_query.order_by(Character.level.desc(), Character.name).offset(offset).limit(PAGE_SIZE)
            result = await db.execute(base_query)
            characters = result.scalars().all()

    except Exception as e:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "session": session,
                "title": "Database Error",
                "message": f"Could not load characters: {str(e)}",
                "code": 0,
            },
        )

    # Build character data for template
    char_list = []
    for c in characters:
        avatar = c.avatar_url or "https://cdn.discordapp.com/embed/avatars/0.png"
        hp_pct = min(round((c.hp_current / max(c.hp_max, 1)) * 100, 1), 100.0)
        max_xp_for_level = c.level * 100  # simplified XP threshold display
        xp_pct = min(round((c.xp / max(max_xp_for_level, 1)) * 100, 1), 100.0)

        conditions = c.conditions if isinstance(c.conditions, list) else []
        skills = c.skill_proficiencies if isinstance(c.skill_proficiencies, list) else []
        languages = c.languages if isinstance(c.languages, list) else []
        relationships = c.relationships if isinstance(c.relationships, list) else []

        char_list.append({
            "id": c.id,
            "name": c.name,
            "race": c.race,
            "char_class": c.char_class,
            "level": c.level,
            "xp": c.xp,
            "hp_current": c.hp_current,
            "hp_max": c.hp_max,
            "hp_temp": c.hp_temp or 0,
            "hp_pct": hp_pct,
            "hp_bar_color": get_hp_bar_color(hp_pct),
            "armor_class": c.armor_class,
            "is_dead": c.is_dead,
            "is_unconscious": c.is_unconscious,
            "is_active": c.is_active,
            "death_saves_success": c.death_saves_success or 0,
            "death_saves_failure": c.death_saves_failure or 0,
            "avatar_url": avatar,
            "strength": c.strength,
            "dexterity": c.dexterity,
            "constitution": c.constitution,
            "intelligence": c.intelligence,
            "wisdom": c.wisdom,
            "charisma": c.charisma,
            "str_mod": calc_modifier(c.strength),
            "dex_mod": calc_modifier(c.dexterity),
            "con_mod": calc_modifier(c.constitution),
            "int_mod": calc_modifier(c.intelligence),
            "wis_mod": calc_modifier(c.wisdom),
            "cha_mod": calc_modifier(c.charisma),
            "background": c.background or "Unknown",
            "backstory": c.backstory or "",
            "inventory": c.inventory if isinstance(c.inventory, list) else [],
            "conditions": conditions,
            "skill_proficiencies": skills,
            "languages": languages,
            "relationships": relationships,
            "religion": c.religion or "",
            "age": c.age or 0,
            "lifespan": c.lifespan or 80,
            "gold": c.gold,
            "balance": c.balance,
            "xp_pct": xp_pct,
            "proxy_open": c.proxy_open or "",
            "proxy_close": c.proxy_close or "",
            "proxy_count": c.proxy_count or 0,
            "ki_points": c.ki_points or 0,
            "ki_max": c.ki_max or 0,
            "bardic_inspiration_dice": c.bardic_inspiration_dice or 0,
            "wild_shape_active": c.wild_shape_active,
            "wild_shape_form": c.wild_shape_form or "",
            "is_owner": str(c.user_id) == str(user_id),
        })

    return templates.TemplateResponse(
        request,
        "characters.html",
        {
            "session": session,
            "world_name": world_name,
            "characters": char_list,
            "is_gm": is_gm,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "search": search,
        },
    )
