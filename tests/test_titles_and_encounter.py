"""Tests for cogs/titles.py (cog-class commands) and cogs/encounter.py (pure helpers)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from conftest import make_interaction, make_character, make_db_session, db_context


# ── TitlesCog — cog-method commands ──────────────────────────────────────────

def make_titles_cog():
    from cogs.titles import TitlesCog
    bot = MagicMock()
    return TitlesCog(bot)


@pytest.mark.asyncio
async def test_title_list_no_char():
    cog = make_titles_cog()
    ix = make_interaction()
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    with patch("cogs.titles.get_db", return_value=cm):
        await cog.title_list.callback(cog, ix)
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_title_set_no_char():
    cog = make_titles_cog()
    ix = make_interaction()
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    with patch("cogs.titles.get_db", return_value=cm):
        await cog.title_set.callback(cog, ix, title_name="The Great")
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_title_clear_no_char():
    cog = make_titles_cog()
    ix = make_interaction()
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    with patch("cogs.titles.get_db", return_value=cm):
        await cog.title_clear.callback(cog, ix)
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()
    assert ix.followup.send.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_title_view_char_not_found():
    cog = make_titles_cog()
    ix = make_interaction()
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=result_mock)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    with patch("cogs.titles.get_db", return_value=cm):
        await cog.title_view.callback(cog, ix, character_name="NonExistentHero")
    ix.response.defer.assert_called_once()
    ix.followup.send.assert_called_once()


# ── encounter pure helpers ────────────────────────────────────────────────────

from cogs.encounter import _build_npc_combatant, _build_boss_combatant, _roll_damage
from services.combat_engine import Combatant


def _make_npc():
    npc = MagicMock()
    npc.id = 1
    npc.name = "Bandit"
    npc.proxy_name = "Bandit"
    npc.hp_max = 30
    npc.hp_current = 30
    npc.armor_class = 13
    npc.attack_bonus = 3
    npc.damage_dice = "1d6"
    npc.damage_bonus = 2
    npc.xp_value = 100
    npc.is_dead = False
    return npc


def _make_boss():
    boss = MagicMock()
    boss.id = 1
    boss.name = "Dragon"
    boss.title = "Ancient Dragon"
    boss.hp_max = 300
    boss.armor_class = 18
    boss.attack_bonus = 8
    boss.damage_dice = "2d10"
    boss.damage_bonus = 5
    boss.xp_value = 5000
    return boss


def test_build_npc_combatant_returns_combatant():
    npc = _make_npc()
    c = _build_npc_combatant(npc)
    assert isinstance(c, Combatant)
    assert c.name == "Bandit"
    assert not c.is_player
    assert c.hp_max == 30
    assert c.armor_class == 13

def test_build_npc_combatant_id_format():
    npc = _make_npc()
    c = _build_npc_combatant(npc)
    assert c.id.startswith("npc:")

def test_build_npc_combatant_level_derived():
    npc = _make_npc()
    npc.xp_value = 100
    c = _build_npc_combatant(npc)
    assert c.level >= 1

def test_build_boss_combatant_returns_combatant():
    boss = _make_boss()
    c = _build_boss_combatant(boss)
    assert isinstance(c, Combatant)
    assert c.name == "Ancient Dragon"
    assert not c.is_player
    assert c.hp_max == 300
    assert c.armor_class == 18

def test_build_boss_combatant_id_format():
    boss = _make_boss()
    c = _build_boss_combatant(boss)
    assert c.id.startswith("boss:")

def test_roll_damage_basic():
    for _ in range(30):
        result = _roll_damage("2d6", bonus=0)
        assert 2 <= result <= 12

def test_roll_damage_with_bonus():
    for _ in range(30):
        result = _roll_damage("1d6", bonus=3)
        assert 4 <= result <= 9

def test_roll_damage_double():
    for _ in range(30):
        result = _roll_damage("1d6", bonus=0, double=True)
        assert 2 <= result <= 12  # 2d6 on double

def test_roll_damage_invalid_defaults_to_d6():
    result = _roll_damage("invalid", bonus=0)
    assert result >= 1
