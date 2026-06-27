"""Lore wiki browser — search, filter, view lore entries."""

import math
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, or_

from database.models import LoreEntry
from database.session import get_db
from dashboard.auth import require_guild
from dashboard.main import templates

router = APIRouter()

PAGE_SIZE = 12
CATEGORIES = ["all", "character", "item", "creature", "religion", "event", "history", "other"]


@router.get("/dashboard/lore", response_class=HTMLResponse)
async def lore_page(
    request: Request,
    page: int = Query(1, ge=1),
    search: str = Query("", max_length=200),
    category: str = Query("all", max_length=30),
    entry_id: int = Query(None, ge=1),
):
    """Browse lore entries for the selected guild."""
    session = require_guild(request)
    guild_id = session["guild_id"]
    is_gm = session.get("is_gm", False)

    # Validate category
    if category not in CATEGORIES:
        category = "all"

    try:
        async with get_db() as db:
            # Build query
            if is_gm:
                base_query = select(LoreEntry).where(LoreEntry.guild_id == guild_id)
                count_query = select(func.count(LoreEntry.id)).where(LoreEntry.guild_id == guild_id)
            else:
                # Players only see public entries
                base_query = select(LoreEntry).where(
                    LoreEntry.guild_id == guild_id,
                    LoreEntry.visibility == "public",
                )
                count_query = select(func.count(LoreEntry.id)).where(
                    LoreEntry.guild_id == guild_id,
                    LoreEntry.visibility == "public",
                )

            # Category filter
            if category != "all":
                base_query = base_query.where(LoreEntry.category == category)
                count_query = count_query.where(LoreEntry.category == category)

            # Search filter
            if search:
                search_pattern = f"%{search}%"
                search_filter = or_(
                    LoreEntry.title.ilike(search_pattern),
                    LoreEntry.content.ilike(search_pattern),
                )
                base_query = base_query.where(search_filter)
                count_query = count_query.where(search_filter)

            # Get specific entry if requested
            selected_entry = None
            if entry_id:
                if is_gm:
                    entry_result = await db.execute(
                        select(LoreEntry).where(
                            LoreEntry.id == entry_id,
                            LoreEntry.guild_id == guild_id,
                        )
                    )
                else:
                    entry_result = await db.execute(
                        select(LoreEntry).where(
                            LoreEntry.id == entry_id,
                            LoreEntry.guild_id == guild_id,
                            LoreEntry.visibility == "public",
                        )
                    )
                selected_entry = entry_result.scalar_one_or_none()

            # Get total count
            total_result = await db.execute(count_query)
            total = total_result.scalar() or 0
            total_pages = max(1, math.ceil(total / PAGE_SIZE))
            if page > total_pages:
                page = total_pages

            # Get page of results
            offset = (page - 1) * PAGE_SIZE
            base_query = base_query.order_by(LoreEntry.updated_at.desc()).offset(offset).limit(PAGE_SIZE)
            result = await db.execute(base_query)
            entries = result.scalars().all()

    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "session": session,
                "title": "Library Access Denied",
                "message": f"The archives could not be reached: {str(e)}",
                "code": 0,
            },
        )

    # Build entry data
    entry_list = []
    for e in entries:
        excerpt = (e.content or "")[:200]
        if len(e.content or "") > 200:
            excerpt += "..."
        entry_list.append({
            "id": e.id,
            "title": e.title,
            "category": e.category,
            "excerpt": excerpt,
            "tags": e.tags or [],
            "visible": e.visibility,
            "created_at": e.updated_at.strftime("%b %d, %Y") if e.updated_at else "Unknown",
        })

    # Build selected entry detail
    selected_data = None
    if selected_entry:
        selected_data = {
            "id": selected_entry.id,
            "title": selected_entry.title,
            "content": selected_entry.content or "",
            "category": selected_entry.category,
            "tags": selected_entry.tags or [],
            "visibility": selected_entry.visibility,
            "updated_at": selected_entry.updated_at.strftime("%B %d, %Y") if selected_entry.updated_at else "Unknown",
        }

    return templates.TemplateResponse(
        "lore.html",
        {
            "request": request,
            "session": session,
            "entries": entry_list,
            "selected_entry": selected_data,
            "is_gm": is_gm,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "search": search,
            "category": category,
            "categories": CATEGORIES,
        },
    )
