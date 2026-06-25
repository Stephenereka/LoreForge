import random
import math

DIFFICULTY_CONFIGS = {
    "easy": {
        "hp": 30, "ac": 10, "attack_bonus": 2, "damage_dice": "1d4",
        "damage_bonus": 0, "xp_mult": 0.5,
        "personality": "makes mistakes, misses often, telegraphs attacks",
        "flavor_prefix": "The dummy swings slowly",
    },
    "medium": {
        "hp": 60, "ac": 14, "attack_bonus": 5, "damage_dice": "1d8+2",
        "damage_bonus": 2, "xp_mult": 1.0,
        "personality": "competent fighter, uses basic tactics",
        "flavor_prefix": "The dummy moves with practiced precision",
    },
    "hard": {
        "hp": 100, "ac": 17, "attack_bonus": 8, "damage_dice": "2d6+4",
        "damage_bonus": 4, "xp_mult": 1.5,
        "personality": "aggressive, uses conditions strategically, counters player patterns",
        "flavor_prefix": "The dummy anticipates your moves",
    },
    "impossible": {
        "hp": 200, "ac": 20, "attack_bonus": 12, "damage_dice": "2d10+6",
        "damage_bonus": 6, "xp_mult": 2.0,
        "personality": "reads every player move, near-perfect counter-play, taunts",
        "flavor_prefix": "The dummy moves with inhuman precision",
    },
}


def roll_dice_simple(count: int, sides: int, bonus: int = 0) -> tuple[int, list[int]]:
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + bonus
    return total, rolls


def generate_dummy_action(difficulty: str, dummy_state: dict, player_state: dict, round_num: int) -> dict:
    """
    Generate the dummy's action for a training round.
    Uses DEEPSEEK-style strategic logic without API calls.
    Returns dict with action description and mechanics.
    """
    config = DIFFICULTY_CONFIGS.get(difficulty, DIFFICULTY_CONFIGS["medium"])
    dummy_hp_pct = dummy_state["hp_current"] / max(1, dummy_state["hp_max"])
    player_hp_pct = player_state["hp_current"] / max(1, player_state["hp_max"])

    # Determine intent based on difficulty and situation
    actions = {
        "basic_attack": {
            "flavor": f"{config['flavor_prefix']} at {player_state['name']}.",
            "damage_bonus": config["damage_bonus"],
        },
        "heavy_attack": {
            "flavor": f"{config['flavor_prefix']} with a heavy strike!",
            "damage_bonus": config["damage_bonus"] + 2,
            "hit_penalty": -2,
        },
        "defensive": {
            "flavor": f"The training dummy shifts into a defensive stance, ready to counter.",
            "defense_bonus": 2,
            "no_damage": True,
        },
    }

    # Difficulty-based AI logic
    if difficulty == "easy":
        # Makes mistakes — sometimes just misses entirely
        if round_num % 3 == 0:
            return {"action": "miss", "flavor": "The dummy swings wildly and misses completely!", "damage": 0, "hit_chance": 0}
        action = "basic_attack"
    elif difficulty == "medium":
        # Basic tactics — mixes attacks and defense
        if dummy_hp_pct < 0.3 and round_num > 2:
            action = "defensive"
        elif player_hp_pct < 0.3:
            action = "heavy_attack"
        else:
            action = "basic_attack"
    elif difficulty == "hard":
        # Strategic — counters and uses conditions
        if player_state.get("conditions"):
            action = "heavy_attack"
        elif dummy_hp_pct < 0.5:
            action = "defensive"
        elif player_state.get("last_action") == "defend":
            action = "heavy_attack"
        else:
            action = "heavy_attack"
    else:  # impossible
        # Near-perfect counterplay
        if player_state.get("conditions"):
            action = "heavy_attack"
        elif player_state.get("last_action") == "attack":
            action = "defensive"
        elif player_hp_pct < 0.5:
            action = "heavy_attack"
        else:
            action = "heavy_attack"

    action_data = actions.get(action, actions["basic_attack"])
    damage_total = 0
    if not action_data.get("no_damage"):
        # Parse damage dice
        dice_str = config["damage_dice"]
        if "+" in dice_str:
            parts = dice_str.split("+")
            dice_part = parts[0]
            extra_bonus = int(parts[1])
        else:
            dice_part = dice_str
            extra_bonus = 0

        count, sides = 1, 6
        if "d" in dice_part:
            parts = dice_part.split("d")
            count = int(parts[0]) if parts[0] else 1
            sides = int(parts[1]) if parts[1] else 6

        total_damage, rolls = roll_dice_simple(count, sides, config["damage_bonus"] + extra_bonus)
        damage_total = max(1, total_damage)

    return {
        "action": action,
        "flavor": action_data["flavor"],
        "damage": damage_total,
        "hit_bonus": config["attack_bonus"] + action_data.get("hit_penalty", 0),
        "defense_bonus": action_data.get("defense_bonus", 0),
        "personality": config["personality"],
    }


# ── Taunt lines per difficulty ────────────────────────────────────────────────

TAUNT_LINES = {
    "easy": ["The dummy stumbles.", "...swing again, I'm not even trying.", "Is that all the strength you have?"],
    "medium": ["Better. But not good enough.", "You telegraph your attacks.", "Work on your footwork."],
    "hard": ["I've seen faster from wounded goblins.", "You fell for that feint?", "Predictable."],
    "impossible": ["I am three moves ahead of you.", "Your technique is flawed at a fundamental level.", "You cannot defeat perfection.", "Every attack you make reveals a weakness."],
}

DEATH_LINES = {
    "easy": ["The dummy collapses in a heap.", "Training successful!", "A solid victory."],
    "medium": ["The dummy shudders and falls.", "Well fought!", "You're getting stronger."],
    "hard": ["With a final, mighty blow, the dummy crumbles!", "Impressive! You've mastered this difficulty.", "The dummy's pieces scatter across the arena."],
    "impossible": ["UNBELIEVABLE! You've defeated the impossible!", "The dummy shatters into a thousand pieces!", "Legendary! Even the impossible dummy bows to your skill!"],
}


def get_taunt(difficulty: str, round_num: int) -> str | None:
    """Return a taunt line if the dummy should taunt. None otherwise."""
    if difficulty == "impossible" and round_num % 2 == 0:
        return random.choice(TAUNT_LINES["impossible"])
    if difficulty == "hard" and round_num % 3 == 0:
        return random.choice(TAUNT_LINES["hard"])
    return None


def get_death_line(difficulty: str) -> str:
    return random.choice(DEATH_LINES.get(difficulty, DEATH_LINES["easy"]))


def get_xp_reward(difficulty: str) -> int:
    """Calculate XP reward for winning a training session at a given difficulty."""
    base_xp = {
        "easy": 25,
        "medium": 50,
        "hard": 100,
        "impossible": 250,
    }
    return base_xp.get(difficulty, 25)
