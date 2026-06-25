import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character, PendingApproval, GuildConfig
from services.combat_engine import STARTER_WEAPONS, STARTER_ATTACKS, WEAPON_DAMAGE, roll as dice_roll
from services.leveling import xp_bar, xp_for_next_level, check_level_up
from services.title_service import get_active_title
import math

# ── Constants ────────────────────────────────────────────────────────────────

MAX_CHARACTERS = 3

RESTRICTED_USER_ID = 849025341783408701
RESTRICTED_CLASSES = ["Heavenly Demon Heir"]

RACES = {
    "Human":     {"str": 1, "dex": 1, "con": 1, "int": 1, "wis": 1, "cha": 1},
    "Elf":       {"dex": 2, "wis": 1},
    "Dwarf":     {"con": 2, "wis": 1},
    "Halfling":  {"dex": 2, "cha": 1},
    "Half-Orc":  {"str": 2, "con": 1},
    "Dragonborn":{"str": 2, "cha": 1},
    "Tiefling":  {"int": 1, "cha": 2},
}

CLASSES = {
    "Fighter":   {"hit_die": 10, "primary": "str", "armor": "heavy", "saves": ["str", "con"]},
    "Rogue":     {"hit_die": 8,  "primary": "dex", "armor": "light", "saves": ["dex", "int"]},
    "Cleric":    {"hit_die": 8,  "primary": "wis", "armor": "medium", "saves": ["wis", "cha"]},
    "Wizard":    {"hit_die": 6,  "primary": "int", "armor": "none", "saves": ["int", "wis"]},
    "Barbarian": {"hit_die": 12, "primary": "str", "armor": "medium", "saves": ["str", "con"]},
    "Warlock":   {"hit_die": 8,  "primary": "cha", "armor": "light", "saves": ["wis", "cha"]},
    "Heavenly Demon Heir": {"hit_die": 8, "primary": "dex", "armor": "light", "saves": ["dex", "wis"]},
    # Phase 4 — Six New Classes
    "Paladin":   {"hit_die": 10, "primary": "str", "armor": "heavy", "description": "A holy warrior who channels divine power to smite enemies and protect allies.", "saves": ["wis", "cha"]},
    "Ranger":    {"hit_die": 10, "primary": "dex", "armor": "medium", "description": "A skilled hunter who tracks prey across any terrain and strikes with deadly precision.", "saves": ["str", "dex"]},
    "Druid":     {"hit_die": 8,  "primary": "wis", "armor": "medium", "description": "A shapeshifter and nature caster who commands the forces of the wild.", "saves": ["int", "wis"]},
    "Bard":      {"hit_die": 8,  "primary": "cha", "armor": "light", "description": "A performer who weaves magic through music and words, inspiring allies and demoralizing foes.", "saves": ["dex", "cha"]},
    "Monk":      {"hit_die": 8,  "primary": "dex", "armor": "none", "description": "A martial artist who harnesses ki energy to perform superhuman feats of speed and precision.", "saves": ["str", "dex"]},
    "Sorcerer":  {"hit_die": 6,  "primary": "cha", "armor": "none", "description": "An innate spellcaster whose raw magical power is as unpredictable as it is devastating.", "saves": ["con", "cha"]},
}

BACKGROUNDS = ["Acolyte", "Criminal", "Soldier", "Noble", "Sage", "Folk Hero"]

STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

STAT_LABELS = {
    "str": "Strength", "dex": "Dexterity", "con": "Constitution",
    "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma",
}

CLASS_STAT_ORDER = {
    "Fighter":   ["str", "con", "dex", "wis", "int", "cha"],
    "Rogue":     ["dex", "int", "con", "cha", "str", "wis"],
    "Cleric":    ["wis", "con", "str", "cha", "dex", "int"],
    "Wizard":    ["int", "dex", "con", "wis", "cha", "str"],
    "Barbarian": ["str", "con", "dex", "wis", "cha", "int"],
    "Warlock":   ["cha", "con", "dex", "wis", "int", "str"],
    "Heavenly Demon Heir": ["dex", "wis", "con", "int", "str", "cha"],
    "Paladin":   ["str", "cha", "con", "wis", "dex", "int"],
    "Ranger":    ["dex", "wis", "con", "str", "int", "cha"],
    "Druid":     ["wis", "con", "dex", "int", "cha", "str"],
    "Bard":      ["cha", "dex", "con", "wis", "int", "str"],
    "Monk":      ["dex", "wis", "str", "con", "int", "cha"],
    "Sorcerer":  ["cha", "con", "dex", "wis", "int", "str"],
}

CLASS_DESCRIPTIONS = {
    "Fighter":   "Tank & damage — Action Surge",
    "Rogue":     "Sneaky damage — Sneak Attack",
    "Cleric":    "Healer & support — Channel Divinity",
    "Wizard":    "Spell caster — Spellbook & Arcane Recovery",
    "Barbarian": "Rage machine — Bonus damage & resistance",
    "Warlock":   "Pact caster — Eldritch Blast & short-rest slots",
    "Heavenly Demon Heir": "Sword cultivator — Tao system & 24 Demonic Forms",
    "Paladin":   "Holy warrior — Divine Smite & healing",
    "Ranger":    "Hunter & tracker — Hunter's Mark & archery",
    "Druid":     "Nature caster — Wild Shape & beast forms",
    "Bard":      "Support & face — Bardic Inspiration & magic",
    "Monk":      "Martial artist — Ki Points & stunning strikes",
    "Sorcerer":  "Raw power — Chaos Bolt & Wild Surge",
}

CLASS_INFO = {
    "Fighter": {
        "hit_die": 10,
        "primary": "Strength",
        "saves": "STR & CON",
        "resource": "**Action Surge** (1/rest) — take one extra action on your turn. **Second Wind** (1/rest) — bonus action to heal 1d10+level HP.",
        "flavor": (
            "The Fighter is the unyielding anchor of any party — a master of arms who wields every weapon "
            "with equal skill. You don't need magic or tricks; you have discipline, steel, and the will to "
            "stand your ground when others flee. In combat, you control the frontline, trading blows with "
            "enemies while your allies maneuver into position.\n\n"
            "Whether you charge in with a greatsword, hold the line with sword and board, or rain arrows "
            "from a distance, the Fighter is adaptable to any situation. Your Action Surge can turn the "
            "tide of a losing battle, and your Second Wind keeps you fighting long after others have fallen."
        ),
        "tips": (
            "• **Position yourself between enemies and your squishy allies** — you're the wall they hide behind.\n"
            "• **Save Action Surge for clutch moments** — an extra attack when the enemy is low can finish the fight.\n"
            "• **Use Parry when you expect a big hit** — +2 AC can mean the difference between standing and falling.\n"
            "• **Upgrade your weapon and armor first** — Fighters live and die by their gear."
        ),
    },
    "Rogue": {
        "hit_die": 8,
        "primary": "Dexterity",
        "saves": "DEX & INT",
        "resource": "**Sneak Attack** (+1d6 per 2 levels) — extra damage when you have advantage or an ally is adjacent to the target.",
        "flavor": (
            "The Rogue dances through combat like a shadow given form — striking where it hurts most and "
            "vanishing before the enemy can react. You're not built for a stand-up fight; you excel at creating "
            "opportunities, exploiting weaknesses, and making sure every hit counts.\n\n"
            "Your Sneak Attack rewards clever positioning and teamwork. Flank with your Fighter, hide in shadows "
            "for advantage, or use your Smoke Feint to blind enemies before delivering the killing blow. The "
            "Rogue is a problem-solver who can pick locks, pockets, and fights with equal finesse."
        ),
        "tips": (
            "• **Always try to get advantage** — Sneak Attack only triggers with advantage or an adjacent ally.\n"
            "• **Use Cunning Action to reposition** — Dash, Disengage, or Hide as a bonus action keeps you mobile.\n"
            "• **Shadow Step is your best friend** — gain Hidden and make your next attack devastating.\n"
            "• **Don't stand still** — a Rogue who isn't moving is a Rogue who's about to get hit."
        ),
    },
    "Cleric": {
        "hit_die": 8,
        "primary": "Wisdom",
        "saves": "WIS & CHA",
        "resource": "**Channel Divinity** (1/rest, 2 at level 6) — Turn Undead or use your domain's special power. **Spellcasting** — prepare spells from the full Cleric list.",
        "flavor": (
            "The Cleric is the living conduit between the mortal world and the divine — a figure who channels "
            "the power of the gods to heal the wounded, smite the wicked, and protect the faithful. You're not "
            "just a healer; you're a spiritual warrior who can wade into battle with a mace in one hand and "
            "holy light in the other.\n\n"
            "Your kit is balanced — you can heal, deal radiant damage, control undead, and buff your allies. "
            "A good Cleric reads the battlefield and chooses the right tool: Smite for damage, Heal for "
            "survival, Turn Undead when facing necromantic horrors."
        ),
        "tips": (
            "• **Heal proactively, not reactively** — keeping allies above half HP is better than panic-healing.\n"
            "• **Smite is excellent against undead** — bonus radiant damage makes you the bane of necromancers.\n"
            "• **Turn Undead can break an encounter** — facing a horde of skeletons? One Channel Divinity can end it.\n"
            "• **Don't forget you can fight** — you have good armor and a mace. You're not a squishy backliner."
        ),
    },
    "Wizard": {
        "hit_die": 6,
        "primary": "Intelligence",
        "saves": "INT & WIS",
        "resource": "**Spell Slots** (2 at level 1, more as you level). **Arcane Recovery** (1/day) — regain half your Wizard level in spell slots (rounded up) on a short rest.",
        "flavor": (
            "The Wizard is the ultimate wielder of arcane power — a student of forbidden knowledge who commands "
            "the forces of reality itself. You are fragile, yes, but you can reshape the battlefield from a "
            "distance. Fire, frost, force, and lightning answer your call.\n\n"
            "Your strength lies in versatility. Magic Missile never misses. Fire Bolt burns from range. Ray of "
            "Frost slows approaching enemies. Shield makes you briefly untouchable. A clever Wizard controls "
            "the fight before it even reaches melee range. Stay behind your Fighter, conserve your spell slots, "
            "and let the cantrips do the work."
        ),
        "tips": (
            "• **Cantrips are free — use them liberally** — Fire Bolt and Ray of Frost cost nothing to cast.\n"
            "• **Save spell slots for important moments** — a well-placed Thunderclap or Shield can save the day.\n"
            "• **Positioning is everything** — you have the lowest HP. Stay behind your party's front line.\n"
            "• **Arcane Recovery on every short rest** — it's free spell slots. Don't waste it."
        ),
    },
    "Barbarian": {
        "hit_die": 12,
        "primary": "Strength",
        "saves": "STR & CON",
        "resource": "**Rage** (2/rest) — +2 melee damage, resistance to bludgeoning/piercing/slashing damage, advantage on STR checks. Lasts 1 minute.",
        "flavor": (
            "The Barbarian is pure, untamed fury made flesh — a warrior who abandons the discipline of the "
            "Fighter for the raw, primal power of anger. When you Rage, pain becomes meaningless. Arrows bounce "
            "off your hide. Swords that would fell a normal warrior barely scratch you.\n\n"
            "Your playstyle is aggressive and relentless. Charge in first, hit the biggest enemy, and trust your "
            "massive HP pool and damage resistance to keep you standing. Reckless Swing gives you advantage "
            "at the cost of defense, and Rage Charge can flatten enemies. You are the hammer, and every problem "
            "is a nail."
        ),
        "tips": (
            "• **Rage at the start of combat** — damage resistance is your main survival tool.\n"
            "• **Reckless Swing is a gamble** — advantage to hit is great, but enemies get advantage against you too.\n"
            "• **You have the highest HP in the game** — use it. Take risks. You can survive hits that kill others.\n"
            "• **Intimidate is your out-of-combat tool** — your terrifying presence can avoid fights entirely."
        ),
    },
    "Warlock": {
        "hit_die": 8,
        "primary": "Charisma",
        "saves": "WIS & CHA",
        "resource": "**Pact Magic** (1 slot at level 1, recovered on short rest). **Eldritch Blast** — your signature cantrip, deals 1d10+CHA force damage. **Invocations** at level 2.",
        "flavor": (
            "The Warlock made a deal with a being of immense power — a fiend, a fey, or an ancient horror — "
            "and now wields forbidden magic that no traditional spellcaster can match. Your spell slots are "
            "few but always at maximum power, and your Eldritch Blast is the most reliable damage cantrip "
            "in the game.\n\n"
            "You combine dark magic with eldritch resilience. Hex your enemies to amplify all your damage. "
            "Drain life from your foes to sustain yourself. Hellish Rebuke punishes anyone who dares strike "
            "you. And when you need defense, Armor of Agathys makes you a frozen nightmare. Short rests are "
            "your best friend — they restore all your pact magic."
        ),
        "tips": (
            "• **Eldritch Blast is your bread and butter** — use it every turn. It scales with your level.\n"
            "• **Hex then blast** — placing Hex on a target before adding 1d6 necrotic to every hit.\n"
            "• **Short rest often** — your spell slots come back on a short rest. Don't hoard them.\n"
            "• **You're a glass cannon** — 1d8 hit die means you can take some hits, but not many. Stay at range."
        ),
    },
    "Heavenly Demon Heir": {
        "hit_die": 8,
        "primary": "Dexterity",
        "saves": "DEX & WIS",
        "resource": "**Tao Points** — fuel the 24 Demonic Sword Forms, telekinetic sword control, and supernatural techniques. Regained on long rest. **Nano System** — advantage on initiative, reroll one attack per turn.",
        "flavor": (
            "The Heavenly Demon Heir is a martial cultivator who combines sword mastery, demonic martial arts, "
            "and an internal Tao system that enhances every facet of combat. Through cultivation of Tao, you "
            "unleash rapid sequences of attacks, manipulate blades through the air with your mind, and ascend "
            "to supernatural dominance over the battlefield.\n\n"
            "Your power comes from the 24 Demonic Sword Forms — forbidden techniques passed down through "
            "generations. From the basic Demonic Strike to the apocalyptic Sword Rain: Heavenly Demon "
            "Cataclysm, each form channels Tao into devastating chains of attacks. At your peak, you command "
            "storms of flying blades as extensions of your will. The Heavenly Demon does not simply wield a "
            "blade. The blade obeys the Heavenly Demon."
        ),
        "tips": (
            "• **Tao is your fuel** — manage it carefully. Running out leaves you unconscious.\n"
            "• **Choose your path at level 3** — Heavenly Demon (sword control), Blood Demon (form combos), or Elemental Demon (elemental damage).\n"
            "• **Chain forms for maximum damage** — Blood Demon path lets you chain 10 forms in one turn.\n"
            "• **Control flying swords for battlefield dominance** — each sword costs 2 Tao but attacks independently.\n"
            "• **Save Absolute Heavenly Demon State and Forbidden Form for boss fights** — they are game-ending.\n"
            "• **Your Nano System gives you advantage on initiative** — you almost always go first."
        ),
    },
}

