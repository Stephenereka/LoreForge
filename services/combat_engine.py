import random
import math
from dataclasses import dataclass, field
from typing import Optional

# ── Dice ─────────────────────────────────────────────────────────────────────

def roll(sides: int) -> int:
    return random.randint(1, sides)

def roll_adv(sides: int) -> int:
    return max(roll(sides), roll(sides))

def roll_dis(sides: int) -> int:
    return min(roll(sides), roll(sides))

def roll_dice(count: int, sides: int) -> list[int]:
    return [roll(sides) for _ in range(count)]

def modifier(score: int) -> int:
    return math.floor((score - 10) / 2)

def proficiency_bonus(level: int) -> int:
    return math.ceil(level / 4) + 1

# ── Combatant ─────────────────────────────────────────────────────────────────

@dataclass
class Combatant:
    """Lightweight snapshot of a fighter for one combat session."""
    id: str                     # user_id str or "enemy:<name>"
    name: str
    is_player: bool

    level: int
    char_class: str

    hp_max: int
    hp_current: int
    weapon: str = "unarmed"
    hp_temp: int = 0

    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    armor_class: int = 10
    is_dead: bool = False
    is_unconscious: bool = False
    death_saves_success: int = 0
    death_saves_failure: int = 0

    conditions: list = field(default_factory=list)
    class_resources: dict = field(default_factory=dict)

    initiative: int = 0         # set during roll_initiative

    @property
    def is_alive(self) -> bool:
        return not self.is_dead and not self.is_unconscious

    @property
    def effective_hp(self) -> int:
        return self.hp_current + self.hp_temp

    def take_damage(self, amount: int) -> str:
        """Apply damage, absorb temp HP first. Returns a status string."""
        absorbed = min(self.hp_temp, amount)
        self.hp_temp -= absorbed
        remaining = amount - absorbed
        self.hp_current = max(0, self.hp_current - remaining)

        if self.hp_current == 0:
            self.is_unconscious = True
            return "unconscious"
        return "alive"

    def heal(self, amount: int) -> int:
        healed = min(amount, self.hp_max - self.hp_current)
        self.hp_current += healed
        if self.is_unconscious and self.hp_current > 0:
            self.is_unconscious = False
            self.death_saves_success = 0
            self.death_saves_failure = 0
        return healed

    def death_save(self) -> dict:
        """Roll a death saving throw. Returns result info."""
        result = roll(20)
        if result == 20:
            self.heal(1)
            return {"roll": result, "outcome": "critical_success", "stable": True}
        elif result == 1:
            self.death_saves_failure += 2
        elif result >= 10:
            self.death_saves_success += 1
        else:
            self.death_saves_failure += 1

        if self.death_saves_success >= 3:
            self.is_unconscious = False
            self.death_saves_success = 0
            self.death_saves_failure = 0
            return {"roll": result, "outcome": "stabilized", "stable": True}
        elif self.death_saves_failure >= 3:
            self.is_dead = True
            self.is_unconscious = False
            return {"roll": result, "outcome": "dead", "stable": False}

        return {
            "roll": result,
            "outcome": "success" if result >= 10 else "failure",
            "successes": self.death_saves_success,
            "failures": self.death_saves_failure,
            "stable": False,
        }


# ── Enemy templates ───────────────────────────────────────────────────────────

ENEMIES: dict[str, dict] = {
    "goblin": {
        "name": "Goblin",
        "hp": 7, "ac": 13, "level": 1,
        "str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8,
        "attack_name": "Scimitar",
        "attack_bonus": 4, "damage_dice": (1, 6), "damage_bonus": 2,
        "xp": 50,
    },
    "skeleton": {
        "name": "Skeleton",
        "hp": 13, "ac": 13, "level": 1,
        "str": 10, "dex": 14, "con": 15, "int": 6, "wis": 8, "cha": 5,
        "attack_name": "Shortsword",
        "attack_bonus": 4, "damage_dice": (1, 6), "damage_bonus": 2,
        "xp": 50,
    },
    "wolf": {
        "name": "Wolf",
        "hp": 11, "ac": 13, "level": 1,
        "str": 12, "dex": 15, "con": 12, "int": 3, "wis": 12, "cha": 6,
        "attack_name": "Bite",
        "attack_bonus": 4, "damage_dice": (2, 4), "damage_bonus": 2,
        "xp": 50,
    },
    "bandit": {
        "name": "Bandit",
        "hp": 11, "ac": 12, "level": 1,
        "str": 11, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10,
        "attack_name": "Scimitar",
        "attack_bonus": 3, "damage_dice": (1, 6), "damage_bonus": 1,
        "xp": 25,
    },
    "orc": {
        "name": "Orc",
        "hp": 15, "ac": 13, "level": 2,
        "str": 16, "dex": 12, "con": 16, "int": 7, "wis": 11, "cha": 10,
        "attack_name": "Greataxe",
        "attack_bonus": 5, "damage_dice": (1, 12), "damage_bonus": 3,
        "xp": 100,
    },
    "troll": {
        "name": "Troll",
        "hp": 84, "ac": 15, "level": 5,
        "str": 18, "dex": 13, "con": 20, "int": 7, "wis": 9, "cha": 7,
        "attack_name": "Claws",
        "attack_bonus": 7, "damage_dice": (2, 6), "damage_bonus": 4,
        "xp": 700,
    },
}

def make_enemy(enemy_key: str) -> Combatant:
    t = ENEMIES[enemy_key]
    return Combatant(
        id=f"enemy:{enemy_key}",
        name=t["name"],
        is_player=False,
        level=t["level"],
        char_class="enemy",
        hp_max=t["hp"],
        hp_current=t["hp"],
        armor_class=t["ac"],
        strength=t["str"],
        dexterity=t["dex"],
        constitution=t["con"],
        intelligence=t["int"],
        wisdom=t["wis"],
        charisma=t["cha"],
    )

def enemy_xp(enemy_key: str) -> int:
    return ENEMIES.get(enemy_key, {}).get("xp", 0)

