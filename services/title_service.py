from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database.models import Title, CharacterTitle, Character

TIER_META = {
    "common":    {"color": 0x95A5A6, "icon": "·",  "label": "Common"},
    "rare":      {"color": 0x5865F2, "icon": "✦",  "label": "Rare"},
    "epic":      {"color": 0x9B59B6, "icon": "⬡",  "label": "Epic"},
    "legendary": {"color": 0xF1C40F, "icon": "👑", "label": "Legendary"},
    "mythic":    {"color": 0xE74C3C, "icon": "🔥", "label": "Mythic"},
}

async def create_title(db: AsyncSession, guild_id: str, name: str, tier: str,
                       description: str | None, is_unique: bool, created_by: str) -> Title:
    """Create a new title for the guild. Raises ValueError if name already exists."""
    existing = await db.scalar(select(Title).where(Title.guild_id == guild_id, Title.name == name))
    if existing:
        raise ValueError(f"Title '{name}' already exists in this server.")
    title = Title(guild_id=guild_id, name=name, tier=tier, description=description,
                  is_unique=is_unique, created_by=created_by)
    db.add(title)
    await db.commit()
    await db.refresh(title)
    return title

async def award_title(db: AsyncSession, character_id: int, title_id: int, awarded_by: str) -> CharacterTitle:
    """Award a title to a character. If title is_unique, revoke from previous holder first."""
    title = await db.get(Title, title_id)
    if not title:
        raise ValueError("Title not found.")
    # If unique, revoke from previous holder
    if title.is_unique:
        prev = await db.scalar(select(CharacterTitle).where(CharacterTitle.title_id == title_id))
        if prev:
            await db.delete(prev)
    # Check if already has this title
    existing = await db.scalar(select(CharacterTitle).where(
        CharacterTitle.character_id == character_id,
        CharacterTitle.title_id == title_id
    ))
    if existing:
        return existing
    ct = CharacterTitle(character_id=character_id, title_id=title_id, awarded_by=awarded_by)
    db.add(ct)
    await db.commit()
    await db.refresh(ct)
    return ct

async def revoke_title(db: AsyncSession, character_id: int, title_id: int) -> bool:
    """Remove a title from a character. Returns True if removed."""
    ct = await db.scalar(select(CharacterTitle).where(
        CharacterTitle.character_id == character_id,
        CharacterTitle.title_id == title_id
    ))
    if not ct:
        return False
    await db.delete(ct)
    await db.commit()
    return True

async def set_active_title(db: AsyncSession, character_id: int, title_id: int | None) -> bool:
    """Set which title is displayed. Pass title_id=None to clear active title."""
    # Deactivate all
    all_titles = (await db.scalars(select(CharacterTitle).where(
        CharacterTitle.character_id == character_id
    ))).all()
    for ct in all_titles:
        ct.is_active = False
    if title_id is not None:
        target = await db.scalar(select(CharacterTitle).where(
            CharacterTitle.character_id == character_id,
            CharacterTitle.title_id == title_id
        ))
        if not target:
            await db.rollback()
            raise ValueError("You don't have this title.")
        target.is_active = True
    await db.commit()
    return True

async def get_active_title(db: AsyncSession, character_id: int) -> tuple[str, int] | None:
    """Returns (display_string, color_int) for the active title, or None if no active title.
    display_string example: '👑 The Undying'
    """
    ct = await db.scalar(select(CharacterTitle).where(
        CharacterTitle.character_id == character_id,
        CharacterTitle.is_active == True
    ))
    if not ct:
        return None
    title = await db.get(Title, ct.title_id)
    if not title:
        return None
    meta = TIER_META.get(title.tier, TIER_META["common"])
    display = f"{meta['icon']} {title.name}"
    return display, meta["color"]

async def get_character_titles(db: AsyncSession, character_id: int) -> list[dict]:
    """Return all titles a character holds with metadata."""
    rows = (await db.scalars(select(CharacterTitle).where(
        CharacterTitle.character_id == character_id
    ))).all()
    result = []
    for ct in rows:
        title = await db.get(Title, ct.title_id)
        if title:
            meta = TIER_META.get(title.tier, TIER_META["common"])
            result.append({
                "id": title.id,
                "name": title.name,
                "tier": title.tier,
                "icon": meta["icon"],
                "display": f"{meta['icon']} {title.name}",
                "color": meta["color"],
                "description": title.description,
                "is_active": ct.is_active,
            })
    return result

async def list_guild_titles(db: AsyncSession, guild_id: str) -> list[Title]:
    """Return all titles defined in this guild."""
    return list((await db.scalars(
        select(Title).where(Title.guild_id == guild_id).order_by(Title.tier, Title.name)
    )).all())
