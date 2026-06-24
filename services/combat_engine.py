import random
import math
from dataclasses import dataclass, field
from typing import Optional

# ── Dice ─────────────────────────────────────────────────────────────────────

def roll(sides: int) -> int:
    return random.randint(1, sides)

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
    weapon: str = "unarmed"

    hp_max: int
    hp_current: int
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
}

CLASS_ATTACK_STAT = {
    "Fighter":   "str",
    "Barbarian": "str",
    "Rogue":     "dex",
    "Cleric":    "wis",
    "Wizard":    "int",
    "Warlock":   "cha",
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

# ── XP thresholds (D&D 5e) ────────────────────────────────────────────────────

XP_THRESHOLDS = [0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
                 85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000]

def xp_for_level(level: int) -> int:
    if level >= len(XP_THRESHOLDS):
        return XP_THRESHOLDS[-1]
    return XP_THRESHOLDS[level]

def check_level_up(current_xp: int, current_level: int) -> Optional[int]:
    """Return the new level if a level-up occurred, else None."""
    if current_level >= 20:
        return None
    needed = xp_for_level(current_level)
    if current_xp >= needed:
        return current_level + 1
    return None

def hp_gain_on_level(char_class: str, con_score: int, new_level: int) -> int:
    hit_die = {"Fighter": 10, "Barbarian": 12, "Rogue": 8,
               "Cleric": 8, "Wizard": 6, "Warlock": 8}.get(char_class, 8)
    avg_roll = math.ceil(hit_die / 2) + 1
    return avg_roll + modifier(con_score)
