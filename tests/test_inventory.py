"""Tests for cogs/inventory.py — pure helper functions."""
import pytest
from unittest.mock import MagicMock
from cogs.inventory import roll_heal, inventory_embed


# ── roll_heal ─────────────────────────────────────────────────────────────────

def test_roll_heal_simple():
    for _ in range(30):
        result = roll_heal("2d4+2")
        assert 4 <= result <= 10  # 2d4 (2-8) + 2 = 4-10

def test_roll_heal_large():
    for _ in range(30):
        result = roll_heal("4d4+4")
        assert 8 <= result <= 20  # 4d4 (4-16) + 4 = 8-20

def test_roll_heal_no_bonus():
    for _ in range(30):
        result = roll_heal("1d6")
        assert 1 <= result <= 6


# ── inventory_embed ───────────────────────────────────────────────────────────

def test_inventory_embed_empty():
    char = MagicMock()
    char.name = "TestHero"
    char.gold = 100
    char.inventory = []

    embed = inventory_embed(char)
    assert "TestHero" in embed.title
    assert embed.fields[0].name == "Empty"


def test_inventory_embed_with_weapon():
    char = MagicMock()
    char.name = "TestHero"
    char.gold = 100
    char.inventory = [{"type": "weapon", "name": "Iron Sword", "key": "iron_sword", "equipped": True}]

    embed = inventory_embed(char)
    weapon_field = next((f for f in embed.fields if f.name == "Weapons"), None)
    assert weapon_field is not None
    assert "Iron Sword" in weapon_field.value


def test_inventory_embed_with_potion():
    char = MagicMock()
    char.name = "TestHero"
    char.gold = 50
    char.inventory = [
        {"type": "potion", "name": "Health Potion"},
        {"type": "potion", "name": "Health Potion"},
    ]

    embed = inventory_embed(char)
    potion_field = next((f for f in embed.fields if f.name == "Potions"), None)
    assert potion_field is not None
    assert "×2" in potion_field.value


def test_inventory_embed_gold_shown():
    char = MagicMock()
    char.name = "Hero"
    char.gold = 999
    char.inventory = []

    embed = inventory_embed(char)
    assert "999" in embed.description
