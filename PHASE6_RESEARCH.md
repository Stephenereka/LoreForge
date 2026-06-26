# Phase 6 — WorldAnvil Competitive Analysis & LoreForge Strategic Roadmap

> **Status:** Research Complete — Ready for Planning  
> **Date:** 2026-06-26  
> **Purpose:** Deep competitive analysis of WorldAnvil + outside-the-box brainstorming for making LoreForge the best RP bot ever  
> **Source:** DeepSeek V3 autonomous research agent

---

## Executive Summary

WorldAnvil (WA) is the gold standard for worldbuilding on the web — a feature-rich wiki platform for GMs, writers, and game designers. LoreForge is a real-time Discord RPG bot with a living world, combat engine, proxy system, and AI narration. **They are not competitors. They are complements.**

LoreForge's strategic advantage: it is **Discord-native** and **real-time**. WA is a reference tool you visit between sessions. LoreForge is the session itself. The opportunity is to absorb WA's best features into Discord's real-time, social environment — while keeping what makes LoreForge unique (proxy chat, live combat, world persistence, AI dummy training).

**One-line vision for Phase 6:** *Every feature WorldAnvil has that still makes GMs leave Discord to use it — we build it natively.*

---

## 1. WorldAnvil Feature Audit — Deep Analysis

### 1.1 Core Worldbuilding Tools

| Feature | How WA Does It | LoreForge Status |
|---|---|---|
| **Articles** (wiki pages) | Rich text editor, categories, tags, custom templates, image galleries, maps, stats blocks, cross-linking | ✅ Lore entries (rich text via modal, categories, tags, images) |
| **Categories** | 70+ built-in category templates (Character, Location, Item, Species, Religion, Language, Spell, etc.) | ⚠️ Lore has categories but no structured templates per type |
| **Timelines** | Interactive timeline view, eras, date ranges, pin events to dates, categories per timeline | ❌ Not built — WorldEvent log exists but no timeline UI |
| **Interactive Maps** | Upload map, place pins, click pins → linked articles, zoom/pan, fog of war, layer system | ✅ Map with location pins, fog of war (hide/reveal), but no click-interactive map — only static image |
| **Family Trees / Genealogy** | Drag-and-drop tree builder, relationships (parent, spouse, sibling, rival), calculate ages, bloodlines | ❌ Not built — Character model has no relationship tracking |
| **Species & Races** | Full taxonomy — biological traits, subraces, naming conventions, culture, religion, homelands | ⚠️ Races exist for character creation but no cultural/lore depth |
| **Languages** | Custom conlangs, scripts, dictionaries, automatic translation flavour, dialect/variants, speak/understand fields on characters | ❌ Not built |
| **Religions & Pantheons** | Deities, domains, holy symbols, tenets, clergy, holy orders, miracles, sacred texts | ❌ Not built |
| **Magic Systems** | Schools of magic, spell lists, mana types, magical traditions, enchanting, alchemy | ⚠️ Spellcasting exists per class but no system-wide magic framework |
| **Technology** | Tech levels, inventions, materials, crafts, trade routes | ❌ Not built |
| **Bestiary** | Creature templates, stats, habitats, loot, encounter tables | ⚠️ NPC/Boss templates exist but no standalone bestiary browser |
| **Maps from Images** | Upload custom maps, pin articles, toggle layers | ✅ Pollinations AI maps + Pillow overlays, pin locations |
| **Sessions & Campaigns** | Campaign manager, session notes, NPC/quest trackers, player handouts, dice rolls | ✅ Session system with auto-summary, quest tracking, combat logs |
| **Character Sheets** | Custom sheets per system (D&D 5e, Pathfinder, homebrew), stats, inventory, spells, journals | ✅ Full D&D-style sheets, custom mode, inventory, stats |

### 1.2 Collaboration & Social Features

