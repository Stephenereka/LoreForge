"""Tests for cogs/rest.py — helper functions and command guards."""
import pytest
from cogs.rest import _full_resources, _short_rest_resources


# ── _full_resources ───────────────────────────────────────────────────────────

def test_full_resources_fighter():
    r = _full_resources("Fighter", 5)
    assert r == {"action_surge": 1}

def test_full_resources_barbarian_rages_scale():
    r1 = _full_resources("Barbarian", 1)
    r5 = _full_resources("Barbarian", 5)
    assert r1["rages"] == 2
    assert r5["rages"] >= r1["rages"]
    assert r1["rage_active"] is False

def test_full_resources_warlock_slots():
    r = _full_resources("Warlock", 4)
    assert "spell_slots" in r
    assert r["spell_slots"] >= 1

def test_full_resources_wizard():
    r = _full_resources("Wizard", 4)
    assert "spell_slots" in r
    assert "arcane_recovery" in r

def test_full_resources_monk_ki():
    r = _full_resources("Monk", 5)
    assert r["ki_points"] == 5

def test_full_resources_unknown_class():
    r = _full_resources("UnknownClass", 5)
    assert r == {}


# ── _short_rest_resources ─────────────────────────────────────────────────────

def test_short_rest_warlock_recovers_slots():
    current = {"spell_slots": 0}
    updated = _short_rest_resources("Warlock", 4, current)
    assert updated["spell_slots"] >= 1

def test_short_rest_monk_recovers_ki():
    current = {"ki_points": 1}
    updated = _short_rest_resources("Monk", 6, current)
    assert updated["ki_points"] > current["ki_points"]

def test_short_rest_fighter_unchanged():
    current = {"action_surge": 1}
    updated = _short_rest_resources("Fighter", 5, current)
    assert updated == current