def enemy_attack(enemy_key: str) -> dict:
    t = ENEMIES[enemy_key]
    attack_roll = roll(20)
    is_crit = attack_roll == 20
    dice_count, dice_sides = t["damage_dice"]
    dmg_rolls = roll_dice(dice_count * (2 if is_crit else 1), dice_sides)
    damage = max(1, sum(dmg_rolls) + t["damage_bonus"])
    return {
        "attack_name": t["attack_name"],
        "attack_roll": attack_roll + t["attack_bonus"],
        "raw_roll": attack_roll,
        "is_crit": is_crit,
        "is_miss": attack_roll == 1,
        "damage": damage,
        "dmg_rolls": dmg_rolls,
        "attack_bonus": t["attack_bonus"],
        "damage_bonus": t["damage_bonus"],
    }

# ── Starter weapons & attacks per class ──────────────────────────────────────

STARTER_WEAPONS: dict[str, str] = {
    "Fighter":   "longsword",
    "Rogue":     "dagger",
    "Wizard":    "quarterstaff",
    "Barbarian": "greataxe",
    "Cleric":    "mace",
    "Warlock":   "unarmed",
    "Heavenly Demon Heir": "longsword",
}

STARTER_ATTACKS: dict[str, list[dict]] = {
    "Fighter": [
        {"name": "Power Strike",  "flavor": "drives their weapon forward with full force",   "stat": "str", "damage_bonus": 2, "desc": "A heavy, two-handed blow that deals extra damage from raw strength."},
        {"name": "Shield Bash",   "flavor": "slams their shield into the enemy",             "stat": "str", "damage_bonus": 0, "desc": "Bash with your shield to deal damage and potentially stun the target if they fail a CON save."},
        {"name": "Parry",         "flavor": "deflects the incoming blow with precision",     "stat": "str", "is_defend": True, "desc": "Raise your guard and gain +2 AC until your next turn, deflecting incoming attacks."},
        {"name": "Riposte",       "flavor": "counters after a successful parry",             "stat": "str", "damage_bonus": 1, "desc": "After parrying, you follow up with a sharp counter-strike. Only usable after Parry."},
        {"name": "Cleave",        "flavor": "sweeps their weapon in a wide arc",             "stat": "str", "damage_bonus": 0, "desc": "A wide, sweeping attack that hits all adjacent enemies. Deals half damage to secondary targets."},
        {"name": "Taunting Strike","flavor": "lands a precise hit while baiting the enemy",  "stat": "str", "damage_bonus": 1, "desc": "A precise strike that deals damage and forces the target into a WIS save or be Taunted on you."},
    ],
    "Rogue": [
        {"name": "Sneak Stab",    "flavor": "darts in from the shadows for a precise strike","stat": "dex", "sneak": True, "desc": "A precise dagger strike from the shadows that applies Bleeding for 2 rounds. Deals bonus Sneak Attack dice."},
        {"name": "Smoke Feint",   "flavor": "feints left and strikes right",                 "stat": "dex", "damage_bonus": 1, "desc": "A feinting maneuver that deals modest damage and Blinds the target for 1 round."},
        {"name": "Pickpocket",    "flavor": "attempts to snatch something from the enemy",   "stat": "dex", "is_special": True, "desc": "A contested Sleight of Hand check. On success, steal 10-15 gold from the target."},
        {"name": "Shadow Step",   "flavor": "vanishes into shadow and reappears",            "stat": "dex", "is_defend": True, "desc": "Melt into shadows and gain the Hidden condition. Next attack has advantage."},
        {"name": "Poison Blade",  "flavor": "coats their blade with a quick-acting poison",  "stat": "dex", "damage_bonus": 0, "desc": "A coated blade that deals normal damage plus 1d4 poison, and Poisons the target for 2 rounds."},
        {"name": "Caltrops",      "flavor": "scatters caltrops behind them as they move",    "stat": "dex", "is_special": True, "desc": "Scatter caltrops in your wake. The next enemy that targets you must pass a DEX save or take 1d4 piercing damage and be Slowed."},
    ],
    "Wizard": [
        {"name": "Magic Missile", "flavor": "launches three darts of magical force",         "stat": "int", "damage_dice": (3, 4), "is_spell": True, "desc": "Three homing darts of force — always hits. Deals 3*(1d4+1) total force damage, no save or roll."},
        {"name": "Fire Bolt",     "flavor": "hurls a mote of searing fire",                 "stat": "int", "damage_dice": (1, 10), "is_spell": True, "desc": "A ranged fire attack that deals 1d10 fire damage and applies Burning for 1 round."},
        {"name": "Shield",        "flavor": "raises a glimmering magical barrier",           "stat": "int", "is_defend": True, "is_spell": True, "desc": "Conjure a magical barrier that grants +5 AC until your next turn."},
        {"name": "Ray of Frost",  "flavor": "unleashes a beam of freezing cold energy",     "stat": "int", "damage_dice": (1, 8), "is_spell": True, "desc": "A beam of freezing energy that deals 1d8 cold damage and Slows the target for 1 round."},
        {"name": "Mage Hand",     "flavor": "commands a spectral hand to interact",          "stat": "int", "is_special": True, "is_spell": True, "desc": "A spectral hand that can manipulate objects, distract enemies, or trigger traps from a distance."},
        {"name": "Thunderclap",   "flavor": "slams their staff, unleashing a shockwave",    "stat": "int", "damage_dice": (1, 6), "is_spell": True, "desc": "A thunderous shockwave that hits all adjacent enemies for 1d6 damage and pushes them back. Deafening boom."},
    ],
    "Barbarian": [
        {"name": "Reckless Swing","flavor": "attacks with wild, furious abandon",            "stat": "str", "damage_bonus": 3, "desc": "A wild attack made with advantage, dealing +3 extra damage. Reduces your AC by 2 until next turn."},
        {"name": "Rage Charge",   "flavor": "charges with terrifying berserk speed",         "stat": "str", "damage_bonus": 2, "desc": "Charge forward and deal +2 damage. Target must pass a STR save or be knocked Prone."},
        {"name": "Intimidate",    "flavor": "unleashes a battle cry to unsettle the foe",   "stat": "str", "is_special": True, "desc": "A terrifying roar that contests CHA vs WIS. On success, Frightens the target for 2 rounds."},
        {"name": "Skull Splitter","flavor": "brings their weapon down with crushing force",  "stat": "str", "damage_bonus": 4, "desc": "An overhead crushing blow dealing +4 damage. On a crit, the target is also Stunned for 1 round."},
        {"name": "Frenzied Strike","flavor": "enters a frenzy, attacking multiple times",    "stat": "str", "damage_bonus": 0, "desc": "Attack twice in a single turn, but each attack deals slightly less damage. Usable only while Raging."},
        {"name": "Shatter Armor", "flavor": "aims for the enemy's defenses",                 "stat": "str", "damage_bonus": 1, "desc": "A targeted strike that deals damage and reduces the target's AC by 1 for the rest of combat."},
    ],
    "Cleric": [
        {"name": "Smite",         "flavor": "channels divine wrath into their strike",       "stat": "wis", "damage_bonus": 2, "is_spell": True, "desc": "Channel divine energy into your weapon, dealing +2 radiant damage (bonus vs undead)."},
        {"name": "Heal",          "flavor": "calls on divine power to mend wounds",          "stat": "wis", "is_heal": True, "is_spell": True, "desc": "Heal yourself for 2d6 + WIS modifier. A staple for keeping yourself in the fight."},
        {"name": "Turn Undead",   "flavor": "raises their holy symbol with divine force",    "stat": "wis", "is_special": True, "is_spell": True, "desc": "Raise your holy symbol — undead targets must pass a WIS save or be Frightened for 2 rounds."},
        {"name": "Guiding Bolt",  "flavor": "calls down a flash of divine radiance",         "stat": "wis", "damage_dice": (4, 6), "is_spell": True, "desc": "A flash of radiant light that deals 4d6 damage and Blinds the target for 1 round."},
        {"name": "Bless",         "flavor": "bestows a divine blessing on an ally",          "stat": "wis", "is_special": True, "is_spell": True, "desc": "Bless yourself or an ally — they gain +1d4 on all attack rolls and saving throws for 3 rounds."},
        {"name": "Sacred Flame",  "flavor": "calls down a column of pure radiance",          "stat": "wis", "damage_dice": (1, 8), "is_spell": True, "desc": "A column of radiant flame that ignores cover. Target must pass a DEX save or take 1d8 radiant damage."},
    ],
    "Warlock": [
        {"name": "Eldritch Blast","flavor": "fires a beam of crackling dark energy",         "stat": "cha", "damage_dice": (1, 10), "is_spell": True, "desc": "Your signature cantrip — a beam of force dealing 1d10 + CHA damage. Also pushes the target back on a failed STR save."},
        {"name": "Hex",           "flavor": "places a dark curse on the target",             "stat": "cha", "is_special": True, "is_spell": True, "desc": "Curse a target for 3 rounds — all your attacks against them deal an extra 1d6 necrotic damage."},
        {"name": "Drain",         "flavor": "siphons life force from the target",            "stat": "cha", "damage_dice": (1, 8), "is_spell": True, "self_heal": True, "desc": "A ranged attack dealing 1d8 necrotic damage. You heal for half the damage dealt."},
        {"name": "Hellish Rebuke","flavor": "wraps themselves in hellfire, punishing attackers", "stat": "cha", "is_special": True, "is_spell": True, "desc": "Wreathe yourself in hellfire. The next enemy that hits you takes 2d10 fire damage and begins Burning."},
        {"name": "Darkness",      "flavor": "shrouds an area in magical darkness",           "stat": "cha", "is_special": True, "is_spell": True, "desc": "Create a 15-foot sphere of magical darkness. Enemies inside are Blinded, and you gain advantage on attacks against them."},
        {"name": "Armor of Agathys","flavor": "wraps themselves in frost",                   "stat": "cha", "is_defend": True, "is_spell": True, "desc": "Cover yourself in frosty armor. Gain +2 AC and deal 1d8 cold damage to any enemy that hits you in melee."},
    ],
    "Heavenly Demon Heir": [
        {"name": "Demonic Strike",  "flavor": "accelerates their blade into a second cut in the same motion",  "stat": "dex", "damage_bonus": 1, "desc": "After hitting, immediately make one additional attack against the same target. +1d6 damage. Costs 1 Tao."},
        {"name": "Shadow Step",     "flavor": "explodes forward in a blur of motion",                          "stat": "dex", "damage_bonus": 0, "desc": "Release Tao beneath your feet to teleport up to 15 ft before striking. Costs 1 Tao."},
        {"name": "Phantom Cut",     "flavor": "slips the blade through gaps in the enemy's guard",             "stat": "dex", "damage_bonus": 1, "desc": "Ignore half the target's AC. +1d6 damage. Costs 1 Tao."},
        {"name": "Demonic Fang",    "flavor": "drives Tao directly into the blade's impact point",             "stat": "dex", "damage_bonus": 2, "desc": "A single devastating strike. +1d8 damage. Costs 2 Tao."},
        {"name": "Sword Flight",    "flavor": "channels Tao into the blade and rides it through the air",      "stat": "dex", "is_defend": True, "desc": "Infuse a blade with Tao to gain flying speed equal to walking speed for 1 minute. Level 2+."},
        {"name": "Demonic Ward",    "flavor": "circles the blade defensively in front of their body",          "stat": "dex", "is_defend": True, "desc": "Enter a defensive posture. Gain +2 AC until your next turn. Your Nano System anticipates incoming attacks."},
    ],
}