| Feature | How WA Does It | LoreForge Status |
|---|---|---|
| **Secrets / Visibility Tiers** | Public → Patrons → Followers → Players → GM Only — each article has a visibility slider | ✅ Visibility tiers on lore entries (public / gm_only / quest_reward) |
| **Co-Authors** | Multiple editors on a world, roles (Admin, Editor, Writer, Reader) | ❌ Not built — world editing is GM-only |
| **Player Secrets** | GMs can create secrets only visible to specific players | ⚠️ gm_only visibility exists but not player-specific secrets |
| **Inline Articles** | Create linked articles inline while writing (e.g., type `@character` to create a new character mid-article) | ❌ Not built — lore entries are created separately |
| **Comments** | Comments on articles and maps | ❌ Not built — Discord threads could serve this |
| **World Import/Export** | JSON/HTML export, cloning, templates | ✅ World JSON import/export with validation |

### 1.3 WorldAnvil's Weaknesses — Why It's Not Enough

| Weakness | Impact | LoreForge Opportunity |
|---|---|---|
| **Not real-time** | WA is a reference wiki. You open it between sessions. No live action happens in WA. | LoreForge IS the session. Combat, travel, NPC conversations all happen live in Discord. |
| **UX friction** | WA's editor is powerful but overwhelming. New GMs face a steep learning curve with 70+ article types. | Slash commands + modals are simpler. Players never 'edit a wiki' — they just play. |
| **No multiplayer gameplay** | WA tracks notes. It doesn't run combat, track HP, manage inventories, or resolve dice rolls. | LoreForge has a full combat engine, inventory system, economy, and stat tracking. |
| **No chat/immersion** | WA is a web app. There's no way for players to speak as their characters or feel present in the world. | LoreForge's proxy system lets players literally *be* their character via Discord webhooks. |
| **High friction for players** | Players need to create a WA account, join the world, learn the interface, and navigate articles. | LoreForge players type /lore search and get results instantly. No account, no login, no learning curve. |
| **Dead world problem** | WA worlds sit static. NPCs don't move, weather doesn't change, no events fire when you're not looking. | LoreForge has weather cycles, time progression, event reminders, and background tasks that keep the world alive. |
| **No AI integration** | WA is purely human-authored. No AI summaries, AI narration, AI NPC dialogue, or auto-generated content. | LoreForge has DeepSeek-powered combat narration, NPC dialogue, session summaries, and training dummies. |
| **Mobile experience is poor** | WA's editor is desktop-only. On mobile it's read-only and clunky. | Discord runs on every platform. LoreForge works fully on mobile via slash commands and buttons. |

---

## 2. How To Build WorldAnvil Features Into LoreForge (Discord-Native)

### 2.1 Structured Article Templates

**What WA Does:** 70+ article types with structured fields per type.  
**Discord Implementation:**
- `/lore add` gets a `template` parameter with type-specific modals:
  - `character` — age, occupation, birthplace, faction, personality, appearance, backstory
  - `item` — type, material, weight, rarity, enchantments, value, lore text
  - `creature` — habitat, diet, behavior, danger level, loot, stats block
  - `religion` — deity name, domains, holy symbol, tenets, clergy structure, sacred sites
  - `event` — date, location, participants, outcome, significance
  - `organization` — type, leader, headquarters, members, goals, secrets
  - `magic` — school, components, effects, limitations, known users
- Each template renders a differently styled embed with color-coded headers
- Implementation: a `TEMPLATES` dict mapping template_name → list of fields, rendered by `render_template_embed()`

### 2.2 Interactive Timelines

**What WA Does:** Visual timeline of world events, sorted by era.  
**Discord Implementation:**
- WorldEvent table already stores timestamped events (combat outcomes, quest completions, deaths)
- `/timeline` renders a paginated embed:
  - Auto-generated from WorldEvent rows sorted by `created_at`
  - GM adds custom entries: `/timeline add <era> <title> <description>`
  - GM creates eras: `/timeline era create <name> <color>`
  - Events show as bullet points with date stamps under era headers
  - Multi-page embed with colored sidebar per era
- Discord Thread alternative: auto-updating `#world-timeline` thread with event summaries posted automatically

### 2.3 Interactive Maps (Clickable Navigation)

**What WA Does:** Click a pin on the map → linked article opens.  
**Discord Implementation:**
- Current `/map` shows a static Pillow-rendered image
- Enhancement: add one button per discovered region below the map image:
  `[Ironhold] [Thornveil] [Crimson Peaks] [Ashgate] [Silverport]`
