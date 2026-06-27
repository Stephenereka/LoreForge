import discord
from discord import app_commands
from discord.ext import commands

# ── /help pages ───────────────────────────────────────────────────────────────

def _home_embed() -> discord.Embed:
    e = discord.Embed(
        title="⚔️ LoreForge — Getting Started",
        description=(
            "LoreForge turns your Discord server into a living RPG world.\n\n"
            "**New player? Start here:**\n"
            "1️⃣ `/classes browse` — pick your class\n"
            "2️⃣ `/character create <name>` — build your hero\n"
            "3️⃣ `/look` — see where you are\n"
            "4️⃣ `/travel <direction>` — explore the world\n\n"
            "**Select a category below to browse commands.**"
        ),
        color=0x8B5CF6,
    )
    e.add_field(
        name="📚 Categories",
        value=(
            "🧙 **Character** — create, edit, sheet, HD class\n"
            "⚔️ **Combat** — fight, conditions, training, titles\n"
            "🌍 **World & Travel** — explore, locations, NPCs, map\n"
            "📜 **Quests & Lore** — missions, codex, factions\n"
            "🔮 **Economy** — Spirit Stones, shop, housing, market\n"
            "🔍 **Investigations & Languages** — mysteries, language, religion\n"
            "🤖 **Sessions & AI** — session logs, AI features, bosses\n"
            "🎯 **Party & Events** — party up, train, schedule events\n"
            "🛡️ **GM Tools** — world management *(GMs only)*"
        ),
        inline=False,
    )
    e.set_footer(text="LoreForge — Use the dropdown below to browse all commands")
    return e


