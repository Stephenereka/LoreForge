"""GM Admin panel — world config, AI controls, approval queue, location editing."""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from typing import Optional

from database.models import GuildConfig, AIConfig, PendingApproval, Character, Location, GuildGM
from database.session import get_db
from dashboard.auth import require_guild, RedirectException
from dashboard.main import templates

router = APIRouter()


def require_gm(request: Request):
    session = require_guild(request)
    if not session.get("is_gm"):
        raise RedirectException(url="/dashboard/")
    return session


# ── Main admin page ────────────────────────────────────────────────────────

@router.get("/dashboard/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    session = require_gm(request)
    guild_id = session["guild_id"]

    try:
        async with get_db() as db:
            cfg_r = await db.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
            cfg = cfg_r.scalar_one_or_none()

            ai_r = await db.execute(select(AIConfig).where(AIConfig.guild_id == guild_id))
            ai_cfg = ai_r.scalar_one_or_none()

            # Pending approvals
            pend_r = await db.execute(
                select(PendingApproval).where(
                    PendingApproval.guild_id == guild_id,
                    PendingApproval.status == "pending",
                ).order_by(PendingApproval.requested_at.desc())
            )
            pending = pend_r.scalars().all()

            # GM roster
            gm_r = await db.execute(select(GuildGM).where(GuildGM.guild_id == guild_id))
            gms = gm_r.scalars().all()

    except Exception as e:
        return templates.TemplateResponse(
            request, "error.html",
            {"session": session, "title": "Admin Error", "message": str(e), "code": 0},
        )

    world = {
        "world_name": cfg.world_name if cfg else "LoreForge World",
        "world_map_url": cfg.world_map_url if cfg else "",
        "current_era": cfg.current_era if cfg else "",
        "gm_role_id": cfg.gm_role_id if cfg else "",
        "log_channel_id": cfg.log_channel_id if cfg else "",
        "gm_channel_id": cfg.gm_channel_id if cfg else "",
        "combat_channel_id": cfg.combat_channel_id if cfg else "",
        "session_recap_channel_id": cfg.session_recap_channel_id if cfg else "",
        "ai_mode_enabled": cfg.ai_mode_enabled if cfg else False,
    }
    ai = {
        "narration_enabled": ai_cfg.narration_enabled if ai_cfg else False,
        "narration_style": ai_cfg.narration_style if ai_cfg else "epic",
        "npc_ai_enabled": ai_cfg.npc_ai_enabled if ai_cfg else False,
        "session_summary_enabled": ai_cfg.session_summary_enabled if ai_cfg else False,
    }

    pending_list = []
    for p in pending:
        pending_list.append({
            "id": p.id,
            "character_name": p.character_name or f"Character #{p.character_id}",
            "character_id": p.character_id,
            "field_name": p.field_name,
            "old_value": p.old_value or "—",
            "new_value": p.new_value,
            "reason": p.reason or "",
            "requested_at": p.requested_at.strftime("%b %d, %Y %I:%M %p") if p.requested_at else "—",
        })

    return templates.TemplateResponse(
        request, "admin.html",
        {
            "session": session,
            "world": world,
            "ai": ai,
            "pending": pending_list,
            "gms": gms,
            "is_gm": True,
        },
    )


# ── World config save ──────────────────────────────────────────────────────

@router.post("/dashboard/admin/world")
async def admin_world_save(
    request: Request,
    world_name: str = Form("LoreForge World"),
    world_map_url: str = Form(""),
    current_era: str = Form(""),
    gm_role_id: str = Form(""),
    log_channel_id: str = Form(""),
    gm_channel_id: str = Form(""),
    combat_channel_id: str = Form(""),
    session_recap_channel_id: str = Form(""),
    ai_mode_enabled: Optional[str] = Form(None),
):
    session = require_gm(request)
    guild_id = session["guild_id"]
    user_id = session["user_id"]

    def to_bigint(v):
        try: return int(v) if v and v.strip() else None
        except: return None

    try:
        async with get_db() as db:
            cfg_r = await db.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
            cfg = cfg_r.scalar_one_or_none()
            if cfg is None:
                cfg = GuildConfig(guild_id=guild_id)
                db.add(cfg)

            cfg.world_name = world_name.strip() or "LoreForge World"
            cfg.world_map_url = world_map_url.strip() or None
            cfg.current_era = current_era.strip() or None
            cfg.gm_role_id = to_bigint(gm_role_id)
            cfg.log_channel_id = to_bigint(log_channel_id)
            cfg.gm_channel_id = to_bigint(gm_channel_id)
            cfg.combat_channel_id = to_bigint(combat_channel_id)
            cfg.session_recap_channel_id = to_bigint(session_recap_channel_id)
            cfg.ai_mode_enabled = ai_mode_enabled == "on"
            await db.commit()
    except Exception as e:
        return templates.TemplateResponse(
            request, "error.html",
            {"session": session, "title": "Save Failed", "message": str(e), "code": 0},
        )

    return RedirectResponse(url="/dashboard/admin?saved=world", status_code=303)


# ── AI config save ─────────────────────────────────────────────────────────

@router.post("/dashboard/admin/ai")
async def admin_ai_save(
    request: Request,
    narration_enabled: Optional[str] = Form(None),
    narration_style: str = Form("epic"),
    npc_ai_enabled: Optional[str] = Form(None),
    session_summary_enabled: Optional[str] = Form(None),
):
    session = require_gm(request)
    guild_id = session["guild_id"]
    user_id = session["user_id"]

    try:
        async with get_db() as db:
            ai_r = await db.execute(select(AIConfig).where(AIConfig.guild_id == guild_id))
            ai_cfg = ai_r.scalar_one_or_none()
            if ai_cfg is None:
                ai_cfg = AIConfig(guild_id=guild_id)
                db.add(ai_cfg)

            ai_cfg.narration_enabled = narration_enabled == "on"
            ai_cfg.narration_style = narration_style
            ai_cfg.npc_ai_enabled = npc_ai_enabled == "on"
            ai_cfg.session_summary_enabled = session_summary_enabled == "on"
            ai_cfg.updated_by = user_id
            await db.commit()
    except Exception as e:
        return templates.TemplateResponse(
            request, "error.html",
            {"session": session, "title": "Save Failed", "message": str(e), "code": 0},
        )

    return RedirectResponse(url="/dashboard/admin?saved=ai", status_code=303)


# ── Approval queue ─────────────────────────────────────────────────────────

@router.post("/dashboard/admin/approve/{approval_id}")
async def admin_approve(request: Request, approval_id: int):
    session = require_gm(request)
    guild_id = session["guild_id"]
    user_id = session["user_id"]

    try:
        async with get_db() as db:
            r = await db.execute(
                select(PendingApproval).where(
                    PendingApproval.id == approval_id,
                    PendingApproval.guild_id == guild_id,
                )
            )
            approval = r.scalar_one_or_none()
            if not approval:
                return RedirectResponse(url="/dashboard/admin", status_code=303)

            # Apply the change to the character
            char_r = await db.execute(
                select(Character).where(Character.id == approval.character_id)
            )
            char = char_r.scalar_one_or_none()
            if char:
                field = approval.field_name
                new_val = approval.new_value
                if hasattr(char, field):
                    col_type = type(getattr(char, field))
                    try:
                        if col_type == int: setattr(char, field, int(new_val))
                        elif col_type == float: setattr(char, field, float(new_val))
                        elif col_type == bool: setattr(char, field, new_val.lower() in ("true", "1", "yes"))
                        else: setattr(char, field, new_val)
                    except: pass

            from datetime import datetime
            approval.status = "approved"
            approval.reviewed_by = user_id
            approval.reviewed_at = datetime.utcnow()
            await db.commit()
    except Exception as e:
        return templates.TemplateResponse(
            request, "error.html",
            {"session": session, "title": "Approve Failed", "message": str(e), "code": 0},
        )

    return RedirectResponse(url="/dashboard/admin#approvals", status_code=303)


@router.post("/dashboard/admin/deny/{approval_id}")
async def admin_deny(request: Request, approval_id: int):
    session = require_gm(request)
    guild_id = session["guild_id"]
    user_id = session["user_id"]

    try:
        async with get_db() as db:
            r = await db.execute(
                select(PendingApproval).where(
                    PendingApproval.id == approval_id,
                    PendingApproval.guild_id == guild_id,
                )
            )
            approval = r.scalar_one_or_none()
            if approval:
                from datetime import datetime
                approval.status = "denied"
                approval.reviewed_by = user_id
                approval.reviewed_at = datetime.utcnow()
                await db.commit()
    except Exception as e:
        return templates.TemplateResponse(
            request, "error.html",
            {"session": session, "title": "Deny Failed", "message": str(e), "code": 0},
        )

    return RedirectResponse(url="/dashboard/admin#approvals", status_code=303)


# ── Location edit ──────────────────────────────────────────────────────────

@router.get("/dashboard/admin/location/{loc_id}", response_class=HTMLResponse)
async def admin_location_edit(request: Request, loc_id: int):
    session = require_gm(request)
    guild_id = session["guild_id"]

    try:
        async with get_db() as db:
            r = await db.execute(
                select(Location).where(Location.id == loc_id, Location.guild_id == guild_id)
            )
            loc = r.scalar_one_or_none()
            if not loc:
                raise RedirectException(url="/dashboard/map")
    except RedirectException:
        raise
    except Exception as e:
        return templates.TemplateResponse(
            request, "error.html",
            {"session": session, "title": "Error", "message": str(e), "code": 0},
        )

    return templates.TemplateResponse(
        request, "admin_location.html",
        {"session": session, "is_gm": True, "loc": {
            "id": loc.id,
            "name": loc.name,
            "description": loc.description or "",
            "short_description": loc.short_description or "",
            "location_type": loc.location_type,
            "biome": loc.biome or "",
            "danger_level": loc.danger_level,
            "is_safe": loc.is_safe,
            "is_hidden": loc.is_hidden,
            "is_indoors": loc.is_indoors,
            "map_x": loc.map_x,
            "map_y": loc.map_y,
            "image_url": loc.image_url or "",
            "ambient_sounds": loc.ambient_sounds or "",
            "population_density": loc.population_density or "sparse",
            "lighting": loc.lighting or "bright",
        }},
    )


@router.post("/dashboard/admin/location/{loc_id}")
async def admin_location_save(
    request: Request, loc_id: int,
    name: str = Form(...),
    description: str = Form(""),
    short_description: str = Form(""),
    location_type: str = Form("wilderness"),
    biome: str = Form(""),
    danger_level: int = Form(0),
    is_safe: Optional[str] = Form(None),
    is_hidden: Optional[str] = Form(None),
    is_indoors: Optional[str] = Form(None),
    map_x: float = Form(0.0),
    map_y: float = Form(0.0),
    image_url: str = Form(""),
    ambient_sounds: str = Form(""),
    population_density: str = Form("sparse"),
    lighting: str = Form("bright"),
):
    session = require_gm(request)
    guild_id = session["guild_id"]

    try:
        async with get_db() as db:
            r = await db.execute(
                select(Location).where(Location.id == loc_id, Location.guild_id == guild_id)
            )
            loc = r.scalar_one_or_none()
            if not loc:
                raise RedirectException(url="/dashboard/map")

            loc.name = name.strip()
            loc.description = description.strip()
            loc.short_description = short_description.strip() or None
            loc.location_type = location_type
            loc.biome = biome.strip() or None
            loc.danger_level = max(0, min(10, danger_level))
            loc.is_safe = is_safe == "on"
            loc.is_hidden = is_hidden == "on"
            loc.is_indoors = is_indoors == "on"
            loc.map_x = max(0.0, min(100.0, map_x))
            loc.map_y = max(0.0, min(100.0, map_y))
            loc.image_url = image_url.strip() or None
            loc.ambient_sounds = ambient_sounds.strip() or None
            loc.population_density = population_density
            loc.lighting = lighting
            await db.commit()
    except RedirectException:
        raise
    except Exception as e:
        return templates.TemplateResponse(
            request, "error.html",
            {"session": session, "title": "Save Failed", "message": str(e), "code": 0},
        )

    return RedirectResponse(url="/dashboard/map", status_code=303)