- Click a button → `/location view` embed for that location
- Buttons auto-generated from all locations with `map_x`/`map_y`, sorted by proximity to player
- Players only see discovered/unhidden locations; GMs see all + a hidden toggle
- Dungeon extension: room-by-room button navigation (Entrance → Guard Chamber → Boss Room)

### 2.4 Family Trees / Genealogy

**What WA Does:** Drag-and-drop relationship tree per character.  
**Discord Implementation:**
- Add `relationships` JSON field to Character model:
  `[{"type": "father", "name": "Aldric", "id": 42, "status": "alive"}]`
- `/character relation add <type> <target>` — link two characters
- `/character relations` — shows a color-coded relationship embed
- `/tree <character>` — renders a text/emoji relationship tree
- NPCs can also have relationships tracked
- Achievement: "Founded a Dynasty" — 3 generations of characters from the same user

### 2.5 Language System

**What WA Does:** Custom conlangs, character language fields, translation flavor.  
**Discord Implementation:**
- Language DB model: `id, guild_id, name, script_type, word_list (JSON)`
- Characters get a `languages` JSON field listing what they speak/understand
- Unknown language in proxy: *"[Kael speaks in Dwarvish — you don't understand]"*
- `/language learn <language>` — spend gold/time to learn
- `/language list` — browse available languages and who speaks them
- `/language speak <lang> <message>` — force proxy message in a specific language
- GM creates via `/language create <name>` and adds vocabulary
- Phase 2: auto-translation flavor — common phrases auto-translate using word_list

### 2.6 Player-Specific Secrets (Enhanced Visibility)

**What WA Does:** Per-article visibility slider with player-specific reveal.  
**Discord Implementation:**
- Add `visibility_whitelist` JSON field to LoreEntry (list of user_ids who can see it)
- Add `visibility_role_id` field (role-gated lore)
- `/lore view` check order: GM → all visible | whitelisted → show | has role → show | else → hidden with 🔒 icon
- Secrets revealed as quest rewards: DM player with unlock notification
- `/lore search` automatically filters to only entries the user can see

### 2.7 AI Session Recap Generation

**What WA Does:** Manual session notes typed by the GM.  
**Discord Implementation:**
- `/session recap` generates a 3-paragraph narrative from session's WorldEvents + combat logs via DeepSeek
- Posts as a rich embed in a configured `#session-recaps` channel
- Stored in SessionLog for `/session log` browsing
- Key events from the recap auto-canonized as LoreEntry rows marked `is_canon=True`
- Players react with 📌 to pin a recap permanently

### 2.8 Bestiary / Creature Codex

**What WA Does:** Searchable, browsable database of all creatures.  
**Discord Implementation:**
- No new DB tables needed — NPCs and BossTemplates already have combat stats
- `/bestiary list` — all creatures, filterable by habitat, danger level, faction
- `/bestiary view <name>` — stats, habitat, loot, lore, image
- `/bestiary search <query>` — find creatures by name, type, or description
- Every boss template and combat NPC automatically appears in the bestiary
- Players can mark creatures as "studied" after encountering them in combat → fills in lore text
- Progress tracker: "You've studied 12/47 creatures in The Merged Realms"

### 2.9 World Codex — Unified Search

**What WA Does:** Search across all article types simultaneously.  
**Discord Implementation:**
- `/codex <query>` — searches lore_entries, NPCs, locations, items, factions in a single call
- Returns top 3 results from each category with relevance indicators
- Multi-category embed: 📚 Lore | 👥 NPCs | 🗺️ Locations | ⚔️ Bestiary | 🏛️ Factions
- Uses ChromaDB vector search with guild-scoped collection
- Falls back to ILIKE full-text search if ChromaDB unavailable

### 2.10 Inline Article Linking

**What WA Does:** Type @NPC or @Location in any article and it auto-links.  
**Discord Implementation:**
- When a proxy message contains `@LocationName` or `@NPCName`, bot posts ephemeral followup:
  *"📚 The Old Mill Road — A winding cobblestone path through the eastern farmlands."*
