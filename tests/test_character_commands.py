"""Tests for cogs/character.py — command guards and helpers."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from conftest import make_interaction, make_character, make_db_session, db_context
from cogs.character import RACES, CLASSES, STANDARD_ARRAY, MAX_CHARACTERS


# ── Data structure sanity ─────────────────────────────────────────────────────

def test_all_races_have_stat_bonuses():
    for race, bonuses in RACES.items():
        assert isinstance(bonuses, dict), f"{race} should have a dict of bonuses"
        assert len(bonuses) > 0, f"{race} has no stat bonuses"

def test_all_classes_have_hit_die():
    for cls, data in CLASSES.items():
        assert "hit_die" in data, f"{cls} missing hit_die"
        assert data["hit_die"] in (6, 8, 10, 12), f"{cls} has unexpected hit_die {data['hit_die']}"

def test_all_classes_have_saves():
    for cls, data in CLASSES.items():
        assert "saves" in data, f"{cls} missing saves"
        assert len(data["saves"]) == 2, f"{cls} should have 2 saving throws"

def test_standard_array_has_six_values():
    assert len(STANDARD_ARRAY) == 6

def test_standard_array_sorted_descending():
    assert STANDARD_ARRAY == sorted(STANDARD_ARRAY, reverse=True)

def test_max_characters_is_positive():
    assert MAX_CHARACTERS > 0


# ── /character create guards ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_character_create_no_guild():
    from cogs.character import character_create
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await character_create.callback(ix, name="Hero")
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_character_create_name_too_short():
    from cogs.character import character_create
    ix = make_interaction()
    await character_create.callback(ix, name="A")
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_character_create_name_too_long():
    from cogs.character import character_create
    ix = make_interaction()
    await character_create.callback(ix, name="A" * 33)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_character_create_max_reached():
    from cogs.character import character_create
    ix = make_interaction()
    chars = [make_character(), make_character(), make_character()]
    with patch("cogs.character.get_characters", new=AsyncMock(return_value=chars)):
        await character_create.callback(ix, name="NewHero")
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_character_create_valid_name_shows_wizard():
    from cogs.character import character_create
    ix = make_interaction()
    with patch("cogs.character.get_characters", new=AsyncMock(return_value=[])):
        await character_create.callback(ix, name="Aragorn")
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()


# ── /character list guard ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_character_list_no_guild():
    from cogs.character import character_list
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await character_list.callback(ix, public=False)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_character_list_no_chars():
    from cogs.character import character_list
    ix = make_interaction()
    db = make_db_session(scalars_result=[])
    with patch("cogs.character.get_db", return_value=db_context(db)):
        await character_list.callback(ix, public=False)
    ix.response.send_message.assert_called_once()


# ── /character sheet guard ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_character_sheet_no_guild():
    from cogs.character import character_sheet
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await character_sheet.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_character_sheet_no_char():
    from cogs.character import character_sheet
    ix = make_interaction()
    with patch("cogs.character.resolve_character", new=AsyncMock(return_value=(None, []))):
        await character_sheet.callback(ix)
    ix.followup.send.assert_called_once()


# ── /character use guard ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_character_use_no_guild():
    from cogs.character import character_use
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await character_use.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_character_use_no_chars():
    from cogs.character import character_use
    ix = make_interaction()
    with patch("cogs.character.get_characters", new=AsyncMock(return_value=[])):
        await character_use.callback(ix)
    ix.followup.send.assert_called_once()


# ── /character delete guard ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_character_delete_no_guild():
    from cogs.character import character_delete
    ix = make_interaction(guild_id=None)
    ix.guild_id = None
    await character_delete.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True
