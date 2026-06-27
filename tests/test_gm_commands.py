"""Tests for cogs/gm.py and cogs/ai_config.py — GM-only command guards."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from conftest import make_interaction, make_db_session, db_context


# ── gm.py ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gm_add_not_owner():
    from cogs.gm import gm_add
    ix = make_interaction()
    ix.user.id = 111
    ix.guild.owner_id = 999  # different from user
    target = MagicMock()
    target.id = 222
    await gm_add.callback(ix, user=target)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_gm_remove_not_owner():
    from cogs.gm import gm_remove
    ix = make_interaction()
    ix.user.id = 111
    ix.guild.owner_id = 999
    target = MagicMock()
    target.id = 222
    await gm_remove.callback(ix, user=target)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_gm_list_non_gm():
    from cogs.gm import gm_list
    ix = make_interaction()
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await gm_list.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_gm_pending_non_gm():
    from cogs.gm import gm_pending
    ix = make_interaction()
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await gm_pending.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_sheet_view_non_gm_no_user():
    from cogs.gm import sheet_view
    ix = make_interaction()
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await sheet_view.callback(ix, user=None)
    ix.response.send_message.assert_called_once()


# ── ai_config.py ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_status_non_gm():
    from cogs.ai_config import ai_status
    ix = make_interaction()
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await ai_status.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_ai_toggle_narration_non_gm():
    from cogs.ai_config import ai_toggle_narration
    ix = make_interaction()
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await ai_toggle_narration.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_ai_toggle_npc_non_gm():
    from cogs.ai_config import ai_toggle_npc
    ix = make_interaction()
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await ai_toggle_npc.callback(ix)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_ai_style_non_gm():
    from cogs.ai_config import ai_style
    ix = make_interaction()
    style_choice = MagicMock()
    style_choice.value = "dramatic"
    with patch("services.utils.is_gm", new=AsyncMock(return_value=False)):
        await ai_style.callback(ix, style=style_choice)
    ix.response.send_message.assert_called_once()
    assert ix.response.send_message.call_args.kwargs.get("ephemeral") is True