# ── Player attack resolution ──────────────────────────────────────────────────

WEAPON_DAMAGE: dict[str, tuple[int, int]] = {
    "unarmed":    (1, 4),
    "dagger":     (1, 4),
    "shortsword": (1, 6),
    "longsword":  (1, 8),
    "greataxe":   (1, 12),
    "greatsword": (2, 6),
    "handaxe":    (1, 6),
    "mace":       (1, 6),
    "quarterstaff":(1, 6),
    "demonic_gauntlet": (1, 10),
}

CLASS_ATTACK_STAT = {
    "Fighter":   "str",
    "Barbarian": "str",
    "Rogue":     "dex",
    "Cleric":    "wis",
    "Wizard":    "int",
    "Warlock":   "cha",
    "Heavenly Demon Heir": "dex",
}

def _stat(combatant: Combatant, stat: str) -> int:
    return getattr(combatant, {"str": "strength", "dex": "dexterity", "con": "constitution",
                                "int": "intelligence", "wis": "wisdom", "cha": "charisma"}[stat])

def player_attack(attacker: Combatant, weapon: str = "unarmed") -> dict:
    pb = proficiency_bonus(attacker.level)
    stat_key = CLASS_ATTACK_STAT.get(attacker.char_class, "str")
    stat_mod = modifier(_stat(attacker, stat_key))

    attack_roll = roll(20)
    is_crit = attack_roll == 20
    is_miss = attack_roll == 1
    total_attack = attack_roll + stat_mod + pb

    dice_count, dice_sides = WEAPON_DAMAGE.get(weapon, (1, 4))
    dmg_rolls = roll_dice(dice_count * (2 if is_crit else 1), dice_sides)
    damage = max(1, sum(dmg_rolls) + stat_mod)

    # Sneak Attack for Rogue (needs advantage OR adjacent ally — simplified: always applies in 1v1)
    sneak_dice = 0
    if attacker.char_class == "Rogue" and not is_miss:
        sneak_dice = math.ceil(attacker.level / 2)
        sneak_rolls = roll_dice(sneak_dice, 6)
        damage += sum(sneak_rolls)

    return {
        "attack_roll": total_attack,
        "raw_roll": attack_roll,
        "is_crit": is_crit,
        "is_miss": is_miss,
        "damage": damage,
        "dmg_rolls": dmg_rolls,
        "stat_mod": stat_mod,
        "pb": pb,
        "sneak_dice": sneak_dice,
        "weapon": weapon,
    }

