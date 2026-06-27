"""
Bestiary — catalog of NPCs and BossTemplates for a guild.
/bestiary list, /bestiary view, /bestiary search
"""

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, or_
from database.session import get_db
from database.models import NPC, BossTemplate


async def _bestiary_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete across both NPC and BossTemplate names."""
    async with get_db() as db:
        npcs = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(f"%{current}%"),
            ).limit(12)
        )
        bosses = await db.execute(
            select(BossTemplate).where(
                BossTemplate.guild_id == interaction.guild_id,
                BossTemplate.name.ilike(f"%{current}%"),
            ).limit(12)
        )
    choices = []
    for n in npcs.scalars().all():
        choices.append(app_commands.Choice(name=f"👤 {n.name} (NPC)", value=f"npc:{n.id}"))
    for b in bosses.scalars().all():
        choices.append(app_commands.Choice(name=f"⚔️ {b.name} (Boss)", value=f"boss:{b.id}"))
    return choices[:25]


bestiary_group = app_commands.Group(name="bestiary", description="Browse creatures and bosses in the world")


@bestiary_group.command(name="list", description="List all known creatures")
@app_commands.describe(
    creature_type="Filter by type: npc, boss, or all (default)",
    page="Page number (default 1)",
)
@app_commands.choices(creature_type=[
    app_commands.Choice(name="All", value="all"),
    app_commands.Choice(name="NPCs", value="npc"),
    app_commands.Choice(name="Bosses", value="boss"),
])
async def bestiary_list(interaction: discord.Interaction, creature_type: str = "all", page: int = 1):
    await interaction.response.defer()

    async with get_db() as db:
        if creature_type in ("all", "npc"):
            npc_query = select(NPC).where(NPC.guild_id == interaction.guild_id)
            if creature_type == "npc":
                npc_query = npc_query.where(NPC.is_dead == False)
            npcs = (await db.execute(npc_query.order_by(NPC.name).limit(50))).scalars().all()
        else:
            npcs = []

        if creature_type in ("all", "boss"):
            bosses = (await db.execute(
                select(BossTemplate).where(
                    BossTemplate.guild_id == interaction.guild_id
                ).order_by(BossTemplate.name).limit(50)
            )).scalars().all()
        else:
            bosses = []

    # Paginate manually
    all_entries = []
    for n in npcs:
        loc_str = f" (Location: {n.location_id})" if n.location_id else ""
        hostile = " ⚔️ Hostile" if n.is_hostile else ""
        all_entries.append(f"👤 **{n.name}**{hostile} — HP:{n.hp_max} AC:{n.armor_class}{loc_str}")
    for b in bosses:
        all_entries.append(f"⚔️ **{b.name}** — HP:{b.hp_max} AC:{b.armor_class} XP:{b.xp_value} ({b.phase_count} phase{'s' if (b.phase_count or 1) > 1 else ''})")

    if not all_entries:
        await interaction.followup.send("No entries found in the bestiary yet.", ephemeral=True)
        return

    per_page = 10
    total_pages = max(1, (len(all_entries) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    chunk = all_entries[start:start + per_page]

    embed = discord.Embed(
        title=f"📖 Bestiary — {creature_type.title()}",
        description="\n".join(chunk),
        color=0x6366F1,
    )
    embed.set_footer(text=f"Page {page}/{total_pages} · {len(all_entries)} entries · Use /bestiary view <name> for details")
    await interaction.followup.send(embed=embed)


@bestiary_group.command(name="view", description="View detailed information about a creature")
@app_commands.describe(name="Name of the creature or boss")
@app_commands.autocomplete(name=_bestiary_autocomplete)
async def bestiary_view(interaction: discord.Interaction, name: str):
    await interaction.response.defer()

    # Parse prefixed value from autocomplete (npc:123 or boss:123)
    entity_type = "npc"
    entity_id = None
    if name.startswith("npc:") or name.startswith("boss:"):
        parts = name.split(":", 1)
        entity_type = parts[0]
        entity_id = int(parts[1])

    async with get_db() as db:
        if entity_id:
            if entity_type == "boss":
                result = await db.execute(select(BossTemplate).where(BossTemplate.id == entity_id))
                boss = result.scalar_one_or_none()
                if boss:
                    embed = _build_boss_embed(boss)
                    await interaction.followup.send(embed=embed)
                    return
            else:
                result = await db.execute(select(NPC).where(NPC.id == entity_id))
                npc = result.scalar_one_or_none()
                if npc:
                    embed = _build_npc_embed(npc)
                    await interaction.followup.send(embed=embed)
                    return

        # Fallback: search by name
        npc_result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(f"%{name}%"),
            )
        )
        npc = npc_result.scalar_one_or_none()
        if npc:
            embed = _build_npc_embed(npc)
            await interaction.followup.send(embed=embed)
            return

        boss_result = await db.execute(
            select(BossTemplate).where(
                BossTemplate.guild_id == interaction.guild_id,
                BossTemplate.name.ilike(f"%{name}%"),
            )
        )
        boss = boss_result.scalar_one_or_none()
        if boss:
            embed = _build_boss_embed(boss)
            await interaction.followup.send(embed=embed)
            return

    await interaction.followup.send(f"**{name}** not found in the bestiary.", ephemeral=True)


def _build_npc_embed(npc: NPC) -> discord.Embed:
    embed = discord.Embed(
        title=f"👤 {npc.name}",
        description=npc.description[:1000] if npc.description else "*No description*",
        color=0xEF4444 if npc.is_hostile else 0x22C55E,
    )
    if npc.title:
        embed.add_field(name="Title", value=npc.title, inline=True)
    if npc.race:
        embed.add_field(name="Race", value=npc.race, inline=True)
    embed.add_field(name="HP", value=f"{npc.hp_current}/{npc.hp_max}", inline=True)
    embed.add_field(name="AC", value=str(npc.armor_class), inline=True)
    embed.add_field(name="Attack", value=f"+{npc.attack_bonus} ({npc.damage_dice})", inline=True)
    embed.add_field(name="XP Value", value=str(npc.xp_value or 0), inline=True)
    embed.add_field(name="Disposition", value=npc.disposition or "neutral", inline=True)
    embed.add_field(name="Hostile", value="⚠️ Yes" if npc.is_hostile else "No", inline=True)
    if npc.faction_id:
        embed.add_field(name="Faction ID", value=str(npc.faction_id), inline=True)
    if npc.location_id:
        embed.add_field(name="Location ID", value=str(npc.location_id), inline=True)
    if npc.is_dead:
        embed.add_field(name="Status", value="💀 Dead", inline=True)
    if npc.image_url:
        embed.set_image(url=npc.image_url)
    return embed


def _build_boss_embed(boss: BossTemplate) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️ {boss.name}",
        description=boss.description[:1000] if boss.description else "*No description*",
        color=0xEF4444,
    )
    if boss.title:
        embed.add_field(name="Title", value=boss.title, inline=True)
    embed.add_field(name="❤️ HP", value=str(boss.hp_max), inline=True)
    embed.add_field(name="🛡️ AC", value=str(boss.armor_class), inline=True)
    embed.add_field(name="⚔️ Attack", value=f"+{boss.attack_bonus} ({boss.damage_dice})", inline=True)
    embed.add_field(name="✨ XP", value=str(boss.xp_value), inline=True)
    embed.add_field(name="⚡ Phases", value=str(boss.phase_count or 1), inline=True)
    embed.add_field(name="🏰 Lair Boss", value="Yes" if boss.is_lair_boss else "No", inline=True)
    embed.add_field(name="⚔️ Legendary Actions", value=str(boss.legendary_action_count), inline=True)

    if boss.phase_abilities:
        ability_lines = []
        for phase_key, abilities in boss.phase_abilities.items():
            for a in abilities:
                ability_lines.append(f"• **{a.get('name', 'Unknown')}** — {a.get('description', '')[:100]}")
        if ability_lines:
            embed.add_field(name="Phase Abilities", value="\n".join(ability_lines[:5]), inline=False)

    if boss.loot_table:
        loot_lines = []
        for item in boss.loot_table[:5]:
            qty = item.get("qty", 1)
            chance = item.get("chance", 1.0)
            loot_lines.append(f"• {item.get('item', 'Unknown')} x{qty} ({round(chance * 100)}%)")
        if loot_lines:
            embed.add_field(name="🎁 Loot", value="\n".join(loot_lines), inline=False)

    if boss.image_url:
        embed.set_image(url=boss.image_url)
    return embed


@bestiary_group.command(name="search", description="Search creatures by name, description, or habitat")
@app_commands.describe(query="Search term")
async def bestiary_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    async with get_db() as db:
        npcs = (await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                or_(
                    NPC.name.ilike(f"%{query}%"),
                    NPC.description.ilike(f"%{query}%"),
                ),
            ).limit(10)
        )).scalars().all()

        bosses = (await db.execute(
            select(BossTemplate).where(
                BossTemplate.guild_id == interaction.guild_id,
                or_(
                    BossTemplate.name.ilike(f"%{query}%"),
                    BossTemplate.description.ilike(f"%{query}%"),
                ),
            ).limit(10)
        )).scalars().all()

    if not npcs and not bosses:
        await interaction.followup.send(f"No creatures match **{query}**.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📖 Bestiary Search: {query}",
        color=0x6366F1,
    )
    if npcs:
        npc_lines = [f"👤 **{n.name}** — {n.description[:80]}..." if len(n.description) > 80 else f"👤 **{n.name}** — {n.description}" for n in npcs]
        embed.add_field(name=f"👥 NPCs ({len(npcs)})", value="\n".join(npc_lines), inline=False)
    if bosses:
        boss_lines = [f"⚔️ **{b.name}** — HP:{b.hp_max} AC:{b.armor_class}" for b in bosses]
        embed.add_field(name=f"⚔️ Bosses ({len(bosses)})", value="\n".join(boss_lines), inline=False)

    await interaction.followup.send(embed=embed)


class BestiaryCog(commands.Cog, name="Bestiary"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(bestiary_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("bestiary")


async def setup(bot):
    await bot.add_cog(BestiaryCog(bot))
