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
- **Combat action classification** uses `llama-3.1-8b-instant` (Groq) — lightweight, fast, cheap. Reads player RP message and returns structured JSON: `{action, target, weapon}`. Only fires when player is in active combat
- **AI narration** (Phase 4) uses `llama-3.3-70b` (Groq) — full storytelling, lore-aware responses. Two separate jobs, two separate models

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
- [x] Project setup (folder structure, .env, database connection)
- [x] Character creation wizard (6 classes, 7 races, standard array) — 4-step flow: Race → Class → Background → Details
- [x] Backstory / lore field — paragraph text entered during creation, shown on character sheet
- [x] Avatar URL — set during creation, shown as thumbnail on sheet and used as proxy face
- [x] Proxy system (Tupperbox-style) — type `[text]` or `prefix>text` in any channel, bot reposts as your character via webhook with their name and avatar. `/character proxy` to update, `/character proxy_remove` to clear.
- [x] Character sheet display embed — stats, HP, AC, XP, gold, saving throws, backstory, proxy brackets
- [x] Multiplayer combat with buttons — lobby system, up to 4 players, initiative order, enemy attacks random player, death saves, flee removes one player
- [x] Basic inventory (weapons, armor, potions) — `/shop` and `/inventory` groups
- [x] XP gain and level up — awarded on combat victory, level-up HP recalculated