def player_defend(defender: Combatant) -> dict:
    """Dodge action — roll CON save, gain temp HP on success."""
    con_mod = modifier(defender.constitution)
    pb = proficiency_bonus(defender.level)
    save_roll = roll(20)
    dc = 13
    success = (save_roll + con_mod + pb) >= dc
    temp_hp = 0
    if success:
        temp_hp = roll(6) + con_mod
        temp_hp = max(1, temp_hp)
        defender.hp_temp = max(defender.hp_temp, temp_hp)
    return {
        "roll": save_roll,
        "total": save_roll + con_mod + pb,
        "dc": dc,
        "success": success,
        "temp_hp": temp_hp,
    }

# ── Initiative ────────────────────────────────────────────────────────────────

def roll_initiative(combatants: list[Combatant]) -> list[Combatant]:
    for c in combatants:
        c.initiative = roll(20) + modifier(c.dexterity)
    return sorted(combatants, key=lambda c: c.initiative, reverse=True)


# ── Conditions ────────────────────────────────────────────────────────────────

CONDITIONS: dict[str, dict] = {
    "poisoned":   {"icon": "🤢", "dot_damage": (1, 4), "dot_type": "poison",   "attack_penalty": True},
    "burning":    {"icon": "🔥", "dot_damage": (1, 6), "dot_type": "fire"},
    "bleeding":   {"icon": "🩸", "dot_damage": (1, 4), "dot_type": "slashing"},
    "stunned":    {"icon": "⭐", "skip_turn": True,    "attackers_advantage": True},
    "blinded":    {"icon": "🫥", "attack_disadvantage": True, "defense_disadvantage": True},
    "frightened": {"icon": "😨", "attack_disadvantage": True},
    "hexed":      {"icon": "🔮", "bonus_damage_on_hit": (1, 6), "bonus_type": "necrotic"},
    "prone":      {"icon": "⬇️", "attack_disadvantage": True, "melee_advantage_against": True},
    "parrying":   {"icon": "🛡️", "ac_bonus": 2},
    "shielded":   {"icon": "✨", "ac_bonus": 5},
    "reckless":   {"icon": "🔴", "ac_penalty": 2},
    "raging":     {"icon": "💢", "damage_bonus": 2, "damage_resistance": True},
    "grappled":   {"icon": "🤜", "attack_disadvantage": True},
    "hidden":     {"icon": "👁️", "defense_advantage": True},
    "slowed":     {"icon": "🐌", "attack_penalty": True},
    "blessed":     {"icon": "✨", "bonus_attack_dice": (1, 4)},
    "sanctuary":   {"icon": "🔵", "ac_bonus": 3, "sanctuary_active": True},
    "webbed":      {"icon": "🕸️", "attack_disadvantage": True, "defense_disadvantage": True},
    "guided":      {"icon": "🎯", "next_attack_advantage": True},
    "restrained":   {"icon": "⛓️", "attack_disadvantage": True, "defense_disadvantage": True},
}


def has_condition(combatant: Combatant, name: str) -> bool:
    return any(c["name"] == name for c in (combatant.conditions or []))


def apply_condition(combatant: Combatant, name: str, duration: int):
    if not has_condition(combatant, name):
        combatant.conditions.append({"name": name, "duration": duration})


def remove_condition(combatant: Combatant, name: str):
    combatant.conditions = [c for c in (combatant.conditions or []) if c["name"] != name]


def tick_conditions(combatant: Combatant) -> list[str]:
    """Apply DoT, reduce durations, remove expired. Returns log lines."""
    lines = []
    expired = []
    for cond in list(combatant.conditions or []):
        info = CONDITIONS.get(cond["name"], {})
        if "dot_damage" in info:
            count, sides = info["dot_damage"]
            dmg = sum(roll(sides) for _ in range(count))
            combatant.take_damage(dmg)
            lines.append(f"{info['icon']} **{combatant.name}** takes **{dmg}** {info['dot_type']} damage from {cond['name']}!")
        cond["duration"] -= 1
        if cond["duration"] <= 0:
            expired.append(cond["name"])
    for name in expired:
        remove_condition(combatant, name)
        lines.append(f"✨ **{combatant.name}** is no longer {name}.")
    return lines


def effective_ac(combatant: Combatant) -> int:
    ac = combatant.armor_class
    for cond in (combatant.conditions or []):
        info = CONDITIONS.get(cond["name"], {})
        ac += info.get("ac_bonus", 0)
        ac -= info.get("ac_penalty", 0)
    return ac


def detect_attack_name(text: str, known_attacks: list[str]) -> str | None:
    text_lower = text.lower()
    for attack in known_attacks:
        if attack.lower() in text_lower:
            return attack
    return None


# ── Special action resolvers ─────────────────────────────────────────────────

def resolve_grapple(attacker: Combatant, target: Combatant) -> dict:
    """STR (Athletics) contested vs target STR or DEX. Applies grappled on success."""
    pb = proficiency_bonus(attacker.level)
    atk_roll = roll(20) + modifier(attacker.strength) + pb
    tgt_roll = roll(20) + max(modifier(target.strength), modifier(target.dexterity))
    success = atk_roll > tgt_roll
    if success:
        apply_condition(target, "grappled", 2)
        lines = [
            f"🤜 **{attacker.name}** lunges and grapples **{target.name}**! (Athletics {atk_roll} vs {tgt_roll})",
            f"🔒 **{target.name}** is grappled — disadvantage on attacks for 2 rounds!",
        ]
    else:
        lines = [
            f"🤜 **{attacker.name}** tries to grapple **{target.name}**! (Athletics {atk_roll} vs {tgt_roll})",
            f"💨 **{target.name}** breaks free!",
        ]
    return {"action": "GRAPPLE", "success": success, "log_lines": lines}