RACE_INFO = {
    "Human":     {"lore": "The most adaptable of all peoples, Humans thrive everywhere. Their ambition and versatility make them natural leaders and innovators.", "bonus_detail": "+1 to ALL six ability scores — a jack of all trades, master of none."},
    "Elf":       {"lore": "Graceful and long-lived, Elves possess an innate connection to nature and magic. Their keen eyes miss nothing.", "bonus_detail": "+2 DEX and +1 WIS — perfect for nimble rogues and wise rangers."},
    "Dwarf":     {"lore": "Stout and resilient, Dwarves are masters of stone and metal. Their constitution is legendary, as is their stubbornness.", "bonus_detail": "+2 CON and +1 WIS — ideal for durable frontliners and stalwart clerics."},
    "Halfling":  {"lore": "Small but brave, Halflings rely on luck and charm to survive in a big world. Their cheerful demeanor hides a fierce survival instinct.", "bonus_detail": "+2 DEX and +1 CHA — perfect for rogues and warlocks who need a lucky break."},
    "Half-Orc":  {"lore": "Born of two worlds, Half-Orcs combine human cunning with orcish ferocity. Their intimidating presence is matched only by their endurance.", "bonus_detail": "+2 STR and +1 CON — built for barbarians and fighters who want raw power."},
    "Dragonborn":{"lore": "Descended from dragons, these proud beings carry draconic blood in their veins. Their breath weapon and natural resilience set them apart.", "bonus_detail": "+2 STR and +1 CHA — excellent for paladins, fighters, and sorcerers with draconic heritage."},
    "Tiefling":  {"lore": "Bearing the mark of infernal ancestry, Tieflings command dark magic and innate charm. Their horns and tails mark them as otherworldly.", "bonus_detail": "+1 INT and +2 CHA — natural warlocks, sorcerers, and bards with a dark edge."},
}

TUTORIALS = {
    "Fighter": [
        {"title": "Welcome, Fighter!", "description": "You are the blade and the bulwark — the one who stands between your allies and certain death.", "fields": [
            {"name": "⚔️ Your Role", "value": "As a Fighter, you control the ebb and flow of battle. Your high HP and AC let you stay on the front lines, trading blows with the enemy while your allies do their jobs."},
            {"name": "🎯 Class Fantasy", "value": "You're not a magical warrior or a divine champion — you're just really, really good at fighting. Every weapon is an extension of your will, and no enemy can match your endurance."},
        ]},
        {"title": "Your Resources", "description": "Here's what your class brings to every fight.", "fields": [
            {"name": "⚡ Action Surge", "value": "Once per rest, take **one extra action** on your turn. That could be an extra attack, a second use of Second Wind, or anything else an action can do. Use it at the perfect moment."},
            {"name": "💚 Second Wind", "value": "Once per rest, use a bonus action to heal **1d10 + your Fighter level** HP. A lifesaver when you're low and the Cleric is busy."},
        ]},
        {"title": "Your Attacks", "description": "The attacks you chose during creation.", "fields": []},
        {"title": "Leveling Up", "description": "What to look forward to as you grow.", "fields": [
            {"name": "Level 3 — Martial Archetype", "value": "Choose a path: **Champion** (improved crit range), **Battle Master** (maneuvers and superiority dice), or **Eldritch Knight** (spellcasting)."},
            {"name": "Level 5 — Extra Attack", "value": "Attack **twice** per turn instead of once. This doubles your damage output."},
            {"name": "Level 11 — Triple Attack", "value": "Attack three times per turn. You're a whirlwind of destruction."},
            {"name": "Level 20 — Legendary Warrior", "value": "Attack four times per turn and gain an extra Action Surge. You are a one-man army."},
        ]},
        {"title": "How to Play", "description": "Tips for being an effective Fighter.", "fields": [
            {"name": "🛡️ Hold the Line", "value": "Your job is to keep enemies away from your squishy allies. Use your high HP and AC to absorb hits."},
            {"name": "⚡ Save Action Surge", "value": "Don't waste Action Surge on the first goblin you see. Save it for the boss, the clutch moment, or when you need to turn the tide."},
            {"name": "🗡️ Gear Matters", "value": "As a Fighter, your weapon is everything. Upgrade whenever possible. A +1 longsword is a massive power spike."},
            {"name": "🔄 Be Flexible", "value": "You can switch between sword-and-board (defense) and two-handed (damage) as the situation demands. Adapt!"},
        ]},
    ],
    "Rogue": [
        {"title": "Welcome, Rogue!", "description": "You are the shadow in the corner, the whisper in the dark — a master of precision and opportunity.", "fields": [
            {"name": "🗡️ Your Role", "value": "The Rogue is a tactical striker who deals devastating single-target damage when conditions are right. You're also the party's skill monkey — locks, traps, and stealth are your domain."},
            {"name": "🎯 Class Fantasy", "value": "You don't win by standing still and trading blows. You win by being where the enemy least expects you, striking when they're vulnerable, and vanishing before they can retaliate."},
        ]},
        {"title": "Your Resources", "description": "What makes a Rogue shine.", "fields": [
            {"name": "🎲 Sneak Attack", "value": "Once per turn, when you have **advantage** or an **ally adjacent** to the target, deal **+1d6 damage** (increases every 2 levels). This is your main source of damage."},
            {"name": "💨 Cunning Action", "value": "At level 2, you can Dash, Disengage, or Hide as a **bonus action**. This makes you incredibly mobile and hard to pin down."},
        ]},
        {"title": "Your Attacks", "description": "The attacks you chose during creation.", "fields": []},
        {"title": "Leveling Up", "description": "What to look forward to as you grow.", "fields": [
            {"name": "Level 3 — Roguish Archetype", "value": "Choose **Thief** (climbing, fast hands), **Arcane Trickster** (spells), or more paths later."},
            {"name": "Level 5 — Uncanny Dodge", "value": "Use your reaction to **halve damage** from one attack per round. Enormous survivability boost."},
            {"name": "Level 7 — Evasion", "value": "AoE effects like fireballs? You take **zero damage** on a successful DEX save, half on a failure."},
            {"name": "Level 11 — Reliable Talent", "value": "Any d20 roll below 10 on a proficient skill check becomes a 10. You literally cannot fail easy tasks."},
        ]},
        {"title": "How to Play", "description": "Tips for being an effective Rogue.", "fields": [
            {"name": "🎯 Always Seek Advantage", "value": "Sneak Attack requires advantage or an adjacent ally. Use Shadow Step, Hide, or flank with your Fighter."},
            {"name": "🏃 Keep Moving", "value": "Never end your turn in the same place you started. Mobility is your defense."},
            {"name": "🔑 You're the Utility Expert", "value": "Picking locks, disarming traps, scouting ahead — these are YOUR jobs. The party depends on you."},
            {"name": "⚡ Don't Trade Blows", "value": "You have a d8 hit die and light armor. If you're taking hits, you're doing it wrong."},
        ]},
    ],
    "Cleric": [
        {"title": "Welcome, Cleric!", "description": "You carry the light of the divine into a dark world — healer, protector, and holy warrior rolled into one.", "fields": [
            {"name": "✝️ Your Role", "value": "The Cleric is the party's lifeline. You keep everyone alive with healing, turn the tide with buffs, and smite evil with radiant fury. You're not just a healer — you're a force of nature."},
            {"name": "🎯 Class Fantasy", "value": "You speak for the gods. Miracles flow through your hands. When you raise your holy symbol, even the undead tremble. You are the reason your party survives the night."},
        ]},
        {"title": "Your Resources", "description": "Divine tools at your disposal.", "fields": [
            {"name": "⚡ Channel Divinity", "value": "Once per rest, you can use **Turn Undead** (frighten undead) or your domain's special power. At level 6, you get a second use per rest."},
            {"name": "📖 Spellcasting", "value": "You prepare spells from the full Cleric list each day. Your primary stat is WIS — it determines your spell save DC and healing power."},
        ]},
        {"title": "Your Attacks", "description": "The attacks you chose during creation.", "fields": []},
        {"title": "Leveling Up", "description": "What to look forward to as you grow.", "fields": [
            {"name": "Level 1 — Divine Domain", "value": "Choose your domain (Life, Light, War, etc.). This grants bonus spells and unique abilities."},
            {"name": "Level 5 — Destroy Undead", "value": "Your Turn Undead becomes **Destroy Undead** — weak undead are instantly annihilated on a failed save."},
            {"name": "Level 10 — Divine Intervention", "value": "Once per week, call upon your deity for a miracle. It always succeeds."},
            {"name": "Level 17 — Supreme Healing", "value": "Your healing spells automatically **max out** their dice rolls. You never roll for healing again."},
        ]},
        {"title": "How to Play", "description": "Tips for being an effective Cleric.", "fields": [
            {"name": "💚 Heal Smart", "value": "Keep allies above half HP rather than panic-healing. A Cleric who pre-heals wins fights before they start."},
            {"name": "⚔️ You Can Fight", "value": "You have good armor and a mace. Don't just stand in the back — wade in and Smite. You're tougher than you look."},
            {"name": "✝️ Turn Undead is Game-Changing", "value": "Against undead hordes, one Channel Divinity can break the encounter entirely."},
            {"name": "🛡️ Position Matters", "value": "You're a middle-line combatant — behind the Fighter, ahead of the Wizard. Read the battlefield and adjust."},
        ]},
    ],
    "Wizard": [
        {"title": "Welcome, Wizard!", "description": "You are a master of the arcane — a weaver of spells who commands forces beyond mortal comprehension.", "fields": [
            {"name": "🔮 Your Role", "value": "The Wizard is a ranged arcane powerhouse who controls the battlefield with versatile spells. You're fragile, but your Cantrips never run out and your spell slots can change the course of any fight."},
            {"name": "🎯 Class Fantasy", "value": "You've spent years hunched over ancient tomes, learning the secret names of reality. Now you speak those names aloud — and the world obeys. Fire, frost, force, and lightning answer your call."},
        ]},
        {"title": "Your Resources", "description": "Arcane tools at your disposal.", "fields": [
            {"name": "📖 Spell Slots", "value": "You start with 2 first-level spell slots. Each day, you prepare a list of spells from your spellbook and cast them using these slots."},
            {"name": "🔋 Arcane Recovery", "value": "Once per day on a short rest, regain spell slots totaling **half your Wizard level** (rounded up). A level 2 Wizard can recover 1 first-level slot."},
        ]},
        {"title": "Your Attacks", "description": "The attacks you chose during creation.", "fields": []},
        {"title": "Leveling Up", "description": "What to look forward to as you grow.", "fields": [
            {"name": "Level 2 — Arcane Tradition", "value": "Choose your school: **Evocation** (big damage), **Abjuration** (shields/wards), or **Necromancy** (undead minions)."},
            {"name": "Level 5 — 3rd-Level Spells", "value": "Fireball. Counterspell. Haste. This is where Wizard power truly explodes."},
            {"name": "Level 11 — Empowered Cantrips", "value": "Your cantrips deal an extra damage die. Fire Bolt becomes 3d10, Ray of Frost becomes 3d8."},
            {"name": "Level 18 — Spell Mastery", "value": "Choose a 1st and 2nd level spell — you can cast them **at will**, no slots required. Shield every turn? Yes."},
        ]},
        {"title": "How to Play", "description": "Tips for being an effective Wizard.", "fields": [
            {"name": "🎯 Stay Behind the Tank", "value": "You have 6 HP per level and no armor. If enemies reach you, something has gone wrong."},
            {"name": "⚡ Cantrips Are Free", "value": "Fire Bolt and Ray of Frost cost nothing. Use them every turn. Save spell slots for when it matters."},
            {"name": "📖 Prepare the Right Spells", "value": "You can swap your prepared spells each day. Facing undead? Bring radiant. Facing a crowd? Fireball."},
            {"name": "🔄 Short Rest = Arcane Recovery", "value": "Never skip a short rest without using Arcane Recovery. Free spell slots are free spell slots."},
        ]},
    ],
    "Barbarian": [
        {"title": "Welcome, Barbarian!", "description": "You are fury incarnate — a primal warrior who laughs in the face of death and hits back twice as hard.", "fields": [
            {"name": "💢 Your Role", "value": "The Barbarian is the ultimate frontliner. You have the highest HP in the game, damage resistance while Raging, and the ability to hit like a freight train. You go where the fight is thickest and make it yours."},
            {"name": "🎯 Class Fantasy", "value": "You don't wear heavy plate or study ancient techniques. You get angry. Really, really angry. And when you're angry, swords bounce off your skin and you can punch through stone walls."},
        ]},
        {"title": "Your Resources", "description": "Rage fuels your power.", "fields": [
            {"name": "💢 Rage (2/rest)", "value": "Enter a rage as a bonus action. Gain **+2 melee damage**, **resistance** to physical damage (bludgeoning/piercing/slashing), and advantage on STR checks. Lasts 1 minute."},
            {"name": "🔄 Rage Tactics", "value": "While raging, you can't cast or concentrate on spells. But who needs spells when you can headbutt a dragon?"},
        ]},
        {"title": "Your Attacks", "description": "The attacks you chose during creation.", "fields": []},
        {"title": "Leveling Up", "description": "What to look forward to as you grow.", "fields": [
            {"name": "Level 3 — Primal Path", "value": "Choose **Berserker** (extra attacks while raging), **Totem Warrior** (spirit animal buffs), or **Zealot** (divine fury)."},
            {"name": "Level 5 — Extra Attack + Fast Movement", "value": "Attack twice per turn and gain +10ft movement speed."},
            {"name": "Level 11 — Relentless Rage", "value": "If you drop to 0 HP while raging, make a CON save to stay at 1 HP instead."},
            {"name": "Level 20 — Primal Champion", "value": "+4 to STR and CON (max 24). Infinite rages. You are a demigod of war."},
        ]},
        {"title": "How to Play", "description": "Tips for being an effective Barbarian.", "fields": [
            {"name": "💢 Rage Early, Rage Often", "value": "You have 2 rages per rest. Use them. Damage resistance makes you incredibly tanky."},
            {"name": "⚔️ Use Reckless Swing", "value": "Advantage on attacks is huge. Yes, enemies get advantage on you. Your HP can take it."},
            {"name": "🛡️ You ARE the Front Line", "value": "Stand between enemies and your allies. With your HP pool and resistance, you can take hits that would kill anyone else."},
            {"name": "🏃 Don't Forget Mobility", "value": "You're fast. Use it to close gaps, chase runners, and reposition when needed."},
        ]},
    ],
    "Heavenly Demon Heir": [
        {"title": "Welcome, Heavenly Demon Heir!", "description": "You are a martial cultivator who commands sword mastery, demonic forms, and the mysterious power of Tao. The blade does not merely obey you — it fears you.", "fields": [
            {"name": "⚔️ Your Role", "value": "You are a devastating melee combatant who chains rapid attacks using Tao. Your 24 Demonic Sword Forms let you stack damage through combo sequences, telekinetically control flying blades, and dominate the battlefield."},
            {"name": "🎯 Class Fantasy", "value": "Through cultivation of internal Tao energy, you transcend normal swordsmanship. Each strike flows into the next — Demonic Strike into Bloody Sequence into Demonic Tempest — until your enemies have nowhere left to run. At your peak, you summon storms of flying swords and call down blade rain from the heavens."},
        ]},
        {"title": "Your Resources", "description": "Tao is everything.", "fields": [
            {"name": "🌀 Tao Points", "value": "You start with **2 Tao** and gain more as you level. Tao fuels your 24 Demonic Sword Forms. If your Tao hits 0, your body collapses from exhaustion. Manage it carefully."},
            {"name": "🤖 Nano System", "value": "Your internal combat AI gives you **advantage on initiative** and lets you **reroll one attack roll per turn**. You almost always strike first."},
        ]},
        {"title": "Your Attacks", "description": "The attacks you chose during creation.", "fields": []},
        {"title": "Leveling Up", "description": "Your power grows with every level.", "fields": [
            {"name": "Level 3 — Choose Your Path", "value": "**Path of the Heavenly Demon** (telekinetic sword master), **Path of the Blood Demon** (form combo specialist), or **Path of the Elemental Demon** (elemental devastation)."},
            {"name": "Level 5 — Extra Attack + Intermediate Forms", "value": "Attack twice per turn. Unlock Intermediate Forms: Cross Slash, Demon Beast Strike, Demonic Dance, and more."},
            {"name": "Level 15 — Supreme Forms", "value": "Unlock Supreme Forms: Absolute Demonic Destruction (12 attacks), Sword Rain, Hundred Blade Massacre, and Void Slash."},
            {"name": "Level 20 — Heavenly Demon Ascension", "value": "Crit on 18-20, resistance to all damage, +300 ft movement. Enter **Absolute Heavenly Demon State** for an unstoppable 1-minute burst. Unleash **Sword Rain: Heavenly Demon Cataclysm** to devastate entire armies."},
        ]},
        {"title": "How to Play", "description": "Tips for mastering the Heavenly Demon arts.", "fields": [
            {"name": "🌀 Manage Your Tao", "value": "Running out of Tao knocks you unconscious. Keep enough in reserve for emergencies. Perfect Tao Circulation (level 10) regenerates Tao every turn."},
            {"name": "⚔️ Chain Your Forms", "value": "Each form flows into the next. Blood Demon path lets you chain 10 forms in a single turn — that's potentially 50+ attacks."},
            {"name": "🗡️ Control Flying Swords", "value": "2 Tao per sword. They attack on your command and orbit you defensively. More swords = more damage."},
            {"name": "💀 Save Your Ultimates", "value": "Heavenly Demon Catastrophe and Sword Rain are 1/long rest. Use them on bosses — they can end encounters instantly."},
        ]},
    ],
    "Warlock": [
        {"title": "Welcome, Warlock!", "description": "You made a pact with a being beyond mortal comprehension — and now you wield power that other spellcasters can only dream of.", "fields": [
            {"name": "🔮 Your Role", "value": "The Warlock is a magical marksman with limited but powerful spell slots. Your Eldritch Blast is the best damage cantrip in the game, and your short-rest recovery means you can keep fighting when other casters are spent."},
            {"name": "🎯 Class Fantasy", "value": "Your power isn't studied or gifted — it's **earned**. You struck a deal with a fiend, a fey, or an ancient horror, and now their power flows through your veins. Every spell you cast is a reminder of that bargain."},
        ]},
        {"title": "Your Resources", "description": "Pact-fueled power.", "fields": [
            {"name": "📖 Pact Magic (1 slot)", "value": "You have 1 spell slot at level 1 — but it's always cast at **maximum level**. And here's the best part: **all your slots recover on a short rest**."},
            {"name": "🔮 Eldritch Blast", "value": "Your signature cantrip. Deals **1d10 + CHA modifier** force damage. At higher levels, it fires multiple beams. This is your main action in combat."},
        ]},
        {"title": "Your Attacks", "description": "The attacks you chose during creation.", "fields": []},
        {"title": "Leveling Up", "description": "What to look forward to as you grow.", "fields": [
            {"name": "Level 2 — Eldritch Invocations", "value": "Choose two invocations. **Agonizing Blast** (CHA to Eldritch Blast damage) is mandatory. **Repelling Blast** (pushes enemies) is incredible."},
            {"name": "Level 3 — Pact Boon", "value": "Choose your pact: **Chain** (invisible familiar), **Tome** (extra cantrips), or **Blade** (summon a magic weapon)."},
            {"name": "Level 5 — 3rd-Level Slots", "value": "Your single slot now casts 3rd-level spells. Your Mystic Arcanum gives you a one-per-day 6th-level spell at level 11."},
            {"name": "Level 11 — Mystic Arcanum", "value": "Cast a 7th, 8th, and 9th-level spell once per day each (at levels 11, 13, and 17). These don't use your pact slots."},
        ]},
        {"title": "How to Play", "description": "Tips for being an effective Warlock.", "fields": [
            {"name": "🔮 Hex + Eldritch Blast = Your Rotation", "value": "Round 1: Hex. Round 2+: Eldritch Blast. That's 1d10+CHA force + 1d6 necrotic per beam. Every turn. Reliable."},
            {"name": "🔄 Short Rest After Every Fight", "value": "Your spell slots recover on short rests. If the party wants to push forward without resting, ask them to wait 1 hour."},
            {"name": "🛡️ You're a Glass Cannon", "value": "d8 hit die and light armor means you can take a hit or two but no more. Stay at range."},
            {"name": "🎯 Save Spells for Big Moments", "value": "With only one slot per short rest, you can't spam spells. Use Eldritch Blast for regular damage, and save your slot for Hex, Drain, or Hellish Rebuke."},
        ]},
    ],
}

