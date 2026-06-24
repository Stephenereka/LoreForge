# LoreForge — Game Plan

> This is the master reference document for the LoreForge Discord bot project.
> Update this file whenever the plan changes. Always read this before starting new work.

---

## What LoreForge Is

A Discord RPG bot that turns a server into a **living world**. The server owner builds their world (lore, factions, locations, NPCs), players create characters and play inside it. The bot handles all the mechanics — character sheets, combat, economy, quests, lore wiki — so the Game Master can focus on storytelling instead of admin work.

**One-line pitch:** Every other bot is a game inside Discord. LoreForge is a *world* inside Discord.

---

## What Makes It Different

| What Exists | The Gap |
|---|---|
| Avrae | D&D 5e only, no story, no world |
| Tupperbox | Just text formatting, no mechanics |
| Mudae | No RPG depth |
| Friends & Fables | AI forgets everything, hits paywall fast |
| World Anvil | Not inside Discord |

**LoreForge = World Anvil + DnD combat engine + optional AI GM, all inside Discord.**

No other bot has combined:
- Database-backed NPC memory (NPCs remember players months later)
- True persistent world state (world changes based on player actions)
- Multiplayer Discord-native play
- Human GM first, AI as an optional assistant

---

## Feature List

### Core
- Character creation wizard (buttons + dropdowns, guided steps)
- Character sheet display as Discord embed
- DnD-style turn-based combat with button interface
- AI Mode (AI Game Master narrates) — **OFF by default, GM toggles on**
- Manual Mode (human GM drives the session)
- XP and leveling system (20 levels, D&D 5e thresholds)

### World & Lore
- In-Discord lore wiki — searchable by players mid-session (`/lore search`)
- Location system (cities, dungeons, wilderness with travel)
- NPC database with persistent memory (NPCs remember players across sessions)
- Faction system with reputation tiers (Outsider → Member → Leader)
- World JSON loader — server owners define their entire world in one file
- Session notes auto-generated after every session

### Social & Competitive
- OC (Original Character) leaderboard — kills, quests, achievements
- Achievement system
- Server economy (gold, items, player market)
- Cross-server shared worlds (server partnerships with real meaning — two servers share the same lore, world events, economy)

### Game Master Tools
- GM dashboard (manage world lore, spawn encounters, override AI)
- Quest builder
- NPC behavior controls
- Manual GM takeover mid-session (disables AI, GM types freely)

### Security
- Never requires Administrator permissions
- Minimum permission set only (Send Messages, Embed Links, Manage Threads, Use Slash Commands)
- All GM commands locked behind a configurable GM role, not admin checks

---

## Tech Stack

| Layer | Tool | Reason |
|---|---|---|
| Bot framework | discord.py 2.x | Best community, fully async, Cogs system |
| Primary database | PostgreSQL + asyncpg | Relational fits RPG data perfectly |
| Active session cache | Redis | Fast reads for live combat state |
| Lore search | ChromaDB | Vector search — AI knows your world |
| AI narration | Groq (llama-3.3-70b) | Fastest inference, cheapest cost |
| AI summaries | Groq (llama-3.1-8b-instant) | Fast + cheap for session summaries |
| Hosting | Railway → Hetzner VPS | Start simple, migrate when ready |
| Monitoring | Sentry + UptimeRobot | Crash alerts + uptime pings |

---

## AI Design Rules

- AI GM is **optional and OFF by default** — the human GM is always first
- AI cannot override dice results — mechanics are deterministic, AI only narrates
- AI uses RAG (lore stored as vectors) so it only states facts from the world file
- After every response, a fast validation pass checks for lore contradictions
- Three-tier memory: immediate context + retrieved memory + archived history
- NPCs store structured memory in the database — not in the AI context window

---

## Game Mechanics (D&D 5e Inspired)

### Character Creation Steps
1. Choose Race (Human, Elf, Dwarf, Halfling, Half-Orc, Dragonborn, Tiefling...)
2. Choose Class (start with 6: Fighter, Rogue, Cleric, Wizard, Barbarian, Warlock)
3. Assign Ability Scores (Standard Array: 15, 14, 13, 12, 10, 8)
4. Choose Background (Acolyte, Criminal, Soldier, Noble, Sage, Folk Hero)
5. Bot calculates HP, AC, modifiers, saving throws automatically

### Ability Scores
STR, DEX, CON, INT, WIS, CHA — modifier = floor((score - 10) / 2)

### Combat Flow
1. All participants roll d20 + DEX → Initiative order
2. Each turn: Attack / Spell / Defend / Item / Flee (Discord buttons)
3. Attack: d20 + modifier + proficiency vs enemy AC → hit = roll damage
4. Natural 20 = Critical Hit (double damage dice)
5. 0 HP = Death saving throws (3 successes = stable, 3 fails = dead)
6. Fight ends: XP awarded, loot dropped

### Starting 6 Classes
| Class | Identity | Key Mechanic |
|---|---|---|
| Fighter | Tank/damage | Action Surge (extra action 1/rest) |
| Rogue | Sneaky damage | Sneak Attack (+Xd6 with advantage) |
| Cleric | Healer/support | Channel Divinity (Turn Undead, domain powers) |
| Wizard | Utility caster | Spellbook + Arcane Recovery |
| Barbarian | Rage machine | Rage (bonus damage + resistance) |
| Warlock | Pact caster | Short rest spell slots + Eldritch Blast |

