"""
Pure function tests for: embed_builder, heavenly_demon, language, proxy, trade.
No Discord connection or DB required.
"""
import pytest
import discord
from unittest.mock import MagicMock


# ── embed_builder ─────────────────────────────────────────────────────────────

from cogs.embed_builder import _parse_color, _build_embed, _total_chars

def test_parse_color_valid_with_hash():
    assert _parse_color("#FF5733") == 0xFF5733

def test_parse_color_valid_no_hash():
    assert _parse_color("FF5733") == 0xFF5733

def test_parse_color_lowercase():
    assert _parse_color("#ff5733") == 0xFF5733

def test_parse_color_empty_returns_default():
    assert _parse_color("") == 0x9B59B6

def test_parse_color_invalid_returns_default():
    assert _parse_color("notacolor") == 0x9B59B6

def test_parse_color_too_short_returns_default():
    assert _parse_color("#FFF") == 0x9B59B6


def test_build_embed_title_and_description():
    data = {"title": "Hello", "description": "World", "color": "#FF0000", "fields": []}
    embed = _build_embed(data)
    assert isinstance(embed, discord.Embed)
    assert embed.title == "Hello"
    assert embed.description == "World"
    assert embed.color.value == 0xFF0000

def test_build_embed_with_fields():
    data = {
        "title": "Test",
        "description": "",
        "color": "",
        "fields": [
            {"name": "Field1", "value": "Value1", "inline": "yes"},
            {"name": "Field2", "value": "Value2", "inline": "no"},
        ],
    }
    embed = _build_embed(data)
    assert len(embed.fields) == 2
    assert embed.fields[0].name == "Field1"
    assert embed.fields[0].inline is True
    assert embed.fields[1].inline is False

def test_build_embed_empty_title_becomes_none():
    data = {"title": "", "description": "desc", "color": "", "fields": []}
    embed = _build_embed(data)
    assert embed.title is None

def test_build_embed_footer():
    data = {"title": "", "description": "", "color": "", "fields": [], "footer": {"text": "My footer"}}
    embed = _build_embed(data)
    assert embed.footer.text == "My footer"

def test_build_embed_author():
    data = {"title": "", "description": "", "color": "", "fields": [], "author": {"name": "AuthorName"}}
    embed = _build_embed(data)
    assert embed.author.name == "AuthorName"


def test_total_chars_empty():
    assert _total_chars({"title": "", "description": "", "fields": []}) == 0

def test_total_chars_title_and_desc():
    assert _total_chars({"title": "Hello", "description": "World", "fields": []}) == 10

def test_total_chars_with_fields():
    data = {"title": "T", "description": "D", "fields": [{"name": "AB", "value": "CDE"}]}
    assert _total_chars(data) == 1 + 1 + 2 + 3  # T+D+AB+CDE = 7


# ── heavenly_demon ────────────────────────────────────────────────────────────

from cogs.heavenly_demon import _mod, _sword_die, _roll_die, _roll, _is_crit, _sword_dmg, _tao_max, _hd_embed

def test_hd_mod_average():
    assert _mod(10) == 0

def test_hd_mod_high():
    assert _mod(18) == 4

def test_hd_mod_low():
    assert _mod(8) == -1

def test_sword_die_low_level():
    assert _sword_die(1) == (1, 8)
    assert _sword_die(4) == (1, 8)

def test_sword_die_mid_level():
    assert _sword_die(5) == (1, 10)
    assert _sword_die(10) == (1, 10)

def test_sword_die_high_level():
    assert _sword_die(11) == (1, 12)
    assert _sword_die(16) == (1, 12)

def test_sword_die_max_level():
    assert _sword_die(17) == (2, 6)
    assert _sword_die(20) == (2, 6)

def test_roll_die_in_range():
    for _ in range(50):
        r = _roll_die(20)
        assert 1 <= r <= 20

