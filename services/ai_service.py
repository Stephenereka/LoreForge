import json
from openai import AsyncOpenAI
from config import DEEPSEEK_API_KEY

_client: AsyncOpenAI | None = None

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
            base_url="https://api.deepseek.com",
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