def _build_pages(show_gm: bool) -> dict[str, discord.Embed]:
    pages: dict[str, discord.Embed] = {}

    # ── Character ──────────────────────────────────────────────────────────────
    e = discord.Embed(title="🧙 Character", color=0x8B5CF6)
    e.add_field(name="Creating Your Hero", value=(
        "`/classes browse` — browse all classes (stats, attacks, milestones)\n"
        "`/character create <name>` — build your character\n"
        "• Roll **two stat sets** (4d6 drop lowest) and pick your favorite\n"
        "• Choose **2 starting attacks** from 6 class options\n"
        "• Receive a **class tutorial via DM** after creation"
    ), inline=False)
    e.add_field(name="Managing Your Character", value=(
        "`/character sheet` — view your stats (private)\n"
        "`/character show` — post your sheet publicly\n"
        "`/character use / unuse` — set or clear your active character\n"
        "`/character list` — all your characters including retired ones\n"
        "`/character edit_cosmetic` — change name, backstory, avatar, proxy *(instant)*\n"
        "`/character edit_stats <field> <value>` — request stat change *(GM approval)*\n"
        "`/character proxy / proxy_remove` — set roleplay proxy brackets\n"
        "• React ❌ on any proxy message to delete it"
    ), inline=False)
    e.add_field(name="🌌 Heavenly Demon Heir (HD Class)", value=(
        "`/hd codex` — full compendium: 24 forms, 3 paths, Tao/Nano system\n"
        "`/hd sheet` — your HD class sheet\n"
        "`/hd path` — choose subclass (Heavenly/Blood/Elemental, Lv3+)\n"
        "`/hd burst / manifest / ascend / catastrophe` — high-level abilities\n"
        "`/form use` — activate a Demonic Sword Form\n"
        "`/tao status / restore / tick` — manage your Tao resource"
    ), inline=False)
    e.add_field(name="Other", value=(
        "`/character wildshape` — Druids transform (Wolf/Bear/Eagle)\n"
        "• At each level-up a **DM arrives** to unlock a new attack"
    ), inline=False)
    e.set_footer(text="LoreForge — Character")
    pages["character"] = e

    # ── Combat ─────────────────────────────────────────────────────────────────
    e = discord.Embed(title="⚔️ Combat", color=0xEF4444)
    e.add_field(name="Starting a Fight", value=(
        "`/combat start <title> <type> [@invite]` — open a lobby (DnD or Manual)\n"
        "`/combat join` — join an open lobby\n"
        "`/combat invite @user` — invite someone mid-fight\n"
        "**DnD fights:** type your action as RP — bot reads, confirms, rolls dice\n"
        "**Manual fights:** declare freely — GM resolves via `/combat hp`"
    ), inline=False)
    e.add_field(name="During Combat", value=(
        "`/combat status` — check state (private)\n"
        "`/combat overview` — post live status embed publicly\n"
        "`/combat hp <amount> [@target]` — update HP: `+5`, `-10`, or `25` (absolute)\n"
        "`/combat edit <field> <value>` — edit Temp HP or conditions\n"
        "`/combat log` — recent action log\n"
        "`/combat forfeit` — leave mid-fight\n"
        "`/combat end` — end fight (GM or host)\n"
        "`/combat pause / resume` — pause a manual fight"
    ), inline=False)
    e.add_field(name="⚡ Conditions", value=(
        "**DoT:** 🤢 Poisoned · 🔥 Burning · 🩸 Bleeding\n"
        "**Status:** ⭐ Stunned · 🫥 Blinded · 😨 Frightened · ⬇️ Prone · 🤜 Grappled\n"
        "**Buffs:** 🛡️ Parrying (+2 AC) · ✨ Shielded (+5 AC) · 💢 Raging · 👁️ Hidden\n"
        "**Debuffs:** 🔮 Hexed (+1d6 on hits) · 🔴 Reckless (−2 AC)"
    ), inline=False)
    e.add_field(name="Titles & Rolling", value=(
        "`/title list / set / clear` — earn and display titles above your name\n"
        "`/training start` — practice vs an AI dummy (Easy→Impossible)\n"
        "`/roll 2d6+3` — roll dice with standard RPG notation"
    ), inline=False)
    e.set_footer(text="LoreForge — Combat")
    pages["combat"] = e

    # ── World & Travel ─────────────────────────────────────────────────────────
    e = discord.Embed(title="🌍 World & Travel", color=0x22C55E)
    e.add_field(name="Exploration", value=(
        "`/look` — see your location: description, time, weather, exits, NPCs\n"
        "`/travel <direction/location>` — move to a connected location\n"
        "`/travel fast <location>` — fast travel to a discovered location\n"
        "`/map` — world map with your position highlighted\n"
        "`/players-here` — list everyone at your location\n"
        "`/search` — roll d20+WIS to find secrets or hidden items\n"
        "`/gather` — collect resources from this location\n"
        "`/discoveries` — log of all locations you've visited"
    ), inline=False)
    e.add_field(name="NPCs", value=(
        "`/npc nearby` — see NPCs at your location\n"
        "`/npc talk <name> [message]` — talk to an NPC (keyword or AI dialogue)\n"
        "`/npc look <name>` — NPC description and appearance\n"
        "`/npc list [location]` — paginated NPC list"
    ), inline=False)
    e.add_field(name="Time & Weather", value=(
        "`/time` — world time, season, and day\n"
        "`/weather` — check current weather"
    ), inline=False)
    e.set_footer(text="LoreForge — World & Travel")
    pages["world"] = e

    # ── Quests & Lore ──────────────────────────────────────────────────────────
    e = discord.Embed(title="📜 Quests · Lore · Factions", color=0xA855F7)
    e.add_field(name="Quests", value=(
        "`/quest list` — available quests (filtered by level)\n"
        "`/quest accept <name>` — accept a quest\n"
        "`/quest status` — active quests with progress bars\n"
        "`/quest complete <name>` — submit for GM approval\n"
        "`/quest journal` — full quest history"
    ), inline=False)
    e.add_field(name="Lore & Codex", value=(
        "`/codex <query>` — search **everything** at once: lore, NPCs, locations, factions, bestiary\n"
        "`/lore search <query>` — top 5 lore matches with relevance score\n"
        "`/lore view <title>` — full lore entry\n"
        "`/lore list [category]` — browse all lore\n"
        "`/lore random` — random lore entry"
    ), inline=False)
    e.add_field(name="Factions", value=(
        "`/faction list` — all factions + your current tier with each\n"
        "`/faction status <name>` — reputation, progress bar, and perks\n"
        "`/faction history <name>` — last 20 reputation change events"
    ), inline=False)
    e.set_footer(text="LoreForge — Quests, Lore & Factions")
    pages["quests"] = e

    # ── Economy ────────────────────────────────────────────────────────────────
    e = discord.Embed(title="🔮 Economy · 🏪 Shop · 🏠 Housing · 🛒 Market", color=0x6B21A8)
    e.add_field(name="Spirit Stones (Currency)", value=(
        "`/economy balance` — your current balance\n"
        "`/economy daily` — daily reward with streak bonus (200→350→500→750)\n"
        "`/economy pay @user <amount>` — send Spirit Stones\n"
        "`/economy leaderboard` — top 10 richest cultivators"
    ), inline=False)
    e.add_field(name="Shop & Inventory", value=(
        "`/shop browse` — weapons, armor, and potions\n"
        "`/shop buy <item>` — purchase\n"
        "`/shop sell <item>` — sell for half price\n"
        "`/inventory view` — your items\n"
        "`/inventory equip <item>` — equip gear\n"
        "`/inventory use <item>` — use a potion"
    ), inline=False)
    e.add_field(name="Housing", value=(
        "`/house buy` — Cave Dwelling (Tier 1 — 500 Spirit Stones)\n"
        "`/house upgrade` — upgrade (up to Tier 5 Sovereign Palace)\n"
        "`/house view` — your dwelling and XP bonus\n"
        "`/house browse` — all tiers, costs, and bonuses"
    ), inline=False)
    e.add_field(name="Player Market & Auctions", value=(
        "`/market post <item> <price>` — list an item for sale\n"
        "`/market browse / buy <id>` — browse and purchase listings\n"
        "`/auction create <item> <price> <hours>` — start an auction (1–72h)\n"
        "`/auction bid <id> <amount>` — place a bid (outbid refunds previous bidder)\n"
        "`/auction browse` — all active auctions\n"
        "`/trade request @user` — open a direct player trade"
    ), inline=False)
    e.add_field(name="💤 Rest", value=(
        "`/rest short` — roll hit dice to recover HP\n"
        "`/rest long` — full HP + all class resources restored"
    ), inline=False)
    e.set_footer(text="LoreForge — Economy & Commerce")
    pages["economy"] = e

    # ── Deep Lore ──────────────────────────────────────────────────────────────
    e = discord.Embed(title="🔍 Investigations · 🗣️ Languages · ⛪ Religion", color=0x7C3AED)
    e.add_field(name="Investigations (Mystery System)", value=(
        "`/investigation clue <name> <text>` — add a clue you discovered\n"
        "`/investigation board [name]` — evidence board with connected clues\n"
        "`/investigation connect <id_a> <id_b>` — link two clues\n"
        "`/investigation theory <name> <text>` — submit a theory (DMs the GM)\n"
        "`/investigation list` — all open investigations"
    ), inline=False)
    e.add_field(name="Languages", value=(
        "`/language learn <name>` — learn a language (500 Spirit Stones)\n"
        "`/language list` — all languages with speaker counts\n"
        "`/language speak <name> <msg>` — speak in a language\n"
        "*(Others see scrambled text if they don't know the language)*"
    ), inline=False)
    e.add_field(name="Religion & Prayer", value=(
        "`/religion list` — all religions\n"
        "`/religion view <name>` — full details (deity, domains, tenets, followers)\n"
        "`/religion worship <name>` — set your character's religion\n"
        "`/prayer` — 1/day divine blessing (1d20+WIS, 15+: gain 2d6 temp HP)"
    ), inline=False)
    e.add_field(name="📜 Timeline & Visions", value=(
        "`/timeline view` — chronological world history (10 events per page)\n"
        "`/character visions` — your character's received visions\n"
        "`/notifications configure` — toggle DMs for faction, quest, and world events\n"
        "*Visions appear automatically after long rests (20% chance)*"
    ), inline=False)
    e.set_footer(text="LoreForge — Investigations, Languages & Religion")
    pages["deep_lore"] = e

    # ── Sessions & AI ──────────────────────────────────────────────────────────
    e = discord.Embed(title="🤖 AI System · 📋 Sessions · 👹 Bosses", color=0x4F46E5)
    e.add_field(name="AI System", value=(
        "`/ai toggle narration` — AI combat narration (on/off)\n"
        "`/ai toggle npc` — AI NPC dialogue generation\n"
        "`/ai toggle summary` — AI session summaries\n"
        "`/ai style <epic|gritty|comedic|minimal>` — narration style\n"
        "`/ai status` — view all current AI settings\n"
        "*All AI features are **OFF** by default — enable per guild*"
    ), inline=False)
    e.add_field(name="Sessions (GM only)", value=(
        "`/session start [title]` — start a session log (pins embed)\n"
        "`/session end` — end session + auto AI recap posted to recap channel\n"
        "`/session summary` — regenerate the AI summary\n"
        "`/session log` — paginated list of past sessions"
    ), inline=False)
    e.add_field(name="Bosses (GM only)", value=(
        "`/gm boss spawn <name>` — deploy a boss to this channel\n"
        "`/gm boss list` — all boss templates\n"
        "`/gm boss force-attack / force-ability / legendary` — control the fight\n"
        "`/gm boss hp / set-phase / summon-minions` — manage boss state\n"
        "`/gm boss kill / flee` — end the encounter"
    ), inline=False)
    e.set_footer(text="LoreForge — AI, Sessions & Bosses")
    pages["sessions_ai"] = e

    # ── Social & Party ─────────────────────────────────────────────────────────
    e = discord.Embed(title="🎯 Training · 👥 Party · 📅 Events", color=0x6366F1)
    e.add_field(name="Training", value=(
        "`/training start` — practice vs an AI dummy (Easy/Medium/Hard/Impossible)\n"
        "`/training stop` — end training early"
    ), inline=False)
    e.add_field(name="Party", value=(
        "`/party create [name]` — form a group\n"
        "`/party invite @user` — invite a player\n"
        "`/party leave / disband` — leave or disband\n"
        "`/party status` — all members, locations, and HP\n"
        "`/party travel <direction>` — leader travels, party follows"
    ), inline=False)
    e.add_field(name="Events & Other", value=(
        "`/event list` — upcoming server events\n"
        "`/event rsvp <id> <status>` — mark your attendance\n"
        "`/tutorial` — 6-step new player tutorial"
    ), inline=False)
    e.set_footer(text="LoreForge — Party & Events")
    pages["social"] = e

    # ── GM Tools ───────────────────────────────────────────────────────────────
    if show_gm:
        e = discord.Embed(
            title="🛡️ GM Tools",
            description="🔒 Visible to GMs and server administrators only.",
            color=0xDC2626,
        )
        e.add_field(name="Setup & Config", value=(
            "`/server setup <world_name> <gm_role>` — configure LoreForge\n"
            "`/config set-recap-channel <#ch>` — AI session recap channel\n"
            "`/combat config log-channel <#ch>` — audit log channel"
        ), inline=False)
        e.add_field(name="Characters & Approvals", value=(
            "`/gm edit [@user]` — full edit panel (all stats in one modal, instant)\n"
            "`/gm xp @user <amount>` — award XP (triggers level-up if threshold hit)\n"
            "`/gm revive <name>` — revive dead character at 1 HP\n"
            "`/gm pending` — pending stat change requests\n"
            "`/gm approve <id> / deny <id> [reason]` — approve or deny requests"
        ), inline=False)
        e.add_field(name="World Building", value=(
            "`/world generate / map / load-template / validate` — world tools\n"
            "`/world set-map / clear-map / annotate` — custom map management\n"
            "`/location create / edit / connect / hide / reveal / lock` — locations\n"
            "`/npc create / edit / move / kill / speak / possess / act` — NPCs\n"
            "`/faction create / edit / delete` — factions\n"
            "`/gm faction award <faction> <@user> <amount>` — award rep\n"
            "`/quest create` — build quests\n"
            "`/lore add / edit / delete` — lore entries\n"
            "`/lore add-template <type> <title>` — structured lore template\n"
            "`/weather set / time advance / announce` — world state"
        ), inline=False)
        e.add_field(name="AI Generation & Phase 6 Tools", value=(
            "`/gm generate quest/npc/encounter` — AI-generate content (preview + Save/Regen)\n"
            "`/gm world-pulse` — manually trigger the living world simulation\n"
            "`/gm vision <@user> <text>` — send a custom vision to a player\n"
            "`/npc-letter <@user> <content>` — send an in-character letter via DM\n"
            "`/investigation start / reveal` — manage mystery investigations\n"
            "`/language create / add-phrase` — create languages\n"
            "`/religion create / edit / set-deity / add-tenet` — manage religions\n"
            "`/timeline add <title> <desc> / era <name>` — timeline management"
        ), inline=False)
        e.add_field(name="Other GM Tools", value=(
            "`/embed create / template <type>` — embed builder\n"
            "`/gm title create / award / revoke / delete` — title management\n"
            "`/gm add / remove / list` — GM roster *(server owner only)*\n"
            "`/gm dashboard` — world overview\n"
            "`/gm quest approve / deny` — approve quest completions\n"
            "`/auction end <id>` — force-end an auction\n"
            "`/tutorial reset @user` — reset a player's tutorial"
        ), inline=False)
        e.set_footer(text="LoreForge — GM Tools")
        pages["gm"] = e

    return pages


