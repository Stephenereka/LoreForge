import discord
from discord import app_commands
from discord.ext import commands

# ── /help pages ───────────────────────────────────────────────────────────────

def _help_pages(show_gm: bool = False) -> list[discord.Embed]:
    pages = []

    # Page 1 — Overview
    e = discord.Embed(
        title="⚔️ LoreForge — Quick Start",
        description=(
            "LoreForge turns your Discord server into a living RPG world.\n"
            "The GM builds the world — players make characters and fight inside it.\n\n"
            "**Getting started:**\n"
            "1️⃣ `/classes browse` — browse class codex to choose your class\n"
            "2️⃣ `/character create <name>` — build your character (DnD wizard or custom free-form)\n"
            "   • **New!** Roll **two stat sets** (4d6-drop-lowest) and pick the one you want\n"
            "   • **New!** Pick your **starting attacks** from a pool of 6 options per class\n"
            "   • **New!** View **race details 📖** and **class details 📖** during selection\n"
            "   • **New!** Get a **class tutorial** via DM after creation (skippable)\n"
            "3️⃣ `/combat start` — open a lobby, choose DnD or Manual fight type\n"
            "4️⃣ **DnD fights:** type your action in RP — bot reads, confirms, rolls\n"
            "4️⃣ **Manual fights:** declare actions freely — GM resolves via `/combat hp`\n"
            "5️⃣ **Level up!** At each level-up, you'll get a **DM to unlock a new attack** 🎯\n"
            "6️⃣ `/roll 2d6+3` — roll any dice with standard RPG notation (d4, d6, d8, d10, d12, d20, d100)\n\n"
            "Use the buttons below to browse all commands."
        ),
        color=0x8B5CF6,
    )
    e.set_footer(text="Page 1 / 10  —  LoreForge")
    pages.append(e)

    # Page 2 — Economy, Housing, Market & Auction
    e = discord.Embed(title="🔮 Economy · 🏠 Housing · 🛒 Market · 🔨 Auctions", color=0x6B21A8)
    e.add_field(
        name="🔮 Economy (Spirit Stones)",
        value=(
            "`/economy balance` — Check your Spirit Stone balance\n"
            "`/economy daily` — Claim daily Spirit Stone reward (streak-based: 200→350→500→750)\n"
            "`/economy pay <@user> <amount>` — Send Spirit Stones to another player\n"
            "`/economy leaderboard` — Top 10 richest cultivators\n"
            "*Earn Spirit Stones from combat victories, daily rewards, and short rests.*"
        ),
        inline=False,
    )
    e.add_field(
        name="🏠 Housing (Murim Dwellings)",
        value=(
            "`/house view` — See your current dwelling and its perks\n"
            "`/house buy` — Buy a Cave Dwelling (Tier 1 — 500 Spirit Stones)\n"
            "`/house upgrade` — Upgrade to the next tier (up to Tier 5 Sovereign Palace)\n"
            "`/house browse` — Browse all housing tiers, costs, and XP bonuses\n"
            "*Housing grants bonus XP from short rests!*"
        ),
        inline=False,
    )
    e.add_field(
        name="🛒 Market",
        value=(
            "`/market post <item> <price> [qty] [desc]` — List an item for sale\n"
            "`/market browse` — Browse all active listings (paginated)\n"
            "`/market buy <listing_id>` — Buy an item (deducts Spirit Stones)\n"
            "`/market cancel <listing_id>` — Cancel your own listing\n"
            "`/market mine` — View your active listings"
        ),
        inline=False,
    )
    e.add_field(
        name="🔨 Auctions",
        value=(
            "`/auction create <item> <start_price> <hours> [qty] [desc]` — Start an auction (1–72h)\n"
            "`/auction bid <auction_id> <amount>` — Place a bid (outbid refunds previous bidder)\n"
            "`/auction view <auction_id>` — See full auction details\n"
            "`/auction browse` — List all active auctions\n"
            "`/auction end <id>` — Force-end an auction (GM only)\n"
            "*Expired auctions auto-finalize — winner gets a DM notification!*"
        ),
        inline=False,
    )
    e.set_footer(text="Page 2 / 10  —  Economy & Commerce")
    pages.append(e)

    # Page 7 — Location & Travel
    e = discord.Embed(title="🗺️ Location & Travel", color=0x22C55E)
    e.add_field(name="/world generate [seed]", value="Generate a base world map via Pollinations.AI (visit the URL in your browser)", inline=False)
    e.add_field(name="/world map", value="Show the world map with all discovered locations", inline=False)
    e.add_field(name="/world load_template <name>", value="Load a pre-built world template (e.g. Murim/Magic)", inline=False)
    e.add_field(name="/world export / /world import", value="Export your world as JSON or import one (GM only)", inline=False)
    e.add_field(name="/location create <name> <type>", value="Create a new location (wizard with coordinates)", inline=False)
    e.add_field(name="/location connect <from> <to> <direction>", value="Link two locations with a directional exit", inline=False)
    e.add_field(name="/location edit <name>", value="Edit all location fields via modal (GM only)", inline=False)
    e.add_field(name="/location hide/reveal <name>", value="Toggle fog of war for a location (GM only)", inline=False)
    e.add_field(name="/location lock/unlock <name> <direction>", value="Lock or unlock a connection (GM only)", inline=False)
    e.add_field(name="/look", value="See your current location with description, time, weather, exits", inline=False)
    e.add_field(name="/travel <direction/location>", value="Move to a connected location", inline=False)
    e.add_field(name="/travel fast <location>", value="Fast travel to a previously discovered location", inline=False)
    e.add_field(name="/map", value="World map with your position highlighted", inline=False)
    e.add_field(name="/players-here", value="List everyone at your location", inline=False)
    e.add_field(name="/search", value="Roll d20+WIS to find secret exits or hidden items", inline=False)
    e.add_field(name="/gather", value="Collect resources from your location's resource nodes", inline=False)
    e.add_field(name="/discoveries", value="Paginated log of all locations you've visited", inline=False)
    e.set_footer(text="Page 3 / 10  —  Location & Travel")
    pages.append(e)

    # Page 8 — NPCs, Quests, Factions, Lore
    e = discord.Embed(title="👥 NPCs  ·  📜 Quests  ·  🏛️ Factions  ·  📚 Lore", color=0xA855F7)
    e.add_field(name="NPC Commands", value=(
        "`/npc create <name>` — Wizard: location, race, title, description, greeting\n"
        "`/npc edit <name>` — Edit all NPC fields via modal\n"
        "`/npc move <name> <location>` — Change NPC's location\n"
        "`/npc kill / revive <name>` — Mark NPC as dead or alive (GM only)\n"
        "`/npc list [location]` — Paginated NPC list\n"
        "`/npc talk <name> [message]` — Talk to an NPC (keyword dialogue)\n"
        "`/npc look <name>` — See NPC description and appearance\n"
        "`/npc speak <name> <message>` — GM speaks AS the NPC via webhook"
    ), inline=False)
    e.add_field(name="Quest Commands", value=(
        "`/quest create` — Multi-step wizard to build a quest\n"
        "`/quest list` — Available quests filtered by level\n"
        "`/quest accept <name>` — Accept a quest\n"
        "`/quest status` — Active quests with progress bars\n"
        "`/quest complete <name>` — Send GM approval embed\n"
        "`/quest journal` — Full quest history"
    ), inline=False)
    e.add_field(name="Faction Commands", value=(
        "`/faction create` — Wizard: name, description, type, color\n"
        "`/faction list` — All factions + your current tier with each\n"
        "`/faction status <name>` — Numeric rep, progress bar, perks\n"
        "`/faction history <name>` — Last 20 rep change events\n"
        "`/gm faction award <faction> <@user> <amount>` — Award faction rep"
    ), inline=False)
    e.add_field(name="Lore Commands", value=(
        "`/lore add <title>` — Add a lore entry via modal\n"
        "`/lore search <query>` — Top 5 results with relevance %\n"
        "`/lore view <title>` — Full lore entry\n"
        "`/lore list [category]` — Paginated lore list\n"
        "`/lore random` — Random lore entry"
    ), inline=False)
    e.set_footer(text="Page 4 / 10  —  NPCs, Quests, Factions & Lore")
    pages.append(e)

    # Page 9 — Training, Party, Time, Housing, Trade, Events
    e = discord.Embed(title="🎯 Training  ·  👥 Party  ·  ⏰ Time  ·  🏠 Housing  ·  🤝 Trade  ·  📅 Events", color=0x6366F1)
    e.add_field(name="Training", value=(
        "`/training start` — Open difficulty selection (Easy/Medium/Hard/Impossible)\n"
        "`/training stop` — End training session early\n"
        "Train against an AI dummy in chat-based combat!"
    ), inline=False)
    e.add_field(name="Party", value=(
        "`/party create [name]` — Form a group\n"
        "`/party invite @user` — Invite someone\n"
        "`/party leave / disband` — Leave or disband\n"
        "`/party status` — See all members, locations, HP\n"
        "`/party travel <direction>` — Leader travels, party follows"
    ), inline=False)
    e.add_field(name="Time & Weather", value=(
        "`/time` — Show world time, season, and day\n"
        "`/time advance <amount> <unit>` — Advance time (GM, manual mode)\n"
        "`/timemode <automatic/manual>` — Toggle time mode (owner only)\n"
        "`/weather` — Check current weather\n"
        "`/weather set <type>` — Override weather (GM only)"
    ), inline=False)
    e.add_field(name="Housing", value=(
        "`/house buy` — Purchase a Cave Dwelling (500 Spirit Stones)\n"
        "`/house upgrade` — Upgrade your dwelling to the next tier\n"
        "`/house view` — See your current dwelling\n"
        "`/house browse` — Browse all housing tiers, costs, and XP bonuses"
    ), inline=False)
    e.add_field(name="Trade & Events", value=(
        "`/trade request @user` — Open a trade\n"
        "`/trade offer <item> [qty]` — Add item to trade\n"
        "`/trade gold <amount>` — Add gold to trade\n"
        "`/trade accept / cancel` — Confirm or cancel\n"
        "`/event create <name> <datetime>` — Schedule an event (GM)\n"
        "`/event list` — Upcoming events\n"
        "`/event rsvp <event_id> <status>` — Mark attendance"
    ), inline=False)
    e.add_field(name="🌐 Other", value=(
        "`/tutorial` — Start or resume the 6-step new player tutorial\n"
        "`/tutorial reset @user` — Reset tutorial (GM only)\n"
        "`/announce <message>` — Post world announcement to configured channel (GM)"
    ), inline=False)
    e.set_footer(text="Page 5 / 10  —  Training, Party & More")
    pages.append(e)

    # Page 2 — Character
    e = discord.Embed(title="🧙 Character Commands", color=0x8B5CF6)
    e.add_field(
        name="/character create <name>",
        value="Choose **DnD** (race → class → **roll stats** → background → **pick attacks** → details) or **Custom** (free-form). DnD now uses **4d6-drop-lowest stat rolling** — pick from two sets! After creation, a **class tutorial** is sent via DM.",
        inline=False,
    )
    e.add_field(name="/character sheet", value="View your character sheet privately (includes **Explain My Class 📖** and **Edit Cosmetics ✏️** buttons)", inline=False)
    e.add_field(name="/character show", value="Post your character sheet to the channel", inline=False)
    e.add_field(name="/character list [public]", value="List all your characters including dead ones", inline=False)
    e.add_field(name="/character use / unuse", value="Set or clear your active character (auto-used in all commands)", inline=False)
    e.add_field(name="/character edit", value="Shows the split edit system info", inline=False)
    e.add_field(name="/character edit_cosmetic", value="Edit name, backstory, avatar, proxy — **instant**, no approval needed", inline=False)
    e.add_field(name="/character edit_stats <field> <value>", value="Request STR/DEX/CON/INT/WIS/CHA/Gold/XP/HP change — **GM approval required**", inline=False)
    e.add_field(name="/character proxy / proxy_remove", value="Set or remove proxy brackets & avatar for roleplay", inline=False)
    e.add_field(name="/character delete", value="Permanently delete a character", inline=False)
    e.add_field(name="\n📖 Class Codex", value="**`/classes browse`** — browse all classes with full details (hit die, stats, attacks, level milestones, tips)", inline=False)
    e.add_field(name="🎓 Tutorial System (via DM)", value="After creating a character, you'll get a **multi-page class tutorial sent via DM** (skippable) covering resources, attacks, leveling, and gameplay tips.", inline=False)
    e.add_field(name="🎯 Level-Up Attack Unlock (via DM)", value="At each level-up, the bot sends you a **DM** to **unlock a new attack** from your class's remaining attacks — you only pick 2 at creation!", inline=False)
    e.set_footer(text="Page 6 / 10  —  Character")
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
    e.set_footer(text="Page 7 / 10  —  Combat: Start & Join")
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
    e.set_footer(text="Page 8 / 10  —  Combat: Management & Conditions")
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
    e.set_footer(text="Page 9 / 10  —  Rest, Shop & Inventory")
    pages.append(e)

    # Page 6 — GM + Server Setup + Coming Soon (only shown to GMs)
    if not show_gm:
        # Skip GM page for non-GM users
        pass
    else:
        e = discord.Embed(title="🛡️ GM Commands  ·  ⚙️ Server Setup", description="🔒 **This page is only visible to GMs and server administrators.**", color=0x4F46E5)
        e.add_field(
            name="Server Setup *(Manage Server required)*",
            value=(
                "`/server setup <world_name> <gm_role>` — Configure LoreForge\n"
                "`/combat config log-channel <#ch>` — Set audit log channel"
            ),
            inline=False,
        )
        e.add_field(
            name="📦 Embed Builder (GM only)",
            value=(
                "`/embed create` — Open the full embed builder with modals and live preview\n"
                "`/embed template <type>` — Start from a template: announcement, quest, lore, npc, event, news\n"
                "*All embeds show live preview as you build. Post to current channel or pick a target channel.*"
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
                "`/gm edit [@user]` — **NEW!** Full GM edit panel (Level, Class, Race, Background, "
                "all 6 stats, HP Max, HP Current, Gold, AC in one modal) — instant, no approval queue\n"
                "`/gm sheet view [@user]` — View any player's character sheet(s)\n"
                "`/gm sheet edit @user` — Edit stats via split modal system (instant, no approval)\n"
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
            name="GM — World Tools",
            value=(
                "`/gm dashboard` — **World overview** (locations, NPCs, quests, factions, weather, time)\n"
                "`/world generate / map / load_template / export / import` — World building\n"
                "`/location create/edit/connect/hide/reveal/lock/unlock` — Manage locations\n"
                "`/npc create/edit/move/kill/revive/speak/act` — Manage NPCs\n"
                "`/quest create` — Build quests with objectives and rewards\n"
                "`/gm quest approve/deny` — Approve or deny quest completions\n"
                "`/faction create/edit/delete` — Manage factions\n"
                "`/gm faction award` — Award faction reputation\n"
                "`/lore add/edit/delete` — Create and manage lore events\n"
                "`/weather set <type>` — Override weather\n"
                "`/time advance <amount> <unit>` — Advance world time\n"
                "`/announce <message>` — Post world announcement"
            ),
            inline=False,
        )
        e.set_footer(text="Page 10 / 10  —  GM & Server")
        pages.append(e)

    # Update all footers dynamically so page count is always accurate
    for i, embed in enumerate(pages):
        footer = embed.footer.text or ""
        parts = footer.split(" — ", 1)
        section_name = parts[1].strip() if len(parts) > 1 else ""
        embed.set_footer(text=f"Page {i+1} / {len(pages)} — {section_name}")

    return pages


class HelpView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], page: int = 0):
        super().__init__(timeout=600)
        self.page = page
        self.pages = pages
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
        from services.utils import is_gm
        gm = await is_gm(interaction)
        pages = _help_pages(show_gm=gm)
        view = HelpView(pages=pages, page=0)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

    @commands.command(name="seed_world")
    @commands.is_owner()
    async def seed_world(self, ctx):
        from database.session import get_db
        from database.models import Location, LocationConnection
        from sqlalchemy import select

        LOCATIONS = [
            dict(name="Ironhold", location_type="city",      description="The iron-walled capital of the realm — a sprawling city of forges, guilds, and ambition. Safe haven for all who enter.", short_description="A fortified capital city at the crossroads of the world.", biome="urban",      map_x=50.0, map_y=50.0, is_safe=True,  is_indoors=False, is_hidden=False, danger_level=1, resources={}),
            dict(name="The Crimson Peaks", location_type="mountain",  description="Jagged peaks stained red by ancient ore veins and old blood. A treacherous highland claimed by rival clans.", short_description="Dangerous red-stone mountains north of Ironhold.", biome="mountain",   map_x=50.0, map_y=15.0, is_safe=False, is_indoors=False, is_hidden=False, danger_level=4, resources={"iron_ore": {"dc": 12, "max_qty": 3}, "bloodstone": {"dc": 18, "max_qty": 1}}),
            dict(name="Thornveil Forest", location_type="forest",    description="An ancient forest where the canopy blocks all light. Strange spirits drift between the trees and few emerge unchanged.", short_description="A dark, enchanted forest to the west.", biome="forest",     map_x=20.0, map_y=50.0, is_safe=False, is_indoors=False, is_hidden=False, danger_level=3, resources={"wood": {"dc": 8, "max_qty": 5}, "rare_herbs": {"dc": 15, "max_qty": 2}}),
            dict(name="Ashgate Ruins", location_type="ruins",     description="The crumbled remains of a forgotten empire. Dungeon entrances descend into darkness below the rubble.", short_description="Ancient ruins hiding deep dungeon systems to the east.", biome="underground", map_x=80.0, map_y=55.0, is_safe=False, is_indoors=False, is_hidden=False, danger_level=5, resources={"ancient_relics": {"dc": 20, "max_qty": 1}}),
            dict(name="Silverport", location_type="port",      description="A bustling port town where merchants, sailors, and smugglers trade under the silver moon. Coin flows freely here.", short_description="A wealthy southern port and trade hub.", biome="coastal",    map_x=50.0, map_y=85.0, is_safe=True,  is_indoors=False, is_hidden=False, danger_level=2, resources={"fish": {"dc": 8, "max_qty": 4}, "sea_salt": {"dc": 10, "max_qty": 3}}),
        ]

        CONNECTIONS = [
            ("Ironhold", "The Crimson Peaks", "north", "south", 60),
            ("Ironhold", "Thornveil Forest",  "west",  "east",  45),
            ("Ironhold", "Ashgate Ruins",     "east",  "west",  90),
            ("Ironhold", "Silverport",        "south", "north", 75),
        ]

        async with get_db() as db:
            created = {}
            for loc_data in LOCATIONS:
                existing = await db.execute(select(Location).where(Location.name == loc_data["name"], Location.guild_id == ctx.guild.id))
                if existing.scalar_one_or_none():
                    continue
                loc = Location(guild_id=ctx.guild.id, created_by=ctx.author.id, **loc_data)
                db.add(loc)
                await db.flush()
                created[loc.name] = loc.id

        async with get_db() as db:
            all_locs = await db.execute(select(Location).where(Location.guild_id == ctx.guild.id))
            loc_map = {l.name: l.id for l in all_locs.scalars().all()}
            for from_name, to_name, fwd_dir, rev_dir, travel_time in CONNECTIONS:
                if from_name not in loc_map or to_name not in loc_map:
                    continue
                for f, t, d in [(loc_map[from_name], loc_map[to_name], fwd_dir), (loc_map[to_name], loc_map[from_name], rev_dir)]:
                    ex = await db.execute(select(LocationConnection).where(LocationConnection.from_location_id == f, LocationConnection.to_location_id == t, LocationConnection.guild_id == ctx.guild.id))
                    if not ex.scalar_one_or_none():
                        db.add(LocationConnection(guild_id=ctx.guild.id, from_location_id=f, to_location_id=t, direction=d, label=None, is_locked=False, is_secret=False, travel_time_minutes=travel_time, search_dc=15))

        names = ", ".join(f"**{n}**" for n in loc_map.keys())
        await ctx.send(f"✅ World seeded!\n🗺️ Locations: {names}\n🔗 All connected to Ironhold (N/S/E/W)")


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
