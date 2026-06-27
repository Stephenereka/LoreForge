"""
Tests for world-building commands:
housing, events, sessions, timeline, religion, investigation, encounter
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from conftest import make_interaction, make_character, make_db_session, db_context


# ── housing ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_house_view_no_guild():
    from cogs.housing import house_view
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await house_view.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_house_view_no_char():
    from cogs.housing import house_view
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.housing.get_db", return_value=db_context(db)):
        await house_view.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_house_browse_sends_embed():
    from cogs.housing import house_browse
    ix = make_interaction()
    await house_browse.callback(ix)
    ix.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_house_buy_no_guild():
    from cogs.housing import house_buy
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await house_buy.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_house_buy_no_char():
    from cogs.housing import house_buy
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.housing.get_db", return_value=db_context(db)):
        await house_buy.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True


# ── events ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_create_non_gm():
    from cogs.events import event_create
    ix = make_interaction()
    with patch("cogs.events.is_gm", new=AsyncMock(return_value=False)):
        await event_create.callback(ix, name="Festival", datetime_str="2026-07-01 18:00")
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_event_list_empty():
    from cogs.events import event_list
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.events.get_db", return_value=db_context(db)):
        await event_list.callback(ix)
    ix.response.send_message.assert_called_once()


# ── sessions ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_start_non_gm():
    from cogs.sessions import session_start
    ix = make_interaction()
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await session_start.callback(ix, title="Session 1")
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_session_end_non_gm():
    from cogs.sessions import session_end
    ix = make_interaction()
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await session_end.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_session_log_no_sessions():
    from cogs.sessions import session_log
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.sessions.get_db", return_value=db_context(db)):
        await session_log.callback(ix)
    ix.followup.send.assert_called_once()


# ── timeline ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_view_empty():
    from cogs.timeline import timeline_view
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.timeline.get_db", return_value=db_context(db)):
        await timeline_view.callback(ix, page=1)
    ix.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_timeline_add_non_gm():
    from cogs.timeline import timeline_add
    ix = make_interaction()
    with patch("cogs.timeline.is_gm", new=AsyncMock(return_value=False)):
        await timeline_add.callback(ix, title="Battle of X", description="A great battle", era=None)
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_timeline_era_non_gm():
    from cogs.timeline import timeline_era
    ix = make_interaction()
    with patch("cogs.timeline.is_gm", new=AsyncMock(return_value=False)):
        await timeline_era.callback(ix, era_name="Age of Chaos")
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True


# ── religion ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_religion_create_non_gm():
    from cogs.religion import religion_create
    ix = make_interaction()
    with patch("cogs.religion.is_gm", new=AsyncMock(return_value=False)):
        await religion_create.callback(ix, name="Sol", deity_name=None, domains=None)
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_religion_list_empty():
    from cogs.religion import religion_list
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.religion.get_db", return_value=db_context(db)):
        await religion_list.callback(ix)
    ix.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_religion_view_not_found():
    from cogs.religion import religion_view
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.religion.get_db", return_value=db_context(db)):
        await religion_view.callback(ix, name="NonExistent")
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True


# ── investigation ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_investigation_start_non_gm():
    from cogs.investigation import investigation_start
    ix = make_interaction()
    with patch("cogs.investigation.is_gm", new=AsyncMock(return_value=False)):
        await investigation_start.callback(ix, name="The Murder", description="Someone is dead")
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_investigation_list_empty():
    from cogs.investigation import investigation_list
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.investigation.get_db", return_value=db_context(db)):
        await investigation_list.callback(ix)
    ix.followup.send.assert_called_once()


# ── encounter ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_encounter_npc_non_gm():
    from cogs.encounter import encounter_npc
    ix = make_interaction()
    player = MagicMock()
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await encounter_npc.callback(ix, npc_name="Bandit", player=player)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_encounter_boss_non_gm():
    from cogs.encounter import encounter_boss
    ix = make_interaction()
    player = MagicMock()
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await encounter_boss.callback(ix, boss_name="Dragon", player=player)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True
