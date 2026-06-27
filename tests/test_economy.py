"""Tests for cogs/economy.py — helper functions and command guards."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from conftest import make_interaction, make_character, make_db_session, db_context
from cogs.economy import _daily_amount


# ── _daily_amount pure function ───────────────────────────────────────────────

def test_daily_amount_day1():
    assert _daily_amount(1) == 200

def test_daily_amount_day2():
    assert _daily_amount(2) == 350

def test_daily_amount_day3():
    assert _daily_amount(3) == 500

def test_daily_amount_day4():
    assert _daily_amount(4) == 750

def test_daily_amount_day5_capped():
    assert _daily_amount(5) == 750

def test_daily_amount_day100_capped():
    assert _daily_amount(100) == 750


# ── /economy balance command ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_balance_no_guild():
    from cogs.economy import economy_balance
    interaction = make_interaction(guild_id=None)
    interaction.guild_id = None

    await economy_balance.callback(interaction)

    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_balance_no_character():
    from cogs.economy import economy_balance
    interaction = make_interaction()
    db = make_db_session(scalar_result=None)

    with patch("cogs.economy.get_db", return_value=db_context(db)):
        await economy_balance.callback(interaction)

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0] if interaction.response.send_message.call_args.args else ""
    assert "create" in msg.lower() or "don't have" in msg.lower()


@pytest.mark.asyncio
async def test_balance_with_character():
    from cogs.economy import economy_balance
    interaction = make_interaction()
    char = make_character(balance=1000, gold=50)
    db = make_db_session(scalar_result=char)

    with patch("cogs.economy.get_db", return_value=db_context(db)):
        await economy_balance.callback(interaction)

    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args.kwargs
    embed = call_kwargs.get("embed")
    assert embed is not None
    assert "1000" in embed.description or "Balance" in embed.title
