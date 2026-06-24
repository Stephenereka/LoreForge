import math

XP_THRESHOLDS = [0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
                 85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000]

HIT_DICE = {
    "Fighter": 10, "Barbarian": 12, "Rogue": 8,
    "Cleric": 8, "Wizard": 6, "Warlock": 8,
}

# ── Expanded Class Features: every class has meaningful unlocks at key levels 1-20 ──

CLASS_FEATURES: dict[str, dict[int, str]] = {
    # ─── FIGHTER ───────────────────────────────────────────────────────────────
    "Fighter": {
        1:  "Fighting Style & Second Wind — bonus action heal 1d10+level HP once per short rest",
        2:  "Action Surge — take one extra action once per short rest",
        3:  "Martial Archetype — choose Champion, Battle Master, or Eldritch Knight path",
        5:  "Extra Attack — attack twice per turn",
        7:  "Martial Versatility — swap a fighting style after a long rest; +1 maneuver die",
        9:  "Indomitable — reroll a failed saving throw once per long rest",
        11: "Triple Attack — attack three times per turn",
        13: "Indomitable x2 — two rerolls per long rest",
        15: "Superior Critical — critical hit on a roll of 18-20",
        17: "Action Surge x2 — two extra-action surges per short rest",
        18: "Survivor — regenerate HP each turn if below half health (CON mod per round)",
        20: "Extra Attack (4) — attack four times per turn; +1 Action Surge use",
    },
    # ─── ROGUE ─────────────────────────────────────────────────────────────────
    "Rogue": {
        1:  "Sneak Attack (1d6) & Thieves' Cant — +1d6 damage on advantage or ally-adjacent attacks",
        2:  "Cunning Action — Dash, Disengage, or Hide as a bonus action",
        3:  "Arcane Trickster or Thief Archetype — unlock specialty abilities",
        5:  "Uncanny Dodge — reaction to halve one attack's damage once per round",
        7:  "Evasion — take no damage from AoE effects on successful DEX save (half on fail)",
        9:  "Sneak Attack (3d6) — upgraded to 3d6; +10 movement speed",
        11: "Reliable Talent — treat any d20 roll of 9 or lower as a 10 on skill checks you're proficient in",
        13: "Sneak Attack (4d6) — upgraded to 4d6; Blindsense — detect hidden foes within 10ft",
        15: "Slippery Mind — proficiency in WIS and CHA saving throws",
        17: "Sneak Attack (5d6) — upgraded to 5d6; +1 Cunning Action use per round",
        18: "Elusive — no attack roll has advantage against you",
        19: "Stroke of Luck — turn a failed attack into a hit or a missed save into a success (once/rest)",
        20: "Sneak Attack (6d6) — upgraded to 6d6; can apply Sneak Attack twice per round",
    },
    # ─── CLERIC ────────────────────────────────────────────────────────────────
    "Cleric": {
        1:  "Divine Domain — choose a domain (Life, Light, War, etc.) granting bonus spells and abilities",
        2:  "Channel Divinity (1/rest) — Turn Undead or domain-specific power; +1 use at level 6",
        3:  "Domain Spells — unlock two additional domain spell slots per long rest",
        5:  "Destroy Undead (CR 1/2) — Turn Undead now destroys weak undead on a failed save",
        7:  "Divine Strike — weapon attacks deal +1d8 radiant damage once per turn",
        9:  "Greater Healing — all healing spells heal +2 HP per die rolled",
        11: "Destroy Undead (CR 2) — upgraded Turn Undead annihilates stronger undead",
        13: "Blessed Strikes — Divine Strike applies to all attacks; +1d8 radiant on cantrips too",
        15: "Improved Channel Divinity — Channel Divinity has 3 uses per rest; DC +2",
        17: "Destroy Undead (CR 4) — Turn Undead consumes even powerful undead",
        18: "Supreme Healing — heal spells restore max HP instead of rolling",
        20: "Divine Intervention — once per week, call upon your deity for a miracle that always succeeds",
    },
    # ─── WIZARD ────────────────────────────────────────────────────────────────
    "Wizard": {
        1:  "Arcane Recovery — regain half your wizard level in spell slots (rounded up) once per day",
        2:  "Arcane Tradition — choose Evocation, Abjuration, or Necromancy school",
        3:  "Cantrip Mastery — cantrips deal +INT modifier damage; learn one extra cantrip",
        5:  "Spell Slots (3rd level) — unlock 3rd-level spells and an additional learned spell slot",
        7:  "School Specialization — reduced cost for your chosen school's spells; enhanced effects",
        9:  "Spell Slots (5th level) — unlock 5th-level spells; Arcane Recovery restores 1 extra slot",
        11: "Empowered Cantrips — cantrips deal an extra die of damage (e.g., 3d10 → 4d10 Fire Bolt)",
        13: "Spell Slots (7th level) — unlock 7th-level spells; +1 prepared spell per day",
        15: "Spell Resistance — advantage on saving throws against magic",
        17: "Spell Slots (9th level) — unlock 9th-level spells (the ultimate arcane secrets)",
        18: "Spell Mastery — choose a 1st and 2nd level spell; cast them at will without slots",
        20: "Signature Spell — choose a 3rd-level spell; cast it once per short rest without expending a slot; auto-empower one spell per day",
    },
    # ─── BARBARIAN ─────────────────────────────────────────────────────────────
    "Barbarian": {
        1:  "Rage (2 rages/rest) — +2 melee damage, resistance to bludgeoning/piercing/slashing, advantage on STR checks",
        2:  "Reckless Attack — advantage on melee attacks; attackers get advantage against you",
        3:  "Primal Path — choose Berserker, Totem Warrior, or Zealot path",
        5:  "Extra Attack + Fast Movement — attack twice per turn; +10ft movement speed",
        7:  "Feral Instinct — advantage on initiative rolls; cannot be surprised while raging",
        9:  "Brutal Critical — add one extra weapon damage die on critical hits",
        11: "Relentless Rage — survive dropping to 0 HP once per rage; CON save (DC 10) to stay up",
        13: "Brutal Critical (2 dice) — add two extra weapon damage dice on crits",
        15: "Persistent Rage — rage lasts until you choose to end it (not from damage or combat end)",
        17: "Primal Champion — STR and CON scores increase by 4 (cap 24); +2 rage damage bonus",
        18: "Indomitable Might — minimum STR check result equals your STR score",
        19: "Rage (unlimited) — unlimited rages per long rest; can rage even while surprised",
        20: "Primal Champion (capstone) — +4 to STR and CON (max 24); infinite rages; Brutal Critical (3 dice)",
    },
    # ─── WARLOCK ───────────────────────────────────────────────────────────────
    "Warlock": {
        1:  "Pact Magic (1 slot) — 1 spell slot recovered on short rest; Eldritch Blast deals CHA-mod bonus damage",
        2:  "Eldritch Invocations — choose 2 invocations (e.g., Agonizing Blast, Devil's Sight, Repelling Blast)",
        3:  "Pact Boon — choose Pact of the Chain, Tome, or Blade; +1 invocation; 2nd-level spells",
        5:  "Pact Magic (3rd-level slots) — 2 slots at 3rd-level; +1 invocation",
        7:  "Pact Boon Upgrade — familiar gains invisibility and voice (Chain); Book of Ancient Secrets (Tome); +2 pact weapon (Blade)",
        9:  "Pact Magic (5th-level slots) — 2 slots at 5th-level; +1 invocation; Mystic Arcanum (6th-level spell 1/day)",
        11: "Mystic Arcanum (7th-level spell) — cast a 7th-level spell once per long rest without a slot",
        13: "Mystic Arcanum (8th-level spell) — cast an 8th-level spell once per long rest",
        15: "Pact Magic (3 slots) — gain a third pact magic slot; +1 invocation",
        17: "Mystic Arcanum (9th-level spell) — cast a 9th-level spell once per long rest; Eldritch Blast fires 4 beams",
        18: "Eternal Servitude — once per day, if you would drop to 0 HP, your patron intervenes; regain 50 HP instead",
        19: "Invocation Mastery — learn one additional invocation; all invocations are always active regardless of prerequisites",
        20: "Eldritch Master — regain all pact magic slots once per short rest; can use two Mystic Arcanum per long rest",
    },
}

