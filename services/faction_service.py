from datetime import datetime
from sqlalchemy import select
from database.session import get_db
from database.models import Faction, FactionReputation, FactionPerk, NPC, Location

# ── Reputation tiers ──────────────────────────────────────────────────────────
REPUTATION_TIERS = {
    "hated": {"min": -3000, "max": -1001, "icon": "🔴", "color": 0xEF4444},
    "hostile": {"min": -1000, "max": -301, "icon": "🟠", "color": 0xF97316},
    "unfriendly": {"min": -300, "max": -1, "icon": "🟡", "color": 0xEAB308},
    "neutral": {"min": 0, "max": 99, "icon": "⚪", "color": 0x9CA3AF},
    "friendly": {"min": 100, "max": 499, "icon": "🟢", "color": 0x22C55E},
    "honored": {"min": 500, "max": 999, "icon": "🔵", "color": 0x3B82F6},
    "revered": {"min": 1000, "max": 1999, "icon": "🟣", "color": 0xA855F7},
    "exalted": {"min": 2000, "max": 99999, "icon": "🟡", "color": 0xEAB308},
}

TIER_ORDER = ["hated", "hostile", "unfriendly", "neutral", "friendly", "honored", "revered", "exalted"]


def get_tier(rep_value: int) -> str:
    """Get the tier name for a reputation value."""
    for tier, info in REPUTATION_TIERS.items():
        if info["min"] <= rep_value <= info["max"]:
            return tier
    return "neutral" if rep_value >= 0 else "hated"


def get_tier_info(tier_name: str) -> dict:
    return REPUTATION_TIERS.get(tier_name, REPUTATION_TIERS["neutral"])


def rep_progress_bar(rep_value: int) -> tuple[str, int, str, str]:
    """Return (current_tier_name, progress_to_next, bar_string, tier_icon)."""
    tier = get_tier(rep_value)
    info = REPUTATION_TIERS.get(tier, REPUTATION_TIERS["neutral"])

    idx = TIER_ORDER.index(tier)
    if idx < len(TIER_ORDER) - 1:
        next_tier = TIER_ORDER[idx + 1]
        next_min = REPUTATION_TIERS[next_tier]["min"]
        current_min = info["min"]
        range_size = next_min - current_min
        progress = rep_value - current_min
        pct = min(1.0, progress / max(1, range_size))
        bar = "█" * int(pct * 10) + "░" * (10 - int(pct * 10))
        return tier, int(pct * 100), bar, info["icon"]
    else:
        return tier, 100, "██████████", info["icon"]


import discord

from services.notifications import notify_player