- Only triggers for entries the player has permission to see
- GM can create entries inline: `/lore quick "The Crown of Embers" --type item` opens a pre-filled modal
- Uses fuzzy matching for near-miss name references

### 2.11 Religion & Pantheon System

**What WA Does:** Deities, domains, holy sites, worship mechanics.  
**Discord Implementation:**
- Religion DB model: `id, guild_id, name, deity_name, domains (JSON), holy_symbol, tenets (JSON), clergy_notes`
- `/religion list` — all religions, brief description, domains
- `/religion view <name>` — tenets, holy sites, clergy, associated factions
- Characters can have a `religion` field on their sheet
- Clerics and Paladins automatically tied to a religion — domain spells come from religion data
- `/prayer` command: roll for divine blessing (1/day, CON-mod cooldown)
- Holy sites on the map grant bonuses to worshipers who rest there

---

## 3. Gap Analysis — LoreForge vs WorldAnvil

### 3.1 Where LoreForge is AHEAD of WorldAnvil

| Feature | Why It Matters |
|---|---|
| **Real-time combat engine** | WA has no dice, no HP tracking, no turn order. LoreForge runs full D&D 5e-style combat with conditions, crits, and phase-based bosses. |
| **Live proxy system** | Players speak as their character via Discord webhooks. WA has no equivalent — it's a wiki, not a chat platform. |
| **AI training dummy** | Chat-based sparring partner powered by DeepSeek that responds to your actions in-character. Nothing else has this. |
| **Living weather & time** | Weather cycles, day/night, seasonal changes affect gameplay. WA has no dynamic simulation. |
| **Faction rep with real unlocks** | 8-tier reputation system that gates areas, discounts, items, and titles. WA faction articles are just text. |
| **Player housing** | Buyable, upgradeable dwellings with XP bonuses. WA has no player-owned property system. |
| **Quest auto-tracking** | 11 objective types that auto-complete based on player actions. WA has no auto-tracking. |
| **Boss encounter system** | Phase-based bosses, legendary actions, lair actions, loot tables. WA has no encounter system. |
| **Crafting & economy** | Resource gathering, recipe discovery, player market, auction house. WA has no economy. |
| **Heavenly Demon / Murim system** | Custom martial arts class with forms, paths, Tao mechanics. WA has no class system. |

### 3.2 Where WorldAnvil is AHEAD of LoreForge

| Feature | Importance | Effort |
|---|---|---|
| Structured article templates (per-type modals) | High | Medium |
| Interactive timelines (era-based event visualization) | Medium | Medium |
| Family trees / genealogy | Medium | Low |
| Language system (conlangs, translation flavor) | Low-Medium | Medium |
| Religion/pantheon system | Medium | Medium |
| Bestiary/codex browser | High | Low ← quick win |
| Inline @reference linking | Medium | Low ← quick win |
| Player-specific secrets | Medium | Low ← quick win |
| Rich text lore editing (markdown preview) | Low | Low ← quick win |
| Clickable map navigation | Medium | Hard |

### 3.3 Both Have — But LoreForge Does Worse

| Feature | WA Advantage | Fix |
|---|---|---|
| Lore editing | Rich text editor (bold, italic, headers, image galleries) | Add markdown rendering + preview in lore embeds |
| Map interaction | Clickable pins, zoom, layers | Button-based region navigation below map |
| Search | Full-text search with tagging | Wire ChromaDB, add tag filtering, relevance scoring |
| Character sheets | Custom per-system templates, exportable | Add template system for different game systems |
| Session notes | Manual rich text, player-visible | Allow GM to add manual notes alongside AI summaries |

### 3.4 Low-Hanging Fruit (Quick Wins)

1. **Bestiary/codex** — reuse NPC + Boss data, add `/bestiary` command. ~2 hours.
2. **Unified `/codex` search** — one command to find anything in the world. ~4 hours.
3. **Player-specific secrets** — whitelist field on LoreEntry, quest-unlock DM. ~2 hours.
4. **Inline @reference linking** — scan proxy messages, ephemeral lore snippets. ~3 hours.
5. **Character relationships** — JSON field + `/character relation` command + tree embed. ~4 hours.
6. **AI session recap** — `/session recap` via DeepSeek, auto-post to channel. ~3 hours.
7. **Achievement system** — event hooks + 50 achievements + `/legacy` page. ~1 day.
8. **Dream/vision system** — hook into `/rest long`, DeepSeek vision generator. ~3 hours.
9. **Markdown lore export** — `/world export markdown` produces a readable document. ~2 hours.
10. **World analytics for GMs** — `/gm dashboard` growth graphs (characters per week, combat frequency). ~3 hours.

