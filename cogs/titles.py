import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character
from services.title_service import (
    get_character_titles, set_active_title, get_active_title, TIER_META,
)


class TitlesCog(commands.Cog, name="Titles"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.tree.add_command(self.title_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("title")

    title_group = app_commands.Group(name="title", description="Manage your character's displayed title")

    # ── /title list ───────────────────────────────────────────────────────

    @title_group.command(name="list", description="View all titles your character holds")
    async def title_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with get_db() as db:
            char = await db.scalar(select(Character).where(
                Character.user_id == str(interaction.user.id),
                Character.guild_id == str(interaction.guild_id),
                Character.is_active == True,
            ))
            if not char:
                await interaction.followup.send(
                    "You don't have an active character.", ephemeral=True
                )
                return
            titles = await get_character_titles(db, char.id)

        if not titles:
            await interaction.followup.send(
                "Your character has no titles yet. Earn them through great deeds!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(title=f"Titles of {char.name}", color=0xF1C40F)
        for t in titles:
            status = " *(active)*" if t["is_active"] else ""
            embed.add_field(
                name=f"{t['display']}{status}",
                value=t["description"] or f"*{t['tier'].title()} title*",
                inline=False,
            )
        embed.set_footer(
            text="Use /title set <name> to choose which title displays above your name."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /title set ────────────────────────────────────────────────────────

    @title_group.command(name="set", description="Set your active displayed title")
    @app_commands.describe(title_name="The name of the title to display")
    async def title_set(self, interaction: discord.Interaction, title_name: str):
        await interaction.response.defer(ephemeral=True)
        async with get_db() as db:
            char = await db.scalar(select(Character).where(
                Character.user_id == str(interaction.user.id),
                Character.guild_id == str(interaction.guild_id),
                Character.is_active == True,
            ))
            if not char:
                await interaction.followup.send(
                    "You don't have an active character.", ephemeral=True
                )
                return
            titles = await get_character_titles(db, char.id)
            match = next((t for t in titles if t["name"].lower() == title_name.lower()), None)
            if not match:
                await interaction.followup.send(
                    f"You don't have a title called '{title_name}'.", ephemeral=True
                )
                return
            await set_active_title(db, char.id, match["id"])

        await interaction.followup.send(
            f"✦ **{match['display']}** is now displayed above your name.",
            ephemeral=True,
        )

    # ── /title clear ──────────────────────────────────────────────────────

    @title_group.command(name="clear", description="Stop displaying a title above your name")
    async def title_clear(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with get_db() as db:
            char = await db.scalar(select(Character).where(
                Character.user_id == str(interaction.user.id),
                Character.guild_id == str(interaction.guild_id),
                Character.is_active == True,
            ))
            if not char:
                await interaction.followup.send(
                    "You don't have an active character.", ephemeral=True
                )
                return
            await set_active_title(db, char.id, None)

        await interaction.followup.send(
            "Title cleared — your character now displays no title.",
            ephemeral=True,
        )

    # ── /title view ───────────────────────────────────────────────────────

    @title_group.command(name="view", description="View another character's titles")
    @app_commands.describe(character_name="Name of the character to inspect")
    async def title_view(self, interaction: discord.Interaction, character_name: str):
        await interaction.response.defer(ephemeral=True)
        async with get_db() as db:
            char = await db.scalar(select(Character).where(
                Character.name.ilike(character_name),
                Character.guild_id == str(interaction.guild_id),
            ))
            if not char:
                await interaction.followup.send(
                    f"No character named '{character_name}' found.", ephemeral=True
                )
                return
            titles = await get_character_titles(db, char.id)
            active = await get_active_title(db, char.id)

        if not titles:
            await interaction.followup.send(
                f"**{char.name}** holds no titles.", ephemeral=True
            )
            return

        color = active[1] if active else 0x95A5A6
        embed = discord.Embed(
            title=f"{active[0] if active else '(No active title)'}",
            description=f"**{char.name}** · {char.char_class} Lv.{char.level}",
            color=color,
        )
        for t in titles:
            status = " *(displayed)*" if t["is_active"] else ""
            embed.add_field(
                name=f"{t['display']}{status}",
                value=t["description"] or f"*{t['tier'].title()} title*",
                inline=False,
            )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TitlesCog(bot))
