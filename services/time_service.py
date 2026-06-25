import math
from datetime import datetime, timezone
from sqlalchemy import select
from database.session import get_db
from database.models import WorldTime

# ── Time of day names ────────────────────────────────────────────────────────
TIME_OF_DAY = {
    (5, 7): "Dawn",
    (8, 11): "Morning",
    (12, 14): "Midday",
    (15, 17): "Afternoon",
    (18, 20): "Dusk",
    (21, 22): "Evening",
    (23, 23): "Midnight",
    (0, 4): "Deep Night",
}

# Hours per time-of-day segment (for get_time_of_day_name)
TIME_SEGMENTS = {
    "Dawn": (5, 7),
    "Morning": (8, 11),
    "Midday": (12, 14),
    "Afternoon": (15, 17),
    "Dusk": (18, 20),
    "Evening": (21, 22),
    "Midnight": (23, 23),
    "Deep Night": (0, 4),
}

SEASONS = {
    "spring": (3, 5),
    "summer": (6, 8),
    "autumn": (9, 11),
    "winter": (12, 2),
}

# 1 real hour = 2 in-world hours
TIME_SCALE = 2.0


def get_time_of_day_name(hour: int) -> str:
    for name, (start, end) in TIME_SEGMENTS.items():
        if hour >= start and hour <= end:
            return name
        if name == "Deep Night":
            if hour == 0 or name == "Deep Night" and (hour >= start or hour <= end):
                return "Deep Night"
    return "Midday"


def is_night(hour: int) -> bool:
    name = get_time_of_day_name(hour)
    return name in ("Dusk", "Evening", "Midnight", "Deep Night")


def hour_to_emoji(hour: int) -> str:
    name = get_time_of_day_name(hour)
    emojis = {
        "Dawn": "🌅", "Morning": "☀️", "Midday": "🌞", "Afternoon": "🌤️",
        "Dusk": "🌆", "Evening": "🌃", "Midnight": "🌙", "Deep Night": "🌑",
    }
    return emojis.get(name, "☀️")


def get_season_name(month: int) -> str:
    for season, (start, end) in SEASONS.items():
        if start <= end:
            if start <= month <= end:
                return season
        else:
            if month >= start or month <= end:
                return season
    return "spring"


def season_emoji(season: str) -> str:
    return {"spring": "🌸", "summer": "☀️", "autumn": "🍂", "winter": "❄️"}.get(season, "🌸")


async def get_world_time(guild_id: int) -> dict:
    """Get the current world time for a guild. Returns a dict with all time fields."""
    async with get_db() as db:
        result = await db.execute(select(WorldTime).where(WorldTime.guild_id == guild_id))
        wt = result.scalar_one_or_none()

    if not wt:
        async with get_db() as db:
            wt = WorldTime(guild_id=guild_id)
            db.add(wt)
            await db.flush()

    hour, day, month, year = wt.current_hour, wt.current_day, wt.current_month, wt.current_year
    season = get_season_name(month)
    time_name = get_time_of_day_name(hour)
    night = is_night(hour)

    return {
        "hour": hour,
        "day": day,
        "month": month,
        "year": year,
        "season": season,
        "time_of_day": time_name,
        "is_night": night,
        "mode": wt.mode,
        "emoji": hour_to_emoji(hour),
        "season_emoji": season_emoji(season),
    }


