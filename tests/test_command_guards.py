"""
Tests for the no-guild and no-character guard patterns that appear in most cogs.
All app_commands.command-decorated functions must be called via .callback() in tests
since discord.py wraps them in a Command object.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from conftest import make_interaction, make_character, make_db_session, db_context


# ── helpers ───────────────────────────────────────────────────────────────────

def no_guild_interaction():
    ix = make_interaction()
    ix.guild_id = None
    return ix


def assert_ephemeral_error(interaction):
    """Assert that the command sent exactly one ephemeral reply."""
    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert kwargs.get("ephemeral") is True, "Expected ephemeral=True on error response"


# ── economy commands ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_economy_balance_no_guild():
    from cogs.economy import economy_balance
    ix = no_guild_interaction()
    await economy_balance.callback(ix)
    assert_ephemeral_error(ix)


@pytest.mark.asyncio
async def test_economy_balance_no_char():
    from cogs.economy import economy_balance
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.economy.get_db", return_value=db_context(db)):
        await economy_balance.callback(ix)
    assert_ephemeral_error(ix)


# ── rest commands ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rest_short_no_guild():
    from cogs.rest import rest_short
    ix = no_guild_interaction()
    await rest_short.callback(ix)
    assert_ephemeral_error(ix)


@pytest.mark.asyncio
async def test_rest_short_no_char():
    from cogs.rest import rest_short
    ix = make_interaction()
    with patch("cogs.rest._sessions", {}), \
         patch("cogs.rest.resolve_character", new=AsyncMock(return_value=(None, []))):
        await rest_short.callback(ix)
    assert_ephemeral_error(ix)


# ── party commands ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_party_create_no_char():
    from cogs.party import party_create
    ix = make_interaction()
    with patch("cogs.party.get_active_character", new=AsyncMock(return_value=None)):
        await party_create.callback(ix, name="My Party")
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True


# ── quest commands ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quest_list_no_char():
    from cogs.quest import quest_list
    ix = make_interaction()
    with patch("cogs.quest.get_active_character", new=AsyncMock(return_value=None)):
        await quest_list.callback(ix)
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True


# ── location commands ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_loc_view_no_results():
    from cogs.location import loc_view
    ix = make_interaction()
    db = make_db_session(scalar_result=None)
    with patch("cogs.location.get_db", return_value=db_context(db)):
        await loc_view.callback(ix, name="Nowhere")
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True


# ── lore commands ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lore_list_returns():
    from cogs.lore import lore_list
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.lore.get_db", return_value=db_context(db)), \
         patch("cogs.lore.is_gm", new=AsyncMock(return_value=False)):
        await lore_list.callback(ix, category=None)
    ix.response.send_message.assert_called_once()


# ── npc commands — GM check ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_npc_create_non_gm():
    from cogs.npc import npc_create
    ix = make_interaction()
    with patch("cogs.npc.is_gm", new=AsyncMock(return_value=False)):
        await npc_create.callback(ix, name="Villain", location=None)
    assert_ephemeral_error(ix)


# ── faction commands ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_faction_list_no_results():
    from cogs.faction import faction_list
    ix = make_interaction()
    db = make_db_session(scalars_result=[], scalar_result=None)
    with patch("cogs.faction.get_db", return_value=db_context(db)):
        await faction_list.callback(ix)
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True
