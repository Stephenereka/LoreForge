"""Tests for cogs/shop.py — buy, sell, browse commands."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from conftest import make_interaction, make_character, make_db_session, db_context


# ── /shop browse ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shop_browse_no_guild():
    from cogs.shop import shop_browse
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await shop_browse.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_shop_browse_with_guild():
    from cogs.shop import shop_browse
    ix = make_interaction()
    await shop_browse.callback(ix)
    ix.response.send_message.assert_called_once()
    embed = ix.response.send_message.call_args.kwargs.get("embed")
    assert embed is not None


# ── /shop buy ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shop_buy_no_guild():
    from cogs.shop import shop_buy
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await shop_buy.callback(ix, item="longsword")
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_shop_buy_unknown_item():
    from cogs.shop import shop_buy
    ix = make_interaction()
    await shop_buy.callback(ix, item="thisisnotanitem")
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_shop_buy_no_character():
    from cogs.shop import shop_buy
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.shop.get_db", return_value=db_context(db)):
        await shop_buy.callback(ix, item="longsword")
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_shop_buy_insufficient_funds():
    from cogs.shop import shop_buy
    ix = make_interaction()
    char = make_character(balance=0)
    db = make_db_session(scalar_result=char)
    with patch("cogs.shop.get_db", return_value=db_context(db)):
        await shop_buy.callback(ix, item="greatsword")  # costs 50
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_shop_buy_success():
    from cogs.shop import shop_buy
    ix = make_interaction()
    char = make_character(balance=1000, inventory=[])
    db = make_db_session(scalar_result=char)
    with patch("cogs.shop.get_db", return_value=db_context(db)):
        await shop_buy.callback(ix, item="dagger")
    ix.response.send_message.assert_called_once()


# ── /shop sell ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shop_sell_no_guild():
    from cogs.shop import shop_sell
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await shop_sell.callback(ix, item="dagger")
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_shop_sell_no_character():
    from cogs.shop import shop_sell
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.shop.get_db", return_value=db_context(db)):
        await shop_sell.callback(ix, item="dagger")
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_shop_sell_item_not_in_inventory():
    from cogs.shop import shop_sell
    ix = make_interaction()
    char = make_character(inventory=[])
    db = make_db_session(scalar_result=char)
    with patch("cogs.shop.get_db", return_value=db_context(db)):
        await shop_sell.callback(ix, item="dagger")
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True