### Economy
- Currency stored as copper, displayed as gp/sp/cp
- Weapons: 1d4 (dagger) to 2d6 (greatsword)
- Armor: AC 11 (leather) to AC 18 (plate)
- Potions, magic items, attunement (max 3 attuned)

---

## Build Order (5 Phases)

### Phase 1 — Core Loop (Weeks 1–3)
- [ ] Project setup (folder structure, .env, database connection)
- [ ] Character creation wizard (6 classes, 5 races, standard array)
- [ ] Character sheet display embed
- [ ] 1v1 combat with buttons (attack, defend, item, flee)
- [ ] Basic inventory (weapons, armor, potions)
- [ ] XP gain and level up

### Phase 2 — Depth (Weeks 4–6)
- [ ] Multiplayer combat (full party vs enemies)
- [ ] Spellcasting (3–4 spells per caster class)
- [ ] Conditions system (poisoned, stunned, blinded, etc.)
- [ ] Short rest and long rest mechanics
- [ ] Shop system with gold economy

### Phase 3 — World (Weeks 7–10)
- [ ] Location system (rooms, travel, exploration)
- [ ] In-Discord lore wiki (`/lore add`, `/lore search`)
- [ ] NPC database with persistent memory
- [ ] Quest system (accept, track, complete)
- [ ] Faction reputation tiers

### Phase 4 — Intelligence (Weeks 11–14)
- [ ] Groq AI narration (optional, GM-toggleable)
- [ ] RAG lore retrieval (ChromaDB)
- [ ] Session auto-summary
- [ ] All 12 classes
- [ ] Boss encounters with special abilities
- [ ] World JSON loader for server owners

### Phase 5 — Scale (Month 3+)
- [ ] OC leaderboard (kills, quests, achievements)
- [ ] Achievement system
- [ ] Cross-server shared worlds
- [ ] Web dashboard
- [ ] Monetization (premium tiers)

---

## Monetization Plan

- **Free tier:** 1 character per user, basic combat, lore wiki (read-only)
- **Server premium ($X/month):** Unlimited characters, AI GM, full lore tools, web dashboard
- **World packs:** Sell pre-built world JSON files (new regions, enemy tables, quest chains)
- **Top.gg listing:** Organic server installs, charge per-server subscription

---

## Key Feedback (From Community Research)

### From Whiztale (RP server owner, early tester)
- AI GM is controversial — "AIs aren't even good enough, they just hallucinate" → AI must be optional and off by default
- World Anvil is the real benchmark — "If you manage to compete with WA you'd be very successful"
- Biggest pain point: "A centralised place to tell people to look at for lore, rather than explaining the same thing over and over"
- OC leaderboard with kills/achievements would be a good bonus for combat-focused servers
- Never require admin permissions — "I've seen people get screwed up because of it"
- Cross-server worlds = real server partnerships, not just mutual promotion

### From Market Research (June 2026)
- Every AI bot forgets context — NPC memory must be database-backed, not context-window dependent
- Free tiers hit paywalls too fast — real free tier matters for trust
- Users need 6–8 bots to cover what LoreForge will do alone
- Nobody has: persistent world state + multiplayer + Discord-native + proactive NPCs all together

---

## Folder Structure (Planned)

```
Discord Bot (LoreForge)/
├── GAME_PLAN.md          ← this file
├── main.py               ← bot entry point
├── config.py             ← env vars, settings
├── .env                  ← secrets (never commit)
├── database/
│   ├── models.py         ← SQLAlchemy models
│   ├── session.py        ← DB connection pool
│   └── migrations/       ← Alembic migrations
├── cogs/
│   ├── character.py      ← /create, /sheet, /levelup
│   ├── combat.py         ← /attack, /defend, /spell
│   ├── exploration.py    ← /travel, /look, /interact
│   ├── economy.py        ← /shop, /buy, /sell
│   ├── lore.py           ← /lore add, /lore search
│   ├── gm.py             ← AI GM integration
│   └── admin.py          ← /setup, /reload, /config
└── services/
    ├── ai_service.py     ← Groq integration
    ├── combat_engine.py  ← Dice, damage, mechanics
    ├── memory_service.py ← NPC/world state memory
    └── rag_service.py    ← ChromaDB lore retrieval
```

---

## Public Bot Requirements

LoreForge will be a public bot listed on Top.gg. This affects the following:

- **PostgreSQL is required** (not SQLite) — file locking breaks under multiple concurrent servers
- **All data must be scoped to `guild_id`** — characters, worlds, NPCs, economy, lore — everything. One server's world never touches another's. This is a hard rule from day one.
- **Sharding** — Discord requires it at 2,500+ servers. Don't build it now, but write code that won't need a rewrite to add it later (`AutoShardedClient` is a one-line swap)
- **Top.gg listing** — list from launch for organic growth (already in monetization plan)
- **Rate limits** — with hundreds of servers active simultaneously, async patterns must be respected everywhere. No blocking calls.
- **Privacy Policy + Terms of Service** — required by Discord for bot verification. Phase 5 task, not urgent now.

---

*Last updated: 2026-06-23*