def test_roll_in_range():
    for _ in range(50):
        r = _roll(3, 6)
        assert 3 <= r <= 18

def test_is_crit_normal_level():
    char = MagicMock()
    char.level = 10
    assert _is_crit(char, 20) is True
    assert _is_crit(char, 19) is False

def test_is_crit_max_level():
    char = MagicMock()
    char.level = 20
    assert _is_crit(char, 18) is True
    assert _is_crit(char, 17) is False

def test_sword_dmg_positive():
    char = MagicMock()
    char.level = 5
    char.dexterity = 14
    for _ in range(20):
        assert _sword_dmg(char) >= 0

def test_tao_max_scales_with_level():
    char_low = MagicMock()
    char_low.level = 1
    char_low.wisdom = 10
    char_low.intelligence = 10

    char_high = MagicMock()
    char_high.level = 10
    char_high.wisdom = 10
    char_high.intelligence = 10

    assert _tao_max(char_high) >= _tao_max(char_low)

def test_hd_embed_returns_embed():
    embed = _hd_embed("Test Title", "Test Desc")
    assert isinstance(embed, discord.Embed)
    assert embed.title == "Test Title"
    assert embed.description == "Test Desc"


# ── language ──────────────────────────────────────────────────────────────────

from cogs.language import _scramble_text

def test_scramble_text_returns_string():
    result = _scramble_text("hello")
    assert isinstance(result, str)
    assert len(result) > 0

def test_scramble_text_differs_from_input():
    result = _scramble_text("hello")
    assert result != "hello"

def test_scramble_text_space_becomes_separator():
    result = _scramble_text("a b")
    assert "᛫" in result

def test_scramble_text_empty_string():
    assert _scramble_text("") == ""

def test_scramble_text_numbers_passthrough():
    result = _scramble_text("abc123")
    assert "1" in result
    assert "2" in result
    assert "3" in result


# ── proxy ─────────────────────────────────────────────────────────────────────

from cogs.proxy import _match_proxy

def test_match_proxy_open_and_close():
    assert _match_proxy("{{hello world}}", "{{", "}}") == "hello world"

def test_match_proxy_prefix_only():
    assert _match_proxy("::hello world", "::", None) == "hello world"

def test_match_proxy_no_match_wrong_open():
    assert _match_proxy("hello world", "{{", "}}") is None

def test_match_proxy_empty_inner_returns_none():
    # "{{" + "}}" = exactly open+close length, no inner
    assert _match_proxy("{{}}", "{{", "}}") is None

def test_match_proxy_no_proxy_open():
    assert _match_proxy("hello", "", "}}") is None

def test_match_proxy_prefix_only_no_content():
    assert _match_proxy("::", "::", None) is None

def test_match_proxy_content_stripped():
    result = _match_proxy("{{  hello  }}", "{{", "}}")
    assert result == "hello"


# ── trade session ─────────────────────────────────────────────────────────────

from cogs.trade import TradeSession

def _make_trade():
    ix = MagicMock()
    ix.user.id = 100
    ix.user.display_name = "Alice"
    target = MagicMock()
    target.id = 200
    target.display_name = "Bob"
    return TradeSession(ix, target), ix, target

def test_trade_session_is_participant_initiator():
    session, _, _ = _make_trade()
    assert session.is_participant(100) is True

def test_trade_session_is_participant_target():
    session, _, _ = _make_trade()
    assert session.is_participant(200) is True

def test_trade_session_is_participant_stranger():
    session, _, _ = _make_trade()
    assert session.is_participant(999) is False

def test_trade_session_initial_state():
    session, _, _ = _make_trade()
    assert session.state == "active"
    assert session.initiator_gold == 0
    assert session.target_gold == 0
    assert not session.initiator_ready
    assert not session.target_ready

def test_trade_session_summary_runs():
    session, _, _ = _make_trade()
    result = session.summary()
    assert isinstance(result, str)
    assert "Alice" in result or "Bob" in result