BACKGROUND_DESCRIPTIONS = {
    "Acolyte":   "Temple servant — Religion & Insight",
    "Criminal":  "Life outside the law — Stealth & Deception",
    "Soldier":   "Military service — Athletics & Intimidation",
    "Noble":     "Privilege & power — History & Persuasion",
    "Sage":      "Scholarly pursuits — Arcana & History",
    "Folk Hero": "Humble origins, great deeds — Survival & Animal Handling",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def modifier(score: int) -> int:
    return math.floor((score - 10) / 2)

def mod_str(score: int) -> str:
    m = modifier(score)
    return f"+{m}" if m >= 0 else str(m)

def calc_hp(char_class: str, con_score: int) -> int:
    return CLASSES[char_class]["hit_die"] + modifier(con_score)

def calc_ac(dex_score: int) -> int:
    return 10 + modifier(dex_score)

def assign_stats(char_class: str, race: str) -> dict:
    order = CLASS_STAT_ORDER[char_class]
    base = dict(zip(order, STANDARD_ARRAY))
    return {stat: base[stat] + RACES[race].get(stat, 0) for stat in base}

def proficiency_bonus(level: int) -> int:
    return math.ceil(level / 4) + 1

def roll_4d6_drop_lowest() -> int:
    """Roll 4d6, drop the lowest die, return the sum of the remaining 3."""
    dice = [dice_roll(6) for _ in range(4)]
    dice.sort(reverse=True)
    return sum(dice[:3])

def roll_stat_set(race: str, char_class: str) -> dict:
    """Generate a full set of 6 stats using 4d6-drop-lowest, mapped to class stat order."""
    order = CLASS_STAT_ORDER[char_class]
    raw_scores = [roll_4d6_drop_lowest() for _ in range(6)]
    raw_scores.sort(reverse=True)
    base = dict(zip(order, raw_scores))
    return {stat: base[stat] + RACES[race].get(stat, 0) for stat in base}

async def _is_valid_image_url(url: str) -> bool:
    if not url:
        return True
    if not url.lower().startswith("https://"):
        return False
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                ct = resp.headers.get("Content-Type", "")
                return ct.startswith("image/")
    except Exception:
        return False

def _starting_resources(char_class: str) -> dict:
    return {
        "Fighter":   {"action_surge": 1},
        "Barbarian": {"rages": 2, "rage_active": False},
        "Warlock":   {"spell_slots": 1},
        "Cleric":    {"channel_divinity": 1},
        "Wizard":    {"spell_slots": 2, "arcane_recovery": 1},
        "Rogue":     {"sneak_attack_dice": 1},
        "Heavenly Demon Heir": {
            "tao_current": 2, "tao_max": 2, "nano_system": True,
            "hd_path": None, "hd_dual_wield": False, "controlled_swords": 0,
            "absolute_state_used": False, "catastrophe_used": False,
            "sword_rain_used": False, "elemental_type": None,
            "tao_exhausted": False,
        },
        "Paladin":   {"divine_smite_available": True},
        "Ranger":    {"hunters_mark_active": False, "hunters_mark_target": None},
        "Druid":     {"wild_shape_uses": 2, "beast_form": None, "beast_hp": 0},
        "Bard":      {"bardic_inspiration_dice": 3, "bardic_inspiration_max": 3},
        "Monk":      {"ki_points": 2, "ki_max": 2},
        "Sorcerer":  {"sorcery_points": 2, "sorcery_points_max": 2},
    }.get(char_class, {})


# ── DB helpers (exported for use in combat.py / rest.py) ─────────────────────

async def get_characters(user_id: int, guild_id: int) -> list[Character]:
    """Return all living characters for this user in this guild."""
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == user_id,
                Character.guild_id == guild_id,
                Character.is_dead == False,
            )
        )
        return list(result.scalars().all())


async def resolve_character(user_id: int, guild_id: int) -> tuple:
    """
    Returns (selected_char, all_chars).
    selected_char is the active char (or the only char if solo).
    If multiple chars and none is active, selected_char is None — caller shows picker.
    """
    chars = await get_characters(user_id, guild_id)
    if not chars:
        return None, []
    if len(chars) == 1:
        return chars[0], chars
    active = next((c for c in chars if c.is_active), None)
    return active, chars


