import json
import random
from services.ai_service import _get_client

FALLBACK_QUEST = {
    "title": "The Lost Relic",
    "description": "An ancient artifact has been stolen from the temple. Find it before it falls into the wrong hands.",
    "objectives": ["Investigate the temple for clues", "Track down the thief", "Recover the relic"],
    "reward_xp": 500,
    "reward_gold": 200,
    "npc_name": "Elder Marcus",
}

FALLBACK_NPC = {
    "name": "Mysterious Stranger",
    "title": "Wanderer",
    "description": "A cloaked figure who keeps to themselves, but seems to know more than they let on.",
    "personality": "Mysterious and cautious",
    "appearance": "Worn brown cloak, scarred hands",
    "dialogue": ["The road ahead is dangerous.", "I've seen things you wouldn't believe."],
    "attitude": "neutral",
}

FALLBACK_ENCOUNTER = {
    "name": "Wild Encounter",
    "description": "Creatures emerge from the shadows!",
    "enemies": [
        {"name": "Shadow Beast", "hp": 30, "attack": 4, "damage": "1d8+2"},
    ],
    "rewards": {"xp": 200, "gold": 50},
}


async def generate_quest(difficulty: str = "medium", location: str = "the realm", theme: str = None) -> dict:
    """Generate a complete quest with objectives and rewards via DeepSeek."""
    system_prompt = (
        "You are a fantasy RPG quest generator. "
        "Always respond with valid JSON only, no markdown, no explanation."
    )
    user_prompt = (
        f"Generate a quest for a fantasy RPG. Difficulty: {difficulty}. "
        f"Location: {location}."
    )
    if theme:
        user_prompt += f" Theme: {theme}."
    user_prompt += (
        " Return JSON with keys: title (string), description (string), "
        "objectives (array of strings, 3-4 items), reward_xp (int 100-2000), "
        "reward_gold (int 50-500), npc_name (string). Only valid JSON."
    )

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=800,
        )
        text = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()
        result = json.loads(text)
        # Validate required keys
        required = ["title", "description", "objectives", "reward_xp", "reward_gold", "npc_name"]
        for key in required:
            if key not in result:
                raise ValueError(f"Missing key: {key}")
        return result
    except Exception:
        quest = dict(FALLBACK_QUEST)
        # Adjust difficulty
        diff_mult = {"easy": 0.5, "medium": 1.0, "hard": 1.5, "deadly": 2.0}
        mult = diff_mult.get(difficulty, 1.0)
        quest["reward_xp"] = int(quest["reward_xp"] * mult)
        quest["reward_gold"] = int(quest["reward_gold"] * mult)
        return quest


async def generate_npc(location: str, role: str) -> dict:
    """Generate an NPC with stats, personality, appearance via DeepSeek."""
    system_prompt = (
        "You are a fantasy NPC generator. "
        "Always respond with valid JSON only, no markdown, no explanation."
    )
    user_prompt = (
        f"Generate a fantasy NPC found in {location} with the role of {role}. "
        "Return JSON with keys: name (string), title (string), description (string, 1-2 sentences), "
        "personality (string), appearance (string), "
        "dialogue (array of 3 strings — things they might say), "
        "attitude (string: friendly/neutral/hostile). Only valid JSON."
    )

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,
            max_tokens=600,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()
        result = json.loads(text)
        required = ["name", "title", "description", "personality", "appearance", "dialogue", "attitude"]
        for key in required:
            if key not in result:
                raise ValueError(f"Missing key: {key}")
        return result
    except Exception:
        npc = dict(FALLBACK_NPC)
        npc["description"] = f"A {role} found in {location}. {npc['description']}"
        return npc


async def generate_encounter(difficulty: str, location: str) -> dict:
    """Generate a balanced combat encounter."""
    system_prompt = (
        "You are a fantasy combat encounter generator. "
        "Always respond with valid JSON only, no markdown, no explanation."
    )
    user_prompt = (
        f"Generate a combat encounter in {location} with {difficulty} difficulty. "
        "Return JSON with keys: name (string), description (string), "
        "enemies (array of objects with keys: name, hp (int 10-100), attack (int 2-8), damage (string like '1d6+2')), "
        "rewards (object with keys: xp (int 50-2000), gold (int 10-500)). "
        f"For {difficulty} difficulty, include 1-3 enemies. Only valid JSON."
    )

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=800,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()
        result = json.loads(text)
        required = ["name", "description", "enemies", "rewards"]
        for key in required:
            if key not in result:
                raise ValueError(f"Missing key: {key}")
        return result
    except Exception:
        enc = dict(FALLBACK_ENCOUNTER)
        diff_mult = {"easy": 0.66, "medium": 1.0, "hard": 1.5, "deadly": 2.0}
        mult = diff_mult.get(difficulty, 1.0)
        for enemy in enc["enemies"]:
            enemy["hp"] = int(enemy["hp"] * mult)
        enc["rewards"]["xp"] = int(enc["rewards"]["xp"] * mult)
        enc["rewards"]["gold"] = int(enc["rewards"]["gold"] * mult)
        return enc
