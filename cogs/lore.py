import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, delete, func
from database.session import get_db
from database.models import LoreEntry
from services.utils import is_gm
import random

lore_group = app_commands.Group(name="lore", description="Browse and manage world lore")


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


class LoreCog(commands.Cog, name="Lore"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(lore_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("lore")


async def setup(bot):
    await bot.add_cog(LoreCog(bot))
