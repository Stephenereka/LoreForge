"""Tests for cogs/shop.py — pure helper functions."""
import pytest
import discord
from cogs.shop import sell_price, calc_ac_with_armor, browse_embed, ITEMS, WEAPONS, ARMORS, POTIONS


# ── ITEMS catalogue ───────────────────────────────────────────────────────────

def test_items_has_required_keys():
    for key, item in ITEMS.items():
        assert "name" in item, f"{key} missing 'name'"
        assert "type" in item, f"{key} missing 'type'"
        assert "price" in item, f"{key} missing 'price'"

def test_weapons_subset():
    for key in WEAPONS:
        assert ITEMS[key]["type"] == "weapon"
        assert "damage" in ITEMS[key]

def test_armors_subset():
    for key in ARMORS:
        assert ITEMS[key]["type"] == "armor"
        assert "ac" in ITEMS[key]

def test_potions_subset():
    for key in POTIONS:
        assert ITEMS[key]["type"] == "potion"
        assert "heal" in ITEMS[key]


# ── sell_price ────────────────────────────────────────────────────────────────

def test_sell_price_half():
    assert sell_price("longsword") == 7   # 15 // 2

def test_sell_price_minimum_one():
    # dagger costs 2, sell = 1
    assert sell_price("dagger") == 1

def test_sell_price_potion():
    # potion costs 50, sell = 25
    assert sell_price("potion") == 25


# ── calc_ac_with_armor ────────────────────────────────────────────────────────

def test_calc_ac_leather_avg_dex():
    # leather = 11 + dex_mod. dex 14 → mod +2 → AC 13
    assert calc_ac_with_armor("leather", 14) == 13

def test_calc_ac_leather_low_dex():
    # dex 8 → mod -1 → AC 10
    assert calc_ac_with_armor("leather", 8) == 10

def test_calc_ac_chain_dex_cap():
    # chain = 13 + min(dex_mod, 2). dex 18 → mod +4 → capped at +2 → AC 15
    assert calc_ac_with_armor("chain", 18) == 15

def test_calc_ac_chain_low_dex():
    # dex 10 → mod 0 → AC 13
    assert calc_ac_with_armor("chain", 10) == 13


# ── browse_embed ──────────────────────────────────────────────────────────────

def test_browse_embed_returns_embed():
    embed = browse_embed()
    assert isinstance(embed, discord.Embed)

def test_browse_embed_has_sections():
    embed = browse_embed()
    field_names = [f.name for f in embed.fields]
    assert any("Weapon" in n for n in field_names)
    assert any("Armor" in n for n in field_names)
    assert any("Potion" in n for n in field_names)
