"""Tests for cogs/training.py — TrainingDummy class."""
import pytest
from cogs.training import TrainingDummy
from services.training_service import DIFFICULTY_CONFIGS


# ── TrainingDummy construction ────────────────────────────────────────────────

def test_dummy_easy_creation():
    dummy = TrainingDummy("easy")
    assert dummy.difficulty == "easy"
    assert dummy.hp_current == dummy.hp_max
    assert dummy.hp_max == DIFFICULTY_CONFIGS["easy"]["hp"]
    assert dummy.ac == DIFFICULTY_CONFIGS["easy"]["ac"]
    assert dummy.is_alive is True
    assert dummy.is_dead is False


def test_dummy_hard_creation():
    dummy = TrainingDummy("hard")
    assert dummy.difficulty == "hard"
    assert dummy.hp_max == DIFFICULTY_CONFIGS["hard"]["hp"]


def test_dummy_impossible_creation():
    dummy = TrainingDummy("impossible")
    assert dummy.hp_max == DIFFICULTY_CONFIGS["impossible"]["hp"]


# ── TrainingDummy.take_damage ─────────────────────────────────────────────────

def test_take_damage_reduces_hp():
    dummy = TrainingDummy("easy")
    start_hp = dummy.hp_current
    dummy.take_damage(5)
    assert dummy.hp_current == start_hp - 5


def test_take_damage_cant_go_negative():
    dummy = TrainingDummy("easy")
    dummy.take_damage(9999)
    assert dummy.hp_current == 0


def test_take_damage_kills_dummy():
    dummy = TrainingDummy("easy")
    dummy.take_damage(9999)
    assert dummy.is_alive is False
    assert dummy.is_dead is True


def test_partial_damage_doesnt_kill():
    dummy = TrainingDummy("easy")
    dummy.take_damage(1)
    assert dummy.is_alive is True
    assert dummy.is_dead is False


# ── TrainingDummy.attack ──────────────────────────────────────────────────────

def test_attack_returns_expected_keys():
    dummy = TrainingDummy("easy")
    result = dummy.attack()
    assert "attack_roll" in result
    assert "damage" in result
    assert "is_miss" in result


def test_attack_roll_in_range():
    dummy = TrainingDummy("easy")
    for _ in range(30):
        result = dummy.attack()
        # attack_roll = d20 + bonus; bonus is ≥ 0 and d20 ≥ 1
        assert result["attack_roll"] >= 1


def test_attack_damage_positive():
    dummy = TrainingDummy("easy")
    for _ in range(20):
        result = dummy.attack()
        assert result["damage"] >= 0
