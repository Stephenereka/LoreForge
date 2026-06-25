import random
import os
import aiohttp

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = "https://api.deepseek.com/v1"

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


async def generate_dummy_action(difficulty: str, dummy_state: dict, player_state: dict, round_num: int) -> dict:
    """
    Generate the training dummy's action for a round.
    Uses rule-based logic for mechanics and DeepSeek for flavor text.
    """
    config = DIFFICULTY_CONFIGS.get(difficulty, DIFFICULTY_CONFIGS["medium"])
    dummy_hp_pct = dummy_state["hp_current"] / max(1, dummy_state["hp_max"])
    player_hp_pct = player_state["hp_current"] / max(1, player_state["hp_max"])

    actions = {
        "basic_attack": {
            "flavor": f"{config['flavor_prefix']} at {player_state.get('name', 'you')}.",
            "damage_bonus": config["damage_bonus"],
        },
        "heavy_attack": {
            "flavor": f"{config['flavor_prefix']} with a heavy strike!",
            "damage_bonus": config["damage_bonus"] + 2,
            "hit_penalty": -2,
        },
        "defensive": {
            "flavor": "The training dummy shifts into a defensive stance, ready to counter.",
            "defense_bonus": 2,
            "no_damage": True,
        },
    }

    # Difficulty-based AI logic
    if difficulty == "easy":
        if round_num % 3 == 0:
            return {"action": "miss", "flavor": "The dummy swings wildly and misses completely!", "damage": 0, "hit_chance": 0}
        action = "basic_attack"
    elif difficulty == "medium":
        if dummy_hp_pct < 0.3 and round_num > 2:
            action = "defensive"
        elif player_hp_pct < 0.3:
            action = "heavy_attack"
        else:
            action = "basic_attack"
    elif difficulty == "hard":
        if player_state.get("conditions"):
            action = "heavy_attack"
        elif dummy_hp_pct < 0.5:
            action = "defensive"
        elif player_state.get("last_action") == "defend":
            action = "heavy_attack"
        else:
            action = "heavy_attack"
    else:  # impossible
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

        total_damage, _ = roll_dice_simple(count, sides, config["damage_bonus"] + extra_bonus)
        damage_total = max(1, total_damage)

    base_result = {
        "action": action,
        "flavor": action_data["flavor"],
        "damage": damage_total,
        "hit_bonus": config["attack_bonus"] + action_data.get("hit_penalty", 0),
        "defense_bonus": action_data.get("defense_bonus", 0),
        "personality": config["personality"],
    }

    # DeepSeek flavor text
    try:
        system_prompt = (
            f"You are a sentient training dummy in a dark fantasy RPG. "
            f"You are {difficulty} difficulty with this personality: {config['personality']}. "
            f"Describe your next attack action in exactly ONE vivid sentence (max 20 words). "
            f"No quotation marks. Stay in character. Be dramatic and menacing."
        )
        user_prompt = (
            f"Round {round_num}. You chose to: {action}. "
            f"Your HP: {dummy_state['hp_current']}/{dummy_state['hp_max']}. "
            f"Opponent HP: {player_state['hp_current']}/{player_state['hp_max']}."
        )
        async with aiohttp.ClientSession() as http:
            resp = await http.post(
                f"{DEEPSEEK_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 50,
                    "temperature": 0.9,
                },
                timeout=aiohttp.ClientTimeout(total=4),
            )
            data = await resp.json()
            ai_flavor = data["choices"][0]["message"]["content"].strip().strip('"')
            base_result["flavor"] = ai_flavor
    except Exception:
        pass  # Fall back to static flavor already set

    return base_result


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
    if difficulty == "impossible" and round_num % 2 == 0:
        return random.choice(TAUNT_LINES["impossible"])
    if difficulty == "hard" and round_num % 3 == 0:
        return random.choice(TAUNT_LINES["hard"])
    return None


def get_death_line(difficulty: str) -> str:
    return random.choice(DEATH_LINES.get(difficulty, DEATH_LINES["easy"]))


def get_xp_reward(difficulty: str) -> int:
    base_xp = {
        "easy": 25,
        "medium": 50,
        "hard": 100,
        "impossible": 250,
    }
    return base_xp.get(difficulty, 25)
