"""Home, login, OAuth2 callback, guild selection."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy import select

from database.models import Character, GuildConfig, GuildGM
from database.session import get_db
from dashboard.auth import (
    get_session,
    require_session,
    set_session_cookie,
    clear_session_cookie,
    exchange_code,
    get_discord_user,
    get_avatar_url,
    OAUTH2_URL,
)
from dashboard.main import templates

router = APIRouter()


@router.get("/dashboard/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show the Discord OAuth2 login page."""
    session = get_session(request)
    if session:
        return RedirectResponse(url="/dashboard/", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "session": {}, "oauth_url": OAUTH2_URL},
    )


@router.get("/dashboard/logout")
async def logout(request: Request):
    """Clear session and redirect to login."""
    response = RedirectResponse(url="/dashboard/login", status_code=302)
    clear_session_cookie(response)
    return response


@router.get("/dashboard/callback")
async def oauth_callback(request: Request, code: str = None, error: str = None):
    """Handle Discord OAuth2 redirect."""
    if error or not code:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "session": {},
                "title": "OAuth Error",
                "message": f"Discord login failed: {error or 'No code received'}",
                "code": 0,
            },
        )

    # Exchange code for token
    token_data = await exchange_code(code)
    if not token_data:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "session": {},
                "title": "Token Exchange Failed",
                "message": "Could not complete login. Please try again.",
                "code": 0,
            },
        )

    access_token = token_data.get("access_token")
    user = await get_discord_user(access_token)
    if not user:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "session": {},
                "title": "User Fetch Failed",
                "message": "Could not fetch your Discord profile. Please try again.",
                "code": 0,
            },
        )

    # Build session data
    session_data = {
        "user_id": int(user["id"]),
        "username": user.get("global_name") or user["username"],
        "avatar": get_avatar_url(user),
        "access_token": access_token,  # short-lived, only for this request
    }

    response = RedirectResponse(url="/dashboard/", status_code=302)
    set_session_cookie(response, session_data)
    return response


@router.get("/dashboard/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Show guild selector (home page after login)."""
    session = require_session(request)
    user_id = session["user_id"]

    guilds = []
    try:
        async with get_db() as db:
            # Find guilds where user has a character OR is a GM
            char_result = await db.execute(
                select(Character.guild_id).where(
                    Character.user_id == user_id,
                    Character.is_active == True,
                ).distinct()
            )
            char_guild_ids = {row[0] for row in char_result.fetchall()}

            gm_result = await db.execute(
                select(GuildGM.guild_id).where(GuildGM.user_id == user_id)
            )
            gm_guild_ids = {row[0] for row in gm_result.fetchall()}

            all_guild_ids = char_guild_ids | gm_guild_ids

            if all_guild_ids:
                config_result = await db.execute(
                    select(GuildConfig).where(
                        GuildConfig.guild_id.in_(all_guild_ids)
                    )
                )
                guilds = config_result.scalars().all()
            else:
                guilds = []
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "session": session,
                "title": "Database Error",
                "message": f"Could not load your guilds: {str(e)}",
                "code": 0,
            },
        )

    return templates.TemplateResponse(
        "home.html",
        {"request": request, "session": session, "guilds": guilds},
    )


@router.get("/dashboard/select-guild")
async def select_guild(request: Request, guild_id: int):
    """Select a guild and store it in the session."""
    session = require_session(request)
    session["guild_id"] = guild_id
    session["is_gm"] = False

    # Check if user is GM
    try:
        from dashboard.auth import check_is_gm
        session["is_gm"] = await check_is_gm(session["user_id"], guild_id)
    except Exception:
        pass

    response = RedirectResponse(url="/dashboard/characters", status_code=302)
    set_session_cookie(response, session)
    return response


@router.get("/dashboard/select-guild-form")
async def select_guild_form(request: Request):
    """Simple guild selector form (fallback for JS-disabled users)."""
    session = require_session(request)
    user_id = session["user_id"]

    guilds = []
    try:
        async with get_db() as db:
            char_result = await db.execute(
                select(Character.guild_id).where(
                    Character.user_id == user_id,
                    Character.is_active == True,
                ).distinct()
            )
            char_guild_ids = {row[0] for row in char_result.fetchall()}

            gm_result = await db.execute(
                select(GuildGM.guild_id).where(GuildGM.user_id == user_id)
            )
            gm_guild_ids = {row[0] for row in gm_result.fetchall()}

            all_guild_ids = char_guild_ids | gm_guild_ids
            if all_guild_ids:
                config_result = await db.execute(
                    select(GuildConfig).where(
                        GuildConfig.guild_id.in_(all_guild_ids)
                    )
                )
                guilds = config_result.scalars().all()
    except Exception:
        guilds = []

    return templates.TemplateResponse(
        "home.html",
        {"request": request, "session": session, "guilds": guilds},
    )
