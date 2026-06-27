"""Shared fixtures for all LoreForge cog tests."""
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Make the bot root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_interaction(guild_id=111, user_id=222, display_name="TestUser"):
    """Build a fake discord.Interaction with the most-used attributes."""
    interaction = MagicMock()
    interaction.guild_id = guild_id
    interaction.guild = MagicMock()
    interaction.guild.id = guild_id
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.display_name = display_name
    interaction.user.mention = f"<@{user_id}>"
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.data = {"values": []}
    return interaction


def make_character(**kwargs):
    """Build a minimal fake Character ORM object."""
    char = MagicMock()
    char.id = kwargs.get("id", 1)
    char.name = kwargs.get("name", "TestHero")
    char.char_class = kwargs.get("char_class", "Fighter")
    char.race = kwargs.get("race", "Human")
    char.level = kwargs.get("level", 1)
    char.xp = kwargs.get("xp", 0)
    char.hp_current = kwargs.get("hp_current", 20)
    char.hp_max = kwargs.get("hp_max", 20)
    char.strength = kwargs.get("strength", 15)
    char.dexterity = kwargs.get("dexterity", 12)
    char.constitution = kwargs.get("constitution", 13)
    char.intelligence = kwargs.get("intelligence", 10)
    char.wisdom = kwargs.get("wisdom", 10)
    char.charisma = kwargs.get("charisma", 10)
    char.balance = kwargs.get("balance", 500)
    char.gold = kwargs.get("gold", 100)
    char.is_dead = kwargs.get("is_dead", False)
    char.user_id = kwargs.get("user_id", 222)
    char.guild_id = kwargs.get("guild_id", 111)
    char.background = kwargs.get("background", "Soldier")
    char.inventory = kwargs.get("inventory", [])
    char.conditions = kwargs.get("conditions", [])
    char.relationships = kwargs.get("relationships", {})
    char.active_weapon = kwargs.get("active_weapon", "unarmed")
    char.attacks_known = kwargs.get("attacks_known", ["unarmed_strike"])
    char.proxy_name = kwargs.get("proxy_name", "TestHero")
    char.proxy_open = kwargs.get("proxy_open", "{{")
    char.proxy_close = kwargs.get("proxy_close", "}}")
    return char


def make_db_session(scalar_result=None, scalars_result=None, scalar_value=None):
    """Build a fake async SQLAlchemy session."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar_result)
    result.scalars = MagicMock()
    result.scalars.return_value.all = MagicMock(return_value=scalars_result or [])
    result.scalar = MagicMock(return_value=scalar_value)
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.scalar = AsyncMock(return_value=scalar_value)
    return db


def db_context(db_session):
    """Wrap a fake DB session in an async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.fixture
def interaction():
    return make_interaction()


@pytest.fixture
def character():
    return make_character()
