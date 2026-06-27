"""Session log viewer — past sessions and world events timeline."""

import math
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func

from database.models import SessionLog, WorldEvent
from database.session import get_db
from dashboard.auth import require_guild
from dashboard.main import templates

router = APIRouter()

PAGE_SIZE = 10


@router.get("/dashboard/sessions", response_class=HTMLResponse)
async def sessions_page(
    request: Request,
    page: int = Query(1, ge=1),
):
    """Show session logs and world events timeline."""
    session = require_guild(request)
    guild_id = session["guild_id"]

    try:
        async with get_db() as db:
            # ── Session logs ───────────────────────────────────────────
            count_result = await db.execute(
                select(func.count(SessionLog.id)).where(SessionLog.guild_id == guild_id)
            )
            total = count_result.scalar() or 0
            total_pages = max(1, math.ceil(total / PAGE_SIZE))
            if page > total_pages:
                page = total_pages

            offset = (page - 1) * PAGE_SIZE
            sessions_result = await db.execute(
                select(SessionLog)
                .where(SessionLog.guild_id == guild_id)
                .order_by(SessionLog.started_at.desc())
                .offset(offset)
                .limit(PAGE_SIZE)
            )
            session_logs = sessions_result.scalars().all()

            # ── World events ────────────────────────────────────────────
            events_result = await db.execute(
                select(WorldEvent)
                .where(WorldEvent.guild_id == guild_id)
                .order_by(WorldEvent.created_at.desc())
                .limit(50)
            )
            world_events = events_result.scalars().all()

    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "session": session,
                "title": "Chronicles Error",
                "message": f"The chronicles could not be read: {str(e)}",
                "code": 0,
            },
        )

    # Build session data
    session_list = []
    for s in session_logs:
        duration = ""
        if s.started_at and s.ended_at:
            delta = s.ended_at - s.started_at
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            if hours > 0:
                duration = f"{hours}h {minutes}m"
            else:
                duration = f"{minutes}m"

        session_list.append({
            "id": s.id,
            "title": s.title or "Untitled Session",
            "started_at": s.started_at.strftime("%b %d, %Y · %I:%M %p") if s.started_at else "Unknown",
            "duration": duration,
            "characters_present": s.characters_present or [],
            "combat_count": s.combat_count or 0,
            "total_xp": s.total_xp or 0,
            "summary_text": s.summary_text or "",
            "quest_completions": s.quest_completions or 0,
        })

    # Build event data
    event_list = []
    for ev in world_events:
        event_list.append({
            "id": ev.id,
            "event_type": ev.event_type.replace("_", " ").title(),
            "narrative": ev.narrative or "",
            "importance": ev.importance or 5,
            "created_at": ev.created_at.strftime("%b %d, %Y · %I:%M %p") if ev.created_at else "Unknown",
        })

    return templates.TemplateResponse(
        "sessions.html",
        {
            "request": request,
            "session": session,
            "sessions": session_list,
            "events": event_list,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )
