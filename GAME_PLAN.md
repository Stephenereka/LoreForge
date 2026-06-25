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
- DnD-style turn-based combat with chat-reading RP flow
- AI Mode (AI Game Master narrates) — **OFF by default, GM toggles on**
- Manual Mode (human GM drives the session)
- XP and leveling system (20 levels, D&D 5e thresholds)

### World & Lore
- In-Discord lore wiki — searchable by players mid-session (`/lore search`) via ChromaDB vector search
- Location system (cities, dungeons, wilderness with travel, locked doors, secret exits)
- NPC database with persistent memory (NPCs remember players across sessions via DB, not AI)
- Faction system with 8 reputation tiers (Hated → Exalted) and real unlocks at each tier
- World JSON loader — server owners define their entire world in one file
- World templates — pre-built worlds GMs can load instantly
- World import/export — backup and share entire worlds as JSON
- Session notes auto-generated after every session
- Weather system — persistent per-guild weather, affects travel + combat descriptions

### Social & Competitive
- OC (Original Character) leaderboard — kills, quests, achievements
- Achievement system
- Cross-server shared worlds (server partnerships — two servers share lore, world events, economy)
- Player-to-player trade system
- Party/group system — shared quest progress, party travel
- Player housing — buy a room, decorate it, invite others
- Discoveries log — track every hidden location a player finds first

### Game Master Tools
- GM dashboard — single command world overview (`/gm dashboard`)
- Quest builder with 11 objective types
- NPC behavior controls and keyword dialogue
- Manual GM takeover mid-session (disables AI, GM types freely)
- World templates and import/export
- Event scheduling — GMs post sessions, players RSVP

### Crafting & Economy
- Resource nodes on locations (mining, herbs, fishing)
- `/gather` command to collect resources
- Crafting recipes (potions, weapons, keys)
- Player-to-player trading
- Server economy (gold, items, player market)

### Security
- Never requires Administrator permissions
- Minimum permission set only (Send Messages, Embed Links, Manage Threads, Use Slash Commands)
- All GM commands locked behind a configurable GM role, not admin checks
- Rate limiting on all high-frequency commands (Redis)

---

## Tech Stack

| Layer | Tool | Reason |
|---|---|---|
| Bot framework | discord.py 2.x | Best community, fully async, Cogs system |
| Primary database | PostgreSQL + asyncpg | Relational fits RPG data perfectly |
| Active session cache | Redis | Fast reads for live combat state + rate limiting |
| Lore search | ChromaDB | Vector search — AI knows your world |
| AI narration | Groq (llama-3.3-70b) | Fastest inference, cheapest cost |
| AI summaries | Groq (llama-3.1-8b-instant) | Fast + cheap for session summaries |
| Map generation | Pollinations.AI + Pillow | Base terrain from AI, overlays from Pillow |
| Dungeon maps | Pillow BSP | Procedural, deterministic, fast |
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
- **AI narration, NPC dialogue, session summaries** (Phase 4+) use **DeepSeek API** (`deepseek-chat` = V3 fast). DeepSeek replaces Groq for all high-quality AI calls. Groq stays only for the combat action classifier (Phase 2, already built)
- Every AI feature has a full manual fallback — bot works completely offline from AI if all toggles are off

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
2. Player types RP action in chat → bot classifies via Groq 8b → confirmation → dice roll
3. Attack: d20 + modifier + proficiency vs enemy AC → hit = roll damage
4. Natural 20 = Critical Hit (double damage dice)
5. 0 HP = Death saving throws (3 successes = stable, 3 fails = dead)
6. Fight ends: XP awarded, loot dropped

### Starting 6 Classes
| Class | Identity | Key Mechanic | Starter Weapon | Basic Attacks |
|---|---|---|---|---|
| Fighter | Tank/damage | Action Surge (extra action 1/rest) | Longsword (1d8) | Power Strike, Shield Bash, Parry |
| Rogue | Sneaky damage | Sneak Attack (+Xd6 with advantage) | Dagger (1d4+DEX) | Sneak Stab, Smoke Feint, Pickpocket |
| Wizard | Utility caster | Spellbook + Arcane Recovery | Staff (1d6) | Magic Missile, Fire Bolt, Shield |
| Barbarian | Rage machine | Rage (bonus damage + resistance) | Greataxe (1d12) | Reckless Swing, Rage Charge, Intimidate |
| Cleric | Healer/support | Channel Divinity (Turn Undead, domain powers) | Mace (1d6) | Smite, Heal, Turn Undead |
| Warlock | Pact caster | Short rest spell slots + Eldritch Blast | Eldritch Blast (1d10) | Hex, Drain, Dark Pact |

### Economy
- Currency stored as copper, displayed as gp/sp/cp
- Weapons: 1d4 (dagger) to 2d6 (greatsword)
- Armor: AC 11 (leather) to AC 18 (plate)
- Potions, magic items, attunement (max 3 attuned)

---

## Build Order (5 Phases)

### Phase 1 — Core Loop ✅ COMPLETE
- [x] Project setup (folder structure, .env, database connection)
- [x] Character creation wizard (6 classes, 7 races, standard array) — 5-step flow: Race → Class → Background → Loadout → Details
- [x] Backstory / lore field
- [x] Avatar URL
- [x] Proxy system (Tupperbox-style)
- [x] Character sheet display embed
- [x] Multiplayer combat with chat-reading RP flow
- [x] Basic inventory (weapons, armor, potions)
- [x] XP gain and level up

### Phase 2 — Depth ✅ COMPLETE
- [x] Full combat system redesign — chat-reading RP flow using Groq 8b for action classification
- [x] Two character types: DnD (AI combat) and Custom (manual combat only)
- [x] Two fight types: AI fight and Manual fight
- [x] Per-channel combat sessions with titles
- [x] Named attacks (3 per class) with unique mechanics
- [x] Full conditions system (12 conditions — poisoned, burning, bleeding, stunned, blinded, frightened, hexed, prone, parrying, shielded, reckless, raging)
- [x] Lobby multiplayer — lobby as public channel message, join/start via lobby_message
- [x] Flee mechanics (player_roll vs enemy_roll, rest on 15+)
- [x] DeathSaveView updated to message-based
- [x] /combat forfeit command
- [x] GM system — /gm add/remove/list/sheet/pending/approve/deny
- [x] Stat change approval queue — pending requests held in DB for GM review
- [x] Character audit log — edit history posted to configured channel
- [x] /character delete + list
- [x] /character use / unuse (active character system)
- [x] Image URL fix — accept any direct .jpg/.jpeg/.png/.gif/.webp
- [x] Spellcasting (3–4 spells per caster class)
- [x] /rest blocks during combat, preserves attack list across rest
- [x] /help updated to 6-page paginated embed
- [x] Shop gold economy fully wired

---

### Phase 3 — World (Weeks 7–10)

#### 3.1 Location System

**Three core DB tables:**

```
Location:
  - id, guild_id, name, description, short_description
  - location_type: city / dungeon / wilderness / tavern / shop / room / landmark / quest_instance
  - parent_id (FK to self — sub-locations, unlimited nesting)
  - image_url, map_x (0.0–100.0), map_y (0.0–100.0)
  - is_hidden (fog of war), is_safe (no combat), is_indoors (no weather)
  - biome: forest / desert / tundra / mountain / swamp / ocean
  - danger_level (0–10)
  - population_density: deserted / sparse / moderate / bustling / crowded
  - lighting: pitch_black / dim / bright
  - ambient_texts (JSON list of rotating flavor text lines)
  - ambient_sounds (text description — "crackling fire, distant gulls")
  - required_key_item (item name required to enter)
  - required_quest_id (quest must be complete to enter)
  - discovered_by (user_id of first player to find it)
  - ground_items (JSON list of items on the floor)
  - hazards (JSON list of environmental hazards)
  - resources (JSON dict of gather nodes — iron_vein, herb_node, fishing_spot)
  - created_by, created_at, updated_at

LocationConnection:
  - id, guild_id, from_location_id, to_location_id
  - direction: north / south / east / west / up / down / enter / exit / portal
  - label (custom name — "The Old Mill Road")
  - is_locked (bool), required_key_item (item name to unlock)
  - is_secret (bool — hidden from /look exit list)
  - search_dc (DC to find secret exit, default 15)
  - travel_time_minutes (narrative travel time)
  - cross_guild_id (nullable — for cross-server portals)
  - cross_location_id (nullable — target location in other guild)

CharacterLocation:
  - id, character_id, guild_id, location_id, arrived_at
  - UNIQUE(character_id, guild_id)
```

