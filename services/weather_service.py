import random
from datetime import datetime
from sqlalchemy import select
from database.session import get_db
from database.models import WeatherState

WEATHER_TYPES = ["clear", "cloudy", "rainy", "stormy", "foggy", "snowy", "windy", "scorching"]

TEMPERATURE_MAP = {
    "clear": "warm",
    "cloudy": "cool",
    "rainy": "cool",
    "stormy": "moderate",
    "foggy": "cool",
    "snowy": "freezing",
    "windy": "cold",
    "scorching": "scorching",
}

WEATHER_ICONS = {
    "clear": "☀️",
    "cloudy": "☁️",
    "rainy": "🌧️",
    "stormy": "⛈️",
    "foggy": "🌫️",
    "snowy": "❄️",
    "windy": "💨",
    "scorching": "🔥",
}

WEATHER_FLAVOR = {
    "clear": "The sky is clear and bright.",
    "cloudy": "Grey clouds blanket the sky.",
    "rainy": "Rain falls steadily from the heavens.",
    "stormy": "A furious storm rages — thunder shakes the ground!",
    "foggy": "Thick fog rolls in, reducing visibility to mere feet.",
    "snowy": "Snow falls gently, blanketing the world in white.",
    "windy": "Strong winds whip through the area, tearing at loose objects.",
    "scorching": "The heat is unbearable — the sun blazes with relentless fury.",
}

INDOOR_WEATHER_FLAVOR = {
    "clear": "Sunlight streams through the windows.",
    "cloudy": "The grey sky casts a pale light through the windows.",
    "rainy": "Rain patters against the windows and roof.",
    "stormy": "The storm howls outside — the walls tremble with each thunderclap.",
    "foggy": "Fog presses against the windows, obscuring the view.",
    "snowy": "Snowflakes drift past the windows, piling on the ledges.",
    "windy": "The wind rattles the windows in their frames.",
    "scorching": "The heat is oppressive even inside — fans and shade do little.",
}

WEATHER_COMBAT_EFFECTS = {
    "clear": {"ranged_disadvantage": False, "spell_failure_chance": 0, "movement_penalty": 0},
    "cloudy": {"ranged_disadvantage": False, "spell_failure_chance": 0, "movement_penalty": 0},
    "rainy": {"ranged_disadvantage": True, "spell_failure_chance": 0.05, "movement_penalty": 0, "flavor": "The rain obscures vision — ranged attacks are at disadvantage."},
    "stormy": {"ranged_disadvantage": True, "spell_failure_chance": 0.15, "movement_penalty": 0, "flavor": "The storm makes ranged attacks nearly impossible and spells may fizzle!"},
    "foggy": {"ranged_disadvantage": True, "spell_failure_chance": 0, "movement_penalty": 0, "flavor": "The fog limits visibility — ranged attacks are at disadvantage."},
    "snowy": {"ranged_disadvantage": False, "spell_failure_chance": 0, "movement_penalty": 5, "flavor": "Deep snow slows movement."},
    "windy": {"ranged_disadvantage": True, "spell_failure_chance": 0.1, "movement_penalty": 0, "flavor": "Gusting winds throw off ranged attacks and disrupt spellcasting."},
    "scorching": {"ranged_disadvantage": False, "spell_failure_chance": 0, "movement_penalty": 0, "flavor": "The heat is exhausting — characters without water protection suffer disadvantage on CON saves."},
}


async def get_weather(guild_id: int) -> dict:
    """Get current weather for a guild. Creates default if not exists."""
    async with get_db() as db:
        result = await db.execute(select(WeatherState).where(WeatherState.guild_id == guild_id))
        ws = result.scalar_one_or_none()

    if not ws:
        async with get_db() as db:
            ws = WeatherState(guild_id=guild_id)
            db.add(ws)
            await db.flush()

    weather_type = ws.weather_type or "clear"
    temperature = ws.temperature or TEMPERATURE_MAP.get(weather_type, "moderate")
    return {
        "weather_type": weather_type,
        "temperature": temperature,
        "icon": WEATHER_ICONS.get(weather_type, "☀️"),
        "flavor": WEATHER_FLAVOR.get(weather_type, ""),
        "combat_effects": WEATHER_COMBAT_EFFECTS.get(weather_type, {}),
        "changed_at": ws.changed_at,
    }


async def set_weather(guild_id: int, weather_type: str) -> dict:
    """GM override: set weather directly."""
    if weather_type not in WEATHER_TYPES:
        raise ValueError(f"Weather must be one of: {', '.join(WEATHER_TYPES)}")

    async with get_db() as db:
        result = await db.execute(select(WeatherState).where(WeatherState.guild_id == guild_id))
        ws = result.scalar_one_or_none()
        if not ws:
            ws = WeatherState(guild_id=guild_id, weather_type=weather_type)
            db.add(ws)
        else:
            ws.weather_type = weather_type
            ws.temperature = TEMPERATURE_MAP.get(weather_type, "moderate")
            ws.changed_at = datetime.utcnow()

    return await get_weather(guild_id)


async def random_weather_change(guild_id: int) -> dict:
    """Randomly shift weather for a guild."""
    async with get_db() as db:
        result = await db.execute(select(WeatherState).where(WeatherState.guild_id == guild_id))
        ws = result.scalar_one_or_none()

    if not ws:
        return await get_weather(guild_id)

    current = ws.weather_type or "clear"

    # Weather transition weights: stay, adjacent, random
    transition_matrix = {
        "clear": ["clear", "clear", "clear", "cloudy", "windy", "scorching"],
        "cloudy": ["cloudy", "cloudy", "clear", "rainy", "foggy", "windy"],
        "rainy": ["rainy", "rainy", "cloudy", "stormy", "foggy", "clear"],
        "stormy": ["stormy", "rainy", "rainy", "windy", "clear"],
        "foggy": ["foggy", "foggy", "cloudy", "rainy", "clear"],
        "snowy": ["snowy", "snowy", "cloudy", "clear", "windy"],
        "windy": ["windy", "windy", "cloudy", "stormy", "clear"],
        "scorching": ["scorching", "scorching", "cloudy", "windy", "clear"],
    }

    new_weather = random.choice(transition_matrix.get(current, WEATHER_TYPES))

    async with get_db() as db:
        result = await db.execute(select(WeatherState).where(WeatherState.guild_id == guild_id))
        ws = result.scalar_one_or_none()
        if ws:
            ws.weather_type = new_weather
            ws.temperature = TEMPERATURE_MAP.get(new_weather, "moderate")
            ws.changed_at = datetime.utcnow()

    return await get_weather(guild_id)


def get_weather_combat_effects(weather_type: str) -> dict:
    """Get combat modifiers for a given weather type."""
    return WEATHER_COMBAT_EFFECTS.get(weather_type, {})


def get_weather_flavor(weather_type: str, is_indoors: bool = False) -> str:
    """Get atmospheric flavor string for weather."""
    if is_indoors:
        return INDOOR_WEATHER_FLAVOR.get(weather_type, "")
    return WEATHER_FLAVOR.get(weather_type, "")
