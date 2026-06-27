"""Tests for cogs/combat.py — command guards."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from conftest import make_interaction, make_character


# ── /combat status guard ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_combat_status_no_guild():
    from cogs.combat import combat_status
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    with patch("cogs.combat._sessions", {}):
        await combat_status.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_combat_status_no_active_combat():
    from cogs.combat import combat_status
    ix = make_interaction()
    ix.channel_id = 999
    with patch("cogs.combat._sessions", {}):
        await combat_status.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True


# ── /combat start guard ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_combat_start_no_guild():
    from cogs.combat import combat_start
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    fight_type = MagicMock()
    fight_type.value = "dnd"
    with patch("cogs.combat._sessions", {}):
        await combat_start.callback(ix, title="Test Combat", fight_type=fight_type, invite=None)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_combat_start_already_active():
    from cogs.combat import combat_start
    ix = make_interaction()
    ix.channel_id = 123
    fight_type = MagicMock()
    fight_type.value = "dnd"
    fake_session = MagicMock()
    with patch("cogs.combat._sessions", {123: fake_session}):
        await combat_start.callback(ix, title="Test", fight_type=fight_type, invite=None)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_combat_start_no_character():
    from cogs.combat import combat_start
    ix = make_interaction()
    ix.channel_id = 123
    fight_type = MagicMock()
    fight_type.value = "dnd"
    with patch("cogs.combat._sessions", {}), \
         patch("cogs.combat.resolve_character", new=AsyncMock(return_value=(None, []))):
        await combat_start.callback(ix, title="Test", fight_type=fight_type, invite=None)
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True


# ── /combat end guard ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_combat_end_no_guild():
    from cogs.combat import combat_end
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    with patch("cogs.combat._sessions", {}):
        await combat_end.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_combat_end_no_active_combat():
    from cogs.combat import combat_end
    ix = make_interaction()
    ix.channel_id = 999
    with patch("cogs.combat._sessions", {}):
        await combat_end.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True


# ── /combat join guard ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_combat_join_no_guild():
    from cogs.combat import combat_join
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    with patch("cogs.combat._sessions", {}):
        await combat_join.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True