**World structure (via parent_id tree):**
- Top-level areas (parent_id = NULL) appear on the world map
- Sub-locations (parent_id set) are entered via `enter` / `exit` direction
- `north/south/east/west` move between sibling locations
- Unlimited nesting depth (dungeons can go as deep as needed)

**Dungeon nesting example:**
```
The Dark Crypt (dungeon, parent=NULL, coord=32,55)
├── Entrance Hall (room, parent=The Dark Crypt)
│   ├── north → Guard Chamber
│   └── east → Supply Room (locked — needs Rusty Key)
├── Guard Chamber (room, parent=The Dark Crypt)
│   ├── south → Entrance Hall
│   └── north → Boss Room (secret — search DC 18)
├── Boss Room (room, parent=The Dark Crypt)
│   └── south → Guard Chamber
```

**GM commands (build the world):**
- `/world generate [seed]` — generates base world map via Pollinations.AI once, stored as image bytes in DB. Same seed = same map always
- `/world map` — posts current world map with all settlements overlaid
- `/world load_template <name>` — load a pre-built world template (Quick Start, Campaign packs, etc.)
- `/world export` — GM downloads full world as JSON (no character data)
- `/world import <attachment>` — restore or clone a world from JSON
- `/location create <name> <type> [description]` — bot prompts for x,y coordinates (0–100) to place on map
- `/location connect <from> <to> <direction>` — link two locations with a named exit
- `/location edit <name>` — edit all fields via modal
- `/location hide <name>` — fog of war — players can't see or travel here until revealed
- `/location reveal <name>` — reveal a hidden location
- `/location lock <name> <direction> [key_item]` — lock an exit, optionally require a key
- `/location unlock <name> <direction>` — unlock an exit
- `/location delete <name>` — remove a location (players inside moved to nearest connection or spawn)
- `/location list` — GM only, all locations
- `/location set-spawn <name>` — where new characters start
- `/location info <name>` — full GM view (connections, hidden status, who's there, resources)
- `/location set-safe <name>` — toggle safe zone (no combat)
- `/location set-hazard <name> <hazard_type>` — add environmental hazard to location
- `/announce <message>` — post a world announcement to configured announcement channel

**Player commands (navigate the world):**
- `/look` — current location: name, description (with time-of-day flavor), biome/lighting/weather, safe/danger info, exits (locked/secret not shown), who else is here, NPCs present, ground items
- `/travel <direction or location name>` — move to connected location, posts arrival embed; checks for locked door (key in inventory?) or secret exit
- `/travel fast <location name>` — skip narrative, arrive instantly at a previously discovered location (costs gold or free depending on server config)
- `/map` — world map with your position highlighted
- `/players-here` — list all characters at your current location
- `/search` — roll d20 + WIS to find secret exits or hidden items in current location
- `/gather` — collect resources from the current location's resource nodes
- `/discoveries` — show all locations the player has discovered, with date first discovered
- `/weather` — check current weather in your location
- `/ambience set <text>` — GM sets mood text for current channel (shown as pinned embed)
- `/ambience get` — see current channel ambiance

**Lock/unlock mechanics:**

Key types:
- **Single-use** — key breaks after use (door stays unlocked for that player only)
- **Permanent** — key is kept, gate unlocks for everyone
- **Per-player** — each player needs their own copy of the key
- **Quest-gated** — key awarded on quest completion

When player tries `/travel` through a locked exit:
1. Bot checks inventory for the required_key_item
2. If found: "Use the Iron Key to unlock this gate? [Yes] [No]"
3. If single-use: key is removed from inventory
4. If no key: "The iron gate is locked. You need an Iron Key."

**Secret exits:**
- Not shown in `/look` exit list
- Player must `/search` — rolls d20 + WIS vs search_dc
- On success: "You notice a crack in the wall behind the tapestry... it could be a hidden passage."
- First player to discover a secret location earns `discovered_by` credit

**Time-of-day flavor in `/look`:**
- Morning (6–11): "Sunlight streams through the tavern windows..."
- Afternoon (12–17): "The market bustles with midday trade..."
- Evening (18–21): "Long shadows stretch across the cobblestones as lamps are lit..."
- Night (22–5): "The crescent moon hangs low. A chill wind blows..."
- Indoors locations: "You hear rain pattering on the roof outside." (uses weather, not sun)

**Environmental hazards (applied on entering or each combat turn):**
- Poison gas — CON save or take damage
- Lava/fire — DEX save or Burning condition
- Slippery floor — DEX save or Prone condition
- Darkness — no ranged attacks, disadvantage on melee (unless light source in inventory)
- Howling wind — ranged attacks at disadvantage
- Magical silence — no spellcasting

**Zone/proximity effect on combat:**
- `/combat start` only shows characters in the same location as the host
- Falls back to server-wide targeting if no location system is set up

**Spawn on character creation:**
- New characters placed at server's spawn location automatically
- If no spawn set: character gets "No location" state until GM assigns one

**Error recovery rules:**
- Location deleted with players inside → players moved to nearest connected location; if none, moved to spawn
- Quest NPC killed → quest becomes impossible; GM must revive or reassign
- Faction deleted → all reputation rows deleted, faction quests marked inactive

**Rate limits:**
- `/travel`: max once per 2 seconds per character
- `/search`: max 5 per minute per user

---

#### 3.2 Map Generation

**Three map types:**

**World Map (Pollinations.AI base + Pillow overlays):**
- Generated ONCE per guild via Pollinations.AI, stored in DB as image bytes
- Prompt: "Fantasy world map, parchment style, realistic continent shapes with coastlines, mountain ranges in brown/grey, forests in dark green, oceans in blue with wave patterns, rivers in thin blue lines, old paper texture background, legend box, compass rose, border frame — terrain only"
- Seed parameter is critical — same seed = same map always
- Every time a new settlement is added, bot loads the stored base image, draws ALL current location markers + name labels on top with Pillow, posts the result
- Location symbols: ★ Capital city (gold), ● City (white), · Town (blue), ☠ Dungeon (red skull)
- Hidden locations NOT drawn for players (GM map shows all)

**City Map (Pollinations.AI, generated once per city):**
- Prompt: "Medieval fantasy city, top-down view, hand-drawn parchment style, labeled districts, city walls with gates, main road, river, docks, compass rose"
- Generated once per city location, stored on the Location row, reused forever

**Dungeon Map (Pillow BSP procedural):**
- BSP (Binary Space Partitioning) algorithm: split 40x40 tile space recursively, place rooms in leaf nodes, connect with L-shaped corridors
- Room labels: Entrance, Boss Room, Treasure Room, Trap Room, Storage
- Render: Floor (dark grey), Walls (dark), Doors (brown), Labels (white)
- Regenerated each time players enter (different layout each visit), same seed for same dungeon instance

**Coordinate system:**
- x,y stored as 0.0–100.0 (percentage of image dimensions)
- Bot converts to pixel coordinates: `pixel_x = (map_x / 100) * image_width`
- GM eyeballs the generated map and enters coordinates when creating a location

**Commands:**
- `/world map` — posts world map with all visible settlements as overlay
- `/map` — same but with player's current position highlighted as a star
- `/location map` — posts the city or dungeon map for the player's current location

**Implementation order:**
1. Location DB models + CRUD commands (prerequisite)
2. Pillow overlay function with test data
3. `/world generate` with Pollinations + seed
4. `/world map` with overlays
5. `/location map` for city maps (Pollinations)
6. BSP dungeon generator (Pillow)

---

#### 3.3 Lore Wiki

**DB Table:**
```
LoreEntry:
  - id, guild_id
  - title, content
  - category: faction / npc / location / event / item / history / rumor / other
  - tags (JSON list)
  - is_canon (bool — confirmed fact)
  - is_rumor (bool — unverified, marked as such in search results)
  - visibility: public / gm_only / quest_reward
  - linked_entry_ids (JSON list of related lore IDs)
  - importance (0–10, used to boost search ranking)
  - image_url (concept art, portrait, or map thumbnail)
  - created_by, updated_at
```

**ChromaDB per-guild namespacing:**
- Each guild gets its own ChromaDB collection: `lore_{guild_id}`
- Write to PostgreSQL first → sync to ChromaDB
- If ChromaDB is down: fall back to SQL ILIKE search

**Search experience:**
- `/lore search "fire weakness trolls"` returns top 5 results with relevance %
- Result ranking: ChromaDB distance score → exact tag match boost (+0.1) → importance boost (+0.05 per point)
- Failure fallbacks: "Did you mean X?" for near-misses, full-text fallback if no vector results

**Commands:**
- `/lore add <title> [content] [category] [tags] [image_url]` — GM adds entry
- `/lore edit <title>` — GM edits via modal
- `/lore delete <title>` — GM removes
- `/lore search <query>` — top 5 results with relevance %
- `/lore view <id_or_title>` — full entry with image
- `/lore list [category]` — paginated list
- `/lore random` — random lore entry (fun for world discovery)

---

#### 3.4 NPC System

**Two DB tables:**

```
NPC:
  - id, guild_id
  - name, title, race, gender, age
  - description, appearance
  - location_id (where the NPC lives)
  - is_roaming (bool — NPC can move between locations)
  - disposition: friendly / neutral / unfriendly / hostile
  - is_hostile (attacks on sight), is_killable, is_dead
  - Combat stats: hp_max, hp_current, armor_class, attack_bonus, damage_dice, damage_bonus, xp_value
  - Economy: gold, shop_inventory (JSON)
  - faction_id (which faction this NPC belongs to)
  - greeting (opening line when player talks to them)
  - dialogue_topics (JSON dict — keyword → response text)
  - image_url
  - created_by, created_at, updated_at

NPCMemory (one row per NPC-player pair):
  - id, npc_id, user_id, guild_id
  - UNIQUE(npc_id, user_id)
  - first_met (datetime)
  - last_spoke (datetime)
  - interaction_count
  - attitude (-10 to +10, starts at 0)
  - favors_done
  - knows_name (bool — NPC knows player's character name)
  - topics_discussed (JSON list)
  - last_topic
  - notes (GM freetext — "this player helped them once")
```

**NPC memory system (no AI required):**

Pure string templating + DB logic. What the bot can do automatically:

| Trigger | Bot Response |
|---|---|
| First time talking | "I haven't seen you around before, stranger." |
| Player returns | "Ah, [name], welcome back!" (if knows_name = true) |
| attitude ≥ 5 | "Good to see you again, friend!" |
| attitude ≤ -3 | NPC is cold or refuses to speak |
| Discussed topic before | "You asked about the mine last time, yes?" |
| Player did a favor | "After what you did for me, I'll tell you anything." |

**Dialogue system (keyword matching, no AI):**
```python
dialogue_topics = {
    "greeting": "Welcome to the Rusty Nail, traveler!",
    "rumors": "I've heard strange noises from the old mine...",
    "work": "I'm a blacksmith. Weapons, armor, tools — I make it all.",
    "quest": "The mayor is looking for help.",
    "weather": "The rains have been heavier than usual.",
    "bye": "Safe travels, friend!"
}
```
Bot extracts keywords from player message and finds the closest key match.

**GM commands:**
- `/npc create <name> [location]` — guided creation wizard
- `/npc edit <name>` — modal for all fields
- `/npc move <name> <location>` — change NPC location
- `/npc kill <name>` — mark NPC as dead
- `/npc revive <name>` — bring back a dead NPC
- `/npc list [location]` — paginated list
- `/npc info <name>` — full GM view (stats, memory summary, location)
- `/npc set-attitude <name> <@user> <value>` — GM adjusts a player's standing with an NPC
- `/npc add-dialogue <name> <keyword> <response>` — add a dialogue topic

**Player commands:**
- `/npc talk <name> [message]` — initiates conversation; bot keyword-matches and responds
- `/npc look <name>` — shows NPC description and appearance embed

**Phase 4 groundwork (built now, used later):**
- Store entire interaction history in NPCMemory (append log)
- Store NPC personality as structured data (traits, speaking style fields)
- Tag dialogue topics with vector embeddings for RAG
- Build append-only event log per NPC-player pair

---

#### 3.5 Quest System

**Three DB tables:**

```
Quest:
  - id, guild_id
  - name, description, journal_entry (longer text shown in player journal)
  - is_active (can be accepted), is_repeatable, is_hidden (discoverable only via NPC talk)
  - min_level
  - required_quest_id (prerequisite chain quest)
  - required_faction, required_reputation (min tier to accept)
  - quest_type: standard / chain / daily / world_event / faction
  - reward_xp, reward_gold
  - reward_items (JSON list — [{"item": "Iron Sword", "qty": 1, "is_choice": true}])
  - reward_faction_rep (JSON dict — {"Thornwall Guard": 75, "Thieves Guild": -20})
  - unlock_location_id (quest reward grants access to a location)
  - unlock_quest_id (quest reward unlocks a follow-up quest)
  - start_location_id, end_location_id
  - giver_npc_id, turnin_npc_id
  - created_by, created_at, updated_at

QuestObjective:
  - id, quest_id, guild_id
  - order (display order), description (player-facing text)
  - objective_type (see 11 types below)
  - target_npc_id, target_enemy_type, required_count
  - talk_npc_id
  - target_location_id
  - item_name, item_count
  - explore_location_id
  - use_item, use_location_id
  - escort_npc_id, escort_destination_id
  - is_optional (bonus objective), hidden_until (reveal after objective X)

PlayerQuest:
  - id, character_id, guild_id, quest_id
  - UNIQUE(character_id, quest_id)
  - status: accepted / completed / failed / turned_in
  - progress (JSON dict — {objective_id: current_count})
  - accepted_at, completed_at, turned_in_at
```

**11 objective types with auto-tracking:**

| Type | Auto-Tracks When |
|---|---|
| kill_npc | Named NPC dies in combat |
| kill_enemy | Combat victory vs matching enemy type |
| talk_to_npc | `/npc talk` used with the right NPC |
| travel_to | `/travel` lands at target location |
| collect_item | Player loots or crafts the item |
| deliver_item | `/npc give <item> <npc>` with matching NPC |
| explore_area | Player first enters a hidden location |
| use_item_at_location | `/item use <item>` while at target location |
| escort_npc | NPC + player both arrive at destination |
| reach_level | Checked on every level-up |
| faction_rep | Checked when faction rep changes |

**Quest flow:**
1. Discovery — NPC dialogue (`/npc talk`), quest item, or `/quest list`
2. Acceptance — `/quest accept "The Missing Sheep"`
3. Active — appears in `/quest status` with objectives + progress bars
4. Auto-tracking — objectives fire in background on matching events
5. Completion — `/quest complete "The Missing Sheep"` sends GM approval embed
6. GM Approval — Approve/Deny buttons; auto-approval option for simple quests in Phase 4
7. Turn-in — if `turnin_npc_id` set, player must `/npc talk` to that NPC to finalize
8. Rewards — gold, XP, items (choice or auto), faction rep, location unlocks awarded

**Reward structure:**
```json
{
  "xp": 500,
  "gold": 200,
  "items": [
    {"item": "Iron Sword", "qty": 1, "is_choice": true},
    {"item": "Steel Shield", "qty": 1, "is_choice": true},
    {"item": "Health Potion", "qty": 3, "is_choice": false}
  ],
  "faction_rep": {"Thornwall Guard": 100, "Merchants Guild": -20},
  "unlock_location": "Throne Room",
  "unlock_quest": "The King's Favor"
}
```

**Commands:**
- `/quest create` — GM quest builder wizard
- `/quest list` — available quests filtered by level, location, prerequisites
- `/quest accept <name>` — creates PlayerQuest row
- `/quest status` — active quests with objective progress bars
- `/quest complete <name>` — sends GM approval embed
- `/quest journal` — full journal view (active + completed + failed)

---

#### 3.6 Faction Reputation

**Three DB tables:**

```
Faction:
  - id, guild_id
  - name, description
  - faction_type: guild / kingdom / religion / mercenary / criminal / merchant / academic
  - color (hex for embeds), icon_emoji
  - starting_rep (default rep all players begin with, usually 0)
  - leader_npc_id
  - headquarters_location_id
  - created_by, created_at, updated_at

FactionReputation:
  - id, character_id, guild_id, faction_id
  - UNIQUE(character_id, faction_id)
  - reputation (int, can be negative)
  - updated_at

FactionPerk:
  - id, faction_id, guild_id
  - required_tier: friendly / honored / revered / exalted
  - perk_type: discount / area_access / item_for_sale / quest_unlock / npc_recruit / combat_aid / title
  - perk_data (JSON — e.g. {"discount_percent": 10} or {"location_id": 42} or {"title": "Champion of Thornwall"})
```

**8 reputation tiers with thresholds:**

| Tier | Min Rep | Max Rep | Color | Effect |
|---|---|---|---|---|
| Hated | -3000 | -1001 | 🔴 Red | Attacked on sight by faction NPCs |
| Hostile | -1000 | -301 | 🟠 Orange | NPCs refuse to speak |
| Unfriendly | -300 | -1 | 🟡 Yellow | Cold greetings, no help |
| Neutral | 0 | 99 | ⚪ White | Default — NPCs indifferent |
| Friendly | 100 | 499 | 🟢 Green | Discounts (10%), basic quests, rumors |
| Honored | 500 | 999 | 🔵 Blue | Restricted area access, 15% discount, mid-level quests, faction items for sale |
| Revered | 1000 | 1999 | 🟣 Purple | Secret areas, 20% discount, unique weapons/armor, special dialogue |
| Exalted | 2000+ | — | 🟡 Gold | Faction leader access, 25% discount, legendary item, call faction aid in combat (1/day), unique title |

**How actions map to rep changes:**

| Action | Rep Change |
|---|---|
| Complete a faction quest | +50 to +200 (by difficulty) |
| Kill a faction member | -50 to -200 (by NPC importance) |
| Kill a faction enemy | +25 to +50 |
| Turn in faction items (scalps, goods) | +5 to +15 per item |
| Donate gold | +1 per 10 gold donated |
| Help a faction member in combat | +10 to +25 |
| Sabotage faction operations | -100 to -500 |
| Choose a faction over another in a quest | +50 to chosen, -20 to rival |
| Betray a faction | -500 to -1000 |
| Champion a faction in PvP combat | +25 per victory |

**Concurrent tracking:** One action can affect multiple factions simultaneously. Killing a faction member might: -100 with that faction, +25 with their rival, +10 with a neutral third party.

**What factions unlock per tier:**

| Tier | Unlocks |
|---|---|
| Friendly | 10% shop discount, basic dialogue, 1–2 simple quests |
| Honored | Restricted area access (inner keep, guild hall), 15% discount, 3–5 mid-level quests, faction-specific items for purchase |
| Revered | Secret area access (vault, archives), 20% discount, unique weapons/armor, faction mount, special dialogue, recruit low-level faction NPCs |
| Exalted | Faction leader access, 25% discount, legendary item, call faction aid in combat once/day, unique title, faction-specific Discord role (if GM configures it) |

**Faction relationships:**
- **Faction + Location** — A location can be owned by a faction (faction_id on Location). Honored+ players enter restricted locations; Hated players are turned away or attacked
- **Faction + NPC** — NPC disposition = base disposition + faction rep modifier. Friendly NPC of a Hated faction may still attack you. Hostile NPC of a faction you're Exalted with may offer a redemption quest
- **Faction + Quest** — Quests can require minimum rep tier. Quest rewards include rep changes. Some quests are faction-exclusive

**Commands:**
- `/faction create` — GM creates a faction
- `/faction edit <name>` — GM edits faction details
- `/faction delete <name>` — GM removes faction (all rep rows deleted, faction quests marked inactive)
- `/faction list` — all factions, brief description, player's current tier with each
- `/faction status <name>` — detailed view: numeric rep, progress bar to next tier, perks unlocked, recent rep changes
- `/faction history <name>` — last 20 rep events ("You gained 75 rep by completing 'Supply Run'")
- `/gm faction award <faction> <@user> <amount>` — GM manually adjusts rep

---

#### 3.7 Weather System

**DB Table:**
```
WeatherState:
  - guild_id (primary key)
  - weather_type: clear / cloudy / rainy / stormy / foggy / snowy / windy / scorching
  - temperature: freezing / cold / cool / moderate / warm / hot / scorching
  - changed_at
```

**How weather works:**
- Each guild has a persistent weather state stored in DB
- Weather changes on a timer (every 30–60 minutes, server-side task) or on GM command
- Weather shown on `/look` location header for outdoor locations
- Indoors (is_indoors=True): "You hear rain pattering on the roof outside."
- Weather effects on combat: rain → ranged attacks at disadvantage; storm → all ranged impossible; fog → targets must be within 15 feet or blinded condition

**Commands:**
- `/weather` — check current weather in your location
- `/weather set <type>` — GM overrides weather manually

---

#### 3.8 Party / Group System

**DB Table:**
```
Party:
  - id, guild_id, leader_character_id
  - name (optional)
  - created_at

PartyMember:
  - id, party_id, character_id, guild_id, joined_at
  - UNIQUE(character_id, guild_id)
```

**Commands:**
- `/party create [name]` — form a group (creates party, creator is leader)
- `/party invite <@user>` — send party invite (target accepts via button)
- `/party leave` — leave the group
- `/party disband` — leader disbands
- `/party status` — see all party members, locations, HP
- `/party travel <direction>` — leader travels, whole party follows (each gets confirmation prompt)

**Party mechanics:**
- Shared quest progress: if one party member completes an objective, all get credit
- Party members see each other on `/players-here`
- Combat: party members can join same combat session directly
- XP split: PvP XP divided equally between all party members in the fight

---

#### 3.9 Player Housing

**DB Table:**
```
PlayerHousing:
  - id, character_id, guild_id
  - location_id (FK to Location — housing is a sub-location)
  - purchase_price (gold paid)
  - description (GM or player writes it)
  - purchased_at
```

**Commands:**
- `/housing buy` — purchase a room at current location (if location has rooms for sale, costs gold)
- `/housing decorate <description>` — write a custom description for your home
- `/housing view [character]` — see your or another player's home
- `/housing invite <@user>` — invite another player into your private home
- Housing is a Location sub-type (type = "room") tied to a player

---

#### 3.10 Crafting System

**DB Table:**
```
CraftingRecipe:
  - id, guild_id
  - name, description
  - output_item, output_qty
  - ingredients (JSON list — [{"item": "Iron Ore", "qty": 2}, {"item": "Leather Strip", "qty": 1}])
  - required_location_type (must be at a forge, alchemy table, etc.)
  - created_by

GatherEvent (log of resource gathering):
  - id, character_id, guild_id, location_id
  - resource_type, qty_gathered, gathered_at
```

**Commands:**
- `/craft list` — see all available recipes (filtered by ingredients you have)
- `/craft <recipe>` — craft an item if you have the resources and are in the right location
- `/gather` — collect resources from the current location's resource nodes (roll DEX or WIS)
- Resources: iron ore (mine), herbs (wilderness), fish (docks/river), wood (forest), leather (wilderness after combat)

---

#### 3.11 Player-to-Player Trade

**Flow:**
1. `/trade request <@user>` — send trade request
2. Both players see a trade window embed (your items + their items + gold amounts)
3. Each side fills in what they're offering via buttons/modals
4. Both click Accept → trade executes atomically
5. Trade posted to audit log channel

**Commands:**
- `/trade request <@user>` — open a trade
- `/trade offer <item> [qty]` — add item to your side of the trade window
- `/trade gold <amount>` — add gold to your side
- `/trade accept` — confirm trade
- `/trade cancel` — cancel trade

---

#### 3.12 Guild Calendar & Event Scheduling

**DB Table:**
```
WorldEvent:
  - id, guild_id
  - name, description
  - event_type: session / world_event / quest / raid
  - location_id (where the event takes place)
  - scheduled_at (datetime)
  - created_by

EventRSVP:
  - id, event_id, user_id, status: attending / maybe / declined
```

**Commands:**
- `/event create <name> <datetime>` — GM schedules a session or event
- `/event list` — upcoming events
- `/event rsvp <event_id> <attending/maybe/declined>` — player marks attendance
- `/event info <event_id>` — details + RSVP list
- Events auto-post a reminder 1 hour before to a configured channel

---

#### 3.13 GM Dashboard

**Command: `/gm dashboard`**

Single embed showing the full world state:
- Total locations (visible / hidden count)
- Total NPCs (alive / dead)
- Total active quests
- Total factions
- Total players currently in-world (characters with a location assigned)
- Current weather
- Recent WorldEvent log (last 5 events)
- Quick links: `/location list`, `/npc list`, `/quest list`, `/faction list`

---

#### 3.14 World Templates

**How templates work:**
- Template is a JSON file bundled with the bot or fetched from a URL
- `/world load_template <name>` reads the JSON and:
  1. Creates all locations, NPCs, quests, factions, lore entries
  2. Assigns guild_id on every row to current guild
  3. Reports: "Loaded 12 locations, 5 NPCs, 3 quests, 2 factions"

**Template types:**
1. **Blank world** — world map generated, GM adds everything
2. **Quick-start** — 3 starter locations (Inn, Market, Wilderness), 2 NPCs, 1 quest, 1 faction — playable in 5 minutes
3. **Full campaign** — 20+ locations, NPCs, quest chains, lore, factions (future premium)

**World import/export:**
- `/world export` — GM downloads full world as JSON (no character/player data)
- `/world import <attachment>` — restore or clone world from JSON
- Export includes a version field for future migration compatibility

---

#### 3.15 Tutorial System

**DB Table:**
```
TutorialProgress:
  - id, user_id, guild_id
  - UNIQUE(user_id, guild_id)
  - completed_steps (JSON list — [1, 2, 3])
  - current_step
  - is_completed (bool)
  - started_at, completed_at
```

**6-step paginated ephemeral embed flow (Next/Back/Skip buttons):**

- Step 1: Welcome — what LoreForge is, what makes it different
- Step 2: Create Your Character — links to `/character create`, tips on starting class
- Step 3: Read the Lore — links to `/lore search`, explains mid-session use
- Step 4: Explore the World — links to `/look` + `/travel`, explains exit types, mentions locked doors and `/search`
- Step 5: Combat Demo — chat-reading explained with example (type → confirm → dice), named attacks, death saves
- Step 6: What's Next — quests, rest, NPCs, factions, shop — one-liner per feature

**Auto-trigger:**
- Offered automatically after first `/character create`
- Auto-offered on first command ever (check TutorialProgress for that user+guild)
- If skipped: 7-day cooldown before auto-offering again
- `/tutorial resume` to continue where they left off

**GM tools:**
- `/tutorial show <@user>` — GM triggers tutorial for a specific player
- `/tutorial reset <@user>` — GM resets a user's tutorial

**Completion reward:** +50 XP starter bonus (teaches the player about rewards)

---

#### 3.16 Discoveries / Exploration Log

- Every time a player is first to enter a hidden location, they earn `discovered_by` credit on that Location
- `/discoveries` — paginated log of all locations the player has ever entered, with date first visited
- First discovery earns a public announcement: "Lyra has discovered the Lost Vault of Ashkara!"
- Achievement milestones: "Pathfinder" at 10 discoveries, "Explorer" at 50

---

#### Phase 3 Build Order

1. DB models — Location, LocationConnection, CharacterLocation, NPC, NPCMemory, Quest, QuestObjective, PlayerQuest, Faction, FactionReputation, FactionPerk, WeatherState, TutorialProgress, LoreEntry, Party, PartyMember, PlayerHousing, CraftingRecipe, WorldEvent, EventRSVP
2. Location CRUD — `/location create`, `/location connect`, `/location edit`, `/location hide/reveal/lock/unlock`, `/location list`, `/location info`, `/location set-spawn`, `/location set-safe`
3. Player travel — `/look` (time-of-day, weather, exits), `/travel` (lock/key check, secret check), `/players-here`, `/search`, `/discoveries`
4. Combat targeting — filter to same location, fall back to server-wide
5. Spawn point wired into character creation
6. World map — `/world generate` (Pollinations + seed), `/world map` (Pillow overlays), `/location map` (city + dungeon BSP)
7. Weather system — WeatherState model, `/weather`, `/weather set`, display in `/look`
8. NPC system — `/npc create/edit/move/kill/revive/list/info/talk/look`, NPCMemory tracking
9. Quest system — `/quest create/list/accept/status/complete`, 11 objective type auto-trackers, GM approval flow, rewards
10. Faction system — `/faction create/edit/delete/list/status/history`, rep tiers, perk table, location/NPC/quest hooks
11. Lore wiki — `/lore add/search/view/edit/delete/list/random` (ChromaDB)
12. World templates — `/world load_template`, `/world export`, `/world import`
13. Party system — `/party create/invite/leave/disband/status/travel`
14. Trade system — `/trade request/offer/gold/accept/cancel`
15. Crafting — `/craft list/craft`, `/gather`, CraftingRecipe table
16. Housing — `/housing buy/decorate/view/invite`
17. Calendar — `/event create/list/rsvp/info`
18. `/gm dashboard`
19. Tutorial — `/tutorial`, TutorialProgress tracking, auto-trigger, 6-step flow
20. Polish — `/discoveries`, ambiance, cooldown display messages, error recovery handlers

---

### Phase 4 — Intelligence (Weeks 11–14)

**Core principle:** AI is optional — every feature works without it. AI adds depth, never replaces GM control.
**AI provider:** DeepSeek API (`deepseek-chat` = V3 fast) for all new AI calls. Every AI toggle is OFF by default.

---

#### 4.1 AI Narration System (DeepSeek, GM-Toggleable)

**How it works:**
- Off by default per guild
- GM enables with `/ai toggle narration`
- When ON: DeepSeek narrates combat hits, misses, kills, crits — lore-aware, 2 sentences max
- When OFF: bot uses pre-written template strings — fully featured, zero API calls

**Narration styles (GM picks one):**
- `epic` — cinematic, dramatic
- `gritty` — brutal, realistic
- `comedic` — light, humorous
- `minimal` — one-liner only

**RAG context injection:**
- Before each AI call, query ChromaDB for top 3 lore snippets relevant to: attacker class + location + enemy type
- Injected as system context — AI can only reference injected facts, never invent lore
- If ChromaDB unavailable: silent fallback to narration without lore context

**Prompt structure:**
```
System: You are a GM narrating combat in {world_name}.
        World facts: {lore_snippet_1} / {lore_snippet_2} / {lore_snippet_3}
        Style: {narration_style}. Max 2 sentences. Never contradict lore.
User: {attacker} used {attack_name} ({weapon}) against {target} → {result}: {damage} dmg.
      {target} has {hp_remaining} HP. Conditions applied: {conditions}.
```

**DB table:**
```
AIConfig:
  - guild_id (PK)
  - narration_enabled (bool, default False)
  - narration_style: epic / gritty / comedic / minimal
  - npc_ai_enabled (bool, default False)
  - session_summary_enabled (bool, default False)
  - updated_by, updated_at
```

**Commands (`/ai` group):**
- `/ai toggle narration` — GM toggles combat AI narration on/off
- `/ai toggle npc` — GM toggles AI NPC dialogue on/off
- `/ai toggle summary` — GM toggles auto session summaries on/off
- `/ai style <epic/gritty/comedic/minimal>` — set narration tone
- `/ai status` — shows all AI toggles for this guild

---

#### 4.2 Session System

**Trigger:** GM calls `/session end` or `/session summary`

**How it works:**
1. Fetch last N messages from session channel (configurable, default 100)
2. Strip bot embeds — keep human messages + key bot events (combat results, quest completions, loot)
3. Send to DeepSeek with structured prompt → formatted summary embed
4. Summary stored in DB, viewable later

**Output format:**
```
📜 Session Summary — [Date]
🎭 Characters: [list]
📍 Location: [location name]
⚔️ Combat: [X fights, Y kills, Z deaths]
📦 Loot: [notable items]
📋 Quests: [completed/progressed]
✨ XP Awarded: [total]
📖 Story: [2-3 sentence AI narrative of the session]
```

**DB table:**
```
SessionLog:
  - id, guild_id, channel_id
  - started_at, ended_at
  - characters_present (JSON list)
  - summary_text
  - combat_count, quest_completions, total_xp
  - created_by
```

**Commands (`/session` group):**
- `/session start [title]` — GM marks session start, posts pinned embed
- `/session end` — GM ends session, triggers auto-summary if enabled
- `/session summary` — manually generate summary for last session (works without AI toggle — just compiles stats)
- `/session log` — paginated history of all past sessions

---

#### 4.3 Boss Encounter System

**Philosophy:** GM has total control. Bosses are GM-spawned enhanced enemies. No AI required — all mechanics are fully deterministic. AI only narrates if narration is toggled on.

**DB tables:**
```
BossTemplate:
  - id, guild_id
  - name, title, description, image_url
  - hp_max, armor_class, attack_bonus, damage_dice, damage_bonus
  - xp_value, gold_drop, loot_table (JSON)
  - phase_count (1–4)
  - phase_thresholds (JSON — e.g. [75, 50, 25] as % HP remaining)
  - phase_abilities (JSON — per phase: {name, description, effect, condition_applied})
  - legendary_actions (JSON — [{name, description, cost}])
  - legendary_action_count (per round, default 3)
  - minion_template_id (FK to BossTemplate — spawns these as minions)
  - minion_count_per_summon (default 2)
  - is_lair_boss (bool — lair actions fire at initiative 20)
  - lair_actions (JSON — [{name, effect, initiative_count}])
  - created_by, created_at

SpawnedBoss:
  - id, guild_id, channel_id, combat_session_id
  - template_id (FK)
  - display_name (can override template name)
  - hp_current, current_phase
  - legendary_actions_remaining (resets each round)
  - conditions (JSON)
  - forced_target_id (character_id — GM pinned a target)
  - spawned_at, spawned_by
```

**Phase system (how it works in combat):**
- Phase 1 (100–76% HP): Normal attacks
- Phase 2 (75–51% HP): Gains new ability ("The dragon's eyes glow red…"), description text changes
- Phase 3 (50–26% HP): AoE attack unlocked, speed changes
- Phase 4 (25–0% HP): Desperate — legendary action count +1, auto-summons minions

**Legendary actions:**
- X actions per round (resets at start of boss turn)
- Used at the END of ANY player's turn — not the boss's own turn
- Cost 1–3 per action (GM defines on template)
- Example: `Attack (1)`, `Tail Sweep AoE (2)`, `Summon Minions (3)`

**Lair actions (optional):**
- At initiative count 20 each round, a lair action fires automatically
- GM defines on boss template: "Stalactites fall — all players DEX save DC 15 or 2d10 piercing"
- Lair actions cycle through the list in order each round

**AoE attacks:**
- Hit all players at same location
- Each player rolls their own DEX save (DC = 8 + boss attack_bonus + boss CON mod)
- Fail → full damage. Save → half damage

**Loot table format:**
```json
[
  {"item": "Dragon Scale", "qty": 1, "chance": 1.0},
  {"item": "Inferno Blade", "qty": 1, "chance": 0.25},
  {"item": "Gold Hoard", "qty_dice": "5d100", "chance": 1.0}
]
```
On boss kill: loot auto-posted as embed, items added to location's `ground_items`. Players pick up via `/item take`.

**GM boss commands (`/gm boss` group):**
- `/gm boss create` — wizard to build a boss template (name, HP, AC, damage dice, phases, abilities, loot)
- `/gm boss edit <name>` — edit existing template via modal
- `/gm boss list` — all boss templates for this guild
- `/gm boss spawn <name> [location] [hp_override] [name_override]` — spawn into active or new combat session
- `/gm boss force-attack <@player>` — force boss to target this player on its next turn
- `/gm boss force-ability <ability_name>` — force boss to use a specific ability this turn
- `/gm boss set-phase <1/2/3/4>` — manually jump boss to a phase (triggers phase announcement)
- `/gm boss hp <value>` — set boss HP directly
- `/gm boss summon-minions` — manually trigger minion spawn outside of phase trigger
- `/gm boss legendary <action_name>` — spend a legendary action manually right now
- `/gm boss kill` — instantly kill the active boss (awards XP + loot, ends encounter cleanly)
- `/gm boss flee` — boss retreats (no loot, partial XP, posts flavor escape text)

**Minion system:**
- Minions are lightweight SpawnedBoss entries (low HP, simple attack, `parent_boss_id` field)
- Act on same initiative as the boss
- Spawned automatically on phase trigger or manually via `/gm boss summon-minions`
- If all minions die, boss does not get extra legendary actions (no catch-up mechanic)

---

#### 4.4 All 12 Classes

**Phase 2 (done):** Fighter, Rogue, Wizard, Barbarian, Cleric, Warlock

**New in Phase 4:**

| Class | Identity | Key Mechanic | Starter Weapon | 3 Named Attacks |
|---|---|---|---|---|
| Paladin | Holy warrior | Divine Smite — spend a spell slot on a hit: +2d8 radiant damage | Longsword (1d8) | Divine Smite, Lay on Hands (heal ally 1d8+level HP), Sacred Weapon (+STR mod to all attacks, 1 min) |
| Ranger | Hunter/tracker | Hunter's Mark — mark a target; deal +1d6 on every hit against them (lasts until rest) | Shortbow (1d6+DEX) | Hunter's Mark, Volley (fire once at every enemy in location), Conceal (DEX roll to go Hidden) |
| Druid | Nature caster | Wild Shape — transform into a beast, gain beast HP pool (reverts at 0 beast HP) | Quarterstaff (1d6) | Thorn Whip (1d6 + pull target, forcing Prone), Healing Word (heal self or ally 1d4+WIS), Entangle (target Prone until STR save) |
| Bard | Support/face | Bardic Inspiration — grant an ally a d6 to add to any roll this turn (3/short rest) | Rapier (1d8+DEX) | Vicious Mockery (1d4 psychic + Frightened), Cutting Words (reduce enemy roll by d6 as reaction), Inspire (give ally +2 to next attack or save) |
| Monk | Mobile striker | Ki Points — spend to power abilities (3 + level per short rest) | Unarmed (1d6+DEX) | Flurry of Blows (2 quick strikes, each 1d4+DEX, costs 1 Ki), Stunning Strike (1 Ki: STR save or Stunned 1 turn), Step of the Wind (1 Ki: Disengage + Prone immunity until next turn) |
| Sorcerer | Raw power | Metamagic — modify spells: Quicken (cast + bonus action), Twin (hit 2 targets), Empower (reroll damage dice once) | Arcane Focus (1d4) | Chaos Bolt (1d8 random type — if doubles: chains to new target), Twinned Fireball (hit target + one adjacent for 2d6), Wild Surge (roll d3: explode 3d8 to all enemies / heal self 2d8 / swap HP with target) |

**Special mechanics to implement:**

Wild Shape (Druid):
- Usable 2× per short rest
- Beast forms: Wolf (AC 13, 2d8+2 HP, Bite 1d6+2), Bear (AC 11, 3d8+9 HP, Claws 2d6+5), Eagle (AC 13, 1d6+2 HP, Talon 2d4+3)
- Conditions persist across transform. Revert on command or when beast HP hits 0 (character HP unchanged)
- DruidWildShapeView — button UI to pick form, posts new combat status showing beast HP vs character HP

Ki Points (Monk):
- `ki_points`, `ki_max` fields added to Character table
- Recharge on short rest. Track spend in combat session state
- `/rest short` recharges Ki

Bardic Inspiration (Bard):
- `bardic_inspiration_dice` field on Character (count of d6s available)
- Ally uses it via reaction button on their next attack/save embed — bot rolls the d6 and adds it
- Recharges on short rest (default) or long rest (if GM config `bard_recharge_long = True`)

Hunter's Mark (Ranger):
- `marked_target_id` field on combat session participant
- Persists until player rests or marks a new target (unmarks old)
- +1d6 auto-added to every hit against the marked target

---

#### 4.5 AI-Enhanced NPC Dialogue (DeepSeek, Optional)

Off by default. When off, Phase 3 keyword matching runs unchanged.

When ON (`/ai toggle npc`):
- `/npc talk <name> <message>` routes to DeepSeek instead of keyword lookup
- NPC context injected as system prompt:
  ```
  You are {npc_name}, a {race} {title}.
  Personality: {personality_traits}. Speaking style: {speaking_style}.
  Your relationship with {player_name}: attitude {attitude}/10,
  {interaction_count} past conversations, last topic: {last_topic}.
  World facts you know: {top 3 lore snippets}.
  Never break character. Max 3 sentences.
  ```
- After each AI response, bot parses a hidden attitude delta tag and updates NPCMemory:
  `<!-- {"attitude_delta": +1} -->`
- GM can always override via `/npc set-attitude` — AI cannot lock a relationship state

---

#### 4.6 Quest Auto-Verification

Auto-complete (no GM approval) for these objective types:

| Objective Type | Auto-Trigger |
|---|---|
| `kill_npc` | Named NPC `is_dead` flipped → scan active quests |
| `kill_enemy` | Boss/enemy killed → match by enemy type tag |
| `travel_to` | `/travel` arrives at target location → scan quests |
| `collect_item` | Item added to inventory → scan quests |
| `reach_level` | Level-up event → scan quests |
| `faction_rep` | Rep change crosses tier threshold → scan quests |

- `auto_complete = True` on QuestObjective rows for these types
- On auto-complete: ephemeral "✅ Objective complete: [description]" to player
- Full quest auto-completes when all objectives done → public reward embed
- Rewards auto-distributed: XP, gold, items, faction rep, location unlocks all fire instantly

Still requires GM approval: `deliver_item`, `escort_npc`, `use_item_at_location`, and any objective with `gm_verify = True`

---

#### 4.7 GM Stat Approval System

```
PendingApproval:
  - id, guild_id, character_id, requested_by
  - field_name (e.g. "strength", "hp_max", "gold")
  - old_value, new_value
  - reason (player note)
  - status: pending / approved / denied
  - reviewed_by, reviewed_at, created_at
```

**Edit routing:**

| Field | Route |
|---|---|
| avatar_url, name, backstory, proxy | Instant — no queue |
| hp_current (player self-update) | Instant |
| STR / DEX / CON / INT / WIS / CHA | → Pending queue |
| hp_max, level, gold | → Pending queue |
| weapons, armor | → Pending queue |
| Any field by GM | Instant — no queue |

**Commands:**
- `/character edit` — modal routes each field per table above
- `/gm pending` — list all pending approval requests for this guild
- `/gm pending-user <@user>` — pending requests for one player
- `/gm approve <request_id>` — approve a pending change
- `/gm deny <request_id> [reason]` — deny, optional reason sent to player

GM channel notification on new request:
- Embed: character name, field, old → new value, player reason
- Buttons: ✅ Approve / ❌ Deny (Deny opens modal for reason)

---

#### 4.8 World JSON Loader (Full Validation)

**Schema:**
```json
{
  "version": "1.0",
  "world_name": "The Shattered Realm",
  "locations": [...],
  "npcs": [...],
  "quests": [...],
  "factions": [...],
  "lore_entries": [...],
  "boss_templates": [...],
  "crafting_recipes": [...],
  "spawn_location": "Market Square"
}
```

**Validation on import:**
- Required field check (version, world_name)
- Referential integrity: NPC `location_id` must match a location in the file
- Quest `giver_npc_id` must exist in the NPC list
- Boss `minion_template_id` must exist in `boss_templates`
- Version field checked — reports incompatible versions with guidance

**Commands:**
- `/world import <file>` — import with full validation + detailed error report
- `/world export` — export full world as JSON (no character data)
- `/world validate <file>` — dry run: validate JSON without importing, list all errors

---

#### Phase 4 Build Order

1. DB models — `AIConfig`, `SessionLog`, `BossTemplate`, `SpawnedBoss`, `PendingApproval` tables
2. `services/ai_service.py` — switch combat classifier + add narration, NPC dialogue, session summary (all DeepSeek)
3. `cogs/ai.py` — `/ai` command group
4. `cogs/sessions.py` — `/session start/end/summary/log`
5. Boss system — `BossTemplate` CRUD, `SpawnedBoss` runtime, phase triggers, legendary actions, AoE, lair actions, loot → `/gm boss` group added to `cogs/gm.py`
6. 6 new classes — add to `CLASSES` dict in `services/combat_engine.py` with all named attacks + class features
7. Wild Shape — `DruidWildShapeView`, beast HP pool, revert logic in `combat_engine.py`
8. Ki Points — `ki_points`/`ki_max` on Character model, spend tracking in combat
9. Bardic Inspiration — `bardic_inspiration_dice` on Character, reaction button on attack embeds
10. Hunter's Mark — `marked_target_id` in combat session, +1d6 auto-added on hits
11. RAG wired to narration — ChromaDB query before each DeepSeek narration call in `ai_service.py`
12. NPC dialogue AI branch — DeepSeek route in `cogs/npc.py` `/npc talk`
13. Quest auto-verify — `auto_complete` flag, event hooks in `services/quest_service.py`
14. Stat approval system — `PendingApproval` model, queue, GM channel notifications
15. World JSON loader full validation — `services/world_loader.py`
16. `/help` update — Phase 4 commands added to paginated embed

---

### Phase 5 — Scale (Month 3+)
- [ ] OC leaderboard (kills, quests, achievements)
- [ ] Achievement system with milestone rewards
- [ ] Cross-server shared worlds (portals between guilds — `LocationConnection.cross_guild_id` already reserved)
- [ ] Web dashboard (read-only: character sheets, world map, session logs)
- [ ] Monetization — free tier limits, server premium subscription, world packs (JSON bundles)
- [ ] Housing upgrades — storage chests, trophies, guest lists, room expansions
- [ ] Player market board — list items for server-wide sale, buyout system
- [ ] World state versioning — revert world to a previous snapshot via `WorldEvent` log
- [ ] Sharding — swap `commands.Bot` to `commands.AutoShardedBot` (one-line change, write sharding-safe from day one)
- [ ] Privacy Policy + Terms of Service (required for Discord verification + Top.gg listing)

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
- Edit any NPC, quest, faction, location, lore entry
- Award XP or faction rep to any player manually
- Override weather
- View GM-only lore entries and hidden locations

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

### Chat-Reading Flow
1. Player types RP action freely (e.g. *"Kael drives his sword into the orc's chest"*)
2. Bot detects the message (player is in active combat)
3. Groq `llama-3.1-8b-instant` classifies: `{action, target, weapon}`
4. Bot sends confirmation: "Attacking [Orc] with [Longsword] — confirm?" (✅ or ❌)
5. Player confirms → bot rolls dice, resolves damage, updates status embed
6. If action is unclear → bot asks once: "Are you attacking or doing something else?"

### Named Attacks
- Each class has 3 named attacks (chosen at character creation)
- Named attacks detected in RP message and shown in confirmation label
- Each named attack has unique mechanics, conditions applied, and log lines
- `combat_engine.resolve_named_attack()` dispatches to 18 handlers (3 per class × 6 classes)

### Combat Status Embed
- Updates live after every action (always posts as new message, at bottom of chat)
- Shows: turn order, HP bars, last action result, active conditions with icons, effective AC

### Conditions System (12 conditions)
**DoT:** 🤢 Poisoned · 🔥 Burning · 🩸 Bleeding
**Status:** ⭐ Stunned · 🫥 Blinded · 😨 Frightened · ⬇️ Prone · 🤜 Grappled
**Buffs:** 🛡️ Parrying (+2 AC) · ✨ Shielded (+5 AC) · 💢 Raging · 👁️ Hidden
**Debuffs:** 🔮 Hexed (+1d6 on hits) · 🔴 Reckless (−2 AC)

### Escape Mechanics
- Player types flee intent → bot detects FLEE
- Roll d20 + DEX vs enemy d20 + DEX
  - **Win + roll ≥ 15** → fully escaped, can rest safely
  - **Win + roll < 15** → escaped but enemy close, no rest, re-engages in next zone
  - **Lose** → caught, combat continues, player loses their turn

### Location-Aware Combat (Phase 3)
- `/combat start` filters target list to characters in the same location
- Falls back to server-wide if no location system configured

---

## XP & Leveling System

**XP thresholds (D&D 5e):**
0 / 300 / 900 / 2,700 / 6,500 / 14,000 / 23,000 / 34,000 / 48,000 / 64,000 / 85,000 / 100,000 / 120,000 / 140,000 / 165,000 / 195,000 / 225,000 / 265,000 / 305,000 / 355,000

**XP sources:**
- PvP combat victory: `defeated_player_level × 50 XP` (split equally among winners)
- Quest completion: reward_xp on the quest
- GM manual award: `/gm xp <@user> <amount>`
- Tutorial completion: +50 XP
- Faction deeds (Phase 4): small XP per rep gain

**On level up:**
- HP increases (roll class hit die + CON modifier, min 1)
- Proficiency bonus increases at levels 5, 9, 13, 17
- Public level-up embed in channel: name, new level, HP before → after, new feature unlocked
- ASI (Ability Score Improvement) at levels 4, 8, 12, 16, 19: ephemeral dropdown (+2 one stat OR +1 two stats)

**Class feature unlocks:**

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

---

## Monetization Plan

- **Free tier:** 1 character per user, basic combat, lore wiki (read-only), 10 locations, 5 NPCs
- **Server premium ($X/month):** Unlimited characters, AI GM, full lore tools, full NPC memory, world templates, crafting, housing, web dashboard
- **World packs:** Sell pre-built world JSON files (new regions, enemy tables, quest chains)
- **Top.gg listing:** Organic server installs, charge per-server subscription

---

## Public Bot Requirements

LoreForge will be a public bot listed on Top.gg. Hard rules:

- **PostgreSQL is required** (not SQLite) — file locking breaks under concurrent servers
- **Every query filters by `guild_id`** — no exceptions. Characters, worlds, NPCs, economy, lore — all scoped per guild
- **Sharding** — Discord requires at 2,500+ servers. `AutoShardedClient` is a one-line swap. Write sharding-safe code from day one
- **Rate limits** — use Redis to track usage per user_id per command group. All high-frequency commands rate-limited
- **ChromaDB guild namespacing** — `lore_{guild_id}` collection per server
- **Privacy Policy + Terms of Service** — required by Discord for verification (Phase 5 task)
- **Top.gg listing** — list from launch for organic growth

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

## Folder Structure (Current)

```
Discord Bot (LoreForge)/
├── GAME_PLAN.md          ← this file
├── PHASE3_RESEARCH.md    ← DeepSeek deep-dive research
├── main.py               ← bot entry point
├── config.py             ← env vars, settings
├── .env                  ← secrets (never commit)
├── database/
│   ├── models.py         ← SQLAlchemy models
│   └── session.py        ← DB connection pool
├── cogs/
│   ├── admin.py          ← /ping, /help, /server setup
│   ├── character.py      ← /character create/sheet/show/list/use/edit/proxy/delete
│   ├── combat.py         ← chat-reading combat, /combat group
│   ├── gm.py             ← /gm group
│   ├── shop.py           ← /shop group
│   ├── inventory.py      ← /inventory group
│   ├── proxy.py          ← on_message webhook proxy
│   └── rest.py           ← /rest short/long
└── services/
    ├── ai_service.py     ← Groq 8b combat action classifier
    ├── combat_engine.py  ← dice, damage, conditions, named attacks
    ├── leveling.py       ← XP table, level-up logic
    └── utils.py          ← is_gm, shared helpers
```

**Planned additions for Phase 3:**
```
cogs/
├── location.py     ← /location, /world, /look, /travel, /map, /search, /gather, /weather
├── npc.py          ← /npc group
├── quest.py        ← /quest group
├── faction.py      ← /faction group
├── lore.py         ← /lore group
├── party.py        ← /party group
├── trade.py        ← /trade group
├── crafting.py     ← /craft, /gather
├── housing.py      ← /housing group
├── events.py       ← /event group
└── tutorial.py     ← /tutorial
services/
├── map_service.py      ← Pollinations API, Pillow overlays, BSP dungeon gen
├── lore_service.py     ← ChromaDB sync, search ranking
├── quest_service.py    ← objective auto-tracking hooks
├── faction_service.py  ← rep changes, tier evaluation, perk unlocks
└── weather_service.py  ← weather state, scheduled weather changes
```

---

*Last updated: 2026-06-24*

---

## Change Log

| Date | Change |
|---|---|
| 2026-06-24 | Added map generation to Phase 3 (dungeon, world, city maps — tied to location system) |
| 2026-06-24 | Added GM approval system for character updates to Phase 4 |
| 2026-06-24 | Full combat system redesign — removed button-driven combat, replaced with chat-reading RP flow |
| 2026-06-24 | Added player confirmation step before bot rolls on classified action |
| 2026-06-24 | Added escape mechanics (flee roll, zone-distance outcomes) |
| 2026-06-24 | Added starter attacks + weapons per class |
| 2026-06-24 | Added zone/proximity system to Phase 3 |
| 2026-06-24 | Added Combat System Design section |
| 2026-06-24 | Added Groq model split to AI Design Rules |
| 2026-06-24 | **BUILT** — services/ai_service.py created (Groq 8b combat action classifier) |
| 2026-06-24 | **BUILT** — services/combat_engine.py: STARTER_WEAPONS and STARTER_ATTACKS |
| 2026-06-24 | **BUILT** — cogs/character.py: Starting Loadout step in character creation |
| 2026-06-24 | **BUILT** — cogs/combat.py full rewrite: chat-reading combat, flee, ConfirmView, DeathSaveView |
| 2026-06-24 | **BUILT** — services/combat_engine.py: full CONDITIONS system, named attack handlers |
| 2026-06-24 | **BUILT** — cogs/combat.py: lobby bug fixed, condition icons + effective_ac in status embed |
| 2026-06-24 | **BUILT** — cogs/rest.py: blocks during combat, preserves attacks list |
| 2026-06-24 | **BUILT** — cogs/admin.py: /help updated to 6-page paginated embed |
| 2026-06-24 | Added /tutorial command to Phase 3 |
| 2026-06-24 | **REDESIGN** — Full Phase 2 combat + GM system overhaul |
| 2026-06-24 | **BUILT** — Image URL fix: accept any direct image URL |
| 2026-06-24 | **BUILT** — /character list |
| 2026-06-24 | **PHASE 2 COMPLETE** |
| 2026-06-25 | **PHASE 4 FULLY EXPANDED** — AI narration system (DeepSeek, not Groq), RAG wired to ChromaDB, session system with auto-summary, boss encounter system (GM spawn/force-attack/phases/legendary actions/lair actions/AoE/minions/loot), all 12 classes (Paladin, Ranger, Druid, Bard, Monk, Sorcerer with full named attacks + Wild Shape, Ki, Bardic Inspiration, Hunter's Mark mechanics), AI-enhanced NPC dialogue (DeepSeek, optional), quest auto-verification, GM stat approval queue, World JSON loader full validation. AI is always optional — every feature works without it |
| 2026-06-25 | AI provider updated to DeepSeek for all Phase 4+ AI calls. Groq stays only for Phase 2 combat classifier (already built) |
| 2026-06-24 | **MAJOR UPDATE** — Phase 3 fully expanded with DeepSeek research: location system (is_safe, is_indoors, lighting, biome, danger_level, ambient_texts, ground_items, hazards, resources, lock mechanics, secret exits, cross-server portal fields), NPC system (full NPC + NPCMemory schema, keyword dialogue, attitude system), Quest system (Quest + QuestObjective + PlayerQuest tables, 11 objective types, auto-tracking, reward structure), Faction system (8 tiers with thresholds and unlocks, FactionPerk table, concurrent rep changes), Weather system, Party system, Player housing, Crafting system, Player trading, Guild calendar/events, GM dashboard, World templates, World import/export, Discoveries log, Tutorial expanded to 6 steps with TutorialProgress table, error recovery rules, rate limiting strategy, full planned folder structure |