def resolve_shove(attacker: Combatant, target: Combatant) -> dict:
    """STR (Athletics) contested vs target STR or DEX. Knocks prone on success."""
    pb = proficiency_bonus(attacker.level)
    atk_roll = roll(20) + modifier(attacker.strength) + pb
    tgt_roll = roll(20) + max(modifier(target.strength), modifier(target.dexterity))
    success = atk_roll > tgt_roll
    if success:
        apply_condition(target, "prone", 1)
        lines = [
            f"💪 **{attacker.name}** shoves **{target.name}**! (Athletics {atk_roll} vs {tgt_roll})",
            f"⬇️ **{target.name}** is knocked prone — attacks against them have advantage!",
        ]
    else:
        lines = [
            f"💪 **{attacker.name}** tries to shove **{target.name}**! (Athletics {atk_roll} vs {tgt_roll})",
            f"🧍 **{target.name}** holds their ground!",
        ]
    return {"action": "SHOVE", "success": success, "log_lines": lines}


def resolve_hide(hider: Combatant) -> dict:
    """DEX (Stealth) check vs DC 14. Applies hidden for 1 round on success."""
    pb = proficiency_bonus(hider.level)
    stealth_roll = roll(20) + modifier(hider.dexterity) + pb
    dc = 14
    success = stealth_roll >= dc
    if success:
        apply_condition(hider, "hidden", 1)
        lines = [
            f"👁️ **{hider.name}** vanishes into the shadows! (Stealth {stealth_roll} vs DC {dc})",
            f"🌑 **{hider.name}** is hidden — next attack has advantage!",
        ]
    else:
        lines = [
            f"👁️ **{hider.name}** tries to hide... (Stealth {stealth_roll} vs DC {dc})",
            f"💡 **{hider.name}** is spotted!",
        ]
    return {"action": "HIDE", "success": success, "log_lines": lines}


def resolve_taunt(taunter: Combatant, target: Combatant) -> dict:
    """CHA (Intimidation) + prof vs target WIS save. Applies frightened on success."""
    pb = proficiency_bonus(taunter.level)
    taunt_roll = roll(20) + modifier(taunter.charisma) + pb
    wis_save = roll(20) + modifier(target.wisdom)
    success = taunt_roll > wis_save
    if success:
        apply_condition(target, "frightened", 2)
        lines = [
            f"😤 **{taunter.name}** taunts **{target.name}**! (Intimidation {taunt_roll} vs WIS save {wis_save})",
            f"😨 **{target.name}** is frightened — disadvantage on attacks for 2 rounds!",
        ]
    else:
        lines = [
            f"😤 **{taunter.name}** tries to taunt **{target.name}**... (Intimidation {taunt_roll} vs WIS save {wis_save})",
            f"😤 **{target.name}** shrugs it off.",
        ]
    return {"action": "TAUNT", "success": success, "log_lines": lines}


# ── Named attack handlers ─────────────────────────────────────────────────────

def _base_result(name: str) -> dict:
    return {
        "attack_name": name, "hit": False, "damage": 0, "crit": False, "miss": False,
        "attack_roll": None, "log_lines": [], "conditions_applied": [],
        "self_conditions": [], "is_heal": False, "heal_amount": 0, "ac_bonus": 0,
    }


def _resolve_hit(raw: int, stat_mod: int, pb: int, target_ac: int, adv: bool = False, dis: bool = False):
    if adv and not dis:
        raw = max(raw, roll(20))
    elif dis and not adv:
        raw = min(raw, roll(20))
    is_crit = raw == 20
    is_miss = raw == 1
    total = raw + stat_mod + pb
    hit = not is_miss and (is_crit or total >= target_ac)
    return raw, total, hit, is_crit, is_miss


# ─── Fighter ──────────────────────────────────────────────────────────────────

def _power_strike(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Power Strike")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.strength)
    dis = has_condition(attacker, "blinded") or has_condition(attacker, "frightened")
    adv = has_condition(target, "stunned") or has_condition(target, "prone")
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target), adv, dis)
    dc, ds = WEAPON_DAMAGE.get(attacker.weapon, (1, 8))
    if crit: dc *= 2
    rolls = roll_dice(dc, ds)
    dmg = max(1, sum(rolls) + sm + 2)
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**CRITICAL HIT!** 🌟" if crit else ("**HIT!**" if hit else ("**NAT 1 — FUMBLE!**" if miss else "**MISS!**"))
    r["log_lines"] = [
        f"⚔️ **{attacker.name}** uses **Power Strike**!",
        f"🎲 d20({raw}) {sm:+} STR  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
        *([ f"💥 {dc}d{ds}({sum(rolls)}) + STR({sm:+}) + Power Strike(+2) = **{dmg} damage**"] if hit else []),
    ]
    return r


def _shield_bash(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Shield Bash")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.strength)
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target))
    bash = roll(4)
    dmg = max(1, bash + sm)
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**")
    lines = [
        f"🛡️ **{attacker.name}** uses **Shield Bash**!",
        f"🎲 d20({raw}) {sm:+} STR  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 1d4({bash}) + STR({sm:+}) = **{dmg} damage**")
        con_save = roll(20) + modifier(target.constitution)
        if con_save < 13:
            apply_condition(target, "stunned", 1)
            r["conditions_applied"].append({"name": "stunned", "duration": 1})
            lines.append(f"⭐ {target.name} fails CON save ({con_save} vs DC 13) — **Stunned** for 1 round!")
        else:
            lines.append(f"{target.name} passes CON save ({con_save}) — not stunned.")
    r["log_lines"] = lines
    return r


