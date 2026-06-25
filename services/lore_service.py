from sqlalchemy import select, or_
from database.session import get_db
from database.models import LoreEntry


async def lore_search(guild_id: int, query: str, user_is_gm: bool = False, limit: int = 5) -> list[dict]:
    """
    Search lore entries using ILIKE fallback.
    Returns list of dicts with title, content excerpt, category, relevance.
    """
    async with get_db() as db:
        stmt = select(LoreEntry).where(LoreEntry.guild_id == guild_id)

        if not user_is_gm:
            stmt = stmt.where(LoreEntry.visibility == "public")

        result = await db.execute(stmt)
        entries = list(result.scalars().all())

    query_lower = query.lower()
    scored = []

    for entry in entries:
        score = 0
        # Exact title match
        if query_lower == entry.title.lower():
            score += 10
        # Title contains query
        elif query_lower in entry.title.lower():
            score += 5
        # Content contains query
        if query_lower in (entry.content or "").lower():
            score += 3
        # Tag match
        for tag in (entry.tags or []):
            if isinstance(tag, str) and query_lower in tag.lower():
                score += 4

        # Add importance boost
        score += (entry.importance or 5) * 0.05

        if score > 0:
            excerpt = entry.content[:200] + "..." if len(entry.content or "") > 200 else (entry.content or "")
            scored.append({
                "id": entry.id,
                "title": entry.title,
                "content_excerpt": excerpt,
                "category": entry.category,
                "relevance": min(100, int(score * 10)),
                "is_rumor": entry.is_rumor,
                "image_url": entry.image_url,
                "visibility": entry.visibility,
            })

    scored.sort(key=lambda x: x["relevance"], reverse=True)
    return scored[:limit]


async def lore_search_iliberal(guild_id: int, query: str, limit: int = 5) -> list[dict]:
    """Fallback search using SQL ILIKE if ChromaDB is unavailable."""
    return await lore_search(guild_id, query, limit=limit)


async def add_lore_entry(guild_id: int, title: str, content: str, category: str = "lore",
                         tags: list = None, is_canon: bool = True, is_rumor: bool = False,
                         visibility: str = "public", importance: int = 5,
                         image_url: str = None, created_by: int = 0) -> int:
    """Add a lore entry to the database."""
    import json
    async with get_db() as db:
        entry = LoreEntry(
            guild_id=guild_id,
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            is_canon=is_canon,
            is_rumor=is_rumor,
            visibility=visibility,
            importance=importance,
            image_url=image_url,
            created_by=created_by,
        )
        db.add(entry)
        await db.flush()
        entry_id = entry.id

    return entry_id


async def edit_lore_entry(entry_id: int, guild_id: int, **kwargs) -> bool:
    """Edit a lore entry. Only provided fields are updated."""
    from datetime import datetime
    allowed_fields = {
        "title", "content", "category", "tags", "is_canon",
        "is_rumor", "visibility", "importance", "image_url",
    }

    async with get_db() as db:
        result = await db.execute(
            select(LoreEntry).where(LoreEntry.id == entry_id, LoreEntry.guild_id == guild_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return False

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(entry, key, value)
        entry.updated_at = datetime.utcnow()

    return True


async def delete_lore_entry(entry_id: int, guild_id: int) -> bool:
    """Delete a lore entry."""
    async with get_db() as db:
        result = await db.execute(
            select(LoreEntry).where(LoreEntry.id == entry_id, LoreEntry.guild_id == guild_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return False
        await db.delete(entry)
    return True


async def get_lore_entry(entry_id: int, guild_id: int) -> dict | None:
    """Get a single lore entry by ID."""
    async with get_db() as db:
        result = await db.execute(
            select(LoreEntry).where(LoreEntry.id == entry_id, LoreEntry.guild_id == guild_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None
        return {
            "id": entry.id,
            "title": entry.title,
            "content": entry.content,
            "category": entry.category,
            "tags": entry.tags or [],
            "is_canon": entry.is_canon,
            "is_rumor": entry.is_rumor,
            "visibility": entry.visibility,
            "importance": entry.importance,
            "image_url": entry.image_url,
            "created_by": entry.created_by,
        }


async def list_lore_entries(guild_id: int, category: str = None, page: int = 0, per_page: int = 10) -> list[dict]:
    """List lore entries for a guild, with optional category filter."""
    async with get_db() as db:
        stmt = select(LoreEntry).where(LoreEntry.guild_id == guild_id)
        if category:
            stmt = stmt.where(LoreEntry.category == category)
        stmt = stmt.order_by(LoreEntry.importance.desc()).offset(page * per_page).limit(per_page)

        result = await db.execute(stmt)
        entries = list(result.scalars().all())

    return [
        {
            "id": e.id,
            "title": e.title,
            "category": e.category,
            "is_rumor": e.is_rumor,
            "importance": e.importance,
        }
        for e in entries
    ]


async def get_random_lore_entry(guild_id: int) -> dict | None:
    """Get a random lore entry."""
    import random
    async with get_db() as db:
        result = await db.execute(
            select(LoreEntry).where(LoreEntry.guild_id == guild_id)
        )
        entries = list(result.scalars().all())
        if not entries:
            return None
        entry = random.choice(entries)
        return {
            "id": entry.id,
            "title": entry.title,
            "content": entry.content,
            "category": entry.category,
        }
