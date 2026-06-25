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
    e.add_field(name="/location set-image <id>", value="Set a custom image for a location (GM only — attach a file)", inline=False)
    e.add_field(name="/world set-map", value="Upload a custom world map image (GM only — attach a file)", inline=False)
    e.add_field(name="/world clear-map", value="Reset to the AI-generated world map (GM only)", inline=False)
    e.add_field(name="/look", value="See your current location with description, time, weather, exits", inline=False)
    e.add_field(name="/look", value="See your current location with description, time, weather, exits, and NPCs", inline=False)
    e.add_field(name="/location view <name>", value="View any location's details and who's there (with autocomplete)", inline=False)
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
        "`/npc nearby` — See all NPCs at your current location\n"
        "`/npc talk <name> [message]` — Talk to an NPC (keyword or AI dialogue)\n"
        "`/npc look <name>` — See NPC description and appearance\n"
        "`/npc list [location]` — Paginated NPC list\n"
        "`/npc create <name>` — Wizard: location, race, title, description, greeting (GM)\n"
        "`/npc edit <name>` — Edit all NPC fields via modal (GM)\n"
        "`/npc move <name> <location>` — Change NPC's location (GM)\n"
        "`/npc kill / revive <name>` — Mark NPC as dead or alive (GM)\n"
        "`/npc speak <name> <msg>` — GM speaks AS the NPC via webhook (GM)\n"
        "`/npc act <name> <action>` — Post an RP action as the NPC (GM)\n"
        "`/npc possess <name>` — Claim an NPC; type its prefix to speak as it live (GM)\n"
        "`/npc release <name>` — Stop possessing an NPC (GM)\n"
        "`/npc mode <name> <auto/manual>` — Switch between automatic & manual proxy (GM)\n"
        "`/npc proxy-set <name>` — Set webhook display name, avatar, prefix (GM)"
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
    e.add_field(name="/character proxy / proxy_remove", value="Set or remove proxy brackets & avatar for roleplay\n• ❌ **React with ❌ on any proxy message to delete it** (you or a GM)", inline=False)
    e.add_field(name="/character delete", value="Permanently delete a character", inline=False)
    e.add_field(name="\n📖 Class Codex", value="**`/classes browse`** — browse all classes with full details (hit die, stats, attacks, level milestones, tips)", inline=False)
    e.add_field(name="🎓 Tutorial System (via DM)", value="After creating a character, you'll get a **multi-page class tutorial sent via DM** (skippable) covering resources, attacks, leveling, and gameplay tips.", inline=False)
    e.add_field(name="🎯 Level-Up Attack Unlock (via DM)", value="At each level-up, the bot sends you a **DM** to **unlock a new attack** from your class's remaining attacks — you only pick 2 at creation!", inline=False)
    e.add_field(
        name="🌌 Heavenly Demon Heir — Full HD Commands",
        value=(
            "**`/hd codex`** — 📖 Complete 10-page class compendium: all 24 forms, all 3 paths, "
            "Tao system, Nano system, sword control, level progression, ultimate techniques.\n"
            "**`/hd sheet`** — Full HD class sheet (Tao, path, swords, stance, forms, features)\n"
            "**`/hd path`** — Choose subclass (Heavenly/Blood/Elemental Demon, Lv3+)\n"
            "**`/hd elemental`** — Pick element (Fire/Lightning/Wind/Cold, Elemental Demon only)\n"
            "**`/hd stance`** — Toggle Dual Wield stance\n"
            "**`/hd flight`** — Sword Flight (Lv2)\n"
            "**`/hd phantom`** — Phantom Step teleport (Lv4, 1 Tao)\n"
            "**`/hd burst`** — Elemental Burst AoE (Lv6, 3 Tao)\n"
            "**`/hd manifest`** — Heavenly Demon Manifestation (Lv17, 8 Tao)\n"
            "**`/hd ascend`** — Absolute Heavenly Demon State (Lv20)\n"
            "**`/hd catastrophe`** — Forbidden Form: Catastrophe (Lv20, 20 Tao)\n"
            "**`/hd sword-rain`** — Sword Rain: Heavenly Demon Cataclysm (Lv20, 30 Tao)\n"
            "**`/hd swords control/attack/dismiss`** — Telekinetic sword control (Lv7+)\n"
            "**`/form list`** — View all 24 Demonic Sword Forms\n"
            "**`/form use`** — Activate a Demonic Form (select from autocomplete)\n"
            "**`/tao status`** — Current Tao, path, swords, features\n"
            "**`/tao restore`** — Full restore (long rest)\n"
            "**`/tao tick`** — Perfect Tao Circulation regen (Lv10+)\n"
            "*HD data auto-shows on your character sheet via `/character sheet`*"
        ),
        inline=False,
    )
    e.set_footer(text="Page 6 / 10  —  Character")
    pages.append(e)

    # Page 7 — Titles
    e = discord.Embed(title="⬡ Title System", color=0xF1C40F)
    e.description = "Earn and display titles that appear above your character's name in all embeds."
    e.add_field(
        name="Player Commands",
        value=(
            "`/title list` — see all your titles\n"
            "`/title set <name>` — display a title above your name\n"
            "`/title clear` — stop displaying a title\n"
            "`/title view <char>` — view another character's titles"
        ),
        inline=False,
    )
    e.add_field(
        name="GM Commands",
        value=(
            "`/gm title create <name> <tier>` — create a new title\n"
            "`/gm title award <char> <title>` — give a title to a character\n"
            "`/gm title revoke <char> <title>` — remove a title from a character\n"
            "`/gm title delete <title>` — permanently delete a title\n"
            "`/gm title list` — list all titles in this server"
        ),
        inline=False,
    )
    e.add_field(
        name="Tiers",
        value=(
            "· Common  |  ✦ Rare  |  ⬡ Epic  |  👑 Legendary  |  🔥 Mythic\n"
            "Each tier has its own color that changes the embed's sidebar when that title is active."
        ),
        inline=False,
    )
    e.set_footer(text="Page 7 / 10  —  Title System")
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
    e.set_footer(text="Page 8 / 10  —  Combat: Start & Join")
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
    e.set_footer(text="Page 9 / 10  —  Combat: Management & Conditions")
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

    # Page 10 — Phase 4: AI System, Sessions, Bosses, New Classes, Approvals
    e = discord.Embed(title="🤖 Phase 4 — AI, Bosses, Sessions & New Classes", color=0x7C3AED)
    e.add_field(
        name="🤖 AI System (toggle per guild)",
        value=(
            "`/ai toggle narration` — Toggle AI combat narration (on/off)\n"
            "`/ai toggle npc` — Toggle AI NPC dialogue generation\n"
            "`/ai toggle summary` — Toggle AI session summaries\n"
            "`/ai style <epic|gritty|comedic|minimal>` — Set narration style\n"
            "`/ai status` — View all AI toggles and current style\n"
            "*All AI features are OFF by default. Must be enabled per guild.*"
        ),
        inline=False,
    )
    e.add_field(
        name="📋 Session Management (GM only)",
        value=(
            "`/session start [title]` — Start a session log (pinned embed)\n"
            "`/session end` — End session, auto-summary if AI enabled\n"
            "`/session summary` — Generate/regenerate session summary\n"
            "`/session log` — Paginated list of past sessions (10 per page)"
        ),
        inline=False,
    )
    e.add_field(
        name="🗡️ Boss Commands (GM only)",
        value=(
            "`/gm boss create` — Create a new boss template (modal wizard)\n"
            "`/gm boss list` — List all boss templates for this guild\n"
            "`/gm boss spawn <name>` — Deploy a boss to current channel\n"
            "`/gm boss force-attack <@user>` — Boss focuses a player\n"
            "`/gm boss force-ability <name>` — Trigger a phase ability\n"
            "`/gm boss set-phase <n>` — Manually set boss phase\n"
            "`/gm boss hp <value>` — Set boss HP directly\n"
            "`/gm boss summon-minions` — Summon minions for active boss\n"
            "`/gm boss legendary <action>` — Use a legendary action\n"
            "`/gm boss kill` — Kill boss, award XP and loot\n"
            "`/gm boss flee` — Boss flees, award half XP"
        ),
        inline=False,
    )
    e.add_field(
        name="⚔️ Six New Classes",
        value=(
            "**Paladin** (d10, STR, Heavy) — Holy warrior with Divine Smite, Lay on Hands, Sacred Weapon\n"
            "**Ranger** (d10, DEX, Medium) — Hunter with Hunter's Mark, Volley, Conceal\n"
            "**Druid** (d8, WIS, Medium) — Nature caster with Thorn Whip, Healing Word, Entangle\n"
            "**Bard** (d8, CHA, Light) — Performer with Vicious Mockery, Cutting Words, Inspire\n"
            "**Monk** (d8, DEX, None) — Martial artist with Flurry of Blows, Stunning Strike, Step of the Wind\n"
            "**Sorcerer** (d6, CHA, None) — Raw power with Chaos Bolt, Twinned Fireball, Wild Surge"
        ),
        inline=False,
    )
    e.add_field(
        name="✨ Special Mechanics",
        value=(
            "• **Wild Shape** (`/character wildshape`) — Druids transform into Wolf/Bear/Eagle\n"
            "• **Ki Points** — Monks spend Ki on Flurry of Blows, Stunning Strike, Step of the Wind\n"
            "• **Bardic Inspiration** — Bards use Inspiration for Cutting Words and buffing allies\n"
            "• **Hunter's Mark** — Rangers mark targets for bonus damage\n"
            "• **Wild Surge** — Sorcerers roll d3 for random effects\n"
            "*Ki and Bardic Inspiration are tracked per character and reset on long rest.*"
        ),
        inline=False,
    )
    e.add_field(
        name="📋 GM Approval Queue",
        value=(
            "`/gm pending` — View all pending stat change requests\n"
            "`/gm pending-user <@user>` — View pending requests for a specific user\n"
            "`/gm approve <id>` — Approve and apply a pending request\n"
            "`/gm deny <id> [reason]` — Deny with optional reason\n"
            "*Cosmetic changes (name, backstory, avatar, proxy) are always instant.*"
        ),
        inline=False,
    )
    e.add_field(
        name="🌍 World Validation",
        value=(
            "`/world validate <attachment>` — Validate a world JSON file before importing\n"
            "Checks: required fields, location references, NPC location IDs, quest NPC IDs, boss minion templates\n"
            "*No DB writes — just validation. Re-import with confidence.*"
        ),
        inline=False,
    )
    e.set_footer(text="Page 10 / 11  —  Phase 4: AI, Bosses & New Classes")
    pages.append(e)

    # Page 11 — GM + Server Setup (only shown to GMs)
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
                "`/world set-map` — Upload custom world map image\n"
                "`/world clear-map` — Reset to AI-generated map\n"
                "`/world annotate <type> <x> <y>` — Add map overlay (road_block/danger_zone/icon/label)\n"
                "`/world annotations` — List all map overlay annotations\n"
                "`/world remove-annotation <id>` — Remove a map overlay annotation\n"
                "`/location create/edit/connect/hide/reveal/lock/unlock` — Manage locations\n"
                "`/location set-image <id>` — Set custom location image\n"
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
        e.set_footer(text="Page 11 / 11  —  GM & Server")
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
        from database.models import Location, LocationConnection, NPC
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

        NPC_SEEDS = [
            dict(location_name="Ironhold", name="Aldric Ironwall", title="Captain of the Guard", race="Human", gender="Male", age="45",
                 description="A weathered veteran with iron-grey hair and a battle-worn breastplate. Aldric has protected Ironhold for twenty years and speaks with the authority of someone who has seen every scheme and skirmish the city has to offer.",
                 appearance="Tall and broad-shouldered, with a scar running from jaw to ear and watchful grey eyes.",
                 disposition="neutral", is_hostile=False, is_killable=False, hp_max=60, hp_current=60, armor_class=16,
                 attack_bonus=6, damage_dice="1d8", damage_bonus=4, gold=50,
                 greeting="Halt. State your business in Ironhold, traveler.",
                 dialogue_topics={"crime": "We don't tolerate it here. Try anything and you'll see the inside of a cell.", "guard": "My men patrol day and night. Ironhold doesn't sleep.", "rumors": "There's been strange lights in the Ashgate direction. Nothing confirmed yet.", "quest": "If you're looking for work, speak to the guilds. I've no time for freelancers."},
                 proxy_name="Captain Aldric", proxy_avatar="https://i.imgur.com/XcxkTLb.png", proxy_prefix="aldric>", proxy_mode="automatic", xp_value=0),
            dict(location_name="Ironhold", name="Mira Ashforge", title="Master Blacksmith", race="Dwarf", gender="Female", age="112",
                 description="A compact dwarven smith with arms like oak branches and hands permanently blackened by forge-soot. Mira's weapons are known across three kingdoms — and she knows it.",
                 appearance="Short and powerful, with braided red hair threaded with iron beads and perpetually squinting eyes from decades of forge-light.",
                 disposition="friendly", is_hostile=False, is_killable=False, hp_max=40, hp_current=40, armor_class=12,
                 attack_bonus=4, damage_dice="1d6", damage_bonus=3, gold=500,
                 greeting="Aye, what do ye need? Weapons, armor, or just to gawk at a master at work?",
                 dialogue_topics={"weapons": "Best steel in the realm comes from my forge. None of that elven silver nonsense.", "repairs": "I can fix what's broken. Usually cheaper than buying new.", "crafting": "I don't teach. Too many apprentices and not enough talent in the lot of 'em.", "ironhold": "Built this forge with my own hands thirty years back. Ironhold grew around it, if you ask me."},
                 proxy_name="Mira Ashforge", proxy_avatar="https://i.imgur.com/8GqhVJK.png", proxy_prefix="mira>", proxy_mode="automatic", xp_value=0),
            dict(location_name="The Crimson Peaks", name="Rhogar Stoneclan", title="Elder of the Red Summit", race="Dwarf", gender="Male", age="300",
                 description="The ancient patriarch of the Stoneclan who has watched these peaks for three centuries. He speaks slowly, weighing each word as if it costs him something.",
                 appearance="Ancient and gnarled, with white-streaked red beard that reaches his belt and deep-set eyes that glow faintly amber in the dark.",
                 disposition="wary", is_hostile=False, is_killable=False, hp_max=50, hp_current=50, armor_class=13,
                 attack_bonus=5, damage_dice="1d6", damage_bonus=2, gold=200,
                 greeting="You walk where clan blood was spilled. Speak carefully.",
                 dialogue_topics={"clan": "The Stoneclan has held these peaks since before the lowland cities had names. We will hold them after.", "ore": "The red veins run deep. But some ore is better left buried.", "danger": "These peaks are alive. The stone remembers old hungers.", "history": "Three centuries is long enough to watch three empires rise and fall. And yet the peaks remain."},
                 proxy_name="Elder Rhogar", proxy_avatar="https://i.imgur.com/M7QK2Hv.png", proxy_prefix="rhogar>", proxy_mode="automatic", xp_value=0),
            dict(location_name="Thornveil Forest", name="Sylvara", title="Voice of the Ancient Wood", race="Dryad", gender="Female", age="Unknown",
                 description="A dryad spirit woven from bark and moonlight. Sylvara speaks in riddles and metaphors, communicating through whispers in the rustling leaves as much as through words.",
                 appearance="Tall and slender with bark-textured skin that shifts like shadows, emerald eyes that glow in darkness, and hair like autumn leaves that drift without wind.",
                 disposition="neutral", is_hostile=False, is_killable=False, hp_max=35, hp_current=35, armor_class=14,
                 attack_bonus=3, damage_dice="1d4", damage_bonus=2, gold=0,
                 greeting="*The leaves part around you.* The forest asks why you have come.",
                 dialogue_topics={"forest": "I am the forest. The forest is me. Do not ask the fire what burning feels like.", "spirits": "They are restless since the ruins were disturbed. Something was awoken.", "herbs": "What grows here has purpose. Take only what you need, and leave something in return.", "danger": "Three travelers entered last moon. The forest keeps them still. Tread with reverence."},
                 proxy_name="Sylvara", proxy_avatar="https://i.imgur.com/9TpYwCz.png", proxy_prefix="sylvara>", proxy_mode="automatic", xp_value=0),
            dict(location_name="Ashgate Ruins", name="Vex the Scholar", title="Antiquarian of the Fallen Empire", race="Human", gender="Male", age="38",
                 description="A gaunt, twitchy academic who has spent years in these ruins cataloguing what no sane person would stay to study. His robes are patched, his notes are everywhere, and his eyes dart constantly toward the deeper shadows.",
                 appearance="Pale and thin, with ink-stained fingers, round spectacles cracked on one lens, and a satchel that seems to contain half a library.",
                 disposition="friendly", is_hostile=False, is_killable=False, hp_max=20, hp_current=20, armor_class=10,
                 attack_bonus=1, damage_dice="1d4", damage_bonus=0, gold=10,
                 greeting="Oh! Another human — what a relief. I was beginning to think the echoes had started answering back.",
                 dialogue_topics={"ruins": "This was the Ashgate Empire's eastern vault. The seals were broken from the inside. That's — that's very unusual.", "danger": "The sub-levels are genuinely hazardous. I go no further than Level 2 now. Something ate my torch on Level 3.", "discovery": "I found a sealed chamber last week. The carvings match nothing in recorded history. I'm very excited and also slightly terrified.", "help": "If you're going deeper, bring light. And perhaps something to fight with. And run fast."},
                 proxy_name="Vex the Scholar", proxy_avatar="https://i.imgur.com/3RTpKcW.png", proxy_prefix="vex>", proxy_mode="automatic", xp_value=0),
            dict(location_name="Silverport", name="Harlan Dusk", title="Harbor Master", race="Human", gender="Male", age="55",
                 description="The ironhanded Harbor Master of Silverport who controls every ship berth, cargo manifest, and dockside dispute. Harlan knows where every coin in Silverport came from and where it's going.",
                 appearance="Heavyset with a sun-cracked face, sea-blue eyes, and a coat with so many pockets it's practically a filing system.",
                 disposition="neutral", is_hostile=False, is_killable=False, hp_max=45, hp_current=45, armor_class=11,
                 attack_bonus=3, damage_dice="1d6", damage_bonus=1, gold=300,
                 greeting="Dock fees are due before you unload anything. After that, welcome to Silverport.",
                 dialogue_topics={"trade": "Silverport moves more coin in a month than Ironhold sees in a year. Don't let the charm fool you — this is a city of business.", "ships": "I track every vessel. If it docked here, I know its cargo, crew, and destination.", "rumors": "Heard a black-sailed ship three nights back, no manifest. Didn't stop. Whatever it carried, someone didn't want records.", "smuggling": "We have none. Officially. Try harder next time."},
                 proxy_name="Harbor Master Dusk", proxy_avatar="https://i.imgur.com/K7Tl3Am.png", proxy_prefix="dusk>", proxy_mode="automatic", xp_value=0),
            dict(location_name="Silverport", name="Selia Brightcoin", title="Merchant of Rare Curiosities", race="Half-Elf", gender="Female", age="34",
                 description="A quick-tongued merchant who specializes in items of dubious origin and unquestionable value. Selia's stall is a chaos of artifacts, maps, and things that occasionally move on their own.",
                 appearance="Slim with coppery skin, silver hair cut sharply to one side, and an ever-present merchant's smile that never quite reaches her golden eyes.",
                 disposition="friendly", is_hostile=False, is_killable=False, hp_max=25, hp_current=25, armor_class=11,
                 attack_bonus=2, damage_dice="1d4", damage_bonus=1, gold=1000,
                 greeting="Ah, a discerning buyer! Come, come — I have something you didn't know you needed.",
                 dialogue_topics={"items": "Everything has a price. Some things just have a very interesting one.", "origin": "I never ask where things come from. It's better for everyone that way.", "rare": "Looking for something specific? Describe it. I may know someone who knows someone.", "haggling": "I respect a good haggle. Make your offer. We'll see if we can come to something beautiful."},
                 proxy_name="Selia Brightcoin", proxy_avatar="https://i.imgur.com/5VrQ8Jp.png", proxy_prefix="selia>", proxy_mode="automatic", xp_value=0),
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

        # Seed NPCs
        npc_count = 0
        async with get_db() as db:
            for npc_data in NPC_SEEDS:
                loc_name = npc_data.pop("location_name")
                loc_id = loc_map.get(loc_name)
                if not loc_id:
                    continue
                existing = await db.execute(
                    select(NPC).where(NPC.guild_id == ctx.guild.id, NPC.name == npc_data["name"])
                )
                if existing.scalar_one_or_none():
                    continue
                npc = NPC(guild_id=ctx.guild.id, location_id=loc_id, created_by=ctx.author.id, **npc_data)
                db.add(npc)
                npc_count += 1

        names = ", ".join(f"**{n}**" for n in loc_map.keys())
        await ctx.send(
            f"✅ World seeded!\n"
            f"🗺️ Locations: {names}\n"
            f"🔗 All connected to Ironhold (N/S/E/W)\n"
            f"👥 NPCs seeded: **{npc_count}** across all locations\n"
            f"*(Run `!seed_world` again to skip existing records)*"
        )


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