def _parry(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Parry")
    apply_condition(attacker, "parrying", 1)
    r["self_conditions"].append({"name": "parrying", "duration": 1})
    r["ac_bonus"] = 2
    r["log_lines"] = [
        f"🛡️ **{attacker.name}** uses **Parry** — bracing to deflect the next blow!",
        f"⬆️ AC {attacker.armor_class} → **{attacker.armor_class + 2}** until next turn.",
    ]
    return r


# ─── Rogue ────────────────────────────────────────────────────────────────────

def _sneak_stab(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Sneak Stab")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.dexterity)
    dis = has_condition(attacker, "blinded")
    adv = has_condition(target, "stunned") or has_condition(target, "blinded")
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target), adv, dis)
    dc, ds = WEAPON_DAMAGE.get(attacker.weapon, (1, 4))
    if crit: dc *= 2
    rolls = roll_dice(dc, ds)
    sneak_n = math.ceil(attacker.level / 2)
    sneak_r = roll_dice(sneak_n * (2 if crit else 1), 6)
    dmg = max(1, sum(rolls) + sm + sum(sneak_r))
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**CRITICAL HIT!** 🌟" if crit else ("**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**"))
    lines = [
        f"🗡️ **{attacker.name}** uses **Sneak Stab** — darting in from the shadows!",
        f"🎲 d20({raw}) {sm:+} DEX  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 {dc}d{ds}({sum(rolls)}) + DEX({sm:+}) + {sneak_n}d6 Sneak({sum(sneak_r)}) = **{dmg} damage**")
        apply_condition(target, "bleeding", 2)
        r["conditions_applied"].append({"name": "bleeding", "duration": 2})
        lines.append(f"🩸 {target.name} is **Bleeding** for 2 rounds!")
    r["log_lines"] = lines
    return r


def _smoke_feint(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Smoke Feint")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.dexterity)
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target))
    dc, ds = WEAPON_DAMAGE.get(attacker.weapon, (1, 4))
    rolls = roll_dice(dc, ds)
    dmg = max(1, sum(rolls) + sm + 1)
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**")
    lines = [
        f"💨 **{attacker.name}** uses **Smoke Feint** — feinting left, striking right!",
        f"🎲 d20({raw}) {sm:+} DEX  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 {dc}d{ds}({sum(rolls)}) + DEX({sm:+}) + Feint(+1) = **{dmg} damage**")
        apply_condition(target, "blinded", 1)
        r["conditions_applied"].append({"name": "blinded", "duration": 1})
        lines.append(f"🫥 {target.name} is **Blinded** for 1 round!")
    r["log_lines"] = lines
    return r


def _pickpocket(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Pickpocket")
    dex_mod = modifier(attacker.dexterity)
    wis_mod = modifier(target.wisdom)
    atk_r = roll(20) + dex_mod + proficiency_bonus(attacker.level)
    def_r = roll(20) + wis_mod
    success = atk_r > def_r
    gold = roll(10) + 5 if success else 0
    r["hit"] = success
    r["log_lines"] = [
        f"🎩 **{attacker.name}** attempts to **Pickpocket** {target.name}!",
        f"🎲 Sleight of Hand {atk_r} vs {target.name} Perception {def_r} — {'✅ Success!' if success else '❌ Caught!'}",
        *([ f"💰 Swiped **{gold} gold** from {target.name}!"] if success else [f"{target.name} noticed the attempt."]),
    ]
    return r


# ─── Wizard ───────────────────────────────────────────────────────────────────

def _magic_missile(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Magic Missile")
    darts = [roll(4) + 1 for _ in range(3)]
    total_dmg = sum(darts)
    r.update(hit=True, damage=total_dmg)
    r["log_lines"] = [
        f"✨ **{attacker.name}** casts **Magic Missile** — three darts of pure force!",
        f"🎯 Auto-hit! 3 darts: {darts[0]}+{darts[1]}+{darts[2]} = **{total_dmg} force damage** (no save possible)",
    ]
    return r


def _fire_bolt(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Fire Bolt")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.intelligence)
    dis = has_condition(attacker, "blinded")
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target), False, dis)
    fire_r = roll_dice(2 if crit else 1, 10)
    dmg = max(1, sum(fire_r))
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**CRITICAL HIT!** 🌟" if crit else ("**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**"))
    lines = [
        f"🔥 **{attacker.name}** hurls **Fire Bolt** at {target.name}!",
        f"🎲 d20({raw}) {sm:+} INT  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 {'2' if crit else '1'}d10({sum(fire_r)}) = **{dmg} fire damage**")
        apply_condition(target, "burning", 1)
        r["conditions_applied"].append({"name": "burning", "duration": 1})
        lines.append(f"🔥 {target.name} is **Burning** for 1 round!")
    r["log_lines"] = lines
    return r


def _wizard_shield(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Shield")
    apply_condition(attacker, "shielded", 1)
    r["self_conditions"].append({"name": "shielded", "duration": 1})
    r["ac_bonus"] = 5
    r["log_lines"] = [
        f"✨ **{attacker.name}** casts **Shield** — a glimmering magical barrier!",
        f"⬆️ AC {attacker.armor_class} → **{attacker.armor_class + 5}** until next turn.",
    ]
    return r


# ─── Barbarian ────────────────────────────────────────────────────────────────

def _reckless_swing(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Reckless Swing")
    raw1, raw2 = roll(20), roll(20)
    raw = max(raw1, raw2)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.strength)
    _, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target))
    dc, ds = WEAPON_DAMAGE.get(attacker.weapon, (1, 12))
    if crit: dc *= 2
    rolls = roll_dice(dc, ds)
    dmg = max(1, sum(rolls) + sm + 3)
    apply_condition(attacker, "reckless", 1)
    r["self_conditions"].append({"name": "reckless", "duration": 1})
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**CRITICAL HIT!** 🌟" if crit else ("**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**"))
    lines = [
        f"🪓 **{attacker.name}** attacks with **Reckless Swing** — wild, furious abandon!",
        f"🎲 Advantage d20({raw1},{raw2})→{raw}  {sm:+} STR  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 {dc}d{ds}({sum(rolls)}) + STR({sm:+}) + Reckless(+3) = **{dmg} damage**")
    lines.append(f"🔴 Reckless: **-2 AC** until {attacker.name}'s next turn!")
    r["log_lines"] = lines
    return r


