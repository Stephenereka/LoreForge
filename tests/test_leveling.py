"""Tests for services/leveling.py — all pure functions."""
import pytest
from services.leveling import (
    xp_to_level, xp_for_next_level, check_level_up,
    xp_bar, hp_gain_on_level, feature_at_level, pvp_xp_reward,
    XP_THRESHOLDS, MAX_LEVEL,
)


# ── xp_to_level ───────────────────────────────────────────────────────────────

def test_xp_to_level_zero():
    assert xp_to_level(0) == 1

def test_xp_to_level_exactly_level2():
    assert xp_to_level(300) == 2

def test_xp_to_level_just_below_level2():
    assert xp_to_level(299) == 1

def test_xp_to_level_max():
    assert xp_to_level(355_000) == 20

def test_xp_to_level_above_max_capped():
    assert xp_to_level(9_999_999) == MAX_LEVEL

def test_xp_to_level_midrange():
    assert xp_to_level(900) == 3


# ── xp_for_next_level ────────────────────────────────────────────────────────

def test_xp_for_next_level_from_zero():
    assert xp_for_next_level(0) == 300

def test_xp_for_next_level_at_max():
    assert xp_for_next_level(355_000) == 0

def test_xp_for_next_level_partial():
    needed = xp_for_next_level(100)
    assert needed == 200  # 300 - 100


# ── check_level_up ────────────────────────────────────────────────────────────

def test_check_level_up_no_level_up():
    assert check_level_up(100, 1) is None

def test_check_level_up_triggers():
    result = check_level_up(300, 1)
    assert result == 2

def test_check_level_up_already_correct_level():
    assert check_level_up(300, 2) is None


# ── xp_bar ───────────────────────────────────────────────────────────────────

def test_xp_bar_returns_string():
    bar = xp_bar(0)
    assert isinstance(bar, str)

def test_xp_bar_max_level():
    bar = xp_bar(355_000)
    assert "MAX" in bar

def test_xp_bar_width():
    bar = xp_bar(0, width=10)
    # Should have some combination of filled/empty blocks
    assert len(bar) >= 10


# ── hp_gain_on_level ─────────────────────────────────────────────────────────

def test_hp_gain_fighter_positive():
    for _ in range(20):
        assert hp_gain_on_level("Fighter", 0) >= 1

def test_hp_gain_with_con_bonus():
    for _ in range(20):
        assert hp_gain_on_level("Fighter", 3) >= 4  # min 1 + 3

def test_hp_gain_average_mode():
    # Average mode = die//2 + 1 + con_mod
    gain = hp_gain_on_level("Fighter", 0, average=True)
    assert gain == 6  # 10//2 + 1 = 6

def test_hp_gain_minimum_one():
    # Even with -5 CON mod it should be at least 1
    for _ in range(20):
        assert hp_gain_on_level("Fighter", -5) >= 1


# ── feature_at_level ─────────────────────────────────────────────────────────

def test_feature_at_level_fighter_level1():
    features = feature_at_level("Fighter", 1)
    assert len(features) > 0
    assert "Second Wind" in features or "Fighting Style" in features

def test_feature_at_level_no_feature():
    # Level 3 Fighter has no feature in generic dict
    features = feature_at_level("Fighter", 3)
    assert isinstance(features, list)

def test_feature_at_level_unknown_class():
    # Unknown class falls back to generic ASI levels
    features = feature_at_level("UnknownClass", 4)
    assert "ASI" in features


# ── pvp_xp_reward ────────────────────────────────────────────────────────────

def test_pvp_xp_reward_same_level():
    reward = pvp_xp_reward(5, 5)
    assert reward == 250  # 50 * 5

def test_pvp_xp_reward_beating_higher_level():
    reward = pvp_xp_reward(3, 5)
    assert reward > 250  # bonus for beating higher level

def test_pvp_xp_reward_beating_lower_level():
    reward = pvp_xp_reward(10, 3)
    assert reward == 150  # 50 * 3, no bonus
