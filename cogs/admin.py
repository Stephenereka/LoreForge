import discord
from discord import app_commands
from discord.ext import commands

# ── /help pages ───────────────────────────────────────────────────────────────

def _help_pages() -> list[discord.Embed]:
    pages = []

    # Page 1 — Overview
    e = discord.Embed(
        title="⚔️ LoreForge — Quick Start",
        description=(
            "LoreForge turns your Discord server into a living RPG world.\n"
            "The GM builds the world — players make characters and fight inside it.\n\n"
            "**Getting started:**\n"
            "1️⃣ `/character create` — build your character (5-step wizard)\n"
            "2️⃣ `/combat start` — pick an enemy and begin a fight\n"
            "3️⃣ Type your actions in RP — the bot reads and resolves them\n\n"
            "Use the buttons below to browse all commands."
        ),
        color=0x8B5CF6,
    )
    e.set_footer(text="Page 1 / 5  —  LoreForge")
    pages.append(e)

    # Page 2 — Character
    e = discord.Embed(title="🧙 Character Commands", color=0x8B5CF6)
    e.add_field(
        name="/character create <name>",
        value="5-step wizard: race → class → background → loadout → backstory & proxy",
        inline=False,
    )
    e.add_field(name="/character sheet", value="View your character sheet privately", inline=False)
    e.add_field(name="/character show", value="Post your character sheet to the channel", inline=False)
    e.add_field(name="/character proxy", value="Set or update your proxy brackets & avatar", inline=False)
    e.add_field(name="/character proxy_remove", value="Remove your proxy", inline=False)
    e.add_field(name="/character delete", value="Permanently delete your character", inline=False)
    e.set_footer(text="Page 2 / 5  —  Character")
    pages.append(e)

    # Page 3 — Combat + Conditions
    e = discord.Embed(
        title="⚔️ Combat",
        description=(
            "**How it works:** Type your action as RP — the bot reads it, asks you to confirm, then rolls.\n"
            "Use your character's named attacks (e.g. *Power Strike*, *Eldritch Blast*) for special mechanics.\n"
            "Dice rolls appear in the channel for everyone to see."
        ),
        color=0xEF4444,
    )
    e.add_field(name="/combat start", value="Pick an enemy and open a public lobby (others can join)", inline=False)
    e.add_field(name="/combat status", value="Check the current combat state", inline=False)
    e.add_field(name="/combat forfeit", value="Leave an active fight mid-combat", inline=False)
    e.add_field(
        name="⚡ Conditions",
        value=(
            "**DoT:** 🟢 Poisoned · 🔥 Burning · 🩸 Bleeding\n"
            "**Status:** ⚡ Stunned · 🌫️ Blinded · 😨 Frightened · 🌀 Prone\n"
            "**Buffs:** 🛡️ Parrying (+2 AC) · 🔰 Shielded (+5 AC) · 💢 Raging\n"
            "**Debuffs:** 💀 Hexed · ⚠️ Reckless (−2 AC)"
        ),
        inline=False,
    )
    e.set_footer(text="Page 3 / 5  —  Combat & Conditions")
    pages.append(e)

    # Page 4 — Rest + Shop + Inventory
    e = discord.Embed(title="💤 Rest  ·  🏪 Shop  ·  🎒 Inventory", color=0x6366F1)
    e.add_field(
        name="Rest",
        value=(
            "`/rest short` — Roll hit dice to recover HP (Warlocks regain spell slots)\n"
            "`/rest long` — Full HP + all class resources restored\n"
            "*Cannot rest during active combat.*"
        ),
        inline=False,
    )
    e.add_field(
        name="Shop",
        value=(
            "`/shop browse` — See all weapons, armor, and potions\n"
            "`/shop buy <item>` — Purchase an item\n"
            "`/shop sell <item>` — Sell for half price"
        ),
        inline=False,
    )
    e.add_field(
        name="Inventory",
        value=(
            "`/inventory view` — See your items and gold\n"
            "`/inventory equip <item>` — Equip a weapon or armor\n"
            "`/inventory use <item>` — Drink a potion"
        ),
        inline=False,
    )
    e.set_footer(text="Page 4 / 5  —  Rest, Shop & Inventory")
    pages.append(e)

    # Page 5 — Server setup + Coming Soon
    e = discord.Embed(title="⚙️ Server Setup  ·  🗺️ Coming Soon", color=0x4F46E5)
    e.add_field(
        name="Server Setup",
        value="`/server setup <world_name> <gm_role>` — Configure LoreForge *(Manage Server required)*",
        inline=False,
    )
    e.add_field(name="Utility", value="`/ping` — Check if the bot is online\n`/help` — Show this menu", inline=False)
    e.add_field(
        name="Coming Soon",
        value=(
            "`/lore` — Search your world's lore wiki\n"
            "`/quest` — View and accept quests\n"
            "`/travel` — Move between locations\n"
            "`/tutorial` — Guided walkthrough for new players\n"
            "`/gm` — Game Master tools"
        ),
        inline=False,
    )
    e.set_footer(text="Page 5 / 5  —  Server & More")
    pages.append(e)

    return pages


class HelpView(discord.ui.View):
    def __init__(self, page: int = 0):
        super().__init__(timeout=120)
        self.page = page
        self.pages = _help_pages()
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page == len(self.pages) - 1

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

# ── /server group ─────────────────────────────────────────────────────────────

server_group = app_commands.Group(
    name="server",
    description="Server setup and configuration",
    default_permissions=discord.Permissions(manage_guild=True),
)


@server_group.command(name="setup", description="Set up LoreForge in this server (Manage Server or GM role)")
@app_commands.describe(world_name="Name of your world", gm_role="The role that acts as Game Master")
async def server_setup(interaction: discord.Interaction, world_name: str, gm_role: discord.Role):
    from services.utils import is_gm
    has_manage = interaction.user.guild_permissions.manage_guild
    if not has_manage and not await is_gm(interaction):
        await interaction.response.send_message(
            "You need **Manage Server** permission or the GM role to run this.", ephemeral=True
        )
        return
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
        view = HelpView(page=0)
        await interaction.response.send_message(embed=view.pages[0], view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