def _rage_charge(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Rage Charge")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.strength)
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target))
    dc, ds = WEAPON_DAMAGE.get(attacker.weapon, (1, 12))
    if crit: dc *= 2
    rolls = roll_dice(dc, ds)
    dmg = max(1, sum(rolls) + sm + 2)
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**CRITICAL HIT!** 🌟" if crit else ("**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**"))
    lines = [
        f"💢 **{attacker.name}** uses **Rage Charge** — charging with terrifying berserk speed!",
        f"🎲 d20({raw}) {sm:+} STR  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 {dc}d{ds}({sum(rolls)}) + STR({sm:+}) + Charge(+2) = **{dmg} damage**")
        str_save = roll(20) + modifier(target.strength)
        if str_save < 14:
            apply_condition(target, "prone", 1)
            r["conditions_applied"].append({"name": "prone", "duration": 1})
            lines.append(f"⬇️ {target.name} fails STR save ({str_save} vs DC 14) — **Knocked Prone** for 1 round!")
        else:
            lines.append(f"{target.name} passes STR save ({str_save}) — stays on their feet.")
    r["log_lines"] = lines
    return r


def _intimidate(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Intimidate")
    cha_mod = modifier(attacker.charisma)
    atk_r = roll(20) + cha_mod + proficiency_bonus(attacker.level)
    def_r = roll(20) + modifier(target.wisdom)
    success = atk_r > def_r
    r["hit"] = success
    lines = [
        f"😤 **{attacker.name}** unleashes an **Intimidating** battle cry!",
        f"🎲 Intimidation {atk_r} vs {target.name} Insight {def_r} — {'success!' if success else 'resisted.'}",
    ]
    if success:
        apply_condition(target, "frightened", 2)
        r["conditions_applied"].append({"name": "frightened", "duration": 2})
        lines.append(f"😨 {target.name} is **Frightened** for 2 rounds — disadvantage on attacks!")
    else:
        lines.append(f"{target.name} stands firm, unshaken.")
    r["log_lines"] = lines
    return r


# ─── Cleric ───────────────────────────────────────────────────────────────────

def _smite(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Smite")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.wisdom)
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target))
    dc, ds = WEAPON_DAMAGE.get(attacker.weapon, (1, 6))
    if crit: dc *= 2
    rolls = roll_dice(dc, ds)
    is_undead = "skeleton" in getattr(target, "id", "")
    rad_sides = 4 if is_undead else 2
    rad_r = roll_dice(2 if crit else 1, rad_sides)
    dmg = max(1, sum(rolls) + sm + sum(rad_r) + 2)
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**CRITICAL HIT!** 🌟" if crit else ("**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**"))
    lines = [
        f"⚡ **{attacker.name}** channels divine wrath — **Smite**!",
        f"🎲 d20({raw}) {sm:+} WIS  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 {dc}d{ds}({sum(rolls)}) + WIS({sm:+}) + {'2' if crit else '1'}d{rad_sides} radiant({sum(rad_r)}) + Smite(+2) = **{dmg} damage**")
        if is_undead:
            lines.append("✝️ *Bonus radiant damage vs undead!*")
    r["log_lines"] = lines
    return r


def _heal_spell(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Heal")
    wis_mod = modifier(attacker.wisdom)
    heal_r = roll_dice(2, 6)
    amount = max(1, sum(heal_r) + wis_mod)
    actual = attacker.heal(amount)
    r.update(is_heal=True, heal_amount=actual)
    r["log_lines"] = [
        f"✝️ **{attacker.name}** calls upon divine power — **Heal**!",
        f"💚 2d6({sum(heal_r)}) + WIS({wis_mod:+}) = **{amount} HP** → healed **{actual} HP** ❤️ `{attacker.hp_current}/{attacker.hp_max}`",
    ]
    return r


def _turn_undead(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Turn Undead")
    wis_mod = modifier(attacker.wisdom)
    is_undead = "skeleton" in getattr(target, "id", "")
    lines = [f"✝️ **{attacker.name}** raises their holy symbol — **Turn Undead**!"]
    if not is_undead:
        lines.append(f"❌ {target.name} is not undead — no effect.")
    else:
        dc = 8 + wis_mod + proficiency_bonus(attacker.level)
        wis_save = roll(20) + modifier(target.wisdom)
        lines.append(f"🎲 {target.name} WIS save: {wis_save} vs DC {dc}")
        if wis_save < dc:
            apply_condition(target, "frightened", 2)
            r["conditions_applied"].append({"name": "frightened", "duration": 2})
            r["hit"] = True
            lines.append(f"😨 **{target.name} is Turned!** Frightened for 2 rounds — cannot attack!")
        else:
            lines.append(f"{target.name} resists the turning.")
    r["log_lines"] = lines
    return r


# ─── Warlock ──────────────────────────────────────────────────────────────────

def _eldritch_blast(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Eldritch Blast")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.charisma)
    dis = has_condition(attacker, "blinded")
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target), False, dis)
    force_r = roll_dice(2 if crit else 1, 10)
    cha_dmg = modifier(attacker.charisma)
    dmg = max(1, sum(force_r) + cha_dmg)
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**CRITICAL HIT!** 🌟" if crit else ("**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**"))
    lines = [
        f"🔮 **{attacker.name}** fires **Eldritch Blast** — a beam of crackling dark energy!",
        f"🎲 d20({raw}) {sm:+} CHA  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 {'2' if crit else '1'}d10({sum(force_r)}) + CHA({cha_dmg:+}) = **{dmg} force damage**")
        str_save = roll(20) + modifier(target.strength)
        lines.append(f"💨 Repelling Blast: {target.name} STR save {str_save} vs DC 12 — " + ("blasted backward!" if str_save < 12 else "holds their ground."))
    r["log_lines"] = lines
    return r


def _hex_spell(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Hex")
    apply_condition(target, "hexed", 3)
    r["conditions_applied"].append({"name": "hexed", "duration": 3})
    r["log_lines"] = [
        f"🔮 **{attacker.name}** places a **Hex** on {target.name}!",
        f"💀 {target.name} is **Hexed** for 3 rounds — each hit deals +1d6 necrotic damage!",
    ]
    return r


def _drain(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Drain")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.charisma)
    dis = has_condition(attacker, "blinded")
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target), False, dis)
    drain_r = roll_dice(2 if crit else 1, 8)
    dmg = max(1, sum(drain_r))
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**CRITICAL HIT!** 🌟" if crit else ("**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**"))
    lines = [
        f"💀 **{attacker.name}** reaches out — **Drain**! Siphoning life from {target.name}!",
        f"🎲 d20({raw}) {sm:+} CHA  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 {'2' if crit else '1'}d8({sum(drain_r)}) = **{dmg} necrotic damage**")
        heal_amount = dmg // 2
        actual = attacker.heal(heal_amount)
        lines.append(f"💚 {attacker.name} absorbs life force — healed **{actual} HP** ❤️ `{attacker.hp_current}/{attacker.hp_max}`")
    r["log_lines"] = lines
    return r


def _ray_of_frost(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Ray of Frost")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.intelligence)
    dis = has_condition(attacker, "blinded")
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target), False, dis)
    cold_r = roll_dice(2 if crit else 1, 8)
    dmg = max(1, sum(cold_r))
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**CRITICAL HIT!** 🌟" if crit else ("**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**"))
    lines = [
        f"❄️ **{attacker.name}** unleashes **Ray of Frost** at {target.name}!",
        f"🎲 d20({raw}) {sm:+} INT  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 {'2' if crit else '1'}d8({sum(cold_r)}) = **{dmg} cold damage**")
        apply_condition(target, "slowed", 1)
        r["conditions_applied"].append({"name": "slowed", "duration": 1})
        lines.append(f"🐌 {target.name} is **Slowed** — speed reduced by 10ft for 1 round!")
    r["log_lines"] = lines
    return r