# kept for compatibility — not used by the new HelpView
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
    e.add_field(name="/world load-template [murim_magic]", value="Seed all locations, NPCs, factions, quests, lore, and bosses from a built-in template — skips anything already created (GM only)", inline=False)
    e.add_field(name="/world validate <json>", value="Validate a world JSON file before importing (no DB writes)", inline=False)
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

    # Page 11 — Phase 6 Tier 2: Investigation, Language, Timeline, Religion, Codex, Notifications, Visions
    e = discord.Embed(title="🔍 Phase 6 — Investigation, Languages, Timeline & Religion", color=0x7C3AED)
    e.add_field(name="📖 Unified Codex Search", value=(
        "`/codex <query>` — Search **Lore**, **NPCs**, **Locations**, **Factions**, and **Bestiary** all at once (ILIKE match)\n"
        "*Shows first 3 matches per category in a single embed.*"
    ), inline=False)
    e.add_field(name="🔍 Investigations", value=(
        "`/investigation start <name> <desc>` — Start an investigation (GM only)\n"
        "`/investigation clue <inv_name> <text>` — Add a clue you discovered\n"
        "`/investigation board [inv_name]` — Evidence board with connected clues\n"
        "`/investigation connect <id_a> <id_b>` — Link two clues together\n"
        "`/investigation theory <inv_name> <text>` — Submit a theory (DMs the GM)\n"
        "`/investigation reveal <inv_name> <text>` — Big reveal! (GM only)\n"
        "`/investigation list` — List all open investigations"
    ), inline=False)
    e.add_field(name="🗣️ Languages", value=(
        "`/language create <name> [script]` — Create a language (GM only)\n"
        "`/language learn <name>` — Learn a language (costs 500 Spirit Stones)\n"
        "`/language list` — List all languages with speakers\n"
        "`/language speak <name> <msg>` — Speak in a language (scrambled if unknown)\n"
        "`/language add-phrase <name> <word> <trans>` — Add vocabulary (GM only)"
    ), inline=False)
    e.add_field(name="📜 Timeline", value=(
        "`/timeline view [page]` — Chronological world events (10 per page)\n"
        "`/timeline add <title> <desc>` — Add a manual event (GM only)\n"
        "`/timeline era <name>` — Set the current world era (GM only)"
    ), inline=False)
    e.add_field(name="⛪ Religion & Prayer", value=(
        "`/religion create <name> [deity] [domains]` — Found a religion (GM only)\n"
        "`/religion list` — List all religions\n"
        "`/religion view <name>` — Full details (deity, domains, tenets, followers)\n"
        "`/religion edit <name>` — Edit clergy notes & holy symbol (GM only)\n"
        "`/religion set-deity <name> <deity>` — Set the deity (GM only)\n"
        "`/religion add-tenet <name> <tenet>` — Add a tenet (GM only)\n"
        "`/religion worship <name>` — Set your character's religion\n"
        "`/prayer` — 1/day divine blessing (1d20+WIS, 15+: gain 2d6 temp HP)"
    ), inline=False)
    e.add_field(name="💫 Visions & Dreams", value=(
        "`/character visions [name]` — View your character's received visions (paginated)\n"
        "*Visions come from long rests (20% chance) and GM custom commands.*"
    ), inline=False)
    e.add_field(name="🔔 Notifications", value=(
        "`/notifications configure` — Toggle DMs for: Faction changes, Quests, World events, NPC movements, Lore unlocks"
    ), inline=False)
    e.add_field(name="📜 AI Session Recaps", value=(
        "`/session end` — Now **auto-generates** a narrated session recap!\n"
        "Poster to the configured recap channel and saved as a LoreEntry (GM-only visibility).\n"
        "*Uses DeepSeek AI to write a 3-paragraph fantasy chronicle.*"
    ), inline=False)
    e.set_footer(text="Page 11 / 12 — Phase 6: Investigation, Languages & Religion")
    pages.append(e)

    # Page 12 — GM + Server Setup (only shown to GMs)
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
                "`/world generate / map / load-template / validate` — World building\n"
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
                "`/lore add-template <type> <title>` — Create a lore entry using a structured template\n"
                "`/weather set <type>` — Override weather\n"
                "`/time advance <amount> <unit>` — Advance world time\n"
                "`/announce <message>` — Post world announcement"
            ),
            inline=False,
        )
        e.add_field(
            name="GM — Phase 6 Tools",
            value=(
                "`/gm generate quest [diff] [loc] [theme]` — AI-generate a quest (preview + Save/Regen/Discard)\n"
                "`/gm generate npc [loc] [role]` — AI-generate an NPC\n"
                "`/gm generate encounter [diff] [loc]` — AI-generate a combat encounter (as boss template)\n"
                "`/gm world-pulse` — Manually trigger the living world simulation tick\n"
                "`/gm vision <@user> <text>` — Send a custom vision/dream to a player\n"
                "`/npc-letter <@user> <content>` — Send an in-character letter to a player (DM)\n"
                "`/timeline add <title> <desc>` — Add a manual timeline event\n"
                "`/timeline era <name>` — Set the current world era\n"
                "`/lore add-template <type> <title>` — Create a lore entry with a structured template"
            ),
            inline=False,
        )
        e.set_footer(text="Page 12 / 12  —  GM & Server")
        pages.append(e)

    # Update all footers dynamically so page count is always accurate
    for i, embed in enumerate(pages):
        footer = embed.footer.text or ""
        parts = footer.split(" — ", 1)
        section_name = parts[1].strip() if len(parts) > 1 else ""
        embed.set_footer(text=f"Page {i+1} / {len(pages)} — {section_name}")

    return pages