# ── Sheet embed ───────────────────────────────────────────────────────────────

def build_sheet_embed(char: Character, active_title_display: str | None = None, active_title_color: int | None = None) -> discord.Embed:
    stats = {
        "str": char.strength, "dex": char.dexterity, "con": char.constitution,
        "int": char.intelligence, "wis": char.wisdom, "cha": char.charisma,
    }
    pb = proficiency_bonus(char.level)
    saves = CLASSES.get(char.char_class, {}).get("saves", [])

    active_tag = "  ★" if char.is_active else ""
    embed_title = f"{active_title_display}  ·  {char.name}{active_tag}" if active_title_display else f"{char.name}{active_tag}"
    embed = discord.Embed(
        title=embed_title,
        description=f"*{char.race} {char.char_class} — Level {char.level}*",
        color=active_title_color or 0x8B5CF6,
    )

    if char.avatar_url:
        embed.set_thumbnail(url=char.avatar_url)

    embed.add_field(
        name="HP / AC",
        value=f"❤️ `{char.hp_current}/{char.hp_max}`  🛡️ `{char.armor_class}`",
        inline=False,
    )

    stat_lines = []
    for abbr, label in STAT_LABELS.items():
        score = stats[abbr]
        save_mark = " ✦" if abbr in saves else ""
        stat_lines.append(f"**{label[:3].upper()}** {score} ({mod_str(score)}){save_mark}")
    embed.add_field(name="Ability Scores  (✦ = save prof.)", value="\n".join(stat_lines), inline=True)

    embed.add_field(
        name="Economy",
        value=f"💰 {char.gold} gp\n📦 {len(char.inventory or [])} item(s)",
        inline=True,
    )
    xp_display = xp_bar(char.xp, char.level)
    embed.add_field(name="Progress", value=f"{xp_display}\nProf. Bonus: `+{pb}`", inline=True)

    attacks = (char.class_resources or {}).get("attacks", [])
    if attacks:
        weapon_key = next(
            (it["key"] for it in (char.inventory or []) if it.get("type") == "weapon" and it.get("equipped")),
            "unarmed",
        )
        dice = WEAPON_DAMAGE.get(weapon_key, (1, 4))
        weapon_line = f"🗡️ **{weapon_key.replace('_', ' ').title()}** ({dice[0]}d{dice[1]})"
        attack_lines = [weapon_line] + [f"• {a}" for a in attacks]
        embed.add_field(name="Loadout", value="\n".join(attack_lines), inline=False)

    # ── Heavenly Demon Heir — Auto-integrated class data ──
    if char.char_class == "Heavenly Demon Heir":
        res = dict(char.class_resources or {})
        from cogs.heavenly_demon import _tao_max, _SWORD_MAX_TABLE, _res, ELEMENT_EMOJI, TIER_EMOJI

        hd_tao_max = _tao_max(char)
        hd_tao_cur = res.get("tao_current", 0)
        hd_path = res.get("hd_path") or "None"
        hd_swords = res.get("controlled_swords", 0)
        hd_max_swords = _SWORD_MAX_TABLE.get(char.level, 1)
        hd_dual = res.get("hd_dual_wield", False)
        hd_element = res.get("elemental_type")
        hd_exhausted = res.get("tao_exhausted", False)

        # Tao bar
        bar_filled = round((hd_tao_cur / max(hd_tao_max, 1)) * 10)
        tao_bar = "█" * bar_filled + "░" * (10 - bar_filled)
        tao_status = f"`{tao_bar}` **{hd_tao_cur}/{hd_tao_max}**"
        if hd_exhausted:
            tao_status += " 💀 **EXHAUSTED**"

        hd_lines = []
        hd_lines.append(f"🌀 **Tao:** {tao_status}")
        hd_lines.append(f"⚔️ **Path:** {hd_path}")
        hd_lines.append(f"🗡️ **Swords:** {hd_swords}/{hd_max_swords}")
        hd_lines.append(f"⚔️ **Dual Wield:** {'Active 🗡️🗡️' if hd_dual else 'Off'}")

        if hd_element:
            emoji = ELEMENT_EMOJI.get(hd_element, "🌪️")
            hd_lines.append(f"{emoji} **Element:** {hd_element}")

        # Key features by level
        hd_features = []
        if char.level >= 2:
            hd_features.append("Sword Flight")
        if char.level >= 4:
            hd_features.append("Phantom Step")
        if char.level >= 5:
            hd_features.append("Extra Attack")
        if char.level >= 7:
            hd_features.append("Sword Control")
        if char.level >= 10:
            hd_features.append("Perfect Tao Circ.")
        if char.level >= 15:
            hd_features.append("Heavenly Demon Body")
        if char.level >= 20:
            hd_features.append("Ascension")
        if hd_features:
            hd_lines.append(f"✨ **Features:** {', '.join(hd_features)}")

        # Cooldowns used this rest
        hd_cooldowns = []
        if res.get("absolute_state_used"):
            hd_cooldowns.append("Absolute State")
        if res.get("catastrophe_used"):
            hd_cooldowns.append("Catastrophe")
        if res.get("sword_rain_used"):
            hd_cooldowns.append("Sword Rain")
        if hd_cooldowns:
            hd_lines.append(f"🔒 **Used:** {', '.join(hd_cooldowns)} (1/long rest)")

        embed.add_field(name="🌌 Heavenly Demon Heir", value="\n".join(hd_lines), inline=False)

    if char.backstory:
        embed.add_field(name="Backstory", value=char.backstory[:500], inline=False)

    proxy_text = ""
    if char.proxy_open or char.proxy_close:
        proxy_text = f"`{char.proxy_open or ''}text{char.proxy_close or ''}`"
        embed.add_field(name="Proxy", value=proxy_text, inline=False)

    embed.set_footer(text=f"Background: {char.background or 'None'}  •  LoreForge")
    return embed

# ── Step embeds ───────────────────────────────────────────────────────────────

def step1_embed(char_name: str) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Character Creation — Step 1 of 5",
        description=f"Creating **{char_name}**\n\nChoose your **race**.",
        color=0x8B5CF6,
    )
    lines = [f"**{race}** — {', '.join(f'+{v} {k.upper()}' for k, v in bonuses.items())}" for race, bonuses in RACES.items()]
    embed.add_field(name="Available Races", value="\n".join(lines), inline=False)
    embed.set_footer(text="Step 1 of 6 — Race")
    return embed

def step2_embed(race: str) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Character Creation — Step 2 of 5",
        description=f"Race: **{race}** ✓\n\nChoose your **class**.",
        color=0x8B5CF6,
    )
    lines = [f"**{cls}** — {desc}" for cls, desc in CLASS_DESCRIPTIONS.items()]
    embed.add_field(name="Available Classes", value="\n".join(lines), inline=False)
    embed.set_footer(text="Step 2 of 6 — Class")
    return embed

def step3_embed(race: str, char_class: str) -> discord.Embed:
    stats = assign_stats(char_class, race)
    stat_preview = "  ".join(f"**{k.upper()}** {v}" for k, v in stats.items())
    embed = discord.Embed(
        title="⚔️ Character Creation — Step 3 of 5",
        description=f"Race: **{race}** ✓\nClass: **{char_class}** ✓\n\nChoose your **background**.",
        color=0x8B5CF6,
    )
    embed.add_field(name="Your Stats", value=stat_preview, inline=False)
    embed.add_field(name="Starting HP / AC", value=f"❤️ {calc_hp(char_class, stats['con'])}  🛡️ {calc_ac(stats['dex'])}", inline=False)
    embed.set_footer(text="Step 3 of 5 — Background")
    return embed

def step4_embed(char_name: str, race: str, char_class: str, background: str,
                chosen_stats: dict | None = None, selected_attacks: list[str] | None = None) -> discord.Embed:
    if chosen_stats:
        stats = chosen_stats
    else:
        stats = assign_stats(char_class, race)
    stat_preview = "  ".join(f"**{k.upper()}** {v}" for k, v in stats.items())
    hp = calc_hp(char_class, stats["con"])
    ac = calc_ac(stats["dex"])

    weapon_key = STARTER_WEAPONS.get(char_class, "unarmed")
    all_attacks = STARTER_ATTACKS.get(char_class, [])
    if selected_attacks:
        shown_attacks = [a["name"] for a in all_attacks if a["name"] in selected_attacks]
    else:
        shown_attacks = [a["name"] for a in all_attacks[:2]]
    dice = WEAPON_DAMAGE.get(weapon_key, (1, 4))
    weapon_label = f"{weapon_key.replace('_', ' ').title()} ({dice[0]}d{dice[1]})"
    attack_list = "  •  ".join(shown_attacks)

    embed = discord.Embed(
        title="⚔️ Character Creation — Step 5 of 6",
        description=(
            f"Almost done, **{char_name}**! Here's everything you chose.\n"
            "Add a backstory, avatar, and proxy below — or skip and set them later."
        ),
        color=0x8B5CF6,
    )
    embed.add_field(
        name="Your Character",
        value=f"🧬 **{race}**  ·  ⚔️ **{char_class}**  ·  📜 **{background}**",
        inline=False,
    )
    embed.add_field(name="Stats", value=stat_preview, inline=False)
    embed.add_field(name="HP / AC", value=f"❤️ {hp}  🛡️ {ac}", inline=True)
    embed.add_field(name="Starting Weapon", value=f"🗡️ {weapon_label}", inline=True)
    embed.add_field(name="Attacks", value=attack_list, inline=False)
    embed.set_footer(text="Step 5 of 6 — Details & Proxy")
    return embed

# ── Starting Kit step (between Background and Details) ───────────────────────

def step_kit_embed(char_name: str, race: str, char_class: str, background: str,
                    chosen_stats: dict | None = None, selected_attacks: list[str] | None = None) -> discord.Embed:
    weapon_key = STARTER_WEAPONS.get(char_class, "unarmed")
    all_attacks = STARTER_ATTACKS.get(char_class, [])
    if selected_attacks:
        chosen_attacks = [a for a in all_attacks if a["name"] in selected_attacks]
    else:
        chosen_attacks = all_attacks[:2]

    embed = discord.Embed(
        title="⚔️ Character Creation — Step 4 of 6",
        description=(
            f"Race: **{race}** ✓  Class: **{char_class}** ✓  Background: **{background}** ✓\n\n"
            "Here's your starting loadout. Locked and loaded!"
        ),
        color=0x8B5CF6,
    )

    dice = WEAPON_DAMAGE.get(weapon_key, (1, 4))
    embed.add_field(
        name="Starting Weapon",
        value=f"**{weapon_key.replace('_', ' ').title()}** ({dice[0]}d{dice[1]})",
        inline=False,
    )

    if chosen_stats:
        hp = calc_hp(char_class, chosen_stats["con"])
        ac = calc_ac(chosen_stats["dex"])
        embed.add_field(name="HP / AC", value=f"❤️ {hp}  🛡️ {ac}", inline=True)

    lines = []
    for atk in chosen_attacks:
        tags = []
        if atk.get("is_spell"):
            tags.append("spell")
        if atk.get("is_defend"):
            tags.append("defensive")
        if atk.get("is_heal"):
            tags.append("heal")
        tag_str = f" *[{', '.join(tags)}]*" if tags else ""
        lines.append(f"**{atk['name']}**{tag_str}\n*{atk.get('desc', atk['flavor'])}*")
    embed.add_field(name="Starting Attacks", value="\n\n".join(lines), inline=False)

    embed.set_footer(text="Step 4 of 6 — Starting Loadout  •  Unlock more through quests and the shop.")
    return embed


class StarterKitView(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str, background: str,
                 chosen_stats: dict | None = None, selected_attacks: list[str] | None = None):
        super().__init__(timeout=600)
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        self.background = background
        self.chosen_stats = chosen_stats
        self.selected_attacks = selected_attacks or []

    @discord.ui.button(label="Looks Good →", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def proceed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=step4_embed(self.char_name, self.race, self.char_class, self.background,
                             self.chosen_stats, self.selected_attacks),
            view=Step4View(self.char_name, self.race, self.char_class, self.background,
                          self.chosen_stats, self.selected_attacks),
        )

    @discord.ui.button(label="← Back to Attacks", style=discord.ButtonStyle.secondary, emoji="⚔️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=attack_select_embed(self.char_name, self.race, self.char_class, self.background, self.chosen_stats or {}),
            view=AttackSelectView(self.char_name, self.race, self.char_class, self.background, self.chosen_stats or {}),
        )

    @discord.ui.button(label="Start Over", style=discord.ButtonStyle.danger, emoji="↩️", row=1)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=step1_embed(self.char_name),
            view=RaceView(self.char_name),
        )


# ── Character picker (for multi-char users) ───────────────────────────────────

def pick_embed(action_label: str) -> discord.Embed:
    return discord.Embed(
        title="📋 Choose a Character",
        description=f"You have multiple characters. Which one do you want to **{action_label}**?\n\n*Tip: use `/character use` to set a default so you never have to choose.*",
        color=0x8B5CF6,
    )