def _guiding_bolt(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Guiding Bolt")
    raw = roll(20)
    pb = proficiency_bonus(attacker.level)
    sm = modifier(attacker.wisdom)
    dis = has_condition(attacker, "blinded")
    raw, total, hit, crit, miss = _resolve_hit(raw, sm, pb, effective_ac(target), False, dis)
    rad_r = roll_dice(2 if crit else 4, 6)
    dmg = max(1, sum(rad_r))
    r.update(miss=miss, crit=crit, attack_roll=total, hit=hit, damage=dmg if hit else 0)
    rw = "**CRITICAL HIT!** 🌟" if crit else ("**HIT!**" if hit else ("**NAT 1!**" if miss else "**MISS!**"))
    lines = [
        f"✨ **{attacker.name}** calls down **Guiding Bolt** on {target.name}!",
        f"🎲 d20({raw}) {sm:+} WIS  {pb:+} Prof = **{total}** vs AC {effective_ac(target)} — {rw}",
    ]
    if hit:
        lines.append(f"💥 {'8' if crit else '4'}d6({sum(rad_r)}) = **{dmg} radiant damage**")
        apply_condition(target, "blinded", 1)
        r["conditions_applied"].append({"name": "blinded", "duration": 1})
        lines.append(f"🫥 {target.name} is **outlined in radiance** — Blinded for 1 round (next attack against them has advantage)!")
    r["log_lines"] = lines
    return r


def _hellish_rebuke(attacker: Combatant, target: Combatant) -> dict:
    r = _base_result("Hellish Rebuke")
    cha_mod = modifier(attacker.charisma)
    pb = proficiency_bonus(attacker.level)
    dc = 8 + cha_mod + pb
    dex_save = roll(20) + modifier(target.dexterity)
    saved = dex_save >= dc
    fire_r = roll_dice(2, 10)
    dmg = max(1, sum(fire_r) // (2 if saved else 1))
    r.update(hit=True, damage=dmg)
    lines = [
        f"🔥 **{attacker.name}** wraps in hellfire — **Hellish Rebuke**!",
        f"💀 {target.name} DEX save: d20({dex_save - modifier(target.dexterity)}) {modifier(target.dexterity):+} DEX = **{dex_save}** vs DC {dc} — {'✅ Half damage!' if saved else '❌ Full damage!'}",
        f"🔥 2d10({sum(fire_r)}) = **{dmg} fire damage** to {target.name}",
    ]
    apply_condition(target, "burning", 1)
    r["conditions_applied"].append({"name": "burning", "duration": 1})
    lines.append(f"🔥 {target.name} is **Burning** for 1 round!")
    r["log_lines"] = lines
    return r


# ── Dispatcher ────────────────────────────────────────────────────────────────

_HANDLERS: dict = {
    "Power Strike":   _power_strike,
    "Shield Bash":    _shield_bash,
    "Parry":          _parry,
    "Sneak Stab":     _sneak_stab,
    "Smoke Feint":    _smoke_feint,
    "Pickpocket":     _pickpocket,
    "Magic Missile":  _magic_missile,
    "Fire Bolt":      _fire_bolt,
    "Shield":         _wizard_shield,
    "Reckless Swing": _reckless_swing,
    "Rage Charge":    _rage_charge,
    "Intimidate":     _intimidate,
    "Smite":          _smite,
    "Heal":           _heal_spell,
    "Turn Undead":    _turn_undead,
    "Eldritch Blast": _eldritch_blast,
    "Hex":            _hex_spell,
    "Drain":          _drain,
    "Ray of Frost":   _ray_of_frost,
    "Guiding Bolt":   _guiding_bolt,
    "Hellish Rebuke": _hellish_rebuke,
}


def resolve_named_attack(attacker: Combatant, attack_name: str, target: Combatant) -> dict:
    handler = _HANDLERS.get(attack_name)
    if handler:
        result = handler(attacker, target)
        # Hex bonus damage on any hit (except Drain which handles it)
        if result["hit"] and result["damage"] > 0 and has_condition(target, "hexed") and attack_name not in ("Drain", "Hex"):
            hex_roll = roll(6)
            result["damage"] += hex_roll
            result["log_lines"].append(f"🔮 Hex triggers! +{hex_roll} necrotic damage!")
        return result
    # Fallback: basic weapon attack
    basic = player_attack(attacker, weapon=attacker.weapon)
    stat_key = CLASS_ATTACK_STAT.get(attacker.char_class, "str")
    sm = modifier(_stat(attacker, stat_key))
    hit = not basic["is_miss"] and basic["attack_roll"] >= effective_ac(target)
    lines = [
        f"⚔️ **{attacker.name}** attacks!",
        f"🎲 d20({basic['raw_roll']}) {sm:+} = **{basic['attack_roll']}** vs AC {effective_ac(target)} — {'**HIT!**' if hit else '**MISS!**'}",
        *([ f"💥 **{basic['damage']} damage**"] if hit else []),
    ]
    return {
        "attack_name": attack_name or "Attack", "hit": hit,
        "damage": basic["damage"] if hit else 0,
        "crit": basic["is_crit"], "miss": basic["is_miss"],
        "attack_roll": basic["attack_roll"], "log_lines": lines,
        "conditions_applied": [], "self_conditions": [],
        "is_heal": False, "heal_amount": 0, "ac_bonus": 0,
    }
