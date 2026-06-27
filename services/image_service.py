"""
Image generation service using Pollinations.ai free API.
No API key needed — returns direct image URLs.
"""

import urllib.parse
import random

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width=512&height=512&nologo=true&seed={seed}"


async def generate_image(prompt: str, seed: int | None = None) -> str:
    """
    Returns the Pollinations image URL (direct link). Does not download.
    Discord will fetch and display the image automatically from the URL.
    """
    if seed is None:
        seed = random.randint(1, 999999)
    encoded = urllib.parse.quote(prompt)
    return POLLINATIONS_URL.format(prompt=encoded, seed=seed)


async def generate_character_portrait(name: str, race: str, class_name: str, appearance: str = "") -> str:
    """Generate a fantasy character portrait."""
    prompt = (
        f"Fantasy RPG character portrait, {race} {class_name} named {name}, "
        f"{appearance}, detailed face, dramatic lighting, painterly style, dark fantasy"
    )
    return await generate_image(prompt)


async def generate_location_art(name: str, description: str, location_type: str = "") -> str:
    """Generate atmospheric location art."""
    prompt = (
        f"Fantasy {location_type or 'location'} called {name}, "
        f"{description}, atmospheric, wide shot, painterly, epic fantasy art"
    )
    return await generate_image(prompt)


async def generate_npc_portrait(name: str, race: str, title: str, appearance: str = "") -> str:
    """Generate an NPC portrait."""
    prompt = (
        f"Fantasy RPG character portrait, {race} {title or 'NPC'} named {name}, "
        f"{appearance}, detailed face, dark fantasy art style"
    )
    return await generate_image(prompt)
