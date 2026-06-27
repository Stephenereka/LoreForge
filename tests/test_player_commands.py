"""
Tests for player-facing commands:
market, achievements, bestiary, language, notifications, trade, titles, tutorial
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from conftest import make_interaction, make_character, make_db_session, db_context


# ── market ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_market_browse_empty():
    from cogs.market import market_browse
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.market.get_db", return_value=db_context(db)):
        await market_browse.callback(ix)
    ix.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_market_post_no_char():
    from cogs.market import market_post
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.market.get_db", return_value=db_context(db)):
        await market_post.callback(ix, item_name="Sword", price=100, quantity=1, description=None)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_market_mine_no_char():
    from cogs.market import market_mine
    ix = make_interaction()
    with patch("cogs.market._get_char", new=AsyncMock(return_value=None)):
        await market_mine.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True


# ── achievements ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_achievements_list_no_char():
    from cogs.achievements import achievements_list
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.achievements.get_db", return_value=db_context(db)):
        await achievements_list.callback(ix, character=None)
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_hall_achievements_empty():
    from cogs.achievements import hall_achievements
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.achievements.get_db", return_value=db_context(db)):
        await hall_achievements.callback(ix)
    ix.followup.send.assert_called_once()


# ── bestiary ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bestiary_list_empty():
    from cogs.bestiary import bestiary_list
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.bestiary.get_db", return_value=db_context(db)):
        await bestiary_list.callback(ix, creature_type="all", page=1)
    ix.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_bestiary_view_not_found():
    from cogs.bestiary import bestiary_view
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.bestiary.get_db", return_value=db_context(db)):
        await bestiary_view.callback(ix, name="Dragon")
    ix.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_bestiary_search_no_results():
    from cogs.bestiary import bestiary_search
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.bestiary.get_db", return_value=db_context(db)):
        await bestiary_search.callback(ix, query="zzzzz")
    ix.followup.send.assert_called_once()


# ── language ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_language_create_no_guild():
    from cogs.language import language_create
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await language_create.callback(ix, name="Elvish", script_type=None)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_language_list_empty():
    from cogs.language import language_list
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.language.get_db", return_value=db_context(db)):
        await language_list.callback(ix)
    ix.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_language_learn_no_char():
    from cogs.language import language_learn
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.language.get_db", return_value=db_context(db)):
        await language_learn.callback(ix, name="Elvish")
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True


# ── trade ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trade_request_self():
    from cogs.trade import trade_request
    ix = make_interaction(user_id=100)
    target = MagicMock()
    target.id = 100  # same as user
    target.bot = False
    await trade_request.callback(ix, user=target)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_trade_request_target_is_bot():
    from cogs.trade import trade_request
    ix = make_interaction(user_id=100)
    target = MagicMock()
    target.id = 200
    target.bot = True
    await trade_request.callback(ix, user=target)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_trade_cancel_no_active_trade():
    from cogs.trade import trade_cancel
    ix = make_interaction(user_id=100)
    with patch("cogs.trade.trade_sessions", {}):
        await trade_cancel.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True


# ── tutorial ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tutorial_start_no_guild():
    from cogs.tutorial import tutorial_start
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await tutorial_start.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_tutorial_gm_non_gm():
    from cogs.tutorial import tutorial_gm
    ix = make_interaction()
    with patch("cogs.tutorial.is_gm", new=AsyncMock(return_value=False)):
        await tutorial_gm.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True


# ── notifications ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notifications_configure_sends_view():
    from cogs.notifications import notifications_configure
    ix = make_interaction()
    config = MagicMock()
    config.faction_changes = True
    config.quest_objectives = True
    config.world_events = False
    config.npc_movements = False
    config.lore_unlocks = True
    with patch("cogs.notifications._get_or_create_config", new=AsyncMock(return_value=config)):
        await notifications_configure.callback(ix)
    ix.followup.send.assert_called_once()