### 3.5 Hard But Worth It (Transformative)

1. **Language system** — New DB model, proxy message modification, GM language creation tools. 3-4 days.
2. **Structured article templates** — Template registry, per-template modals, per-template embed rendering. 3-4 days.
3. **Interactive timelines** — WorldEvent rendering with era coloring, pagination, GM timeline editing. 2-3 days.
4. **Cross-article auto-linking** — Scan lore content for references, auto-generate "Related Articles" section using ChromaDB. 2-3 days.
5. **Clickable map navigation** — Dynamic button rows from map_x/map_y, dungeon room navigation state tracking. 3-4 days.
6. **Family tree visualization** — Tree rendering with ASCII/emoji in embeds, nested field layout. 2-3 days.

---

## 4. Outside-The-Box Ideas — Beyond WorldAnvil

### 4.1 Living World Simulation (Offline Events)

**Concept:** The world keeps running even when no players are online.  
**Implementation:**
- Background task every 15 minutes per guild:
  - 10% chance: a random NPC moves to an adjacent location (roaming)
  - 5% chance: a random faction event fires (patrol attacked, trade caravan arrived)
  - Resources on gather nodes respawn by 10% of max
  - If a PC has been offline 7+ days: NPCs comment on their absence
- `/world pulse` — GM manually triggers a world update tick
- Events are logged to WorldEvent and optionally posted to a `#world-news` channel
- Creates the feeling of a REAL world, not a frozen game waiting for players

### 4.2 AI Dungeon Master Mode (Full Autonomous Sessions)

**Concept:** A complete AI GM that can run sessions using the world data, no human GM needed.  
**Implementation:**
- GM toggles `/ai toggle dungeon-master`
- AI DM has full access to: all lore entries, all NPC data, all locations, all faction states, all active quests (ChromaDB RAG)
- AI handles: NPC conversations, combat narration, quest hooks, faction decisions, action resolution
- Safety rails: AI cannot delete characters, cannot override mechanics, everything is logged for GM review
- GM steps in anytime: `/gm takeover` disables AI and lets them speak directly
- Players never know if the session is AI or human-run (seamless fallback)

### 4.3 Procedural Content Generation (Infinite World)

**Concept:** AI generates dungeons, quests, NPCs, items, and events on demand.  
**Implementation:**
- `/quest generate <difficulty>` — DeepSeek generates a complete quest with objectives, rewards, NPC dialogue
- `/dungeon generate <size>` — BSP algorithm creates dungeon layout, DeepSeek populates room descriptions and encounters
- `/npc generate <location> <role>` — Creates an NPC with stats, dialogue, personality, appearance
- `/encounter generate <difficulty>` — Balanced combat encounter using existing enemy templates
- All generated content shows: ephemeral preview with [Save] [Regenerate] [Discard] buttons before committing
- GMs set generation constraints: "Only use forest creatures" or "Must involve the Thieves Guild"

### 4.4 Achievement & Legacy System

**Concept:** Permanent records of heroic deeds, deaths, and world-shaping events.  
**Implementation:**
- `/legacy <character>` — character's legacy page:
  - Total kills, quests completed, gold earned, locations discovered
  - "First to discover" badges (Ashgate Ruins, The Lost Temple)
  - Notable kills (bosses slain, rival NPCs defeated)
  - Relationships formed (factions at Exalted, NPCs befriended)
  - World events participated in
- `/hall-of-fame` — server-wide leaderboard for each category
- When a character dies permanently: legacy auto-becomes a LoreEntry ("The Legend of Kael Ironhand")
- New characters from the same user can discover relics of their past character
- 50+ achievements across all game systems (combat, exploration, questing, crafting, social)

### 4.5 Dream / Vision System (AI-Narrated Quest Hooks)

