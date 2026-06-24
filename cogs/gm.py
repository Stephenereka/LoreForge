import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character
from services.utils import gm_only

gm_group = app_commands.Group(name="gm", description="Game Master tools")


@gm_group.command(name="revive", description="Bring a dead character back to life (GM only)")
@app_commands.describe(character_name="Exact name of the dead character to revive")
async def gm_revive(interaction: discord.Interaction, character_name: str):
    if not await gm_only(interaction):
        return

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.name.ilike(character_name.strip()),
                Character.is_dead == True,
            )
        )
        char = result.scalar_one_or_none()

        if not char:
            await interaction.response.send_message(
                f"No dead character named **{character_name}** found in this server.",
                ephemeral=True,
            )
            return

        char.is_dead = False
        char.is_unconscious = False
        char.hp_current = 1
        char.death_saves_success = 0
        char.death_saves_failure = 0

    embed = discord.Embed(
        title="✨ Character Revived",
        description=f"**{char.name}** has been brought back to life by {interaction.user.display_name}.",
        color=0x22C55E,
    )
    embed.add_field(name="HP", value="1 / " + str(char.hp_max), inline=True)
    embed.add_field(name="Status", value="Alive", inline=True)
    embed.set_footer(text="LoreForge")
    await interaction.response.send_message(embed=embed)


class GmCog(commands.Cog, name="GM"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(gm_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("gm")


async def setup(bot):
    await bot.add_cog(GmCog(bot))
