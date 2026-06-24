import discord
from discord.ext import commands
from discord import app_commands


class AdminCog(commands.Cog, name="Admin"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check if LoreForge is online")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"LoreForge is online. Latency: `{latency}ms`",
            ephemeral=True
        )

    @app_commands.command(name="help", description="Show all LoreForge commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚔️ LoreForge — Command List",
            description="LoreForge turns your Discord server into a living RPG world.\nAll commands are slash commands — type `/` to see them.",
            color=0x8B5CF6,
        )

        embed.add_field(
            name="🧙 Character",
            value=(
                "`/create <name>` — Create your character. Walks you through race, class, and background step by step.\n"
                "`/sheet` — View your character sheet privately.\n"
                "`/sheet_public` — Post your character sheet for the whole server to see."
            ),
            inline=False,
        )

        embed.add_field(
            name="⚙️ Server Setup",
            value=(
                "`/setup <world_name> <gm_role>` — Set up LoreForge in this server. Requires **Manage Server** permission.\n"
                "`/ping` — Check if the bot is online and see its latency."
            ),
            inline=False,
        )

        embed.add_field(
            name="🗺️ Coming Soon",
            value=(
                "`/attack` — Start a combat encounter\n"
                "`/lore` — Search your world's lore wiki\n"
                "`/quest` — View and accept quests\n"
                "`/shop` — Browse and buy items\n"
                "`/travel` — Move between locations"
            ),
            inline=False,
        )

        embed.set_footer(text="LoreForge — Every server is a world.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setup", description="Set up LoreForge in this server (requires Manage Server)")
    @app_commands.describe(world_name="Name of your world", gm_role="The role that acts as Game Master")
    @app_commands.default_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction, world_name: str, gm_role: discord.Role):
        from database.session import get_db
        from database.models import GuildConfig
        from sqlalchemy import select

        async with get_db() as db:
            result = await db.execute(
                select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
            )
            config = result.scalar_one_or_none()

            if config:
                config.world_name = world_name
                config.gm_role_id = gm_role.id
            else:
                config = GuildConfig(
                    guild_id=interaction.guild_id,
                    world_name=world_name,
                    gm_role_id=gm_role.id
                )
                db.add(config)

        await interaction.response.send_message(
            f"LoreForge is set up!\nWorld: **{world_name}**\nGM Role: {gm_role.mention}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
