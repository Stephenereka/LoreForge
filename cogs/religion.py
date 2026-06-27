import discord
import random
import json
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from database.session import get_db
from database.models import Religion, Character, Faction
from services.utils import is_gm


religion_group = app_commands.Group(
    name="religion", description="Religion and pantheon system"
)


async def _autocomplete_religion(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if not interaction.guild_id:
        return []
    async with get_db() as db:
        result = await db.execute(
            select(Religion).where(
                Religion.guild_id == interaction.guild_id,
                Religion.name.ilike(f"%{current}%"),
            )
        )
        rels = result.scalars().all()
    return [app_commands.Choice(name=r.name[:80], value=r.name) for r in rels[:25]]


@religion_group.command(name="create", description="GM only: Create a new religion")
@app_commands.describe(name="Religion name", deity_name="Name of the deity (optional)", domains="Comma-separated domains (optional)")
async def religion_create(interaction: discord.Interaction, name: str, deity_name: str = None, domains: str = None):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if not await is_gm(interaction):
        await interaction.followup.send("Only GMs can create religions.", ephemeral=True)
        return

    domains_list = [d.strip() for d in domains.split(",") if d.strip()] if domains else []

    async with get_db() as db:
        existing = await db.execute(
            select(Religion).where(
                Religion.guild_id == interaction.guild_id,
                Religion.name.ilike(name),
            )
        )
        if existing.scalar_one_or_none():
            await interaction.followup.send(f"Religion '{name}' already exists.", ephemeral=True)
            return

        rel = Religion(
            guild_id=interaction.guild_id,
            name=name,
            deity_name=deity_name,
            domains=domains_list,
        )
        db.add(rel)
        await db.commit()

    await interaction.followup.send(f"⛪ Created religion: **{name}**", ephemeral=True)


@religion_group.command(name="list", description="List all religions in the world")
async def religion_list(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer()

    async with get_db() as db:
        result = await db.execute(
            select(Religion).where(Religion.guild_id == interaction.guild_id).order_by(Religion.name)
        )
        rels = list(result.scalars().all())

    if not rels:
        await interaction.followup.send("No religions have been established in this world yet.")
        return

    embed = discord.Embed(title="⛪ Religions of the World", color=0x8B5CF6)
    for rel in rels:
        domains_str = ", ".join(rel.domains or []) or "None"
        embed.add_field(
            name=rel.name,
            value=f"Deity: {rel.deity_name or 'Unknown'}\nDomains: {domains_str}",
            inline=True,
        )

    await interaction.followup.send(embed=embed)


@religion_group.command(name="view", description="View details of a religion")
@app_commands.describe(name="Religion name")
@app_commands.autocomplete(name=_autocomplete_religion)
async def religion_view(interaction: discord.Interaction, name: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer()

    async with get_db() as db:
        result = await db.execute(
            select(Religion).where(
                Religion.guild_id == interaction.guild_id,
                Religion.name.ilike(name),
            )
        )
        rel = result.scalar_one_or_none()

    if not rel:
        await interaction.followup.send(f"Religion '{name}' not found.", ephemeral=True)
        return

    embed = discord.Embed(title=f"⛪ {rel.name}", color=0x8B5CF6)
    embed.add_field(name="Deity", value=rel.deity_name or "Unknown", inline=True)
    embed.add_field(name="Domains", value=", ".join(rel.domains or []) or "None", inline=True)

    if rel.holy_symbol:
        embed.add_field(name="Holy Symbol", value=rel.holy_symbol, inline=False)
    if rel.tenets:
        tenets_text = "\n".join(f"• {t}" for t in rel.tenets[:5])
        embed.add_field(name="Tenets", value=tenets_text, inline=False)
    if rel.clergy_notes:
        embed.add_field(name="Clergy Notes", value=rel.clergy_notes[:500], inline=False)

    # Show associated faction if any
    if rel.associated_faction_id:
        async with get_db() as db:
            fac_result = await db.execute(
                select(Faction).where(Faction.id == rel.associated_faction_id)
            )
            faction = fac_result.scalar_one_or_none()
            if faction:
                embed.add_field(name="Associated Faction", value=faction.name, inline=True)

    # Show followers count
    async with get_db() as db:
        follower_result = await db.execute(
            select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.religion == rel.name,
            )
        )
        followers = list(follower_result.scalars().all())
        if followers:
            embed.add_field(
                name="Followers",
                value=", ".join(c.name for c in followers[:5]) + (f" *+{len(followers)-5} more*" if len(followers) > 5 else ""),
                inline=False,
            )

    await interaction.followup.send(embed=embed)


@religion_group.command(name="edit", description="GM only: Edit a religion")
@app_commands.describe(name="Religion name")
@app_commands.autocomplete(name=_autocomplete_religion)
async def religion_edit(interaction: discord.Interaction, name: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can edit religions.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Religion).where(
                Religion.guild_id == interaction.guild_id,
                Religion.name.ilike(name),
            )
        )
        rel = result.scalar_one_or_none()
        if not rel:
            await interaction.response.send_message("Religion not found.", ephemeral=True)
            return

    class ReligionEditModal(discord.ui.Modal, title=f"Edit: {name[:45]}"):
        description = discord.ui.TextInput(label="Description / Clergy Notes", style=discord.TextStyle.long, required=False)
        holy_symbol = discord.ui.TextInput(label="Holy Symbol", required=False, max_length=500)

        def __init__(self, existing_clergy: str, existing_symbol: str):
            super().__init__()
            self.description.default = existing_clergy or ""
            self.holy_symbol.default = existing_symbol or ""

        async def on_submit(self, modal_interaction: discord.Interaction):
            async with get_db() as db:
                result = await db.execute(
                    select(Religion).where(
                        Religion.guild_id == modal_interaction.guild_id,
                        Religion.name.ilike(name),
                    )
                )
                r = result.scalar_one_or_none()
                if r:
                    r.clergy_notes = self.description.value or None
                    r.holy_symbol = self.holy_symbol.value or None
                    await db.commit()
            await modal_interaction.response.send_message(f"✅ **{name}** updated.", ephemeral=True)

    await interaction.response.send_modal(ReligionEditModal(rel.clergy_notes, rel.holy_symbol))


@religion_group.command(name="set-deity", description="GM only: Set the deity name for a religion")
@app_commands.describe(religion_name="Religion name", deity_name="Name of the deity")
@app_commands.autocomplete(religion_name=_autocomplete_religion)
async def religion_set_deity(interaction: discord.Interaction, religion_name: str, deity_name: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if not await is_gm(interaction):
        await interaction.followup.send("Only GMs can set deities.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Religion).where(
                Religion.guild_id == interaction.guild_id,
                Religion.name.ilike(religion_name),
            )
        )
        rel = result.scalar_one_or_none()
        if not rel:
            await interaction.followup.send("Religion not found.", ephemeral=True)
            return
        rel.deity_name = deity_name
        await db.commit()

    await interaction.followup.send(f"⭐ **{rel.name}** now worships **{deity_name}**!", ephemeral=True)


@religion_group.command(name="add-tenet", description="GM only: Add a tenet to a religion")
@app_commands.describe(religion_name="Religion name", tenet="The tenet to add")
@app_commands.autocomplete(religion_name=_autocomplete_religion)
async def religion_add_tenet(interaction: discord.Interaction, religion_name: str, tenet: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if not await is_gm(interaction):
        await interaction.followup.send("Only GMs can add tenets.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Religion).where(
                Religion.guild_id == interaction.guild_id,
                Religion.name.ilike(religion_name),
            )
        )
        rel = result.scalar_one_or_none()
        if not rel:
            await interaction.followup.send("Religion not found.", ephemeral=True)
            return
        tenets = list(rel.tenets or [])
        tenets.append(tenet)
        rel.tenets = tenets
        flag_modified(rel, "tenets")
        await db.commit()

    await interaction.followup.send(f"📜 Added tenet to **{rel.name}**: _{tenet}_", ephemeral=True)


@religion_group.command(name="worship", description="Set your character's religion")
@app_commands.describe(religion_name="Religion to follow")
@app_commands.autocomplete(religion_name=_autocomplete_religion)
async def religion_worship(interaction: discord.Interaction, religion_name: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.followup.send("You need a character first!", ephemeral=True)
            return

        rel_result = await db.execute(
            select(Religion).where(
                Religion.guild_id == interaction.guild_id,
                Religion.name.ilike(religion_name),
            )
        )
        rel = rel_result.scalar_one_or_none()
        if not rel:
            await interaction.followup.send(f"Religion '{religion_name}' not found.", ephemeral=True)
            return

        char.religion = rel.name
        await db.commit()

    await interaction.followup.send(f"🙏 You now follow **{rel.name}**, devoted to **{rel.deity_name or 'the divine'}**.", ephemeral=True)


# ── /prayer ──────────────────────────────────────────────────────────────────

@religion_group.command(name="prayer", description="Daily divine blessing — 1/day, requires a religion")
async def religion_prayer(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.followup.send("You need a character first!", ephemeral=True)
            return

        if not char.religion:
            await interaction.followup.send("You don't follow any religion. Use `/religion worship` first.", ephemeral=True)
            return

        # Check if already prayed today (track in class_resources.prayer_date)
        resources = dict(char.class_resources or {})
        last_prayer_date = resources.get("prayer_date")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if last_prayer_date == today:
            await interaction.followup.send("You have already prayed today. The divine listens only once per day.", ephemeral=True)
            return

        # Roll for blessing: 1d20 + WIS mod
        wisdom_mod = (char.wisdom - 10) // 2 if hasattr(char, 'wisdom') else 0
        roll = random.randint(1, 20)
        total = roll + wisdom_mod

        if total >= 15:
            # Grant temporary HP or bonus
            temp_hp = random.randint(2, 12) + random.randint(2, 12)  # 2d6
            char.hp_temp = (char.hp_temp or 0) + temp_hp
            resources["prayer_blessing"] = "divine_favor"
            resources["prayer_date"] = today
            char.class_resources = resources
            flag_modified(char, "class_resources")
            await db.commit()

            await interaction.followup.send(
                f"🙏 You kneel in prayer to **{char.religion}**. The divine answers! "
                f"(Rolled **{roll}** + **{wisdom_mod}** WIS = **{total}**) "
                f"\n✨ You gain **{temp_hp} temporary HP**!",
                ephemeral=True,
            )
        else:
            resources["prayer_date"] = today
            char.class_resources = resources
            flag_modified(char, "class_resources")
            await db.commit()

            await interaction.followup.send(
                f"🙏 You kneel in prayer to **{char.religion}**. "
                f"(Rolled **{roll}** + **{wisdom_mod}** WIS = **{total}**) "
                f"\nThe divine remains silent for now. Perhaps tomorrow...",
                ephemeral=True,
            )


class ReligionCog(commands.Cog, name="Religion"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(religion_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("religion")


async def setup(bot):
    await bot.add_cog(ReligionCog(bot))
