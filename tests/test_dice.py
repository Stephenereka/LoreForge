"""Tests for cogs/dice.py — pure functions and the /roll command."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from conftest import make_interaction
from cogs.dice import parse_dice, roll_dice, DiceCog


# ── parse_dice ────────────────────────────────────────────────────────────────

def test_parse_dice_basic():
    assert parse_dice("d20") == (1, 20, 0)

def test_parse_dice_multi():
    assert parse_dice("2d6") == (2, 6, 0)

def test_parse_dice_modifier_plus():
    assert parse_dice("2d6+3") == (2, 6, 3)

def test_parse_dice_modifier_minus():
    assert parse_dice("3d8-1") == (3, 8, -1)

def test_parse_dice_large():
    assert parse_dice("4d6") == (4, 6, 0)

def test_parse_dice_invalid_text():
    assert parse_dice("hello") is None

def test_parse_dice_too_many_dice():
    assert parse_dice("21d6") is None

def test_parse_dice_too_many_sides():
    assert parse_dice("1d1001") is None

def test_parse_dice_zero_sides():
    assert parse_dice("1d1") is None

def test_parse_dice_empty():
    assert parse_dice("") is None


# ── roll_dice ─────────────────────────────────────────────────────────────────

def test_roll_dice_range():
    for _ in range(50):
        results = roll_dice(3, 6)
        assert len(results) == 3
        assert all(1 <= r <= 6 for r in results)

def test_roll_dice_d20():
    results = roll_dice(1, 20)
    assert len(results) == 1
    assert 1 <= results[0] <= 20


# ── /roll command handler ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_roll_command_valid():
    bot = MagicMock()
    cog = DiceCog(bot)
    interaction = make_interaction()

    await cog.roll.callback(cog, interaction, "2d6")

    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    embed = call_kwargs.kwargs.get("embed") or call_kwargs.args[0]
    assert embed.title == "🎲 Dice Roll"


@pytest.mark.asyncio
async def test_roll_command_with_modifier():
    bot = MagicMock()
    cog = DiceCog(bot)
    interaction = make_interaction()

    await cog.roll.callback(cog, interaction, "2d6+3")

    interaction.response.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_roll_command_invalid_expression():
    bot = MagicMock()
    cog = DiceCog(bot)
    interaction = make_interaction()

    await cog.roll.callback(cog, interaction, "notdice")

    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_roll_command_too_many_dice():
    bot = MagicMock()
    cog = DiceCog(bot)
    interaction = make_interaction()

    await cog.roll.callback(cog, interaction, "21d6")

    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True