async def recalc_automatic_time(guild_id: int):
    """In automatic mode, recalculate current in-world time from the real clock."""
    async with get_db() as db:
        result = await db.execute(select(WorldTime).where(WorldTime.guild_id == guild_id))
        wt = result.scalar_one_or_none()
        if not wt or wt.mode != "automatic":
            return

        now = datetime.now(timezone.utc)
        if wt.last_real_timestamp is None:
            wt.last_real_timestamp = now
            return

        elapsed_real_seconds = (now - wt.last_real_timestamp).total_seconds()
        elapsed_world_hours = (elapsed_real_seconds / 3600) * TIME_SCALE

        if elapsed_world_hours < 1:
            return

        wt.last_real_timestamp = now
        total_minutes = wt.current_hour * 60 + elapsed_world_hours * 60
        total_hours = total_minutes / 60

        days_passed = int(total_hours // 24)
        new_hour = int(total_hours % 24)

        wt.current_hour = new_hour
        wt.current_day += days_passed

        while wt.current_day > 30:
            wt.current_day -= 30
            wt.current_month += 1
            if wt.current_month > 12:
                wt.current_month = 1
                wt.current_year += 1

        wt.season = get_season_name(wt.current_month)


async def advance_time(guild_id: int, hours: int) -> dict:
    """Advance world time manually (manual mode only). Returns new time dict."""
    async with get_db() as db:
        result = await db.execute(select(WorldTime).where(WorldTime.guild_id == guild_id))
        wt = result.scalar_one_or_none()
        if not wt:
            wt = WorldTime(guild_id=guild_id)
            db.add(wt)

        total_hours = wt.current_hour + hours
        days_passed = total_hours // 24
        new_hour = total_hours % 24

        wt.current_hour = new_hour
        wt.current_day += days_passed

        while wt.current_day > 30:
            wt.current_day -= 30
            wt.current_month += 1
            if wt.current_month > 12:
                wt.current_month = 1
                wt.current_year += 1

        wt.season = get_season_name(wt.current_month)

    return await get_world_time(guild_id)


async def set_time_mode(guild_id: int, mode: str) -> bool:
    """Switch between 'automatic' and 'manual' time mode."""
    if mode not in ("automatic", "manual"):
        return False
    async with get_db() as db:
        result = await db.execute(select(WorldTime).where(WorldTime.guild_id == guild_id))
        wt = result.scalar_one_or_none()
        if not wt:
            wt = WorldTime(guild_id=guild_id, mode=mode)
            db.add(wt)
        else:
            wt.mode = mode
            if mode == "automatic":
                wt.last_real_timestamp = datetime.now(timezone.utc)
    return True


def get_time_flavor(time_name: str, is_indoors: bool, weather_type: str = "clear"):
    """Generate atmospheric flavor text based on time of day."""
    indoor_suffix = "You hear the sounds of the outside world muffled through the walls."
    weather_sounds = {
        "rainy": "Rain patters against the windows and roof.",
        "stormy": "Thunder rumbles in the distance, shaking the very walls.",
        "windy": "The wind howls outside, rattling shutters.",
        "snowy": "Snow falls silently beyond the frost-covered windows.",
        "foggy": "A thick Fog presses against the windows, obscuring the outside world.",
        "scorching": "The heat is oppressive even inside — the sun bakes the world outside.",
    }

    time_flavors = {
        "Dawn": "The first light of dawn paints the sky in shades of amber and rose.",
        "Morning": "The morning sun casts long, golden shadows across the land.",
        "Midday": "The sun stands high overhead, casting short, sharp shadows.",
        "Afternoon": "The afternoon sun begins its slow descent toward the horizon.",
        "Dusk": "The sky blazes with the fiery colors of sunset as day gives way to night.",
        "Evening": "Stars begin to pierce the deepening blue of the evening sky.",
        "Midnight": "The moon hangs at its zenith, casting silver light upon the world.",
        "Deep Night": "The deepest hour of night — all is still and dark beneath the stars.",
    }

    base = time_flavors.get(time_name, "")
    if is_indoors:
        indoor = "Inside, the world outside is a distant murmur."
        if weather_type in weather_sounds:
            indoor = weather_sounds[weather_type] + " " + indoor_suffix
        return f"{indoor}"
    else:
        weather_line = ""
        if weather_type in weather_sounds:
            weather_line = weather_sounds[weather_type] + " "
        return f"{weather_line}{base}"
