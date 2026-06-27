"""Bestiary browser — boss templates and NPCs."""

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, or_

from database.models import BossTemplate, NPC, Location
from database.session import get_db
from dashboard.auth import require_guild
from dashboard.main import templates

router = APIRouter()


@router.get("/dashboard/bestiary", response_class=HTMLResponse)
async def bestiary_page(
    request: Request,
    search: str = Query("", max_length=100),
):
    """Browse boss templates and NPCs for the guild."""
    session = require_guild(request)
    guild_id = session["guild_id"]

    try:
        async with get_db() as db:
            # ── Boss Templates ──────────────────────────────────────────
            boss_query = select(BossTemplate).where(BossTemplate.guild_id == guild_id)
            if search:
                search_pattern = f"%{search}%"
                boss_query = boss_query.where(BossTemplate.name.ilike(search_pattern))
            boss_result = await db.execute(boss_query.order_by(BossTemplate.name))
            bosses = boss_result.scalars().all()

            # ── NPCs ────────────────────────────────────────────────────
            npc_query = select(NPC).where(NPC.guild_id == guild_id)
            if search:
                search_pattern = f"%{search}%"
                npc_query = npc_query.where(
                    or_(NPC.name.ilike(search_pattern), NPC.race.ilike(search_pattern))
                )
            npc_result = await db.execute(npc_query.order_by(NPC.name))
            npcs = npc_result.scalars().all()

            # Get location names for NPCs
            location_ids = {n.location_id for n in npcs if n.location_id}
            locations = {}
            if location_ids:
                loc_result = await db.execute(
                    select(Location).where(Location.id.in_(location_ids))
                )
                for loc in loc_result.scalars().all():
                    locations[loc.id] = loc.name

    except Exception as e:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "session": session,
                "title": "Bestiary Error",
                "message": f"The bestiary could not be opened: {str(e)}",
                "code": 0,
            },
        )

    # Build boss data
    boss_list = []
    for b in bosses:
        boss_list.append({
            "id": b.id,
            "name": b.name,
            "title": b.title or "",
            "description": b.description or "",
            "hp_max": b.hp_max,
            "armor_class": b.armor_class,
            "xp_value": b.xp_value,
            "phase_count": b.phase_count or 1,
            "phase_abilities": b.phase_abilities or {},
            "attack_bonus": b.attack_bonus,
            "damage_dice": b.damage_dice,
            "damage_bonus": b.damage_bonus,
            "gold_drop": b.gold_drop or 0,
            "is_lair_boss": b.is_lair_boss,
            "lair_actions": b.lair_actions or [],
            "legendary_actions": b.legendary_actions or [],
        })

    # Build NPC data
    npc_list = []
    for n in npcs:
        hp_pct = min(round((n.hp_current / max(n.hp_max, 1)) * 100, 1), 100.0)
        npc_list.append({
            "id": n.id,
            "name": n.name,
            "title": n.title or "",
            "race": n.race or "Unknown",
            "location_name": locations.get(n.location_id, "Unknown"),
            "disposition": n.disposition or "neutral",
            "is_hostile": n.is_hostile,
            "is_dead": n.is_dead,
            "hp_current": n.hp_current,
            "hp_max": n.hp_max,
            "hp_pct": hp_pct,
            "armor_class": n.armor_class,
            "attack_bonus": n.attack_bonus,
            "damage_dice": n.damage_dice,
            "xp_value": n.xp_value or 0,
            "description": n.description or "",
            "appearance": n.appearance or "",
        })

    return templates.TemplateResponse(
        request,
        "bestiary.html",
        {
            "session": session,
            "bosses": boss_list,
            "npcs": npc_list,
            "search": search,
        },
    )