**Concept:** When a character rests, a 20% chance they receive an AI-narrated vision hinting at future events or hidden lore.  
**Implementation:**
- Triggered on `/rest long` completion
- DeepSeek receives: player's recent events (last 5 WorldEvents), current location, faction standings, unresolved quests
- Generates a 3-5 sentence dreamlike vision in narrative style
- Posts as ephemeral embed only visible to the player: "💫 As you sleep, a vision comes to you..."
- Hints at: hidden locations, quest solutions, future dangers
- GM can write custom visions for specific triggers: `/vision set <trigger_condition> <vision_text>`
- Players can archive them: `/visions` — view all past visions

### 4.6 Relationship / Social Graph System

**Concept:** Track player-to-player relationships and have the world react mechanically.  
**Implementation:**
- CharacterRelationship DB model: `character_id, target_id, relation_type, score (-10 to +10)`
- `/relation set <character> <type>` — declare a relationship (both must confirm)
- Rivals get +1 to attack rolls against each other in combat
- Allies get +1d4 bonus healing when resting together
- NPCs reference relationships in dialogue: "I heard you travel with Lyra. She's good people."
- Faction reputation can be influenced by who you associate with
- `/social <character>` — shows a character's social graph as a visual embed

### 4.7 Notification System (World DMs)

