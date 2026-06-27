"""LoreForge Web Dashboard — FastAPI application."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from database.session import init_db
from dashboard.auth import get_session, RedirectException

# ── Templates ──────────────────────────────────────────────────────────────

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

from datetime import datetime
templates.env.globals["now"] = datetime.utcnow


# ── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB tables on startup."""
    try:
        await init_db()
        print("[Dashboard] DB initialized.")
    except Exception as e:
        print(f"[Dashboard] DB init skipped: {e}")
    yield


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LoreForge Dashboard",
    description="Web dashboard for the LoreForge Discord RPG bot.",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Static files ───────────────────────────────────────────────────────────

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/dashboard/static", StaticFiles(directory=static_dir), name="dashboard_static")


# ── Session injection middleware ───────────────────────────────────────────

class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        session = get_session(request)
        request.state.session = session or {}
        response = await call_next(request)
        return response


app.add_middleware(SessionMiddleware)


# ── Redirect exception handler ─────────────────────────────────────────────

@app.exception_handler(RedirectException)
async def redirect_exception_handler(request: Request, exc: RedirectException):
    return RedirectResponse(url=exc.url, status_code=exc.status_code)


# ── Import and register routers ────────────────────────────────────────────

from dashboard.routes import home, characters, lore, map as map_route, sessions, bestiary

app.include_router(home.router)
app.include_router(characters.router)
app.include_router(lore.router)
app.include_router(map_route.router)
app.include_router(sessions.router)
app.include_router(bestiary.router)


# ── 404 handler ────────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found(request: Request, exc):
    session = get_session(request)
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "session": session or {},
            "title": "The Path is Lost in Shadows...",
            "message": "404 — The page you seek does not exist in this realm.",
            "code": 404,
        },
        status_code=404,
    )


@app.exception_handler(500)
async def server_error(request: Request, exc):
    session = get_session(request)
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "session": session or {},
            "title": "The Weave is Broken",
            "message": "500 — A great disturbance in the weave. Try again later.",
            "code": 500,
        },
        status_code=500,
    )