async def change_reputation(
    character_id: int,
    guild_id: int,
    faction_id: int,
    amount: int,
    reason: str = "",
    bot=None,
    user_id: int = None,
    faction_name: str = "",
) -> dict:
    """Change a character's reputation with a faction. Returns result with tier change info."""
    async with get_db() as db:
        result = await db.execute(
            select(FactionReputation).where(
                FactionReputation.character_id == character_id,
                FactionReputation.faction_id == faction_id,
                FactionReputation.guild_id == guild_id,
            )
        )
        rep_row = result.scalar_one_or_none()

        old_tier = "neutral"
        if not rep_row:
            rep_row = FactionReputation(
                character_id=character_id,
                guild_id=guild_id,
                faction_id=faction_id,
                reputation=amount,
            )
            db.add(rep_row)
            old_tier = get_tier(0)
        else:
            old_tier = get_tier(rep_row.reputation)
            rep_row.reputation += amount
            rep_row.updated_at = datetime.utcnow()

        new_tier = get_tier(rep_row.reputation)
        tier_changed = old_tier != new_tier

    # Notify player on tier change
    if tier_changed and bot and user_id and faction_name:
        tier_info = get_tier_info(new_tier)
        embed = discord.Embed(
            title=f"{tier_info['icon']} Faction Standing Change",
            description=f"Your reputation with **{faction_name}** has changed!",
            color=tier_info["color"],
        )
        embed.add_field(name="Old Standing", value=f"**{old_tier.capitalize()}**", inline=True)
        embed.add_field(name="New Standing", value=f"**{new_tier.capitalize()}**", inline=True)
        embed.add_field(name="Reputation Change", value=f"{amount:+d}", inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        try:
            await notify_player(bot, user_id, guild_id, "faction_changes", embed)
        except Exception:
            pass

    return {
        "new_rep": rep_row.reputation,
        "old_tier": old_tier,
        "new_tier": new_tier,
        "tier_changed": tier_changed,
        "amount": amount,
        "reason": reason,
    }


async def get_faction_perks(character_id: int, guild_id: int, faction_id: int) -> list[dict]:
    """Get all unlocked perks for a character's rep with a faction."""
    async with get_db() as db:
        rep_result = await db.execute(
            select(FactionReputation).where(
                FactionReputation.character_id == character_id,
                FactionReputation.faction_id == faction_id,
            )
        )
        rep = rep_result.scalar_one_or_none()
        if not rep:
            return []

        tier = get_tier(rep.reputation)
        tier_idx = TIER_ORDER.index(tier)

        perks_result = await db.execute(
            select(FactionPerk).where(
                FactionPerk.faction_id == faction_id,
                FactionPerk.guild_id == guild_id,
            )
        )
        all_perks = list(perks_result.scalars().all())

    unlocked = []
    for perk in all_perks:
        perk_tier_idx = TIER_ORDER.index(perk.required_tier) if perk.required_tier in TIER_ORDER else -1
        if perk_tier_idx >= 0 and perk_tier_idx <= tier_idx:
            unlocked.append({
                "perk_type": perk.perk_type,
                "data": perk.perk_data,
                "tier": perk.required_tier,
            })
    return unlocked


async def check_area_access(character_id: int, guild_id: int, location_id: int) -> tuple[bool, str]:
    """Check if a character can access a location based on faction reputation."""
    async with get_db() as db:
        loc_result = await db.execute(
            select(Location).where(Location.id == location_id, Location.guild_id == guild_id)
        )
        location = loc_result.scalar_one_or_none()
        if not location:
            return True, ""

        faction_result = await db.execute(
            select(Faction).where(Faction.guild_id == guild_id, Faction.headquarters_location_id == location_id)
        )
        faction = faction_result.scalar_one_or_none()
        if not faction:
            return True, ""

        rep_result = await db.execute(
            select(FactionReputation).where(
                FactionReputation.character_id == character_id,
                FactionReputation.faction_id == faction.id,
            )
        )
        rep = rep_result.scalar_one_or_none()
        rep_value = rep.reputation if rep else 0
        tier = get_tier(rep_value)

        if tier in ("hated", "hostile"):
            tier_info = get_tier_info(tier)
            return False, f"You are **{tier_info['icon']} {tier.capitalize()}** with **{faction.name}**. They will not let you enter."

        if tier in ("unfriendly",):
            return False, f"You are not welcome here. Your reputation with **{faction.name}** is too low."

        if tier in ("neutral",):
            if location.is_hidden:
                return False, f"You need to be at least **Friendly** with **{faction.name}** to enter this area."

    return True, ""


async def get_character_reps(character_id: int, guild_id: int) -> list[dict]:
    """Get all faction reputations for a character."""
    async with get_db() as db:
        result = await db.execute(
            select(FactionReputation).where(
                FactionReputation.character_id == character_id,
                FactionReputation.guild_id == guild_id,
            )
        )
        reps = list(result.scalars().all())

    factions_result = await db.execute(
        select(Faction).where(Faction.guild_id == guild_id)
    )
    factions = {f.id: f for f in list(factions_result.scalars().all())}

    results = []
    for rep in reps:
        faction = factions.get(rep.faction_id)
        if faction:
            tier = get_tier(rep.reputation)
            info = get_tier_info(tier)
            results.append({
                "faction_id": rep.faction_id,
                "faction_name": faction.name,
                "faction_icon": faction.icon_emoji or "",
                "reputation": rep.reputation,
                "tier": tier,
                "tier_icon": info["icon"],
            })
    return results
