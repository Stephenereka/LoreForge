import json
import httpx
from openai import AsyncOpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL

_client: AsyncOpenAI | None = None
_httpx_client: httpx.AsyncClient | None = None


def _get_httpx_client() -> httpx.AsyncClient:
    global _httpx_client
    if _httpx_client is None:
        _httpx_client = httpx.AsyncClient(
            base_url=DEEPSEEK_API_URL,
            timeout=30.0,
        )
    return _httpx_client


async def _deepseek_call(system_prompt: str, user_prompt: str, max_tokens: int = 200, temperature: float = 0.7) -> str:
    """Generic call to DeepSeek via httpx. Returns empty string on any failure."""
    try:
        client = _get_httpx_client()
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        return ""
    except Exception:
        return ""

_OOC_SIGNALS = {
    "lol", "lmao", "haha", "gg", "brb", "nvm", "omg", "wtf", "smh", "lmfao",
    "xd", "oof", "rip", "fr", "ngl", "tbh", "imo", "ikr", "ffs",
}

_ATTACK_WORDS = {
    "strike", "punch", "hit", "slash", "stab", "shoot", "attack", "smash",
    "bash", "swing", "throw", "cut", "bite", "claw", "pierce", "jab", "slam",
    "thrust", "whack", "chop", "hack",
}
_GRAPPLE_WORDS = {"grab", "grapple", "tackle", "wrestle", "pin", "restrain", "clutch", "seize", "hold onto"}
_SHOVE_WORDS = {"shove", "push", "knock back", "kick away", "push back", "topple", "sweep"}
_HIDE_WORDS = {"hide", "sneak", "go invisible", "slip into shadow", "vanish", "conceal", "blend in", "disappear"}
_ITEM_WORDS = {"potion", "bandage", "scroll", "drink", "use item", "heal item", "consume"}
_HELP_WORDS = {"help", "assist", "support", "aid"}
_TAUNT_WORDS = {"taunt", "insult", "provoke", "challenge", "intimidate", "mock", "bait", "trash talk"}
_DASH_WORDS = {"dash", "sprint", "charge", "rush toward", "run toward", "lunge forward"}
_DEFEND_WORDS = {"block", "dodge", "parry", "brace", "shield", "deflect", "guard", "take cover", "sidestep"}
_FLEE_WORDS = {"flee", "run away", "retreat", "escape", "dash away", "get out", "back out", "withdraw"}


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_API_URL,
        )
    return _client


def _is_ooc(text: str) -> bool:
    lower = text.lower().strip()
    words = set(lower.split())
    if words & _OOC_SIGNALS:
        return True
    all_action_words = (
        _ATTACK_WORDS | _GRAPPLE_WORDS | _SHOVE_WORDS | _HIDE_WORDS
        | _ITEM_WORDS | _HELP_WORDS | _TAUNT_WORDS | _DASH_WORDS
        | _DEFEND_WORDS | _FLEE_WORDS | {"cast", "use", "spell"}
    )
    if len(lower) < 12 and not any(w in lower for w in all_action_words):
        return True
    return False


def _keyword_classify(text: str, known_skills: list[str]) -> str | None:
    lower = text.lower()
    for skill in known_skills:
        if skill.lower() in lower:
            return "SKILL"
    for w in _GRAPPLE_WORDS:
        if w in lower:
            return "GRAPPLE"
    for w in _SHOVE_WORDS:
        if w in lower:
            return "SHOVE"
    for w in _HIDE_WORDS:
        if w in lower:
            return "HIDE"
    for w in _HELP_WORDS:
        if w in lower:
            return "HELP"
    for w in _TAUNT_WORDS:
        if w in lower:
            return "TAUNT"
    for w in _ATTACK_WORDS:
        if w in lower:
            return "ATTACK"
    for w in _DEFEND_WORDS:
        if w in lower:
            return "DEFEND"
    for w in _FLEE_WORDS:
        if w in lower:
            return "FLEE"
    for w in _ITEM_WORDS:
        if w in lower:
            return "ITEM"
    for w in _DASH_WORDS:
        if w in lower:
            return "DASH"
    return None


