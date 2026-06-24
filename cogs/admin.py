import discord
from discord import app_commands
from discord.ext import commands

# ── /server group ─────────────────────────────────────────────────────────────

server_group = app_commands.Group(
    name="server",
    description="Server setup and configuration",
    default_permissions=discord.Permissions(manage_guild=True),
)


@server_group.command(name="setup", description="Set up LoreForge in this server (requires Manage Server)")
@app_commands.describe(world_name="Name of your world", gm_role="The role that acts as Game Master")
async def server_setup(interaction: discord.Interaction, world_name: str, gm_role: discord.Role):
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
                gm_role_id=gm_role.id,
            )
            db.add(config)

    await interaction.response.send_message(
        f"LoreForge is set up!\nWorld: **{world_name}**\nGM Role: {gm_role.mention}",
        ephemeral=True,
    )


# ── Admin cog (top-level utility commands) ────────────────────────────────────

class AdminCog(commands.Cog, name="Admin"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(server_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("server")

    @app_commands.command(name="ping", description="Check if LoreForge is online")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"LoreForge is online. Latency: `{latency}ms`",
            ephemeral=True,
        )

    @app_commands.command(name="help", description="Show all LoreForge commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚔️ LoreForge — Command List",
            description="LoreForge turns your Discord server into a living RPG world.\nType `/` and a group name to see its commands.",
            color=0x8B5CF6,
        )

        embed.add_field(
            name="🧙 `/character` — Your character",
            value=(
                "`/character create <name>` — 4-step wizard: race → class → background → backstory & proxy\n"
                "`/character sheet` — View your character sheet (only you see it)\n"
                "`/character show` — Post your character sheet to the channel\n"
                "`/character proxy` — Set or update your proxy brackets & avatar\n"
                "`/character proxy_remove` — Remove your proxy"
            ),
            inline=False,
        )

        embed.add_field(
            name="⚙️ `/server` — Server setup",
            value=(
                "`/server setup <world_name> <gm_role>` — Configure LoreForge for this server *(Manage Server required)*"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔧 Utility",
            value=(
                "`/ping` — Check if the bot is online\n"
                "`/help` — Show this menu"
            ),
            inline=False,
        )

        embed.add_field(
            name="⚔️ `/combat` — Battles",
            value=(
                "`/combat start` — Pick an enemy and begin a fight\n"
                "`/combat status` — Check the current combat state"
            ),
            inline=False,
        )

        embed.add_field(
            name="🏪 `/shop` — Buy & sell",
            value=(
                "`/shop browse` — See all weapons, armor, and potions for sale\n"
                "`/shop buy <item>` — Purchase an item\n"
                "`/shop sell <item>` — Sell an item for half price"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎒 `/inventory` — Your items",
            value=(
                "`/inventory view` — See your items and gold\n"
                "`/inventory equip <item>` — Equip a weapon or armor\n"
                "`/inventory use <item>` — Drink a potion"
            ),
            inline=False,
        )

        embed.add_field(
            name="🗺️ Coming Soon",
            value=(
                "`/lore` — Search your world's lore wiki\n"
                "`/quest` — View and accept quests\n"
                "`/travel` — Move between locations\n"
                "`/gm` — Game Master tools"
            ),
            inline=False,
        )

        embed.set_footer(text="LoreForge — Every server is a world.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
