"""Telegram /mode command — registry surface (menu, help, command names).

M127: `/model` was removed (model/provider are fixed at daemon launch);
these tests assert it is gone from the menu/help and that `/mode` stays.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.channels._telegram_commands import (
    all_command_names,
    dispatch,
    menu_descriptors,
)
from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway


@pytest.fixture()
def session_map(tmp_path: Path) -> SessionMap:
    return SessionMap.load(tmp_path / "telegram-sessions.json")


def _make_gateway(session_map: SessionMap) -> TelegramGateway:
    class _NullClient:
        async def submit_run(self, prompt: str, *, session_id=None):  # noqa: ARG002
            return {"run_id": "x", "session_id": session_id, "state": "running"}

        async def stream_events(self, run_id):  # noqa: ARG002
            if False:
                yield

    return TelegramGateway(
        bot_token="X",
        daemon_client=_NullClient(),  # type: ignore[arg-type]
        session_map=session_map,
    )


# ---- /mode without session: hint message ----


async def test_mode_without_session_returns_hint(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "999", "mode", "")
    assert reply is not None
    assert "send a message first" in reply


# ---- registry exposure: /mode present, /model gone ----


async def test_mode_in_menu_model_absent(session_map: SessionMap) -> None:
    del session_map
    cmds = {d["command"] for d in menu_descriptors()}
    assert "mode" in cmds
    assert "model" not in cmds


async def test_mode_recognised_model_not(session_map: SessionMap) -> None:
    del session_map
    names = all_command_names()
    assert "mode" in names
    assert "model" not in names


async def test_model_is_unknown_command(session_map: SessionMap) -> None:
    """`/model` no longer dispatches — `dispatch` returns None (unknown)."""
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "42", "model", "")
    assert reply is None


async def test_help_lists_mode_not_model(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "42", "help", "")
    assert reply is not None
    assert "/mode" in reply
    assert "/model" not in reply