class HelpView(discord.ui.View):
    def __init__(self, show_gm: bool = False):
        super().__init__(timeout=600)
        self.show_gm = show_gm
        self.pages = _build_pages(show_gm)
        self._add_select()

    def _add_select(self):
        options = [
            discord.SelectOption(label="Getting Started", value="home", emoji="🏠", description="Quick start guide for new players"),
            discord.SelectOption(label="Character", value="character", emoji="🧙", description="Create, edit, and manage your character"),
            discord.SelectOption(label="Combat", value="combat", emoji="⚔️", description="Fight mechanics, conditions, training"),
            discord.SelectOption(label="World & Travel", value="world", emoji="🌍", description="Explore, travel, NPCs, map"),
            discord.SelectOption(label="Quests, Lore & Factions", value="quests", emoji="📜", description="Missions, codex search, factions"),
            discord.SelectOption(label="Economy & Market", value="economy", emoji="🔮", description="Spirit Stones, shop, housing, auctions"),
            discord.SelectOption(label="Investigations, Languages & Religion", value="deep_lore", emoji="🔍", description="Mystery system, languages, religion, timeline"),
            discord.SelectOption(label="Sessions & AI", value="sessions_ai", emoji="🤖", description="Session logs, AI features, bosses"),
            discord.SelectOption(label="Training, Party & Events", value="social", emoji="🎯", description="Party up, train, schedule events"),
        ]
        if self.show_gm:
            options.append(discord.SelectOption(label="GM Tools", value="gm", emoji="🛡️", description="World management (GM only)"))

        select = discord.ui.Select(
            placeholder="📖 Browse categories...",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        embed = _home_embed() if value == "home" else self.pages.get(value, _home_embed())
        await interaction.response.edit_message(embed=embed, view=self)

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


# ── /config group ─────────────────────────────────────────────────────────────

config_group = app_commands.Group(
    name="config",
    description="Server configuration commands",
)


@config_group.command(name="set-recap-channel", description="Set the channel for session recaps (GM only)")
@app_commands.describe(channel="The channel to post session recaps in")
async def config_set_recap_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    from services.utils import is_gm
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can use this.", ephemeral=True)
        return
    from database.session import get_db
    from database.models import GuildConfig
    from sqlalchemy import select
    async with get_db() as db:
        result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            config = GuildConfig(guild_id=interaction.guild_id)
            db.add(config)
        config.session_recap_channel_id = channel.id
    await interaction.response.send_message(
        f"✅ Session recaps will be posted to {channel.mention}.", ephemeral=True
    )


# ── Admin cog (top-level utility commands) ────────────────────────────────────

class AdminCog(commands.Cog, name="Admin"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(server_group)
        bot.tree.add_command(config_group)

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
        view = HelpView(show_gm=gm)
        await interaction.response.send_message(embed=_home_embed(), view=view, ephemeral=True)

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

    @commands.command(name="seed_bosses")
    @commands.is_owner()
    async def seed_bosses(self, ctx):
        """Seed 3 pre-built D&D boss templates into this server."""
        from database.session import get_db
        from database.models import BossTemplate
        from sqlalchemy import select

        BOSSES = [
            dict(
                name="Malvaxis the Undying",
                title="Lord of the Eternal Tomb",
                description=(
                    "An ancient lich who transcended death centuries ago and now rules a sprawling undead fortress "
                    "beneath the Ashgate Ruins. His phylactery is hidden deep within his lair — defeat him without "
                    "finding it and he simply reforms. Cold, calculating, and utterly without mercy, Malvaxis views "
                    "living beings as raw material for his undead armies."
                ),
                hp_max=300,
                armor_class=17,
                attack_bonus=9,
                damage_dice="3d10",
                damage_bonus=5,
                xp_value=15000,
                gold_drop=500,
                phase_count=3,
                phase_thresholds=[0.5, 0.25],
                phase_abilities={
                    "2": {
                        "name": "Awaken the Dead",
                        "description": (
                            "Malvaxis tears at the veil — 1d4 skeleton warriors claw from the ground at the start "
                            "of each of his turns (AC 13, 26 HP). His eyes ignite with violet flame and his attacks "
                            "deal an additional 2d8 necrotic damage."
                        ),
                    },
                    "3": {
                        "name": "Lichform Unbound",
                        "description": (
                            "The lich sheds his mortal pretense entirely. His form becomes partially incorporeal "
                            "— he gains resistance to all non-magical damage. His legendary action count increases "
                            "to 5. The air temperature drops 20 degrees and undead creatures in the room are healed "
                            "for 10 HP at the start of each round."
                        ),
                    },
                },
                legendary_actions=[
                    {"name": "Cantrip", "description": "Casts Chill Touch — target cannot regain HP until start of Malvaxis's next turn.", "cost": 0},
                    {"name": "Soul Drain", "description": "One target takes 2d8+5 necrotic damage and loses 1d4 from their next attack roll.", "cost": 1},
                    {"name": "Void Burst", "description": "All creatures within 20 ft take 4d10 necrotic damage, DC 16 CON save for half. The ground in the area becomes difficult terrain (bone shards).", "cost": 2},
                ],
                legendary_action_count=3,
                is_lair_boss=True,
                lair_actions=[
                    {"name": "Necrotic Surge", "description": "Necrotic energy surges from the floor — one creature must make a DC 15 CON save or take 3d8 necrotic damage and have their max HP reduced by that amount until a long rest.", "initiative_count": 20},
                    {"name": "Gravewalk", "description": "Malvaxis phases through walls and reappears anywhere within 60 ft of his original position. This movement does not provoke opportunity attacks.", "initiative_count": 10},
                    {"name": "Bone Cage", "description": "Skeletal arms erupt from the ground to grapple one creature — DC 16 STR to escape. The creature is restrained until they break free.", "initiative_count": 5},
                ],
                loot_table=[
                    {"item": "Phylactery Shard", "chance": 0.30, "qty_min": 1, "qty_max": 1},
                    {"item": "Staff of the Undying", "chance": 0.10, "qty_min": 1, "qty_max": 1},
                    {"item": "Lich Crown Fragment", "chance": 0.20, "qty_min": 1, "qty_max": 1},
                    {"item": "Necrotic Essence", "chance": 0.80, "qty_min": 1, "qty_max": 3},
                    {"item": "Ancient Gold Coins", "chance": 1.00, "qty_min": 200, "qty_max": 500},
                ],
            ),
            dict(
                name="Ignarok the Flame Tyrant",
                title="Scourge of the Crimson Peaks",
                description=(
                    "An adult red dragon who has terrorized the Crimson Peaks for three hundred years. Ignarok's "
                    "hoard is legendary — piled deep within a volcanic lair where the walls run with molten rock. "
                    "He is arrogant, theatrical, and takes great pleasure in monologuing before incinerating "
                    "anything that dares challenge him. His breath weapon can incinerate an armored knight instantly."
                ),
                hp_max=256,
                armor_class=19,
                attack_bonus=13,
                damage_dice="2d6",
                damage_bonus=8,
                xp_value=12000,
                gold_drop=1000,
                phase_count=2,
                phase_thresholds=[0.40],
                phase_abilities={
                    "2": {
                        "name": "Volcanic Rage",
                        "description": (
                            "Ignarok takes to the air — he becomes immune to ground-based effects and gains the "
                            "ability to use his Fire Breath as a bonus action (recharge 5–6). His roar shakes the "
                            "cavern: all creatures make a DC 18 CON save or be deafened for 1 minute. Each melee "
                            "hit against him causes 1d6 fire damage back to the attacker from his superheated scales."
                        ),
                    },
                },
                legendary_actions=[
                    {"name": "Detect", "description": "Ignarok makes a Wisdom (Perception) check — reveals hidden creatures within 60 ft.", "cost": 0},
                    {"name": "Tail Swipe", "description": "One creature within 15 ft takes 2d8+8 bludgeoning damage, DC 21 STR or be knocked prone.", "cost": 1},
                    {"name": "Wing Attack", "description": "All creatures within 15 ft take 2d6+8 bludgeoning damage, DC 19 STR or be knocked back 10 ft and knocked prone. Ignarok can then fly up to half his speed.", "cost": 2},
                    {"name": "Fire Breath (Recharge)", "description": "60-ft cone of fire — 16d6 fire damage, DC 21 DEX save for half. Can only be used if the ability is recharged (roll 5–6).", "cost": 3},
                ],
                legendary_action_count=3,
                is_lair_boss=True,
                lair_actions=[
                    {"name": "Lava Burst", "description": "Magma erupts from fissures — 10-ft radius area of the GM's choice becomes lava terrain (5d10 fire on entry, 5 ft movement costs 10 ft). Lasts 1 minute.", "initiative_count": 20},
                    {"name": "Volcanic Smoke", "description": "Thick volcanic smoke fills a 40-ft radius area — all creatures in it are heavily obscured and must succeed a DC 14 CON save or be poisoned (disadvantage on attacks) for 1 round.", "initiative_count": 10},
                    {"name": "Seismic Tremor", "description": "The lair shudders — all creatures on the ground make a DC 15 DEX save or be knocked prone. Structures in the lair take 2d10 bludgeoning damage.", "initiative_count": 5},
                ],
                loot_table=[
                    {"item": "Dragon Scale (Red)", "chance": 0.40, "qty_min": 2, "qty_max": 6},
                    {"item": "Dragon Fang", "chance": 0.60, "qty_min": 1, "qty_max": 3},
                    {"item": "Fire Gem", "chance": 0.50, "qty_min": 1, "qty_max": 2},
                    {"item": "Ancient Hoard Coin", "chance": 1.00, "qty_min": 500, "qty_max": 1000},
                    {"item": "Ignarok's Crown Scale", "chance": 0.15, "qty_min": 1, "qty_max": 1},
                ],
            ),
            dict(
                name="The Shadowreaver",
                title="Blade of the Void",
                description=(
                    "A shadow demon fused with the soul of a master assassin — the Shadowreaver exists at the edge "
                    "of the material plane, slipping between shadows as easily as breathing. It was summoned by a "
                    "forgotten cult seeking to eliminate key figures in Ironhold, and has since escaped their "
                    "control entirely. It kills for the pleasure of it now. No one has seen its true face — "
                    "only the void-black blades that materialize from darkness."
                ),
                hp_max=180,
                armor_class=18,
                attack_bonus=10,
                damage_dice="2d8",
                damage_bonus=6,
                xp_value=8000,
                gold_drop=300,
                phase_count=2,
                phase_thresholds=[0.30],
                phase_abilities={
                    "2": {
                        "name": "Shadow Form",
                        "description": (
                            "The Shadowreaver fully merges with darkness — it becomes resistant to all damage except "
                            "radiant and force. It gains the ability to teleport up to 60 ft as a bonus action on "
                            "each turn. All of its attacks now count as critical hits on a 19–20. The lights in the "
                            "room go out — creatures without darkvision fight at disadvantage."
                        ),
                    },
                },
                legendary_actions=[
                    {"name": "Shadow Step", "description": "The Shadowreaver teleports up to 60 ft to an unoccupied space it can see. Does not provoke opportunity attacks.", "cost": 0},
                    {"name": "Poison Blade", "description": "One creature takes 1d8+6 piercing damage and 2d6 poison damage, DC 16 CON save or be Poisoned (disadvantage on attacks and ability checks) until end of their next turn.", "cost": 1},
                    {"name": "Void Rend", "description": "A slash of void energy tears through one creature for 3d10+6 necrotic damage, DC 17 CON save or the creature's HP maximum is reduced by the damage taken until they complete a long rest.", "cost": 2},
                ],
                legendary_action_count=3,
                is_lair_boss=False,
                lair_actions=[],
                loot_table=[
                    {"item": "Void Dagger", "chance": 0.10, "qty_min": 1, "qty_max": 1},
                    {"item": "Shadow Essence", "chance": 0.50, "qty_min": 1, "qty_max": 2},
                    {"item": "Assassin's Hood", "chance": 0.25, "qty_min": 1, "qty_max": 1},
                    {"item": "Void Crystal", "chance": 0.35, "qty_min": 1, "qty_max": 2},
                    {"item": "Dark Coin Purse", "chance": 1.00, "qty_min": 100, "qty_max": 300},
                ],
            ),
        ]

        async with get_db() as db:
            count = 0
            for boss_data in BOSSES:
                existing = await db.execute(
                    select(BossTemplate).where(
                        BossTemplate.guild_id == ctx.guild.id,
                        BossTemplate.name == boss_data["name"],
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                boss = BossTemplate(
                    guild_id=ctx.guild.id,
                    created_by=ctx.author.id,
                    **boss_data,
                )
                db.add(boss)
                count += 1

        if count == 0:
            await ctx.send("All 3 boss templates already exist — nothing to seed.")
            return

        embed = discord.Embed(
            title="👹 Boss Templates Seeded",
            description=f"**{count}** boss template(s) added to this server.",
            color=0xEF4444,
        )
        embed.add_field(
            name="🦴 Malvaxis the Undying",
            value="300 HP · AC 17 · 3 phases · Lair boss · 15,000 XP\n*Ancient lich, Ashgate Ruins*",
            inline=False,
        )
        embed.add_field(
            name="🐉 Ignarok the Flame Tyrant",
            value="256 HP · AC 19 · 2 phases · Lair boss · 12,000 XP\n*Adult red dragon, Crimson Peaks*",
            inline=False,
        )
        embed.add_field(
            name="🗡️ The Shadowreaver",
            value="180 HP · AC 18 · 2 phases · 8,000 XP\n*Shadow assassin demon, anywhere*",
            inline=False,
        )
        embed.add_field(
            name="How to spawn",
            value="`/gm boss spawn <name>` — spawns the boss in the current channel\n`/gm boss list` — see all templates with IDs",
            inline=False,
        )
        embed.set_footer(text="LoreForge Boss System · Use !seed_bosses again to skip existing")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