**Concept:** Players receive Discord DMs about world events relevant to their character.  
**Implementation:**
- `/notifications configure` — player sets what they receive DMs about:
  - Faction reputation changes (with new tier + progress bar)
  - Quest objective auto-completions (celebration message)
  - World events in locations they've visited
  - Lore entries unlocked for them
  - NPC movements (NPCs they've met moving locations)
- GM sends in-character letters: `/npc letter <player> <content>` — delivered as a styled in-world DM
- All notifications are optional, configurable per player, with guild-level master toggle

### 4.8 Investigation / Mystery System

**Concept:** Full detective-RP mechanics — clue gathering, evidence boards, revelation moments.  
**Implementation:**
- `/investigation start <name> <description>` — GM opens a mystery scenario
- `/investigation clue <name> <text>` — player discovers a clue (added to their log)
- `/investigation board` — shows all discovered clues as an evidence board embed (grid layout with clue cards)
- `/investigation connect <clue_a> <clue_b>` — link two clues to form a theory
- `/investigation theory <text>` — submit theory; GM evaluates and reveals the next layer
- `/investigation reveal <text>` — GM triggers a revelation moment (all players see the big picture)
- Clues have visibility tiers: some only visible with high perception, arcana knowledge, etc.
- Mystery scenarios can be saved as templates and reused across campaigns

### 4.9 Character Aging & Generational Play

**Concept:** Characters age, retire, and pass on — creating dynasties and long-term world investment.  
**Implementation:**
- Characters have `age` and `lifespan` fields (race-based: Elf = 750, Human = 80, etc.)
- World time system tracks in-game days. Every 30 in-game days = +1 year to character age
- At 75% of lifespan: −1 STR/DEX/CON (aging penalties), +1 INT/WIS/CHA (wisdom bonuses)
- `/character retire` — character enters retirement, becomes an NPC in the world
- `/character legacy <name>` — create a new character as child/apprentice:
  - Inherits: faction reputation, some gold, one title, one NPC relationship
  - Gains: "Born to a Legend" — +10% XP for first 5 levels
- When a character dies with a legacy established: their tomb becomes a discoverable location
- Generational achievement: "Three Generations of Heroes — the Ironhand Dynasty endures"

### 4.10 Audio / Ambience System

**Concept:** Ambient soundscapes and combat music per location and event.  
**Implementation:**
- Each location has an `ambient_sound_url` field — a URL to a royalty-free ambient track
- `/ambience set <description>` — GM sets text-based ambiance for a voice channel (pinned embed)
- Phase 2: integration with a music bot or Freesound.org API to play ambiance in voice
- Combat auto-triggers a different "combat" ambience URL
- `/sound play <url>` — GM plays a specific sound effect (thunder, dragon roar, door creak)
- All sounds are text-described for players not in voice: "A deep drumbeat echoes through the hall..."

### 4.11 Image Generation Per World Element

**Concept:** Auto-generate character portraits, location art, and battle maps using Pollinations.ai.  
**Implementation:**
- Already using Pollinations for world map — extend to all major world elements
- `/character portrait` — generate portrait from character's race, class, appearance description
- `/location art <name>` — generate an atmospheric image for any location
- `/npc portrait <name>` — generate NPC appearance from their description fields
- `/item art <name>` — generate item illustration from item's description
- All images are posted to the channel AND saved as the entity's `image_url` field in DB
- GMs can regenerate with `/art regenerate` or override with a manual URL

### 4.12 Cross-Server World Events

**Concept:** Shared events that affect multiple Discord servers simultaneously.  
**Implementation:**
- `/world-event global create <name> <description> <duration>` — creates a cross-server event
- Participating guilds see the event in their `/event list`
- Global progress bar: "Dragon Siege: 4,582/10,000 dragons slain across all servers"
- When the global goal is met: every participating guild receives the reward (new location, permanent buff, exclusive item in shop)
- Shared event calendar listing upcoming global events
- Creates a sense of community beyond a single server — the entire LoreForge player base united

### 4.13 Player-Written Lore (Community Canon)

**Concept:** Players submit lore entries that GMs review and approve — building the world together.  
**Implementation:**
- `/lore submit <title> <content> [category]` — creates a LoreEntry with `visibility='submitted'`
- GM gets an approval embed in the GM channel: [Approve] [Deny] [Edit]
- If approved: visibility becomes `public`, player receives XP + "Scribe" title
- If denied: DM sent to player with GM's optional reason
- Submitted lore is marked as player-written in the embed footer
- GM can designate "Canon Scribes" — trusted players whose submissions skip the queue
- Creates community investment: players literally build the world they play in

### 4.14 Mobile-First Optimization

**Concept:** Design every interaction to work with 2 taps max on mobile.  
**Implementation:**
- All critical actions: one command → one button press
- Replace long modals with select menus and button flows where possible
- Character creation on mobile: entirely button/select-menu driven, no typing required
- `/quick-action` — single command with autocomplete for common actions: Look around, Check quests, Check inventory, Talk to nearest NPC
- Embed text kept under 2000 characters to avoid scrolling on mobile
- Status embeds update in-place (no new messages = cleaner on mobile)

---

## 5. Priority Roadmap

### Tier 1 — Build Next (High Impact, Low Effort)

| Feature | Description | How to Build |
|---|---|---|
| **Bestiary / Codex** | Searchable creature database reusing NPC + Boss data | Add `/bestiary` group with list/view/search subcommands querying Character, NPC, BossTemplate |
| **Unified `/codex` search** | One command to search all world content | Multi-table query + ChromaDB vector search, categorized embed output |
| **Player-specific lore secrets** | GMs reveal lore to specific players as quest rewards | Add `visibility_whitelist` JSON to LoreEntry, DM player on unlock |
| **Inline @reference linking** | Proxy messages auto-show lore snippets for @mentions | Scan proxy message content for @Name patterns, post ephemeral lore embed |
| **Character relationships** | Link characters as allies, rivals, family, mentors | Add relationships JSON to Character, `/character relation add/view` commands |
| **AI session recap** | AI-generates a narrative summary of the session | Hook into `/session end`, DeepSeek summarizes WorldEvents + combat log, posts to `#recaps` |
| **Achievement system** | 50+ unlockable achievements across all game systems | Event hook system that checks conditions and grants achievements, `/achievements` view |
| **Dream / Vision system** | AI-narrated visions on rest that hint at quests and lore | Hook into `/rest long`, DeepSeek generates vision from recent player events, ephemeral DM |
| **Image generation per entity** | Auto-generate portraits and art for characters, locations, NPCs | Pollinations.ai prompt builder from entity fields, save URL back to DB |

### Tier 2 — Build Soon (High Impact, More Effort)

| Feature | Description | How to Build |
|---|---|---|
| **AI Dungeon Master Mode** | AI runs sessions autonomously with full world context | `/ai toggle dungeon-master`, DeepSeek + ChromaDB RAG over all guild world data |
| **Living World Simulation** | World keeps updating even when players are offline | Background asyncio task every 15 min, NPC roaming, faction events, resource respawn |
| **Investigation / Mystery System** | Full detective RP mechanic set | New Investigation DB model, `/investigation` command group, evidence board embed |
| **Language System** | Custom conlangs with translation flavor in proxy messages | Language DB model, character `languages` field, proxy message language-detection middleware |
| **Structured Lore Templates** | Per-type article templates (character, item, creature, religion, event) | TEMPLATES registry dict, per-template modal builder, per-template embed renderer |
| **Interactive Timeline** | Visual timeline auto-populated from WorldEvents | `/timeline` command with paginated era-based embed, GM timeline editing tools |
| **Relationship Mechanics** | Allies/rivals get mechanical bonuses, NPCs react to relationships | Extend relationship JSON to include combat hooks, NPC dialogue templates |
| **Notification System** | Player DMs for world events, faction changes, NPC messages | Per-player NotificationConfig model, notification dispatcher called on faction/quest/lore events |
| **Religion & Pantheon System** | Deities, domains, holy sites, divine mechanics | Religion DB model, `/religion` commands, holy site bonuses on location model |
| **Procedural Content Generation** | AI-generated quests, dungeons, NPCs, encounters | DeepSeek prompt templates per content type, GM preview flow with save/discard buttons |

### Tier 3 — Long-Term Vision (Transformative, Complex)

| Feature | Description | How to Build |
|---|---|---|
| **Full AI GM with Safety Rails** | AI can run entire sessions with ChromaDB world knowledge, GM can take over anytime | Full DeepSeek RAG pipeline over all world data, session state machine, safety validator layer |
| **Generational Play** | Character aging, retirement, legacy inheritance, dynasty achievements | World time integration, lifespan tracking, `/character retire` → NPC pipeline, legacy inheritance system |
| **Cross-Server World Events** | Shared global event system across all LoreForge guilds with combined progress | Central LoreForge API server tracking global event state, guild hooks posting updates |
| **Clickable Interactive Map** | Button-based region navigation from map, dungeon room exploration | Dynamic button grid from map_x/map_y coords, dungeon state machine per session |
| **Full Economy Simulation** | Supply/demand, inflation, trade routes between locations, NPC merchants that buy/sell dynamically | Economic model with supply/demand curves, trade route pathfinding, daily price tick background task |

---

## 6. External Tools & APIs to Integrate

| Tool / API | Use Case | Cost |
|---|---|---|
| **DeepSeek V3** | AI narration, NPC dialogue, session recaps, vision generation, quest generation | Already integrated |
| **Pollinations.ai** | Character portraits, location art, battle maps, item illustrations | Free |
| **Freesound.org API** | Ambient soundscapes per location (thunder, forest, tavern, dungeon) | Free (attribution) |
| **ChromaDB** | Vector search for lore, NPC dialogue RAG, world codex | Free (self-hosted, already planned) |
| **Open Meteo API** | Map real-world weather to in-game weather (location-based) | Free |
| **Moon Phase API** | Lunar cycle affects in-game tides, werewolf encounters, dark magic | Free |
| **Discord Scheduled Events** | In-server event announcements for raids, festivals, server-wide events | Free (Discord built-in) |
| **GitHub Actions** | Automated world backup, test suite, deployment pipeline | Free |
| **Webhook.site / ntfy.sh** | Push notifications for GM when players take major actions | Free |

---

## 7. The One-Page Vision for Phase 6

> **Goal:** By the end of Phase 6, LoreForge should be able to answer "yes" to every question a GM would ask WorldAnvil — but without ever leaving Discord.

A GM should be able to:
- Run an entire campaign session — combat, NPC dialogue, quest tracking — without opening any external tool
- Have the world keep evolving between sessions (living world simulation)
- Generate a session recap with one command and have it auto-canonized
- Let an AI DM run a session while they sleep, and review the log in the morning
- Show any player "the lore" for anything in the world with one slash command
- Build a 100-article world wiki collaboratively with their players inside Discord

That is what separates LoreForge from every other RPG bot, worldbuilding tool, and Discord game — and Phase 6 is how we get there.
