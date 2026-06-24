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
            "1️⃣ `/character create` — build your character (DnD wizard or custom free-form)\n"
            "2️⃣ `/combat start` — open a lobby, choose DnD or Manual fight type\n"
            "3️⃣ **DnD fights:** type your action in RP — bot reads, confirms, rolls\n"
            "3️⃣ **Manual fights:** declare actions freely — GM resolves via `/combat hp`\n\n"
            "Use the buttons below to browse all commands."
        ),
        color=0x8B5CF6,
    )
    e.set_footer(text="Page 1 / 6  —  LoreForge")
    pages.append(e)

    # Page 2 — Character
    e = discord.Embed(title="🧙 Character Commands", color=0x8B5CF6)
    e.add_field(
        name="/character create <name>",
        value="Choose **DnD** (5-step wizard: race → class → background → loadout → details) or **Custom** (free-form: any race, class, and background you imagine — manual combat only)",
        inline=False,
    )
    e.add_field(name="/character sheet", value="View your character sheet privately (shows XP bar, loadout, proxy)", inline=False)
    e.add_field(name="/character show", value="Post your character sheet to the channel", inline=False)
    e.add_field(name="/character list [public]", value="List all your characters including dead ones", inline=False)
    e.add_field(name="/character use / unuse", value="Set or clear your active character (auto-used in all commands)", inline=False)
    e.add_field(name="/character edit <field> <value>", value="Request a mechanical stat change — submitted for GM approval", inline=False)
    e.add_field(name="/character proxy / proxy_remove", value="Set or remove proxy brackets & avatar for roleplay", inline=False)
    e.add_field(name="/character delete", value="Permanently delete a character", inline=False)
    e.set_footer(text="Page 2 / 6  —  Character")
    pages.append(e)

    # Page 3 — Combat
    e = discord.Embed(
        title="⚔️ Combat — Starting & Joining",
        description=(
            "**DnD fights** — Type your action as RP; the bot reads it, shows a confirm, then rolls dice.\n"
            "Use named attacks (*Power Strike*, *Eldritch Blast*, etc.) for special mechanics.\n\n"
            "**Manual fights** — Freely declare actions; the bot logs them. GM resolves results via `/combat hp`."
        ),
        color=0xEF4444,
    )
    e.add_field(name="/combat start <title> <type> [@invite]", value="Open a lobby — choose DnD or Manual, optionally invite someone", inline=False)
    e.add_field(name="/combat join", value="Join an open lobby in this server (pick from list if multiple)", inline=False)
    e.add_field(name="/combat invite @user", value="Invite a specific user to the current lobby", inline=False)
    e.add_field(name="/combat status", value="Check current combat state (ephemeral)", inline=False)
    e.add_field(name="/combat overview", value="Post the live status embed publicly", inline=False)
    e.add_field(name="/combat list", value="List all active combats in this server", inline=False)
    e.add_field(name="/combat log", value="Show the recent action log for this fight", inline=False)
    e.add_field(name="/combat forfeit", value="Leave an active fight mid-combat", inline=False)
    e.add_field(name="/combat end", value="End the fight (GM or host only)", inline=False)
    e.set_footer(text="Page 3 / 6  —  Combat: Start & Join")
    pages.append(e)

    # Page 4 — Combat management + Conditions
    e = discord.Embed(title="⚔️ Combat — Management & Conditions", color=0xEF4444)
    e.add_field(name="/combat pause / resume", value="Pause or resume a manual fight (GM or host only)", inline=False)
    e.add_field(name="/combat hp <amount> [@target]", value="Update HP: `+5`, `-10`, or `25` (absolute). GM can target anyone; players update own HP in manual fights only", inline=False)
    e.add_field(name="/combat edit <field> <value> [@target]", value="Edit Temp HP, set conditions (comma-separated), or clear all conditions. Manual fights + GM", inline=False)
    e.add_field(name="/combat summary", value="Generate a Battle Report embed from the fight log", inline=False)
    e.add_field(name="/combat save <#channel>", value="Pin the fight summary to a channel (GM or host only)", inline=False)
    e.add_field(name="/combat config log-channel <#channel>", value="Set the audit log channel for character edits *(Manage Server required)*", inline=False)
    e.add_field(
        name="⚡ Conditions",
        value=(
            "**DoT:** 🤢 Poisoned · 🔥 Burning · 🩸 Bleeding\n"
            "**Status:** ⭐ Stunned · 🫥 Blinded · 😨 Frightened · ⬇️ Prone · 🤜 Grappled\n"
            "**Buffs:** 🛡️ Parrying (+2 AC) · ✨ Shielded (+5 AC) · 💢 Raging · 👁️ Hidden\n"
            "**Debuffs:** 🔮 Hexed (+1d6 on hits) · 🔴 Reckless (−2 AC)"
        ),
        inline=False,
    )
    e.set_footer(text="Page 4 / 6  —  Combat: Management & Conditions")
    pages.append(e)

    # Page 5 — Rest + Shop + Inventory
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
    e.set_footer(text="Page 5 / 6  —  Rest, Shop & Inventory")
    pages.append(e)

    # Page 6 — GM + Server Setup + Coming Soon
    e = discord.Embed(title="🛡️ GM Commands  ·  ⚙️ Server Setup", color=0x4F46E5)
    e.add_field(
        name="Server Setup *(Manage Server required)*",
        value=(
            "`/server setup <world_name> <gm_role>` — Configure LoreForge\n"
            "`/combat config log-channel <#ch>` — Set audit log channel"
        ),
        inline=False,
    )
    e.add_field(
        name="GM — Roster *(server owner only)*",
        value=(
            "`/gm add @user` — Grant GM status\n"
            "`/gm remove @user` — Revoke GM status\n"
            "`/gm list` — List all GMs in this server"
        ),
        inline=False,
    )
    e.add_field(
        name="GM — Characters",
        value=(
            "`/gm sheet view [@user]` — View any player's character sheet(s)\n"
            "`/gm sheet edit @user` — Edit any stat on any player's character (instant, no approval needed)\n"
            "`/gm revive <name>` — Revive a dead character at 1 HP\n"
            "`/gm xp @user <amount>` — Award XP manually (triggers level-up if threshold reached)"
        ),
        inline=False,
    )
    e.add_field(
        name="GM — Approval Queue",
        value=(
            "`/gm pending` — View all pending stat change requests\n"
            "`/gm approve <id>` — Approve a pending request (applies the change)\n"
            "`/gm deny <id> [reason]` — Deny a pending request"
        ),
        inline=False,
    )
    e.add_field(
        name="Coming Soon",
        value=(
            "`/lore` — Search your world's lore wiki\n"
            "`/quest` — View and accept quests\n"
            "`/travel` — Move between locations\n"
            "`/tutorial` — Guided walkthrough for new players"
        ),
        inline=False,
    )
    e.set_footer(text="Page 6 / 6  —  GM & Server")
    pages.append(e)

    return pages


class HelpView(discord.ui.View):
    def __init__(self, page: int = 0):
        super().__init__(timeout=600)
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

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync_commands(self, ctx):
        guild = discord.Object(id=ctx.guild.id)
        self.bot.tree.copy_global_to(guild=guild)
        synced = await self.bot.tree.sync(guild=guild)
        await ctx.send(f"✅ Synced {len(synced)} commands to this server.")

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
