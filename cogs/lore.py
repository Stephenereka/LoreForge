import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, delete, func
from database.session import get_db
from database.models import LoreEntry, GuildConfig
from services.utils import is_gm
import random

lore_group = app_commands.Group(name="lore", description="Browse and manage world lore")


async def _lore_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete for lore entries visible to the user."""
    async with get_db() as db:
        query = select(LoreEntry).where(
            LoreEntry.guild_id == interaction.guild_id,
            LoreEntry.title.ilike(f"%{current}%"),
        )
        # Non-GM users only see public entries
        from services.utils import is_gm
        if not await is_gm(interaction):
            query = query.where(LoreEntry.visibility == "public")
        query = query.limit(25)
        result = await db.execute(query)
        entries = result.scalars().all()
    return [
        app_commands.Choice(name=f"{e.title} ({e.category})"[:100], value=e.title)
        for e in entries
    ][:25]


class LoreAddModal(discord.ui.Modal, title="Add Lore Entry"):
    content = discord.ui.TextInput(label="Content", style=discord.TextStyle.long, required=True)
    category = discord.ui.TextInput(label="Category (e.g., history, faction, location)", required=False, max_length=30)
    tags = discord.ui.TextInput(label="Tags (comma-separated)", required=False, max_length=200)
    image_url = discord.ui.TextInput(label="Image URL (optional)", required=False, max_length=500)

    def __init__(self, title_name: str):
        super().__init__()
        self._title = title_name

    async def on_submit(self, interaction: discord.Interaction):
        tags_list = [t.strip() for t in self.tags.value.split(",") if t.strip()] if self.tags.value else []

        async with get_db() as db:
            db.add(LoreEntry(
                guild_id=interaction.guild_id,
                title=self._title,
                content=self.content.value,
                category=self.category.value or "lore",
                tags=tags_list,
                is_rumor=False,
                visibility="public",
                image_url=self.image_url.value or None,
                created_by=interaction.user.id,
            ))

        embed = discord.Embed(
            title=f"📚 {self._title}",
            description=f"Added to **{self.category.value or 'lore'}** category.",
            color=0xA855F7,
        )
        await interaction.response.send_message(embed=embed)


class LoreEditModal(discord.ui.Modal, title="Edit Lore Entry"):
    content = discord.ui.TextInput(label="Content", style=discord.TextStyle.long, required=True)
    category = discord.ui.TextInput(label="Category", required=False, max_length=30)

    def __init__(self, existing: LoreEntry):
        super().__init__()
        self._entry_id = existing.id
        self.content.default = existing.content
        self.category.default = existing.category

    async def on_submit(self, interaction: discord.Interaction):
        async with get_db() as db:
            result = await db.execute(select(LoreEntry).where(LoreEntry.id == self._entry_id))
            entry = result.scalar_one_or_none()
            if entry:
                entry.content = self.content.value
                entry.category = self.category.value or "lore"
        await interaction.response.send_message("✅ Lore entry updated.", ephemeral=True)


@lore_group.command(name="add", description="Add a new lore entry (GM only)")
@app_commands.describe(title="Title of the lore entry")
async def lore_add(interaction: discord.Interaction, title: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can add lore.", ephemeral=True)
        return
    await interaction.response.send_modal(LoreAddModal(title))


@lore_group.command(name="edit", description="Edit an existing lore entry (GM only)")
@app_commands.describe(title="Title of the lore entry to edit")
@app_commands.autocomplete(title=_lore_autocomplete)
async def lore_edit(interaction: discord.Interaction, title: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can edit lore.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(LoreEntry).where(
                LoreEntry.guild_id == interaction.guild_id,
                LoreEntry.title.ilike(title),
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            await interaction.response.send_message("Lore entry not found.", ephemeral=True)
            return
    await interaction.response.send_modal(LoreEditModal(entry))


@lore_group.command(name="delete", description="Delete a lore entry (GM only)")
@app_commands.describe(title="Title of the lore entry to delete")
@app_commands.autocomplete(title=_lore_autocomplete)
async def lore_delete(interaction: discord.Interaction, title: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can delete lore.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(LoreEntry).where(
                LoreEntry.guild_id == interaction.guild_id,
                LoreEntry.title.ilike(title),
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            await interaction.response.send_message("Lore entry not found.", ephemeral=True)
            return
        await db.delete(entry)
    await interaction.response.send_message(f"🗑️ Deleted lore entry **{title}**.")


@lore_group.command(name="search", description="Search lore entries")
@app_commands.describe(query="Search term")
async def lore_search(interaction: discord.Interaction, query: str):
    async with get_db() as db:
        result = await db.execute(
            select(LoreEntry).where(
                LoreEntry.guild_id == interaction.guild_id,
                LoreEntry.visibility == "public",
                (LoreEntry.title.ilike(f"%{query}%")) | (LoreEntry.content.ilike(f"%{query}%")),
            ).limit(5)
        )
        entries = result.scalars().all()

    if not entries:
        await interaction.response.send_message(f"No lore entries match **{query}**.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📚 Search Results: {query}",
        color=0xA855F7,
    )
    for entry in entries:
        excerpt = entry.content[:100] + "..." if len(entry.content) > 100 else entry.content
        embed.add_field(
            name=f"{entry.title} ({entry.category})",
            value=f"*{excerpt}*",
            inline=False,
        )

    await interaction.response.send_message(embed=embed)


@lore_group.command(name="view", description="View a lore entry")
@app_commands.describe(title="Title of the lore entry")
@app_commands.autocomplete(title=_lore_autocomplete)
async def lore_view(interaction: discord.Interaction, title: str):
    async with get_db() as db:
        result = await db.execute(
            select(LoreEntry).where(
                LoreEntry.guild_id == interaction.guild_id,
                LoreEntry.title.ilike(title),
            )
        )
        entry = result.scalar_one_or_none()

    if not entry:
        await interaction.response.send_message("Lore entry not found.", ephemeral=True)
        return

    # Visibility check
    user_is_gm = await is_gm(interaction)
    if entry.visibility not in ("public",) and not user_is_gm:
        await interaction.response.send_message("Lore entry not found.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📚 {entry.title}",
        description=entry.content[:2000] if entry.content else "*No content.*",
        color=0xA855F7,
    )
    embed.add_field(name="Category", value=entry.category, inline=True)
    embed.add_field(name="Tags", value=", ".join(entry.tags or []) or "None", inline=True)
    if entry.image_url:
        embed.set_image(url=entry.image_url)
    embed.set_footer(text=f"Canon: {'Yes' if entry.is_canon else 'No'}  ·  Rumor: {'Yes' if entry.is_rumor else 'No'}")

    await interaction.response.send_message(embed=embed)


@lore_group.command(name="list", description="List all lore entries")
@app_commands.describe(category="Filter by category (optional)")
async def lore_list(interaction: discord.Interaction, category: str = None):
    async with get_db() as db:
        query = select(LoreEntry).where(
            LoreEntry.guild_id == interaction.guild_id,
            LoreEntry.visibility == "public",
        )
        if category:
            query = query.where(LoreEntry.category.ilike(category))
        query = query.order_by(LoreEntry.updated_at.desc()).limit(25)
        result = await db.execute(query)
        entries = result.scalars().all()

    if not entries:
        await interaction.response.send_message("No lore entries found.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📚 Lore Entries{f' ({category})' if category else ''}",
        color=0xA855F7,
    )
    text = ""
    for entry in entries:
        tag_str = f" [{', '.join(entry.tags[:2])}]" if entry.tags else ""
        text += f"• **{entry.title}** ({entry.category}){tag_str}\n"

    if len(text) > 1000:
        embed.description = text[:1000] + f"\n\n*...and {len(entries) - 10} more*"
    else:
        embed.description = text

    await interaction.response.send_message(embed=embed)


@lore_group.command(name="random", description="Get a random lore entry")
async def lore_random(interaction: discord.Interaction):
    async with get_db() as db:
        result = await db.execute(
            select(func.count()).select_from(LoreEntry).where(
                LoreEntry.guild_id == interaction.guild_id,
                LoreEntry.visibility == "public",
            )
        )
        count = result.scalar()
        if count == 0:
            await interaction.response.send_message("No lore entries yet.", ephemeral=True)
            return

        result = await db.execute(
            select(LoreEntry).where(
                LoreEntry.guild_id == interaction.guild_id,
                LoreEntry.visibility == "public",
            )
        )
        entries = result.scalars().all()
        entry = random.choice(entries)

    embed = discord.Embed(
        title=f"📚 Random Lore: {entry.title}",
        description=entry.content[:2000] if entry.content else "*No content.*",
        color=0xA855F7,
    )
    embed.add_field(name="Category", value=entry.category, inline=True)

    await interaction.response.send_message(embed=embed)


# ── Phase 6: Player-Specific Lore Secrets ────────────────────────────────────

@lore_group.command(name="reveal", description="Reveal a lore entry to a specific player (GM only)")
@app_commands.describe(title="Title of the lore entry", user="The player to reveal it to")
@app_commands.autocomplete(title=_lore_autocomplete)
async def lore_reveal(interaction: discord.Interaction, title: str, user: discord.Member):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can reveal lore.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        result = await db.execute(
            select(LoreEntry).where(
                LoreEntry.guild_id == interaction.guild_id,
                LoreEntry.title.ilike(title),
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            await interaction.followup.send("Lore entry not found.", ephemeral=True)
            return

        from sqlalchemy.orm.attributes import flag_modified
        whitelist = list(entry.visibility_whitelist or [])
        if user.id not in whitelist:
            whitelist.append(user.id)
            entry.visibility_whitelist = whitelist
            flag_modified(entry, "visibility_whitelist")

    # DM the player
    preview = entry.content[:200] + "..." if len(entry.content) > 200 else entry.content
    dm_embed = discord.Embed(
        title="🔓 A Secret Has Been Revealed to You",
        description=f"**{entry.title}**\n\n{preview}",
        color=0xA855F7,
    )
    dm_embed.set_footer(text="This lore is now unlocked for you.")
    try:
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        pass

    await interaction.followup.send(f"✅ **{entry.title}** revealed to {user.mention}.", ephemeral=True)


@lore_group.command(name="hide", description="Hide a lore entry from a specific player (GM only)")
@app_commands.describe(title="Title of the lore entry", user="The player to hide it from")
@app_commands.autocomplete(title=_lore_autocomplete)
async def lore_hide(interaction: discord.Interaction, title: str, user: discord.Member):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can hide lore.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        result = await db.execute(
            select(LoreEntry).where(
                LoreEntry.guild_id == interaction.guild_id,
                LoreEntry.title.ilike(title),
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            await interaction.followup.send("Lore entry not found.", ephemeral=True)
            return

        from sqlalchemy.orm.attributes import flag_modified
        whitelist = list(entry.visibility_whitelist or [])
        if user.id in whitelist:
            whitelist.remove(user.id)
            entry.visibility_whitelist = whitelist
            flag_modified(entry, "visibility_whitelist")

    await interaction.followup.send(f"❌ **{entry.title}** hidden from {user.mention}.", ephemeral=True)


# ── Phase 6: Player-Written Lore Submissions ──────────────────────────────────

class LoreSubmitModal(discord.ui.Modal, title="Submit Lore Entry"):
    content = discord.ui.TextInput(label="Content", style=discord.TextStyle.long, required=True)
    category = discord.ui.TextInput(label="Category (e.g., history, faction, location)", required=False, max_length=30)

    def __init__(self, title_name: str):
        super().__init__()
        self._title = title_name

    async def on_submit(self, interaction: discord.Interaction):
        async with get_db() as db:
            entry = LoreEntry(
                guild_id=interaction.guild_id,
                title=self._title,
                content=self.content.value,
                category=self.category.value or "lore",
                tags=[],
                is_rumor=False,
                visibility="submitted",
                submitted_by=interaction.user.id,
                created_by=interaction.user.id,
            )
            db.add(entry)
            await db.flush()
            entry_id = entry.id

        # Notify GM channel
        gc_result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
        )
        gc = gc_result.scalar_one_or_none()

        class ApproveDenyView(discord.ui.View):
            def __init__(self, entry_id: int, title: str, submitter_id: int):
                super().__init__(timeout=86400)
                self.entry_id = entry_id
                self.title = title
                self.submitter_id = submitter_id

            @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success)
            async def approve(self, interaction2: discord.Interaction, btn: discord.ui.Button):
                if not await is_gm(interaction2):
                    await interaction2.response.send_message("Only GMs can approve.", ephemeral=True)
                    return
                async with get_db() as db2:
                    e = (await db2.execute(select(LoreEntry).where(LoreEntry.id == self.entry_id))).scalar_one_or_none()
                    if e:
                        e.visibility = "public"
                from services.achievements import grant_achievement
                await grant_achievement(interaction2.client, 0, interaction2.guild_id, "scribe", channel=interaction2.channel)
                try:
                    submitter = await interaction2.guild.fetch_member(self.submitter_id)
                    if submitter:
                        await submitter.send(f"✅ Your lore entry **{self.title}** has been approved! +100 XP")
                except Exception:
                    pass
                await interaction2.response.edit_message(content=f"✅ **{self.title}** approved!", view=None)

            @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger)
            async def deny(self, interaction2: discord.Interaction, btn: discord.ui.Button):
                if not await is_gm(interaction2):
                    await interaction2.response.send_message("Only GMs can deny.", ephemeral=True)
                    return
                async with get_db() as db2:
                    e = (await db2.execute(select(LoreEntry).where(LoreEntry.id == self.entry_id))).scalar_one_or_none()
                    if e:
                        await db2.delete(e)
                try:
                    submitter = await interaction2.guild.fetch_member(self.submitter_id)
                    if submitter:
                        await submitter.send(f"❌ Your lore entry **{self.title}** was not approved by the GM.")
                except Exception:
                    pass
                await interaction2.response.edit_message(content=f"❌ **{self.title}** denied and removed.", view=None)

        gm_embed = discord.Embed(
            title="📝 New Lore Submission",
            description=f"**{self._title}**\n\n{self.content.value[:500]}",
            color=0xF59E0B,
        )
        gm_embed.add_field(name="Submitted by", value=interaction.user.mention, inline=True)
        gm_embed.add_field(name="Category", value=self.category.value or "lore", inline=True)
        gm_embed.set_footer(text=f"Entry ID: {entry_id}")

        if gc and gc.gm_channel_id:
            gm_channel = interaction.guild.get_channel(gc.gm_channel_id)
            if gm_channel:
                await gm_channel.send(embed=gm_embed, view=ApproveDenyView(entry_id, self._title, interaction.user.id))

        await interaction.response.send_message(
            f"✅ Your lore entry **{self._title}** has been submitted for GM review.",
            ephemeral=True,
        )


@lore_group.command(name="submit", description="Submit a player-written lore entry for GM review")
@app_commands.describe(title="Title of your lore entry")
async def lore_submit(interaction: discord.Interaction, title: str):
    """Submit player-written lore for GM approval."""
    await interaction.response.send_modal(LoreSubmitModal(title))


class LoreCog(commands.Cog, name="Lore"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(lore_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("lore")


async def setup(bot):
    await bot.add_cog(LoreCog(bot))
