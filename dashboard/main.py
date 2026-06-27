"""LoreForge Web Dashboard — FastAPI application."""

import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database.session import init_db
from dashboard.auth import get_session, RedirectException

# ── Templates ──────────────────────────────────────────────────────────────

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)
templates.env.globals["now"] = datetime.utcnow


# ── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        print("[Dashboard] DB initialized.")
    except Exception as e:
        print(f"[Dashboard] DB init skipped: {e}")
    yield


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LoreForge Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Static files ───────────────────────────────────────────────────────────

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/dashboard/static", StaticFiles(directory=static_dir), name="dashboard_static")


# ── Exception handlers ─────────────────────────────────────────────────────

@app.exception_handler(RedirectException)
async def redirect_exception_handler(request: Request, exc: RedirectException):
    return RedirectResponse(url=exc.url, status_code=exc.status_code)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"[Dashboard] Unhandled exception on {request.url}:\n{tb}")
    try:
        session = get_session(request)
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "session": session or {},
                "title": "The Weave is Broken",
                "message": f"500 — {type(exc).__name__}: {exc}",
                "code": 500,
            },
            status_code=500,
        )
    except Exception as inner:
        print(f"[Dashboard] Error handler also failed: {inner}")
        return PlainTextResponse(f"500 — {type(exc).__name__}: {exc}\n\nHandler error: {inner}", status_code=500)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    try:
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
    except Exception as e:
        return PlainTextResponse(f"404 — {request.url.path}", status_code=404)


# ── Routers ────────────────────────────────────────────────────────────────

from dashboard.routes import home, characters, lore, map as map_route, sessions, bestiary, admin

app.include_router(home.router)
app.include_router(characters.router)
app.include_router(lore.router)
app.include_router(map_route.router)
app.include_router(sessions.router)
app.include_router(bestiary.router)
app.include_router(admin.router)
