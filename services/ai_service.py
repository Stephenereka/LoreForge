import json
from groq import AsyncGroq
from config import GROQ_API_KEY

_client: AsyncGroq | None = None


def _groq() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=GROQ_API_KEY)
    return _client


async def classify_combat_action(text: str, player_name: str, enemy_name: str) -> dict:
    """
    Reads a player's RP message and returns the combat action they're taking.
    Returns: {action, target, weapon}
    action: ATTACK | DEFEND | FLEE | ITEM | SPELL | UNCLEAR
    """
    prompt = (
        f'Player "{player_name}" is in combat against "{enemy_name}".\n'
        f'Their message: "{text}"\n\n'
        "Classify as exactly one of:\n"
        "ATTACK - any offensive strike, hit, slash, stab, punch, or attack\n"
        "DEFEND - blocking, dodging, bracing, parrying, taking cover\n"
        "FLEE - running, retreating, escaping, dashing away\n"
        "ITEM - using a potion, bandage, or consumable item\n"
        "SPELL - casting a spell or channeling magic\n"
        "UNCLEAR - pure roleplay with no clear combat action\n\n"
        "Respond ONLY with valid JSON, no explanation:\n"
        '{"action": "ATTACK", "target": "target name or null", "weapon": "weapon used or null"}'
    )
    try:
        resp = await _groq().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.0,
        )
        raw = resp.choices[0].message.content.strip()
        i, j = raw.find("{"), raw.rfind("}") + 1
        if i >= 0 and j > i:
            return json.loads(raw[i:j])
    except Exception:
        pass
    return {"action": "UNCLEAR", "target": None, "weapon": None}