class CharacterPickSelect(discord.ui.Select):
    def __init__(self, chars: list, action: str):
        self._chars = chars
        self._action = action
        options = [
            discord.SelectOption(
                label=c.name,
                value=str(c.id),
                description=f"Lv{c.level} {c.race} {c.char_class}" + ("  ★ active" if c.is_active else ""),
            )
            for c in chars
        ]
        super().__init__(placeholder="Choose a character...", options=options)

    async def callback(self, interaction: discord.Interaction):
        char_id = int(self.values[0])
        char = next((c for c in self._chars if c.id == char_id), None)
        if not char:
            await interaction.response.send_message("Character not found.", ephemeral=True)
            return

        action = self._action

        if action == "sheet":
            async with get_db() as db:
                active = await get_active_title(db, char.id)
            embed = build_sheet_embed(char, active_title_display=active[0] if active else None,
                                           active_title_color=active[1] if active else None)
            await interaction.response.edit_message(embed=embed, view=SheetView(char))

        elif action == "show":
            async with get_db() as db:
                active = await get_active_title(db, char.id)
            embed = build_sheet_embed(char, active_title_display=active[0] if active else None,
                                           active_title_color=active[1] if active else None)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            await interaction.response.edit_message(content="✅ Posted to channel!", embed=None, view=None)
            await interaction.channel.send(embed=embed)

        elif action == "delete":
            embed = discord.Embed(
                title="⚠️ Delete Character?",
                description=f"**{char.name}** — Level {char.level} {char.race} {char.char_class}\n\nThis is **permanent**. All XP, gold, and inventory will be lost.",
                color=0xEF4444,
            )
            await interaction.response.edit_message(embed=embed, view=DeleteConfirmView(char.name, char.id))

        elif action == "proxy":
            await interaction.response.send_modal(ProxySetModal(char.id))

        elif action == "proxy_remove":
            async with get_db() as db:
                result = await db.execute(select(Character).where(Character.id == char_id))
                c = result.scalar_one_or_none()
                if c:
                    c.proxy_open = None
                    c.proxy_close = None
            await interaction.response.edit_message(
                content=f"Proxy removed from **{char.name}**.", embed=None, view=None
            )

        elif action == "use":
            async with get_db() as db:
                result = await db.execute(
                    select(Character).where(
                        Character.user_id == interaction.user.id,
                        Character.guild_id == interaction.guild_id,
                        Character.is_dead == False,
                    )
                )
                for c in result.scalars().all():
                    c.is_active = (c.id == char_id)
            await interaction.response.edit_message(
                content=f"✅ **{char.name}** is now your active character. All commands will use them automatically.",
                embed=None,
                view=None,
            )


class CharacterPickView(discord.ui.View):
    def __init__(self, chars: list, action: str):
        super().__init__(timeout=300)
        self.add_item(CharacterPickSelect(chars, action))


# ── Step 4: Details modal ─────────────────────────────────────────────────────

class DetailsModal(discord.ui.Modal, title="Character Details"):
    backstory = discord.ui.TextInput(
        label="Backstory / Lore",
        style=discord.TextStyle.paragraph,
        placeholder="Write your character's history, personality, motivations...",
        required=False,
        max_length=1000,
    )
    avatar_url = discord.ui.TextInput(
        label="Avatar URL (image link)",
        style=discord.TextStyle.short,
        placeholder="https://example.com/image.png  (.jpg/.png/.gif/.webp)",
        required=False,
        max_length=500,
    )
    proxy_open = discord.ui.TextInput(
        label="Proxy opening bracket",
        style=discord.TextStyle.short,
        placeholder="e.g.  [  or  char>",
        required=False,
        max_length=10,
    )
    proxy_close = discord.ui.TextInput(
        label="Proxy closing bracket (optional)",
        style=discord.TextStyle.short,
        placeholder="e.g.  ]  — leave blank if using a prefix only",
        required=False,
        max_length=10,
    )

    def __init__(self, char_name: str, race: str, char_class: str, background: str,
                 chosen_stats: dict | None = None, selected_attacks: list[str] | None = None):
        super().__init__()
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        self.background = background
        self.chosen_stats = chosen_stats
        self.selected_attacks = selected_attacks or []

    async def on_submit(self, interaction: discord.Interaction):
        raw_url = self.avatar_url.value.strip() or None
        if raw_url and not await _is_valid_image_url(raw_url):
            await interaction.response.send_message(
                "That URL doesn't point to an image. Make sure it's a direct link to a `.jpg`, `.png`, `.gif`, `.webp`, or any image hosted online.",
                ephemeral=True,
            )
            return

        new_open = self.proxy_open.value.strip() or None
        if new_open:
            async with get_db() as db:
                conflict = await db.execute(
                    select(Character).where(
                        Character.guild_id == interaction.guild_id,
                        Character.proxy_open == new_open,
                        Character.is_dead == False,
                    )
                )
                if conflict.scalar_one_or_none():
                    await interaction.response.send_message(
                        f"Another character already uses `{new_open}` as their proxy. Your character will be created without a proxy — set one later with `/character proxy`.",
                        ephemeral=True,
                    )
                    new_open = None

        await _create_character(
            interaction,
            char_name=self.char_name,
            race=self.race,
            char_class=self.char_class,
            background=self.background,
            backstory=self.backstory.value.strip() or None,
            avatar_url=self.avatar_url.value.strip() or None,
            proxy_open=new_open,
            proxy_close=self.proxy_close.value.strip() or None,
            chosen_stats=self.chosen_stats,
            selected_attacks=self.selected_attacks,
        )


class Step4View(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str, background: str,
                 chosen_stats: dict | None = None, selected_attacks: list[str] | None = None):
        super().__init__(timeout=600)
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        self.background = background
        self.chosen_stats = chosen_stats
        self.selected_attacks = selected_attacks or []

    @discord.ui.button(label="Add Backstory & Proxy →", style=discord.ButtonStyle.primary, emoji="📖")
    async def add_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            DetailsModal(self.char_name, self.race, self.char_class, self.background,
                        self.chosen_stats, self.selected_attacks)
        )

    @discord.ui.button(label="Skip & Create", style=discord.ButtonStyle.secondary, emoji="⚔️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await _create_character(
            interaction,
            char_name=self.char_name,
            race=self.race,
            char_class=self.char_class,
            background=self.background,
            chosen_stats=self.chosen_stats,
            selected_attacks=self.selected_attacks,
        )

    @discord.ui.button(label="Start Over", style=discord.ButtonStyle.danger, emoji="↩️", row=1)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=step1_embed(self.char_name),
            view=RaceView(self.char_name),
        )

# ── Shared character creation ──────────────────────────────────────────────────