ASI_LEVELS: set[int] = {4, 8, 12, 16, 19}


def xp_to_reach(level: int) -> int:
    """Total XP needed to reach `level`. Level 1 = 0 XP."""
    if level <= 1:
        return 0
    if level >= len(XP_THRESHOLDS):
        return XP_THRESHOLDS[-1]
    return XP_THRESHOLDS[level - 1]


def xp_for_next_level(current_level: int) -> int:
    """Total XP needed to level up from current_level."""
    return xp_to_reach(current_level + 1)


def check_level_up(current_xp: int, current_level: int) -> int | None:
    """Return new level if XP qualifies for a level-up, else None."""
    if current_level >= 20:
        return None
    if current_xp >= xp_for_next_level(current_level):
        return current_level + 1
    return None


def hp_gain_on_level(char_class: str, con_score: int) -> int:
    """HP gained when levelling up (average roll + CON mod, min 1)."""
    hit_die = HIT_DICE.get(char_class, 8)
    avg_roll = math.ceil(hit_die / 2) + 1
    return max(1, avg_roll + math.floor((con_score - 10) / 2))


def proficiency_bonus(level: int) -> int:
    return math.ceil(level / 4) + 1


def feature_at_level(char_class: str, level: int) -> str | None:
    return CLASS_FEATURES.get(char_class, {}).get(level)


def pvp_xp_reward(loser_level: int, winner_count: int) -> int:
    """XP each winner earns after defeating a player in PvP."""
    return (loser_level * 50) // max(winner_count, 1)


def xp_bar(current_xp: int, current_level: int, bar_width: int = 10) -> str:
    """Return a text XP progress bar string."""
    if current_level >= 20:
        return f"XP `{current_xp}` — **MAX LEVEL**"
    needed = xp_for_next_level(current_level)
    start = xp_to_reach(current_level)
    progress = current_xp - start
    span = needed - start
    pct = min(progress / span, 1.0) if span > 0 else 1.0
    filled = round(pct * bar_width)
    bar = "▓" * filled + "░" * (bar_width - filled)
    return f"XP `{current_xp}/{needed}` {bar} → Lv{current_level + 1}"