async def classify_combat_action(
    text: str,
    player_name: str,
    combatants: list[dict],
    player_skills: list[str] | None = None,
) -> dict:
    """
    Reads a player's RP message and returns the combat action they're taking.

    combatants: list of {"name": str, "hp": str, "class_": str} for all fighters in the session
    player_skills: list of known class ability names (e.g. ["Power Strike", "Shield Bash"])

    Returns: {action, target, weapon, skill_name}
    action: ATTACK | SPELL | SKILL | GRAPPLE | SHOVE | DASH | HIDE | HELP | TAUNT | DEFEND | ITEM | FLEE | OOC | UNCLEAR
    """
    player_skills = player_skills or []

    if _is_ooc(text):
        return {"action": "OOC", "target": None, "weapon": None, "skill_name": None}

    kw = _keyword_classify(text, player_skills)

    others = [c for c in combatants if c["name"] != player_name]
    combatant_list = "\n".join(
        f"- {c['name']} (HP: {c['hp']}, Class: {c['class_']})" for c in others
    ) or "none"
    skills_str = ", ".join(player_skills) if player_skills else "none"

    prompt = (
        f'Player "{player_name}" is in combat.\n'
        f"Other combatants in this fight:\n{combatant_list}\n\n"
        f"Player's known class skills/abilities: {skills_str}\n\n"
        f'Their message: "{text}"\n\n'
        "Classify as EXACTLY ONE of these actions:\n"
        "ATTACK   — offensive strike: hit, slash, stab, punch, shoot, swing, bite, claw, throw weapon\n"
        "SPELL    — casting a named spell or channeling magic (fireball, lightning bolt, etc.)\n"
        f"SKILL    — using one of the player's known abilities by name [{skills_str}]\n"
        "GRAPPLE  — grab, tackle, wrestle, pin, restrain an opponent\n"
        "SHOVE    — push, shove, knock someone back or down (prone)\n"
        "DASH     — sprint or charge forward (movement without attacking)\n"
        "HIDE     — hide, sneak, go invisible, slip into shadows\n"
        "HELP     — assist an ally, give them advantage on their next action\n"
        "TAUNT    — taunt, insult, intimidate, provoke, mock, challenge\n"
        "DEFEND   — block, dodge, parry, brace, take cover, raise shield\n"
        "ITEM     — use a potion, bandage, scroll, or consumable item\n"
        "FLEE     — retreat, escape, run away from the fight entirely\n"
        "OOC      — clearly out-of-character chat (not a combat action at all)\n"
        "UNCLEAR  — combat-flavored but truly impossible to classify\n\n"
        "target: exact name of the combatant they are targeting from the list above, or null.\n"
        "skill_name: if SKILL, the exact skill name from the player's list, else null.\n\n"
        "Respond ONLY with valid JSON, no explanation:\n"
        '{"action": "ATTACK", "target": "name or null", "weapon": "weapon or null", "skill_name": "skill or null"}'
    )

    try:
        resp = await _get_client().chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.0,
        )
        raw = resp.choices[0].message.content.strip()
        i, j = raw.find("{"), raw.rfind("}") + 1
        if i >= 0 and j > i:
            data = json.loads(raw[i:j])
            if kw:
                data["action"] = kw
            return data
    except Exception:
        pass

    if kw:
        return {"action": kw, "target": None, "weapon": None, "skill_name": None}
    return {"action": "UNCLEAR", "target": None, "weapon": None, "skill_name": None}


# ── Phase 4: AI Narration ─────────────────────────────────────────────────────

async def narrate_combat(
    guild_id: int,
    attacker_name: str,
    attack_name: str,
    weapon: str,
    target_name: str,
    result: str,
    damage: int,
    hp_remaining: int,
    conditions: list,
    world_name: str,
    lore_snippets: list[str],
    style: str = "epic",
) -> str:
    """Generate a 1-2 sentence combat narration via DeepSeek. Returns empty string on failure."""
    lore_text = "\n".join(lore_snippets) if lore_snippets else "No additional world context."
    cond_text = ", ".join(c["name"] if isinstance(c, dict) else str(c) for c in (conditions or [])) or "none"
    system_prompt = (
        f"You are a GM narrating combat in {world_name}.\n"
        f"World facts: {lore_text}\n"
        f"Style: {style}. Max 2 sentences. Never contradict lore. "
        "Keep it vivid but brief — just the action, no meta-commentary."
    )
    user_prompt = (
        f"{attacker_name} used {attack_name} ({weapon}) against {target_name} → {result}: {damage} dmg. "
        f"{target_name} has {hp_remaining} HP remaining. Conditions: {cond_text}."
    )
    return await _deepseek_call(system_prompt, user_prompt, max_tokens=120)


async def generate_npc_dialogue(
    npc_name: str,
    race: str,
    title: str,
    personality_traits: str,
    speaking_style: str,
    attitude: int,
    interaction_count: int,
    last_topic: str,
    lore_snippets: list[str],
    player_name: str,
    player_message: str,
) -> str:
    """Generate NPC dialogue via DeepSeek. Returns empty string on failure."""
    lore_text = "\n".join(lore_snippets) if lore_snippets else "No additional lore."
    system_prompt = (
        f"You are {npc_name}, a {race} {title or 'character'}.\n"
        f"Personality: {personality_traits or 'neutral, polite'}.\n"
        f"Speaking style: {speaking_style or 'normal'}.\n"
        f"Your relationship with {player_name}: attitude {attitude}/10, "
        f"{interaction_count} past conversations, last topic: {last_topic or 'nothing specific'}.\n"
        f"World facts you know: {lore_text}\n"
        "Never break character. Max 3 sentences. Speak naturally — don't describe actions in asterisks."
    )
    user_prompt = f"{player_name} says to you: \"{player_message}\"\n\nHow do you respond?"
    return await _deepseek_call(system_prompt, user_prompt, max_tokens=200)


async def summarize_session(
    messages_text: str,
    characters: list[str],
    location: str,
    combat_count: int,
    quest_completions: int,
    total_xp: int,
) -> str:
    """Generate a 2-3 sentence narrative summary of a session. Returns empty string on failure."""
    system_prompt = (
        "You are a session chronicler. Summarize the events of an RPG session "
        "in 2-3 narrative sentences. Focus on key events, combat, and character moments. "
        "Be concise and engaging."
    )
    user_prompt = (
        f"Session location: {location}\n"
        f"Characters: {', '.join(characters)}\n"
        f"Combat encounters: {combat_count}\n"
        f"Quests completed: {quest_completions}\n"
        f"Total XP earned: {total_xp}\n\n"
        f"Messages from the session:\n{messages_text[:2000]}\n\n"
        "Write a 2-3 sentence narrative summary."
    )
    return await _deepseek_call(system_prompt, user_prompt, max_tokens=250)