async def _create_character(
    interaction: discord.Interaction,
    char_name: str,
    race: str,
    char_class: str,
    background: str,
    backstory: str | None = None,
    avatar_url: str | None = None,
    proxy_open: str | None = None,
    proxy_close: str | None = None,
    is_custom: bool = False,
    chosen_stats: dict | None = None,
    selected_attacks: list[str] | None = None,
):
    # Restricted class check — only the authorized user can create this class
    if char_class in RESTRICTED_CLASSES and interaction.user.id != RESTRICTED_USER_ID:
        if interaction.response.is_done():
            await interaction.followup.send("This class is not available to you.", ephemeral=True)
        else:
            await interaction.response.send_message("This class is not available to you.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        existing = list(result.scalars().all())
        if len(existing) >= MAX_CHARACTERS:
            msg = f"You already have {MAX_CHARACTERS} characters. Delete one with `/character delete` first."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        # First character is auto-set as active
        is_first = len(existing) == 0

        if is_custom:
            # Custom characters: flat 10 in all stats, base HP/AC, no starter gear
            char = Character(
                user_id=interaction.user.id,
                guild_id=interaction.guild_id,
                name=char_name,
                race=race,
                char_class=char_class,
                background=background,
                level=1,
                xp=0,
                is_custom=True,
                strength=10,
                dexterity=10,
                constitution=10,
                intelligence=10,
                wisdom=10,
                charisma=10,
                hp_max=10,
                hp_current=10,
                armor_class=10,
                gold=100,
                inventory=[],
                conditions=[],
                skill_proficiencies=[],
                class_resources={},
                backstory=backstory,
                avatar_url=avatar_url,
                proxy_open=proxy_open,
                proxy_close=proxy_close,
                is_dead=False,
                is_unconscious=False,
                is_active=is_first,
            )
        else:
            if chosen_stats:
                stats = chosen_stats
            else:
                stats = assign_stats(char_class, race)

            weapon_key = STARTER_WEAPONS.get(char_class, "unarmed")
            starting_inventory = (
                [{"key": weapon_key, "type": "weapon", "equipped": True}]
                if weapon_key != "unarmed" else []
            )

            resources = _starting_resources(char_class)
            if selected_attacks:
                resources["attacks"] = selected_attacks
            else:
                resources["attacks"] = [atk["name"] for atk in (STARTER_ATTACKS.get(char_class) or [])[:2]]

            char = Character(
                user_id=interaction.user.id,
                guild_id=interaction.guild_id,
                name=char_name,
                race=race,
                char_class=char_class,
                background=background,
                level=1,
                xp=0,
                is_custom=False,
                strength=stats["str"],
                dexterity=stats["dex"],
                constitution=stats["con"],
                intelligence=stats["int"],
                wisdom=stats["wis"],
                charisma=stats["cha"],
                hp_max=calc_hp(char_class, stats["con"]),
                hp_current=calc_hp(char_class, stats["con"]),
                armor_class=calc_ac(stats["dex"]),
                gold=100,
                inventory=starting_inventory,
                conditions=[],
                skill_proficiencies=[],
                class_resources=resources,
                backstory=backstory,
                avatar_url=avatar_url,
                proxy_open=proxy_open,
                proxy_close=proxy_close,
                is_dead=False,
                is_unconscious=False,
                is_active=is_first,
            )
        db.add(char)

    embed = build_sheet_embed(char)
    embed.title = f"⚔️ {char.name} has entered the world!"
    if is_first:
        embed.description = (embed.description or "") + "\n\n★ Set as your active character automatically."
    else:
        embed.description = (embed.description or "") + "\n\nUse `/character use` to make this your active character."
    if proxy_open:
        brackets = f"`{proxy_open}text{proxy_close or ''}`"
        embed.set_footer(text=f"Proxy active — type {brackets} to speak as {char.name}")

    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.edit_original_response(embed=embed, view=None)

    # Send class tutorial via DM
    if not is_custom and char.char_class in TUTORIALS:
        tutorial_view = TutorialView(char.char_class, page=0)
        tutorial_embed = tutorial_view._build_embed()
        try:
            dm_channel = await interaction.user.create_dm()
            msg = await dm_channel.send(
                embed=tutorial_embed,
                view=tutorial_view,
            )
            tutorial_view.message = msg
        except discord.Forbidden:
            # User has DMs disabled — silently skip
            pass
        except Exception:
            pass

# ── Steps 1-3: Race → Class → Background ─────────────────────────────────────

class RaceSelect(discord.ui.Select):
    def __init__(self, char_name: str):
        self.char_name = char_name
        options = [
            discord.SelectOption(
                label=race,
                description=f"Bonuses: {', '.join(f'+{v} {k.upper()}' for k, v in bonuses.items())}"
            )
            for race, bonuses in RACES.items()
        ]
        super().__init__(placeholder="Choose your race...", options=options)

    async def callback(self, interaction: discord.Interaction):
        race = self.values[0]
        info = RACE_INFO[race]
        bonuses = RACES[race]
        bonus_str = ", ".join(f"+{v} {k.upper()}" for k, v in bonuses.items())
        embed = discord.Embed(
            title=f"🧬 {race} Selected",
            description=(
                f"**{race}**\n\n"
                f"{info['lore']}\n\n"
                f"**Racial Bonuses:** {bonus_str}\n"
                f"*{info['bonus_detail']}*"
            ),
            color=0x8B5CF6,
        )
        await interaction.response.edit_message(
            embed=embed,
            view=RaceConfirmView(self.char_name, race),
        )


class RaceConfirmView(discord.ui.View):
    """Confirm race selection and proceed to class, or go back."""
    def __init__(self, char_name: str, race: str):
        super().__init__(timeout=600)
        self.char_name = char_name
        self.race = race

    @discord.ui.button(label="Looks Good → Choose Class", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def proceed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=step2_embed(self.race),
            view=ClassView(self.race, self.char_name, user_id=interaction.user.id),
        )

    @discord.ui.button(label="View Race Details 📖", style=discord.ButtonStyle.secondary)
    async def view_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show full RACE_INFO ephemerally before choosing."""
        info = RACE_INFO[self.race]
        bonuses = RACES[self.race]
        bonus_str = ", ".join(f"+{v} {k.upper()}" for k, v in bonuses.items())
        embed = discord.Embed(
            title=f"📖 {self.race} — Full Details",
            description=info["lore"],
            color=0x6366F1,
        )
        embed.add_field(name="Racial Bonuses", value=bonus_str, inline=False)
        embed.add_field(name="Recommended For", value=info["bonus_detail"], inline=False)
        embed.set_footer(text=f"Step 1 of 6 — {self.race}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="← Back to All Races", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=step1_embed(self.char_name), view=RaceView(self.char_name))


class RaceView(discord.ui.View):
    def __init__(self, char_name: str):
        super().__init__(timeout=600)
        self.add_item(RaceSelect(char_name))


class ClassSelect(discord.ui.Select):
    def __init__(self, race: str, char_name: str, user_id: int = 0):
        self.race = race
        self.char_name = char_name
        # Filter restricted classes — only shown to the authorized user
        options = [
            discord.SelectOption(label=cls, description=CLASS_DESCRIPTIONS[cls])
            for cls in CLASSES
            if cls not in RESTRICTED_CLASSES or user_id == RESTRICTED_USER_ID
        ]
        super().__init__(placeholder="Choose your class...", options=options)

    async def callback(self, interaction: discord.Interaction):
        char_class = self.values[0]
        # Double-check restricted class access
        if char_class in RESTRICTED_CLASSES and interaction.user.id != RESTRICTED_USER_ID:
            await interaction.response.send_message(
                "This class is not available to you.", ephemeral=True
            )
            return
        # Show class details confirmation with View Full Details button
        info = CLASS_INFO[char_class]
        embed = discord.Embed(
            title=f"⚔️ {char_class} Selected",
            description=(
                f"Race: **{self.race}** ✓\n\n"
                f"**{char_class}** — {CLASS_DESCRIPTIONS[char_class]}\n"
                f"🎲 Hit Die: d{info['hit_die']}  |  ⭐ Primary: {info['primary']}  |  🛡️ Saves: {info['saves']}\n\n"
                "Before we continue, you'll get to **roll for stats** and pick your **starting attacks**."
            ),
            color=0x8B5CF6,
        )
        embed.add_field(name="Class Resource", value=info["resource"], inline=False)
        await interaction.response.edit_message(
            embed=embed,
            view=StatOrDetailsView(self.char_name, self.race, char_class),
        )


class ClassView(discord.ui.View):
    def __init__(self, race: str, char_name: str, user_id: int = 0):
        super().__init__(timeout=600)
        self.add_item(ClassSelect(race, char_name, user_id=user_id))


# ── Stat Rolling Views ────────────────────────────────────────────────────────

def _stat_set_embed(race: str, char_class: str, stats: dict, label: str) -> discord.Embed:
    """Build an embed for one stat set."""
    hp = calc_hp(char_class, stats["con"])
    ac = calc_ac(stats["dex"])
    stat_lines = []
    for abbr, label_name in STAT_LABELS.items():
        score = stats[abbr]
        racial = RACES[race].get(abbr, 0)
        racial_str = f" (incl. +{racial})" if racial else ""
        stat_lines.append(f"**{label_name[:3].upper()}** {score}{racial_str} ({mod_str(score)})")
    embed = discord.Embed(
        title=f"🎲 Stat Set {label}",
        description=f"4d6-drop-lowest + racial bonuses applied\n\n" + "\n".join(stat_lines),
        color=0x6366F1,
    )
    embed.add_field(name="❤️ HP", value=str(hp), inline=True)
    embed.add_field(name="🛡️ AC", value=str(ac), inline=True)
    return embed


class StatRollView(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str, set_a: dict, set_b: dict):
        super().__init__(timeout=300)
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        self.set_a = set_a
        self.set_b = set_b

    @discord.ui.button(label="Choose Set A", style=discord.ButtonStyle.primary, emoji="🔷")
    async def choose_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._choose(interaction, self.set_a)

    @discord.ui.button(label="Choose Set B", style=discord.ButtonStyle.success, emoji="🔶")
    async def choose_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._choose(interaction, self.set_b)

    async def _choose(self, interaction: discord.Interaction, chosen: dict):
        embed = discord.Embed(
            title="✅ Stats Chosen!",
            description=f"Race: **{self.race}** ✓  Class: **{self.char_class}** ✓\n\nNow choose your **background**.",
            color=0x22C55E,
        )
        stat_preview = "  ".join(f"**{k.upper()}** {v}" for k, v in chosen.items())
        embed.add_field(name="Your Stats", value=stat_preview, inline=False)
        embed.add_field(name="Starting HP / AC", value=f"❤️ {calc_hp(self.char_class, chosen['con'])}  🛡️ {calc_ac(chosen['dex'])}", inline=False)
        embed.set_footer(text="Step 3 of 6 — Background")
        await interaction.response.edit_message(
            embed=embed,
            view=BackgroundView(self.char_name, self.race, self.char_class, chosen),
        )


# ── Class Details & Stat Roll gate ────────────────────────────────────────────

class StatOrDetailsView(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str):
        super().__init__(timeout=600)
        self.char_name = char_name
        self.race = race
        self.char_class = char_class

    @discord.ui.button(label="View Full Details 📖", style=discord.ButtonStyle.secondary)
    async def view_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        info = CLASS_INFO[self.char_class]
        embed = discord.Embed(
            title=f"📖 {self.char_class} — Full Breakdown",
            description=info["flavor"],
            color=0x8B5CF6,
        )
        embed.add_field(name="🎲 Hit Die", value=f"d{info['hit_die']}", inline=True)
        embed.add_field(name="⭐ Primary Stat", value=info["primary"], inline=True)
        embed.add_field(name="🛡️ Saving Throws", value=info["saves"], inline=True)
        embed.add_field(name="⚡ Class Resource", value=info["resource"], inline=False)
        embed.add_field(name="💡 How to Play", value=info["tips"], inline=False)
        embed.set_footer(text="Close this and click 'Roll Stats →' when ready!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Roll Stats →", style=discord.ButtonStyle.primary, emoji="🎲")
    async def roll_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Roll two stat sets
        set_a = roll_stat_set(self.race, self.char_class)
        set_b = roll_stat_set(self.race, self.char_class)
        # Ensure they're different (reroll if identical)
        attempts = 0
        while set_a == set_b and attempts < 5:
            set_b = roll_stat_set(self.race, self.char_class)
            attempts += 1

        embed = discord.Embed(
            title="🎲 Roll Your Stats!",
            description=(
                f"Race: **{self.race}** ✓  Class: **{self.char_class}** ✓\n\n"
                "Two stat sets were rolled using **4d6-drop-lowest**.\n"
                "Racial bonuses have been applied to both.\n\n"
                "**Choose the set you want!**"
            ),
            color=0x6366F1,
        )
        embed.set_footer(text="Step 2.5 of 6 — Stat Rolling")

        embed_a = _stat_set_embed(self.race, self.char_class, set_a, "A 🟦")
        embed_b = _stat_set_embed(self.race, self.char_class, set_b, "B 🟧")

        # Send the choice embed + the two stat sets as followup
        await interaction.response.edit_message(embed=embed, view=None)
        await interaction.followup.send(embed=embed_a, ephemeral=True)
        await interaction.followup.send(
            embed=embed_b,
            view=StatRollView(self.char_name, self.race, self.char_class, set_a, set_b),
            ephemeral=True,
        )


# ── Background Selection (now stores chosen stats) ────────────────────────────

class BackgroundSelect(discord.ui.Select):
    def __init__(self, char_name: str, race: str, char_class: str, chosen_stats: dict):
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        self.chosen_stats = chosen_stats
        options = [
            discord.SelectOption(label=bg, description=BACKGROUND_DESCRIPTIONS[bg])
            for bg in BACKGROUNDS
        ]
        super().__init__(placeholder="Choose your background...", options=options)

    async def callback(self, interaction: discord.Interaction):
        background = self.values[0]
        # Show attack selection next
        await interaction.response.edit_message(
            embed=attack_select_embed(self.char_name, self.race, self.char_class, background, self.chosen_stats),
            view=AttackSelectView(self.char_name, self.race, self.char_class, background, self.chosen_stats),
        )


class BackgroundView(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str, chosen_stats: dict):
        super().__init__(timeout=600)
        self.add_item(BackgroundSelect(char_name, race, char_class, chosen_stats))

# ── Attack Selection ──────────────────────────────────────────────────────────

def attack_select_embed(char_name: str, race: str, char_class: str, background: str, chosen_stats: dict) -> discord.Embed:
    attacks = STARTER_ATTACKS.get(char_class, [])
    embed = discord.Embed(
        title="⚔️ Character Creation — Choose Attacks",
        description=(
            f"Race: **{race}** ✓  Class: **{char_class}** ✓  Background: **{background}** ✓\n\n"
            f"Pick **2 attacks** from your class's available options to start with.\n"
            f"You can unlock more through leveling up and quests."
        ),
        color=0x8B5CF6,
    )
    for atk in attacks:
        tags = []
        if atk.get("is_spell"):
            tags.append("✨ spell")
        if atk.get("is_defend"):
            tags.append("🛡️ def")
        if atk.get("is_heal"):
            tags.append("💚 heal")
        if atk.get("is_special"):
            tags.append("⚡ special")
        tag_str = f"  *[{', '.join(tags)}]*" if tags else ""
        embed.add_field(
            name=f"• {atk['name']}{tag_str}",
            value=f"{atk.get('desc', atk['flavor'])}",
            inline=False,
        )
    embed.set_footer(text="Select 2 attacks from the dropdown below")
    return embed


class AttackSelect(discord.ui.Select):
    def __init__(self, char_name: str, race: str, char_class: str, background: str, chosen_stats: dict):
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        self.background = background
        self.chosen_stats = chosen_stats
        attacks = STARTER_ATTACKS.get(char_class, [])
        options = [
            discord.SelectOption(
                label=atk["name"],
                value=atk["name"],
                description=atk["flavor"][:100],
            )
            for atk in attacks
        ]
        super().__init__(
            placeholder="Select up to 2 attacks...",
            options=options,
            max_values=min(2, len(options)),
            min_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values
        embed = step_kit_embed(
            self.char_name, self.race, self.char_class, self.background,
            chosen_stats=self.chosen_stats, selected_attacks=selected,
        )
        await interaction.response.edit_message(
            embed=embed,
            view=StarterKitView(self.char_name, self.race, self.char_class, self.background,
                               chosen_stats=self.chosen_stats, selected_attacks=selected),
        )


class AttackSelectView(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str, background: str, chosen_stats: dict):
        super().__init__(timeout=600)
        self.add_item(AttackSelect(char_name, race, char_class, background, chosen_stats))

    @discord.ui.button(label="← Back to Background", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        stats = self.children[0].chosen_stats if isinstance(self.children[0], AttackSelect) else {}
        embed = discord.Embed(
            title="⚔️ Character Creation — Step 3 of 6",
            description=f"Race: **{self.children[0].race}** ✓  Class: **{self.children[0].char_class}** ✓\n\nChoose your **background**.",
            color=0x8B5CF6,
        )
        stat_preview = "  ".join(f"**{k.upper()}** {v}" for k, v in stats.items())
        embed.add_field(name="Your Stats", value=stat_preview, inline=False)
        hp = calc_hp(self.children[0].char_class, stats.get("con", 10))
        ac = calc_ac(stats.get("dex", 10))
        embed.add_field(name="Starting HP / AC", value=f"❤️ {hp}  🛡️ {ac}", inline=False)
        embed.set_footer(text="Step 3 of 6 — Background")
        await interaction.response.edit_message(
            embed=embed,
            view=BackgroundView(
                self.children[0].char_name if isinstance(self.children[0], AttackSelect) else self.char_name,
                self.children[0].race if isinstance(self.children[0], AttackSelect) else self.race,
                self.children[0].char_class if isinstance(self.children[0], AttackSelect) else self.char_class,
                stats,
            ),
        )


# ── Tutorial System ───────────────────────────────────────────────────────────

class TutorialView(discord.ui.View):
    def __init__(self, char_class: str, page: int = 0):
        super().__init__(timeout=300)
        self.char_class = char_class
        self.page = page
        self.pages = TUTORIALS.get(char_class, [])
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= len(self.pages) - 1

    def _build_embed(self) -> discord.Embed:
        page_data = self.pages[self.page]
        embed = discord.Embed(
            title=page_data["title"],
            description=page_data["description"],
            color=0x6366F1,
        )
        for field in page_data.get("fields", []):
            if field["name"] == "Your Attacks" and self.char_class:
                # Dynamically populate with character's actual attacks
                attacks = STARTER_ATTACKS.get(self.char_class, [])
                if attacks:
                    atk_lines = "\n\n".join(
                        f"**{a['name']}** — {a.get('desc', a['flavor'])}" for a in attacks[:2]
                    )
                    embed.add_field(name="Your Starting Attacks", value=atk_lines, inline=False)
                    if len(attacks) > 2:
                        more = "\n".join(f"• {a['name']} — {a.get('desc', a['flavor'])[:50]}..." for a in attacks[2:])
                        embed.add_field(name="More Available (unlock later)", value=more, inline=False)
                else:
                    embed.add_field(name="Starting Attacks", value="No attacks data available.", inline=False)
            else:
                embed.add_field(name=field["name"], value=field["value"], inline=False)
        embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)}  •  Tutorial")
        return embed

    @discord.ui.button(label="← Back", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="Next →", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="Skip Tutorial", style=discord.ButtonStyle.danger, emoji="⏭️", row=1)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Tutorial skipped — happy adventuring! ⚔️", embed=None, view=None)

    async def on_timeout(self):
        try:
            await self.message.edit(content="Tutorial timed out.", embed=None, view=None)
        except Exception:
            pass


# ── Sheet Buttons View ────────────────────────────────────────────────────────

class SheetView(discord.ui.View):
    def __init__(self, char: "Character"):
        super().__init__(timeout=None)
        self.char = char

    @discord.ui.button(label="Explain My Class 📖", style=discord.ButtonStyle.secondary)
    async def explain_class(self, interaction: discord.Interaction, button: discord.ui.Button):
        char = self.char
        class_name = char.char_class
        if class_name not in TUTORIALS:
            await interaction.response.send_message("No tutorial available for this class.", ephemeral=True)
            return
        view = TutorialView(class_name, page=0)
        embed = view._build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Edit Cosmetics ✏️", style=discord.ButtonStyle.secondary)
    async def edit_cosmetics(self, interaction: discord.Interaction, button: discord.ui.Button):
        from database.session import get_db
        from sqlalchemy import select
        async with get_db() as db:
            result = await db.execute(select(Character).where(Character.id == self.char.id))
            char = result.scalar_one_or_none()
            if not char:
                await interaction.response.send_message("Character not found.", ephemeral=True)
                return
            await interaction.response.send_modal(CosmeticEditModal(char.id))


class CosmeticEditModal(discord.ui.Modal, title="Edit Cosmetics"):
    char_name = discord.ui.TextInput(
        label="Name",
        style=discord.TextStyle.short,
        required=False,
        max_length=32,
    )
    backstory = discord.ui.TextInput(
        label="Backstory",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
    )
    avatar_url = discord.ui.TextInput(
        label="Avatar URL",
        style=discord.TextStyle.short,
        required=False,
        max_length=500,
    )
    proxy_open = discord.ui.TextInput(
        label="Proxy Opening",
        style=discord.TextStyle.short,
        required=False,
        max_length=10,
    )
    proxy_close = discord.ui.TextInput(
        label="Proxy Closing",
        style=discord.TextStyle.short,
        required=False,
        max_length=10,
    )

    def __init__(self, char_id: int):
        super().__init__()
        self.char_id = char_id

    async def on_submit(self, interaction: discord.Interaction):
        from database.session import get_db
        from sqlalchemy import select
        async with get_db() as db:
            result = await db.execute(select(Character).where(Character.id == self.char_id))
            char = result.scalar_one_or_none()
            if not char:
                await interaction.response.send_message("Character not found.", ephemeral=True)
                return
            if self.char_name.value.strip():
                char.name = self.char_name.value.strip()
            if self.backstory.value.strip():
                char.backstory = self.backstory.value.strip()
            raw_url = self.avatar_url.value.strip()
            if raw_url:
                if not await _is_valid_image_url(raw_url):
                    await interaction.response.send_message("Invalid image URL.", ephemeral=True)
                    return
                char.avatar_url = raw_url
            if self.proxy_open.value.strip():
                char.proxy_open = self.proxy_open.value.strip()
            if self.proxy_close.value.strip():
                char.proxy_close = self.proxy_close.value.strip()
        await interaction.response.send_message("✅ Cosmetics updated!", ephemeral=True)


# ── Delete confirm ────────────────────────────────────────────────────────────

class DeleteConfirmView(discord.ui.View):
    def __init__(self, char_name: str, char_id: int):
        super().__init__(timeout=300)
        self.char_name = char_name
        self.char_id = char_id

    @discord.ui.button(label="Yes, delete forever", style=discord.ButtonStyle.danger, emoji="💀")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with get_db() as db:
            result = await db.execute(select(Character).where(Character.id == self.char_id))
            char = result.scalar_one_or_none()
            if not char:
                await interaction.response.edit_message(content="No character found.", view=None, embed=None)
                return
            was_active = char.is_active
            await db.delete(char)

        msg = f"**{self.char_name}** has been permanently deleted."
        if was_active:
            msg += " Use `/character use` to set another active character."
        await interaction.response.edit_message(content=msg, view=None, embed=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Deletion cancelled.", view=None, embed=None)


# ── Proxy set modal ───────────────────────────────────────────────────────────

class ProxySetModal(discord.ui.Modal, title="Set Proxy"):
    proxy_open = discord.ui.TextInput(
        label="Opening bracket / prefix",
        style=discord.TextStyle.short,
        placeholder="e.g.  [  or  char>",
        required=True,
        max_length=10,
    )
    proxy_close = discord.ui.TextInput(
        label="Closing bracket (optional)",
        style=discord.TextStyle.short,
        placeholder="e.g.  ]  — leave blank for prefix-only",
        required=False,
        max_length=10,
    )
    avatar_url = discord.ui.TextInput(
        label="Avatar URL (optional, updates existing)",
        style=discord.TextStyle.short,
        placeholder="https://example.com/image.png  (.jpg/.png/.gif/.webp)",
        required=False,
        max_length=500,
    )

    def __init__(self, char_id: int):
        super().__init__()
        self.char_id = char_id

    async def on_submit(self, interaction: discord.Interaction):
        raw_url = self.avatar_url.value.strip()
        if raw_url and not await _is_valid_image_url(raw_url):
            await interaction.response.send_message(
                "That URL doesn't point to an image. Make sure it's a direct link to a `.jpg`, `.png`, `.gif`, `.webp`, or any image hosted online.",
                ephemeral=True,
            )
            return

        new_open = self.proxy_open.value.strip()
        async with get_db() as db:
            conflict = await db.execute(
                select(Character).where(
                    Character.guild_id == interaction.guild_id,
                    Character.proxy_open == new_open,
                    Character.id != self.char_id,
                    Character.is_dead == False,
                )
            )
            if conflict.scalar_one_or_none():
                await interaction.response.send_message(
                    f"Another character in this server already uses `{new_open}` as their proxy. Choose a different bracket.",
                    ephemeral=True,
                )
                return

            result = await db.execute(select(Character).where(Character.id == self.char_id))
            char = result.scalar_one_or_none()
            if not char:
                await interaction.response.send_message("Character not found.", ephemeral=True)
                return
            char.proxy_open = new_open
            char.proxy_close = self.proxy_close.value.strip() or None
            if self.avatar_url.value.strip():
                char.avatar_url = self.avatar_url.value.strip()

        brackets = f"`{char.proxy_open}text{char.proxy_close or ''}`"
        await interaction.response.send_message(
            f"✅ Proxy set for **{char.name}**.\nType {brackets} in any channel to speak as them.",
            ephemeral=True,
        )

# ── Custom character creation ─────────────────────────────────────────────────

class CustomCharacterModal(discord.ui.Modal, title="Create Custom Character"):
    char_class = discord.ui.TextInput(
        label="Class / Role",
        placeholder="e.g. Shadow Assassin, Arcane Archer",
        max_length=50,
    )
    race = discord.ui.TextInput(
        label="Race / Species",
        placeholder="e.g. Aasimar, Kitsune, Half-Dragon",
        max_length=50,
    )
    background = discord.ui.TextInput(
        label="Background",
        placeholder="e.g. Fallen Noble, Street Rat, War Veteran",
        max_length=50,
    )
    backstory = discord.ui.TextInput(
        label="Backstory (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
    )
    avatar_url = discord.ui.TextInput(
        label="Avatar URL (optional)",
        required=False,
        max_length=500,
    )

    def __init__(self, char_name: str):
        super().__init__()
        self.char_name = char_name

    async def on_submit(self, interaction: discord.Interaction):
        raw_url = self.avatar_url.value.strip() or None
        if raw_url and not await _is_valid_image_url(raw_url):
            await interaction.response.send_message(
                "That URL doesn't point to an image. Make sure it's a direct link to a `.jpg`, `.png`, `.gif`, `.webp`, or any image hosted online.",
                ephemeral=True,
            )
            return

        await _create_character(
            interaction,
            char_name=self.char_name,
            race=self.race.value.strip(),
            char_class=self.char_class.value.strip(),
            background=self.background.value.strip(),
            backstory=self.backstory.value.strip() or None,
            avatar_url=raw_url,
            is_custom=True,
        )


class CharTypeView(discord.ui.View):
    def __init__(self, char_name: str):
        super().__init__(timeout=300)
        self.char_name = char_name

    @discord.ui.button(label="DnD Character", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def dnd_char(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=step1_embed(self.char_name), view=RaceView(self.char_name))

    @discord.ui.button(label="Custom Character", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def custom_char(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomCharacterModal(self.char_name))


# ── Command group ─────────────────────────────────────────────────────────────

character_group = app_commands.Group(name="character", description="Create and manage your character")


@character_group.command(name="create", description="Create a new character (max 3 per server)")
@app_commands.describe(name="Your character's name")
async def character_create(interaction: discord.Interaction, name: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    name = name.strip()
    if len(name) < 2 or len(name) > 32:
        await interaction.response.send_message("Name must be 2–32 characters.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    chars = await get_characters(interaction.user.id, interaction.guild_id)
    if len(chars) >= MAX_CHARACTERS:
        await interaction.followup.send(
            f"You already have {MAX_CHARACTERS} characters. Delete one with `/character delete` first.",
            ephemeral=True,
        )
        return

    type_embed = discord.Embed(
        title="⚔️ Create Character — Choose Type",
        description=(
            f"**{name}**\n\n"
            "What kind of character do you want to create?\n\n"
            "**DnD Character** — Race → Class → Roll Stats → Background → Pick Attacks → Details (6-step wizard)\n"
            "**Custom Character** — Completely free-form: any race, class, and background you imagine"
        ),
        color=0x8B5CF6,
    )
    type_embed.set_footer(text="Custom characters can only do manual combat (no AI resolution)")
    await interaction.followup.send(embed=type_embed, view=CharTypeView(name), ephemeral=True)


@character_group.command(name="use", description="Set your active character — all commands use them automatically")
async def character_use(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    chars = await get_characters(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.followup.send("No characters found. Use `/character create`.", ephemeral=True)
        return

    if len(chars) == 1:
        async with get_db() as db:
            result = await db.execute(select(Character).where(Character.id == chars[0].id))
            c = result.scalar_one_or_none()
            if c:
                c.is_active = True
        await interaction.followup.send(
            f"✅ **{chars[0].name}** is your active character.", ephemeral=True
        )
        return

    await interaction.followup.send(
        embed=pick_embed("set as active"),
        view=CharacterPickView(chars, "use"),
        ephemeral=True,
    )


@character_group.command(name="unuse", description="Clear your active character — you'll be asked to choose each time")
async def character_unuse(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        char = result.scalar_one_or_none()
        if not char:
            await interaction.followup.send("You don't have an active character set.", ephemeral=True)
            return
        name = char.name
        char.is_active = False

    await interaction.followup.send(
        f"**{name}** is no longer your active character. You'll be asked to choose each time.",
        ephemeral=True,
    )


@character_group.command(name="sheet", description="View your character sheet (private)")
async def character_sheet(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.followup.send("No character found. Use `/character create`.", ephemeral=True)
        return
    if char:
        view = SheetView(char)
        async with get_db() as db:
            active = await get_active_title(db, char.id)
        embed = build_sheet_embed(char, active_title_display=active[0] if active else None,
                                       active_title_color=active[1] if active else None)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.followup.send(
            embed=pick_embed("view sheet for"), view=CharacterPickView(chars, "sheet"), ephemeral=True
        )


@character_group.command(name="show", description="Show your character sheet to the server")
async def character_show(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    await interaction.response.defer()

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.followup.send("No character found. Use `/character create`.", ephemeral=True)
        return
    if char:
        async with get_db() as db:
            active = await get_active_title(db, char.id)
        embed = build_sheet_embed(char, active_title_display=active[0] if active else None,
                                       active_title_color=active[1] if active else None)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(
            embed=pick_embed("show"), view=CharacterPickView(chars, "show"), ephemeral=True
        )


@character_group.command(name="proxy", description="Set or update a character's proxy brackets")
async def character_proxy(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
        return
    if char:
        await interaction.response.send_modal(ProxySetModal(char.id))
    else:
        await interaction.response.send_message(
            embed=pick_embed("set proxy for"), view=CharacterPickView(chars, "proxy"), ephemeral=True
        )


@character_group.command(name="delete", description="Permanently delete a character")
async def character_delete(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.followup.send("You don't have any characters to delete.", ephemeral=True)
        return
    if char:
        embed = discord.Embed(
            title="⚠️ Delete Character?",
            description=f"**{char.name}** — Level {char.level} {char.race} {char.char_class}\n\nThis is **permanent**. All XP, gold, and inventory will be lost.",
            color=0xEF4444,
        )
        await interaction.followup.send(embed=embed, view=DeleteConfirmView(char.name, char.id), ephemeral=True)
    else:
        await interaction.followup.send(
            embed=pick_embed("delete"), view=CharacterPickView(chars, "delete"), ephemeral=True
        )


@character_group.command(name="list", description="List all your characters in this server")
@app_commands.describe(public="Show the list publicly in the channel (default: private)")
async def character_list(interaction: discord.Interaction, public: bool = False):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=not public)

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
            ).order_by(Character.is_active.desc(), Character.id)
        )
        chars = list(result.scalars().all())

    if not chars:
        await interaction.response.send_message(
            "You have no characters in this server. Use `/character create` to make one.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title=f"📋 {interaction.user.display_name}'s Characters",
        color=0x8B5CF6,
    )
    for char in chars:
        if char.is_dead:
            status = "💀 Dead"
        elif char.is_unconscious:
            status = "😵 Unconscious"
        elif char.is_active:
            status = "★ Active"
        else:
            status = "✅ Alive"
        embed.add_field(
            name=f"{char.name}  —  {status}",
            value=f"Lv{char.level} {char.race} {char.char_class}  ·  ❤️ {char.hp_current}/{char.hp_max}  ·  💰 {char.gold} gp  ·  XP: {char.xp}",
            inline=False,
        )
    embed.set_footer(text=f"{len(chars)}/{MAX_CHARACTERS} character slots used  •  LoreForge")

    await interaction.followup.send(embed=embed, ephemeral=not public)


@character_group.command(name="proxy_remove", description="Remove a character's proxy")
async def character_proxy_remove(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.followup.send("No character found.", ephemeral=True)
        return
    if char:
        async with get_db() as db:
            result = await db.execute(select(Character).where(Character.id == char.id))
            c = result.scalar_one_or_none()
            if c:
                c.proxy_open = None
                c.proxy_close = None
        await interaction.followup.send(f"Proxy removed from **{char.name}**.", ephemeral=True)
    else:
        await interaction.followup.send(
            embed=pick_embed("remove proxy from"), view=CharacterPickView(chars, "proxy_remove"), ephemeral=True
        )


@character_group.command(name="edit", description="Edit your character (cosmetic changes are instant; stats need GM approval)")
async def character_edit(interaction: discord.Interaction):
    """Legacy command — shows info about the split edit system."""
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    embed = discord.Embed(
        title="✏️ Character Editing",
        description=(
            "Editing has been split into two commands:\n\n"
            "**`/character edit_cosmetic`** — Change your name, backstory, avatar, or proxy. **Instant**, no approval needed.\n\n"
            "**`/character edit_stats`** — Request a stat, Gold, XP, or HP Max change. Goes through **GM approval queue**."
        ),
        color=0x8B5CF6,
    )
    embed.set_footer(text="LoreForge  •  GMs can use /gm edit for instant changes")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /classes Browse Command ───────────────────────────────────────────────────

classes_group = app_commands.Group(name="classes", description="Browse all available classes like a codex")


class ClassBrowseSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=cls, description=CLASS_DESCRIPTIONS[cls])
            for cls in CLASSES
        ]
        super().__init__(placeholder="Choose a class to inspect...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cls = self.values[0]
        info = CLASS_INFO[cls]
        class_data = CLASSES[cls]

        embed = discord.Embed(
            title=f"📖 {cls} — Class Codex",
            description=info["flavor"],
            color=0x8B5CF6,
        )
        embed.add_field(name="🎲 Hit Die", value=f"d{class_data['hit_die']}", inline=True)
        embed.add_field(name="⭐ Primary Stat", value=info["primary"], inline=True)
        embed.add_field(name="🛡️ Saving Throws", value=info["saves"], inline=True)
        embed.add_field(name="🏹 Starting Weapons", value=f"**{STARTER_WEAPONS.get(cls, 'unarmed').replace('_', ' ').title()}**", inline=True)
        embed.add_field(name="⚡ Resource", value=info["resource"], inline=False)

        # Starting attacks
        attacks = STARTER_ATTACKS.get(cls, [])
        atk_lines = "\n".join(f"• **{a['name']}** — {a.get('desc', a['flavor'])}" for a in attacks[:3])
        if len(attacks) > 3:
            atk_lines += f"\n*...and {len(attacks) - 3} more*"
        embed.add_field(name="Starting Attacks", value=atk_lines, inline=False)

        # Level milestones
        milestones = []
        from services.leveling import CLASS_FEATURES
        features = CLASS_FEATURES.get(cls, {})
        for lvl in [1, 3, 5, 10, 20]:
            if lvl in features:
                milestones.append(f"**Level {lvl}** — {features[lvl]}")
        embed.add_field(name="📈 Level Milestones", value="\n".join(milestones), inline=False)

        embed.add_field(name="💡 How to Play", value=info["tips"], inline=False)

        embed.set_footer(text="LoreForge  •  Click 'Create Character' below to start playing!")
        await interaction.response.edit_message(embed=embed, view=ClassBrowseView(cls))


class ClassBrowseView(discord.ui.View):
    def __init__(self, selected_class: str | None = None):
        super().__init__(timeout=300)
        self.selected_class = selected_class
        self.add_item(ClassBrowseSelect())
        if selected_class:
            self.create_btn.disabled = False

    @discord.ui.button(label="Create a Character with this Class →", style=discord.ButtonStyle.success, emoji="⚔️", row=1)
    async def create_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_class:
            await interaction.response.send_message("Select a class first!", ephemeral=True)
            return
        # Launch character creation
        name_embed = discord.Embed(
            title="⚔️ Create a New Character",
            description=f"Class: **{self.selected_class}**\n\nStart by giving your character a name!",
            color=0x8B5CF6,
        )
        # We can't easily link into the create flow without a name, so just tell user to use /character create
        await interaction.response.send_message(
            f"Use `/character create YourName` to start and **{self.selected_class}** is ready to be chosen!",
            ephemeral=True,
        )


@classes_group.command(name="browse", description="Browse all available classes like a codex")
async def classes_browse(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Class Codex",
        description="Select a class from the dropdown below to see its full details.\n\n"
                    + "\n".join(f"**{cls}** — {desc}" for cls, desc in CLASS_DESCRIPTIONS.items()),
        color=0x8B5CF6,
    )
    embed.set_footer(text="LoreForge Class Codex")
    await interaction.response.send_message(embed=embed, view=ClassBrowseView(), ephemeral=True)


# ── Split /character edit into cosmetic and stats ────────────────────────────

@character_group.command(name="edit_cosmetic", description="Edit your character's name, backstory, avatar, or proxy (instant)")
async def character_edit_cosmetic(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
        return
    if not char:
        await interaction.response.send_message("Set an active character with `/character use` first.", ephemeral=True)
        return
    await interaction.response.send_modal(CosmeticEditModal(char.id))


@character_group.command(name="edit_stats", description="Request a stat/Gold/XP/HP change (requires GM approval)")
@app_commands.describe(field="Which stat to change", value="New value for the stat")
@app_commands.choices(field=[
    app_commands.Choice(name="Strength", value="strength"),
    app_commands.Choice(name="Dexterity", value="dexterity"),
    app_commands.Choice(name="Constitution", value="constitution"),
    app_commands.Choice(name="Intelligence", value="intelligence"),
    app_commands.Choice(name="Wisdom", value="wisdom"),
    app_commands.Choice(name="Charisma", value="charisma"),
    app_commands.Choice(name="Gold", value="gold"),
    app_commands.Choice(name="XP", value="xp"),
    app_commands.Choice(name="HP Max", value="hp_max"),
])
async def character_edit_stats(interaction: discord.Interaction, field: app_commands.Choice[str], value: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    # Validate value is a positive integer
    try:
        new_value_int = int(value)
        if new_value_int < 0:
            raise ValueError
    except ValueError:
        await interaction.response.send_message(
            "Value must be a positive whole number (e.g. `15`, `250`, `10`).",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
        return
    if not char:
        await interaction.response.send_message(
            "You have multiple characters with no active one — use `/character use` first.",
            ephemeral=True,
        )
        return

    # Get old value
    old_value = str(getattr(char, field.value, "?"))

    # Create PendingApproval record
    async with get_db() as db:
        approval = PendingApproval(
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
            character_id=char.id,
            character_name=char.name,
            field_name=field.value,
            old_value=old_value,
            new_value=str(new_value_int),
            status="pending",
        )
        db.add(approval)
        await db.flush()
        approval_id = approval.id

    # Try to notify GM channel
    gm_channel = None
    try:
        async with get_db() as db:
            result = await db.execute(
                select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
            )
            config = result.scalar_one_or_none()
            if config and config.gm_channel_id:
                gm_channel = interaction.guild.get_channel(config.gm_channel_id)
    except Exception:
        pass

    if gm_channel:
        gm_embed = discord.Embed(
            title="📋 Stat Change Request",
            color=0xF59E0B,
        )
        gm_embed.add_field(name="Character", value=char.name, inline=True)
        gm_embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        gm_embed.add_field(name="Field", value=field.name, inline=True)
        gm_embed.add_field(name="Change", value=f"`{old_value}` → `{new_value_int}`", inline=True)
        gm_embed.add_field(name="Request ID", value=f"`#{approval_id}`", inline=True)
        gm_embed.set_footer(text=f"Use /gm approve {approval_id} or /gm deny {approval_id}")
        try:
            await gm_channel.send(embed=gm_embed)
        except Exception:
            pass

    await interaction.response.send_message(
        f"Your request to change **{field.name}** from `{old_value}` to `{new_value_int}` has been submitted. "
        "A GM will review it.",
        ephemeral=True,
    )


# ── Level-Up Attack Unlock ────────────────────────────────────────────────────

def _locked_attacks(char_class: str, unlocked: list[str]) -> list[dict]:
    """Return attacks the character has NOT yet unlocked."""
    all_attacks = STARTER_ATTACKS.get(char_class, [])
    return [a for a in all_attacks if a["name"] not in unlocked]


async def _offer_attack_unlock(bot: commands.Bot, char: Character, new_level: int):
    """
    Send a DM to the character's owner offering to unlock a new attack.
    Called when a character levels up. Only works for standard DnD classes.
    """
    char_class = char.char_class
    if char_class not in STARTER_ATTACKS:
        return

    unlocked = (char.class_resources or {}).get("attacks", [])
    locked = _locked_attacks(char_class, unlocked)
    if not locked:
        # All attacks already unlocked — nothing to offer
        return

    user = bot.get_user(char.user_id)
    if not user:
        try:
            user = await bot.fetch_user(char.user_id)
        except Exception:
            return

    # Only offer one attack per level-up
    view = LevelUpAttackView(char_class, char.id, unlocked, locked)
    embed = discord.Embed(
        title=f"🎉 Level {new_level} — New Ability Unlock!",
        description=(
            f"**{char.name}** has reached **Level {new_level}** and can unlock a new ability.\n\n"
            f"Pick **one** attack from the list below to add to your arsenal.\n"
            f"You currently have {len(unlocked)}/{len(unlocked) + len(locked)} attacks unlocked."
        ),
        color=0xA855F7,
    )
    for atk in locked:
        tags = []
        if atk.get("is_spell"):
            tags.append("✨ spell")
        if atk.get("is_defend"):
            tags.append("🛡️ def")
        if atk.get("is_heal"):
            tags.append("💚 heal")
        if atk.get("is_special"):
            tags.append("⚡ special")
        tag_str = f"  *[{', '.join(tags)}]*" if tags else ""
        embed.add_field(
            name=f"• {atk['name']}{tag_str}",
            value=atk.get("desc", atk["flavor"]),
            inline=False,
        )
    embed.set_footer(text="You'll unlock more abilities at future levels too!")

    try:
        dm = await user.create_dm()
        await dm.send(embed=embed, view=view)
    except discord.Forbidden:
        pass


class LevelUpAttackSelect(discord.ui.Select):
    def __init__(self, char_class: str, char_id: int, unlocked: list[str], locked: list[dict]):
        self.char_class = char_class
        self.char_id = char_id
        self.unlocked = unlocked
        self.locked = locked
        options = [
            discord.SelectOption(
                label=atk["name"],
                value=atk["name"],
                description=atk["flavor"][:100],
            )
            for atk in locked
        ]
        super().__init__(placeholder="Choose an ability to unlock...", options=options)

    async def callback(self, interaction: discord.Interaction):
        chosen = self.values[0]
        # Update character's class_resources
        async with get_db() as db:
            result = await db.execute(select(Character).where(Character.id == self.char_id))
            char = result.scalar_one_or_none()
            if not char:
                await interaction.response.send_message("Character not found.", ephemeral=True)
                return
            resources = dict(char.class_resources or {})
            attacks = list(resources.get("attacks", []))
            if chosen not in attacks:
                attacks.append(chosen)
            resources["attacks"] = attacks
            char.class_resources = resources

        embed = discord.Embed(
            title="✅ Ability Unlocked!",
            description=f"**{chosen}** has been added to **{interaction.user.display_name}**'s arsenal!",
            color=0x22C55E,
        )
        # Updated attack count
        new_unlocked = self.unlocked + [chosen]
        remaining = len(self.locked) - 1
        if remaining > 0:
            embed.set_footer(text=f"{remaining} more ability/ies to unlock at future levels!")
        else:
            embed.set_footer(text="All abilities unlocked! 🎉")

        await interaction.response.edit_message(embed=embed, view=None)
        self.view.stop()


class LevelUpAttackView(discord.ui.View):
    def __init__(self, char_class: str, char_id: int, unlocked: list[str], locked: list[dict]):
        super().__init__(timeout=86400)  # 24h timeout
        self.add_item(LevelUpAttackSelect(char_class, char_id, unlocked, locked))

    @discord.ui.button(label="Skip for now", style=discord.ButtonStyle.secondary, emoji="⏭️", row=1)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⏭️ Skipped",
            description="You can unlock abilities later through other means.",
            color=0x6B7280,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


# ── Cog ───────────────────────────────────────────────────────────────────────

class CharacterCog(commands.Cog, name="Character"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(character_group)
        bot.tree.add_command(classes_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("character")
        self.bot.tree.remove_command("classes")


async def setup(bot):
    await bot.add_cog(CharacterCog(bot))
