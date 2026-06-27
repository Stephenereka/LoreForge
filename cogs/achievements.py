"""
Achievement viewer and Hall of Fame leaderboard.
"""

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, func, desc
from database.session import get_db
from database.models import Achievement, Character, Quest, PlayerQuest
from services.achievements import ACHIEVEMENTS


achievement_group = app_commands.Group(name="achievements", description="View your earned achievements")
hall_group = app_commands.Group(name="hall-of-fame", description="Server leaderboards")


async def _character_autocomplete(interaction: discord.Interaction, current: str):
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.name.ilike(f"%{current}%"),
            ).limit(25)
        )
        return [
            app_commands.Choice(name=c.name, value=str(c.id))
            for c in result.scalars().all()
        ]


@achievement_group.command(name="list", description="View your or another character's achievements")
@app_commands.describe(character="Name of the character (leave blank for your own)")
@app_commands.autocomplete(character=_character_autocomplete)
async def achievements_list(interaction: discord.Interaction, character: str | None = None):
    await interaction.response.defer(ephemeral=True)

    async with get_db() as db:
        if character:
            # Try to parse as character ID from autocomplete
            try:
                char_id = int(character)
                result = await db.execute(select(Character).where(Character.id == char_id))
            except ValueError:
                result = await db.execute(
                    select(Character).where(
                        Character.guild_id == interaction.guild_id,
                        Character.name.ilike(f"%{character}%"),
                    )
                )
        else:
            result = await db.execute(
                select(Character).where(
                    Character.user_id == interaction.user.id,
                    Character.guild_id == interaction.guild_id,
                    Character.is_active == True,
                )
            )
        char = result.scalar_one_or_none()

        if not char:
            await interaction.followup.send("Character not found.", ephemeral=True)
            return

        # Get all achievements for this character
        ach_result = await db.execute(
            select(Achievement).where(
                Achievement.character_id == char.id,
            ).order_by(Achievement.achieved_at.desc())
        )
        earned = {a.achievement_key: a for a in ach_result.scalars().all()}

    total = len(ACHIEVEMENTS)
    earned_count = len(earned)

    embed = discord.Embed(
        title=f"🏆 Achievements — {char.name}",
        description=f"**{earned_count}/{total}** achievements unlocked",
        color=0xF1C40F,
    )

    # Group by earned/unearned
    earned_lines = []
    unearned_lines = []
    for key, ach_def in sorted(ACHIEVEMENTS.items(), key=lambda x: x[1]["name"]):
        icon = ach_def.get("icon", "🏆")
        name = ach_def.get("name", key)
        if key in earned:
            earned_lines.append(f"{icon} **{name}** — {ach_def['desc']}")
        else:
            unearned_lines.append(f"🔒 {name}")

    if earned_lines:
        embed.add_field(
            name=f"✅ Unlocked ({earned_count})",
            value="\n".join(earned_lines[:20]),
            inline=False,
        )
    if unearned_lines and earned_count < total:
        remaining = total - earned_count
        embed.add_field(
            name=f"🔒 Locked ({remaining})",
            value="\n".join(unearned_lines[:20]),
            inline=False,
        )

    await interaction.followup.send(embed=embed, ephemeral=True)


@hall_group.command(name="achievements", description="Server leaderboard: most achievements earned")
async def hall_achievements(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        result = await db.execute(
            select(
                Achievement.character_id,
                func.count(Achievement.id).label("count"),
            ).where(
                Achievement.guild_id == interaction.guild_id,
            ).group_by(Achievement.character_id).order_by(desc("count")).limit(10)
        )
        rows = result.all()

    if not rows:
        await interaction.followup.send("No achievements earned yet in this server.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🏆 Hall of Fame — Most Achievements",
        color=0xF1C40F,
    )
    lines = []
    for i, row in enumerate(rows, 1):
        async with get_db() as db2:
            c = await db2.execute(select(Character).where(Character.id == row.character_id))
            char = c.scalar_one_or_none()
            name = char.name if char else f"Character #{row.character_id}"
        lines.append(f"**{i}.** {name} — **{row.count}** achievements")
    embed.description = "\n".join(lines)
    await interaction.followup.send(embed=embed, ephemeral=True)


@hall_group.command(name="quests", description="Server leaderboard: most quests completed")
async def hall_quests(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        result = await db.execute(
            select(
                PlayerQuest.character_id,
                func.count(PlayerQuest.id).label("count"),
            ).where(
                PlayerQuest.guild_id == interaction.guild_id,
                PlayerQuest.status == "completed",
            ).group_by(PlayerQuest.character_id).order_by(desc("count")).limit(10)
        )
        rows = result.all()

    if not rows:
        await interaction.followup.send("No quests completed yet.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📜 Hall of Fame — Most Quests Completed",
        color=0x22C55E,
    )
    lines = []
    for i, row in enumerate(rows, 1):
        async with get_db() as db2:
            c = await db2.execute(select(Character).where(Character.id == row.character_id))
            char = c.scalar_one_or_none()
            name = char.name if char else f"Character #{row.character_id}"
        lines.append(f"**{i}.** {name} — **{row.count}** quests")
    embed.description = "\n".join(lines)
    await interaction.followup.send(embed=embed, ephemeral=True)


class AchievementsCog(commands.Cog, name="Achievements"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(achievement_group)
        bot.tree.add_command(hall_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("achievements")
        self.bot.tree.remove_command("hall-of-fame")


async def setup(bot):
    await bot.add_cog(AchievementsCog(bot))
