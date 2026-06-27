"""Discord OAuth2 authentication helpers for the LoreForge dashboard."""

import os
from typing import Optional
from urllib.parse import urlencode

import httpx
from itsdangerous import URLSafeTimedSerializer
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from database.models import Character, GuildGM, GuildConfig
from database.session import get_db
from sqlalchemy import select


class RedirectException(Exception):
    """Raised to trigger a redirect response from inside helper functions."""
    def __init__(self, url: str, status_code: int = 302):
        self.url = url
        self.status_code = status_code

# ── Config from env ────────────────────────────────────────────────────────

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/dashboard/callback")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-me")
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "false").lower() == "true"

DISCORD_API = "https://discord.com/api/v10"
OAUTH2_URL = (
    f"https://discord.com/api/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&response_type=code"
    f"&scope=identify"
)

serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="lf-session")

SESSION_COOKIE = "lf_session"


# ── Session helpers ────────────────────────────────────────────────────────

def get_session(request: Request) -> Optional[dict]:
    """Extract and verify the signed session cookie. Returns None if invalid/missing."""
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    try:
        data = serializer.loads(raw, max_age=86400)  # 24 hours
        return data
    except Exception:
        return None


def require_session(request: Request):
    """Raise RedirectException to login if no valid session."""
    session = get_session(request)
    if session is None:
        raise RedirectException(url="/dashboard/login")
    return session


def require_guild(request: Request):
    """Raise RedirectException to home if no guild selected."""
    session = require_session(request)
    if "guild_id" not in session:
        raise RedirectException(url="/dashboard/")
    return session


def set_session_cookie(response: Response, data: dict):
    """Sign data and set the session cookie on the response."""
    signed = serializer.dumps(data)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=signed,
        max_age=86400,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="lax",
        path="/dashboard",
    )


def clear_session_cookie(response: Response):
    """Clear the session cookie."""
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/dashboard",
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="lax",
    )


# ── Discord API helpers ────────────────────────────────────────────────────

async def exchange_code(code: str) -> Optional[dict]:
    """Exchange an OAuth2 authorization code for an access token."""
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data=data,
            headers=headers,
        )
        if resp.status_code != 200:
            return None
        return resp.json()


async def get_discord_user(access_token: str) -> Optional[dict]:
    """Fetch user info from Discord using an access token."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{DISCORD_API}/users/@me", headers=headers)
        if resp.status_code != 200:
            return None
        return resp.json()


async def check_is_gm(user_id: int, guild_id: int) -> bool:
    """Check if a user has GM status in a guild (via GuildGM table)."""
    async with get_db() as db:
        result = await db.execute(
            select(GuildGM).where(
                GuildGM.guild_id == guild_id,
                GuildGM.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None


def get_avatar_url(user: dict) -> str:
    """Build a Discord CDN avatar URL from the user dict."""
    user_id = user["id"]
    avatar_hash = user.get("avatar")
    if avatar_hash:
        ext = "gif" if avatar_hash.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{ext}"
    discriminator = user.get("discriminator")
    if discriminator and discriminator != "0":
        default_index = int(discriminator) % 5
    else:
        default_index = (int(user_id) >> 22) % 6
    return f"https://cdn.discordapp.com/embed/avatars/{default_index}.png"