### Phase 2 — Depth (Weeks 4–6)
- [ ] **Combat system full redesign** (see Combat System Design section below)
  - Two character types: DnD (AI combat) and Custom (manual combat only)
  - Two fight types: AI fight and Manual fight — chosen when starting combat
  - Per-channel combat sessions — multiple simultaneous fights, no hard limit
  - Combat sessions have a title — players join by picking from a list
  - Player vs Player only for now — no NPCs
  - Target dropdown shows ALL characters registered in the server
  - Status embed re-posts as new message after every action (always at bottom of chat)
  - AI combat: bot reads proxy messages only (PluralKit/Tupperbox webhooks) — regular messages ignored as OOC
  - Manual combat: bot logs declarations, resolves nothing — GM inputs results at end, AI summarizes
  - `/combat start` — pick title + fight type, pick who you want to fight from all server characters
  - `/combat join` — dropdown of all active combats in server by title
  - `/combat end` — players end combats they're in; GMs end any combat in server
  - `/combat list` — see all active combats in server
  - `/combat overview` — see everyone's current stats in the fight
  - `/combat pause` / `/combat resume` — manual fights only
  - `/combat hp [amount]` — update own HP (manual fights only; GM can update anyone's)
  - `/combat edit` — edit own combat state: conditions, temp HP (manual only; GM edits anyone's)
  - `/combat action [text]` — declare action for your turn
  - `/combat target` — pick target from full server character list
  - `/combat log` — see running log of all actions in the current fight
  - `/combat summary` — generate AI summary of fight (preview or final)
  - `/combat save` — save/pin summary to chosen channel
  - AI combat is fully locked to players — only GM can override anything
- [ ] **GM system** (see GM System section below)
  - `/gm add @User` — server owner assigns a GM
  - `/gm remove @User` — server owner removes a GM
  - `/gm list` — list all GMs in server
  - `/gm sheet view @User` — GM views any player's character sheet
  - `/gm sheet edit @User` — GM edits any field on any player's sheet
  - `/gm pending` — see all pending stat change requests
  - `/gm approve @User` — approve a pending stat change
  - `/gm deny @User` — deny a pending stat change
- [ ] **Character system updates**
  - Custom character type — free text class/race/background, `is_custom` flag in DB, manual combat only
  - `/character delete` — players delete own characters; GMs delete anyone's
  - `/character list` — list characters with public/private (ephemeral) option
  - Image URLs: accept any direct URL ending in .jpg/.jpeg/.png/.gif/.webp — remove imgur-only restriction
  - Stat changes require GM approval — held as pending, GM approve/deny via `/gm pending`
  - HP changes: players update their own freely, no approval needed
  - Every character sheet edit (by anyone) posted to configured audit log channel (before → after)
- [ ] `/combat config log-channel #channel` — set audit log channel
- [ ] Starter attacks + weapons per class (same count for all classes, chosen at character creation, shown on sheet)
- [ ] Spellcasting (3–4 spells per caster class)
- [ ] Conditions system (poisoned, stunned, blinded, etc.)
- [ ] Short rest and long rest mechanics
- [ ] Shop system with gold economy

### Phase 3 — World (Weeks 7–10)
- [ ] Location system (rooms, travel, exploration)
- [ ] **Zone/proximity system** — defines how close players must be to trigger combat. Once zones exist, enemy targeting locks to same zone only (Phase 2 uses server-wide targeting as a placeholder)
- [ ] In-Discord lore wiki (`/lore add`, `/lore search`)
- [ ] NPC database with persistent memory
- [ ] Quest system (accept, track, complete)
- [ ] Faction reputation tiers
- [ ] Paginate `/help` — overview page + one page per command group, button row to navigate
- [ ] **`/tutorial` command** — guides new players through the server step by step:
  - Step 1: What LoreForge is and how the world works
  - Step 2: How to create your character (`/character create`)
  - Step 3: Where to read the server lore before playing
  - Step 4: Real-time combat example — demonstrates the chat-reading system with a dummy fight so players know how to type actions, confirm, and read dice results
  - Delivered as a paginated ephemeral embed with Next/Back buttons, skippable at any time
- [ ] **Map generation** (tied to location system — generate and send a map image when a player enters or explores a location)
  - Dungeon/room layouts — procedural BSP algorithm + Pillow render → PNG sent to Discord
  - World/region maps — Perlin noise terrain + Pillow render → biomes, markers, region names
  - City maps — Pollinations.AI (free, no key needed) with fantasy map prompt
  - All three output as `discord.File` PNG via `generate_dungeon()`, `generate_world()`, `generate_city()`
- [ ] **XP & Leveling System** (max level 20, D&D 5e thresholds)
  - **XP thresholds:** 0 / 300 / 900 / 2,700 / 6,500 / 14,000 / 23,000 / 34,000 / 48,000 / 64,000 / 85,000 / 100,000 / 120,000 / 140,000 / 165,000 / 195,000 / 225,000 / 265,000 / 305,000 / 355,000
  - **XP from PvP combat:** winner earns `defeated_player_level × 50 XP`; if multiple winners XP is split equally; killing or sparing both award full XP
  - **GM XP awards:** `/gm xp @user <amount>` — GM manually grants XP for roleplay, quests, story moments
  - **On level up:**
    - HP increases — roll class hit die + CON modifier (min 1), saved to DB
    - Proficiency bonus increases at levels 5, 9, 13, 17
    - Bot posts a public level-up embed in the channel: name, new level, HP before → after, new feature unlocked
  - **Ability Score Improvements (ASI)** at levels 4, 8, 12, 16, 19:
    - Bot sends ephemeral prompt with two options: +2 to one stat OR +1 to two different stats
    - Player picks via dropdown; stat updates live immediately
  - **Class feature unlocks per level:**

    | Class | Level | Feature |
    |---|---|---|
    | Fighter | 5 | Extra Attack (2 attacks per turn) |
    | Fighter | 11 | Three attacks per turn |
    | Rogue | 5 | Uncanny Dodge (halve one attack's damage 1/turn) |
    | Rogue | 11 | Reliable Talent (min 10 on skill rolls) |
    | Cleric | 5 | Destroy Undead |
    | Wizard | 5 | Extra spell slot |
    | Barbarian | 5 | Extra Attack + Fast Movement |
    | Barbarian | 11 | Relentless Rage (survive 0 HP once per rage) |
    | Warlock | 5 | Third spell slot + 3rd level spells |

  - **Implementation plan:**
    - `services/leveling.py` — XP table, `check_level_up()`, `hp_on_level()`, `class_features_at()`, `proficiency_bonus()`
    - Update `_end_combat` in `cogs/combat.py` — award XP to winner(s) after combat ends, call level-up check, post embed
    - Update `cogs/character.py` — show XP bar and next-level threshold on `/character sheet`
    - Add `/gm xp` to `cogs/gm.py`

### Phase 4 — Intelligence (Weeks 11–14)
- [ ] Groq AI narration (optional, GM-toggleable)
- [ ] RAG lore retrieval (ChromaDB)
- [ ] Session auto-summary
- [ ] All 12 classes
- [ ] Boss encounters with special abilities
- [ ] World JSON loader for server owners
- [ ] **GM approval system for character updates**
  - Cosmetic updates (avatar, name, backstory, proxy) → apply instantly, no GM needed
  - Mechanical updates (stats, HP, level, gold, weapons, attacks, class, race) → require GM approval
  - Bot sends a pending approval embed to the GM channel with Approve / Deny buttons
  - GM approves → stat updates live, player notified
  - GM denies → player notified, optional reason from GM
  - GM channel must be configured via `/setup gm_channel #channel` during server setup

### Phase 5 — Scale (Month 3+)
- [ ] OC leaderboard (kills, quests, achievements)
- [ ] Achievement system
- [ ] Cross-server shared worlds
- [ ] Web dashboard
- [ ] Monetization (premium tiers)

---

## GM System Design

### Who Is a GM

- Server owner is always a GM automatically — no setup needed
- Server owner can assign additional GMs via `/gm add @User`
- GMs stored in DB per server (`guild_id` + `user_id`)
- No Discord role required — purely DB-based

### GM Powers (no limits, override everything)

- Edit any character sheet field directly
- Approve or deny any pending stat change request
- View any character sheet at any time
- Delete any player's character
- End any combat in the server
- Override any combat result (manual and AI fights)
- Input fight results for AI summary
- Update HP or combat state of any player during manual fights
- Assign/remove other GMs (server owner only)

### Character Edit Approval Rules

| Edit Type | Who Can Do It | Needs GM Approval? |
|---|---|---|
| HP update | Player (own) / GM (anyone) | No |
| Avatar, name, backstory, proxy | Player (own) | No |
| Stats (STR/DEX/etc.), level, class, gold, weapons | Player (own) | Yes — held as pending |
| Any field | GM | No — applies immediately |

### Audit Log

- Every edit to any character sheet posts to configured log channel
- Format: before → after, who made the change, timestamp
- Covers both player self-edits and GM edits
- Configure with `/combat config log-channel #channel`

---

## Combat System Design

### Philosophy
RP first, mechanics second. Players type freely in the channel — the bot listens and resolves. Buttons kill immersion. The only UI is a status embed that updates passively.

### How Combat Starts
- For now (no zones): any player can target any character or NPC in the server via `/attack @target`
- Once zones exist (Phase 3): combat can only start between players/NPCs in the same zone
- GM can also spawn an encounter manually in any channel

### Chat-Reading Flow
1. Player types RP action freely in the channel (e.g. *"Kael drives his sword into the orc's chest"*)
2. Bot detects the message (player is flagged as in active combat)
3. Groq `llama-3.1-8b-instant` classifies the action → returns `{action, target, weapon}`
4. Bot sends a confirmation message: *"Attacking [Orc] with [Longsword] — confirm?"* (player reacts ✅ or ❌)
5. Player confirms → bot rolls dice, resolves damage, updates combat embed
6. If action is unclear → bot asks once: *"Are you attacking or doing something else?"*

### Combat Status Embed
- Updates live in the channel after every action
- Shows: turn order, HP bars for all participants, last action result, active conditions
- No action buttons — players always type their next action

### Escape Mechanics
- Player types flee intent (e.g. *"he turns and sprints away"*) → bot detects FLEE
- Roll d20 + DEX modifier vs enemy d20 + DEX modifier
  - **Win + roll ≥ 15** → fully escaped, far enough to rest safely
  - **Win + roll < 15** → escaped but enemy is close, no rest, re-engages in next zone entered
  - **Lose** → caught, combat continues, player loses their turn

### Starter Attacks & Weapons Per Class
- All classes get the same number of basic attacks at character creation
- Players choose their attacks during the character creation wizard
- Starting weapon is assigned by class, shown on character sheet
- Weapons can be upgraded/replaced via the shop (currency affects combat loadout)

| Class | Starter Weapon | Basic Attacks |
|---|---|---|
| Fighter | Longsword (1d8) | Power Strike, Shield Bash, Parry |
| Rogue | Dagger (1d4+DEX) | Sneak Stab, Smoke Feint, Pickpocket |
| Wizard | Staff (1d6) | Magic Missile, Fire Bolt, Shield |
| Barbarian | Greataxe (1d12) | Reckless Swing, Rage Charge, Intimidate |
| Cleric | Mace (1d6) | Smite, Heal, Turn Undead |
| Warlock | Eldritch Blast (1d10) | Hex, Drain, Dark Pact |

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

*Last updated: 2026-06-24*

---

## Change Log

| Date | Change |
|---|---|
| 2026-06-24 | Added map generation to Phase 3 (dungeon, world, city maps — tied to location system) |
| 2026-06-24 | Added GM approval system for character updates to Phase 4 (cosmetic = instant, mechanical = GM channel approval embed) |
| 2026-06-24 | Full combat system redesign — removed button-driven combat, replaced with chat-reading RP flow using Groq 8b for action classification |
| 2026-06-24 | Added player confirmation step before bot rolls on classified action |
| 2026-06-24 | Added escape mechanics (flee roll, zone-distance outcomes) |
| 2026-06-24 | Added starter attacks + weapons per class (same count for all classes, chosen at character creation) |
| 2026-06-24 | Added zone/proximity system to Phase 3 — placeholder until zones built: players can target any character or NPC in the server |
| 2026-06-24 | Added Combat System Design section as standalone reference |
| 2026-06-24 | Added Groq model split to AI Design Rules — 8b for combat classification, 70b for narration |
| 2026-06-24 | **BUILT** — services/ai_service.py created (Groq 8b combat action classifier) |
| 2026-06-24 | **BUILT** — services/combat_engine.py: added STARTER_WEAPONS and STARTER_ATTACKS (3 attacks per class) |
| 2026-06-24 | **BUILT** — cogs/character.py: added Starting Loadout step in character creation (shows weapon + 3 attacks before Details step); starter weapon added to inventory as equipped on creation; attacks stored in class_resources["attacks"]; Loadout field added to character sheet embed |
| 2026-06-24 | **BUILT** — cogs/combat.py full rewrite: removed CombatView buttons, added on_message listener + ConfirmView + chat-reading combat, new escape mechanics (player_roll vs enemy_roll, rest on 15+), DeathSaveView updated to message-based, added /combat forfeit command, all end conditions (victory/defeat/flee) now edit session.status_message directly |
| 2026-06-24 | **BUILT** — services/combat_engine.py: full CONDITIONS system (12 conditions — poisoned, burning, bleeding, stunned, blinded, frightened, hexed, prone, parrying, shielded, reckless, raging); added condition helpers (has_condition, apply_condition, remove_condition, tick_conditions, effective_ac); added detect_attack_name; all 18 named attack handlers (3 per class × 6 classes) with unique mechanics, log_lines, conditions_applied/self_conditions; resolve_named_attack dispatcher |
| 2026-06-24 | **BUILT** — cogs/combat.py: lobby multiplayer bug fixed (lobby now sent as public channel message, join/start work off lobby_message instead of ephemeral); status_embed now shows condition icons + effective_ac; _update_status_and_prompt now ticks conditions at turn start, posts DoT to channel, skips turn if stunned; _resolve_player_action now detects named attacks and routes to resolve_named_attack with log_lines posted as channel messages; _resolve_enemy_turn now ticks enemy conditions, skips if stunned, cowers if frightened, posts attack roll to channel; on_message now detects named attack names and shows them in confirmation label |
| 2026-06-24 | **BUILT** — cogs/rest.py: both /rest short and /rest long now block during active combat; /rest long preserves class_resources["attacks"] list across rest (starter attacks not wiped) |
| 2026-06-24 | **BUILT** — cogs/admin.py: /help updated — character creation now shows 5-step wizard, combat section updated with chat-reading explanation + /combat forfeit, new Conditions field added, rest commands note cannot rest during combat |
| 2026-06-24 | Added /tutorial command to Phase 3 (guided new-player flow: LoreForge intro → character creation → lore reading → real-time combat demo, paginated ephemeral embed with Next/Back) |
| 2026-06-24 | **REDESIGN** — Full Phase 2 combat + GM system overhaul: two character types (DnD/Custom), two fight modes (AI/Manual), per-channel sessions with titles, PvP only, proxy-only AI reading, GM system with DB-backed roles, full manual combat command set, character audit log, stat change approval flow, image URL fix, /character delete + list |
| 2026-06-24 | **BUILT** — Image URL fix: accept any direct .jpg/.jpeg/.png/.gif/.webp URL in character creation and proxy modal; removed imgur-only placeholder text; added _is_valid_image_url validator with error message on invalid input |
| 2026-06-24 | **BUILT** — /character list: lists all user's characters (including dead ones) with status, level, race, class, HP, gold, XP; public/private (ephemeral) toggle via optional `public` param |
