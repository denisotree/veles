"""Telegram inline-keyboard callbacks for /mode trigger
DaemonClient.update_session via the daemon's PATCH endpoint.

M127: the `/model` picker (and its `m:`/`mn:`/`mc:` callbacks) was
removed — model/provider are fixed at daemon launch. Only `/mode`
(`mo:`) and the trust-prompt (`v:`) callbacks remain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from veles.channels._telegram_commands import dispatch
from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway


@pytest.fixture()
def session_map(tmp_path: Path) -> SessionMap:
    sm = SessionMap.load(tmp_path / "sessions.json")
    sm.set("42", "sess-existing")
    return sm


class _RecordingClient:
    """Captures update_session and submit_prompt_answer calls so tests
    can assert what the gateway invoked."""

    def __init__(self) -> None:
        self.update_calls: list[dict[str, Any]] = []
        self.submit_calls: list[dict[str, Any]] = []
        self.fail_update: Exception | None = None

    async def update_session(
        self,
        session_id: str,
        *,
        model: str | None = None,
        mode: str | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        if self.fail_update is not None:
            raise self.fail_update
        self.update_calls.append(
            {"session_id": session_id, "model": model, "mode": mode, "provider": provider}
        )
        return {"session_id": session_id, "overrides": {"model": model, "mode": mode, "provider": provider}}

    async def submit_prompt_answer(
        self, run_id: str, prompt_id: str, choice: str
    ) -> dict[str, Any]:
        self.submit_calls.append(
            {"run_id": run_id, "prompt_id": prompt_id, "choice": choice}
        )
        return {"ok": True}

    async def submit_run(self, prompt: str, *, session_id=None):  # noqa: ARG002
        return {"run_id": "r", "session_id": session_id, "state": "running"}

    async def stream_events(self, run_id):  # noqa: ARG002
        if False:
            yield


def _make_gateway(
    session_map: SessionMap, sends: list[tuple[str, dict[str, Any]]]
) -> tuple[TelegramGateway, _RecordingClient]:
    client = _RecordingClient()

    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        if method == "sendMessage":
            return {"message_id": 1, "chat": payload.get("chat_id")}
        if method == "answerCallbackQuery":
            return {"ok": True}
        return {}

    gw = TelegramGateway(
        bot_token="X",
        daemon_client=client,  # type: ignore[arg-type]
        session_map=session_map,
    )
    gw._telegram_send = stub_send
    return gw, client


# ---- /mode keyboard rendering ----


async def test_mode_command_sends_inline_keyboard(session_map) -> None:
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, _ = _make_gateway(session_map, sends)
    reply = await dispatch(gateway, "42", "mode", "")
    # Returned "" because gateway already sent the keyboard
    assert reply == ""
    msgs = [p for m, p in sends if m == "sendMessage"]
    assert msgs, "expected /mode to send a keyboard message"
    kb = msgs[0].get("reply_markup", {}).get("inline_keyboard")
    assert kb is not None
    flat = [b for row in kb for b in row]
    assert len(flat) == 4
    callback_data = {b["callback_data"] for b in flat}
    assert callback_data == {"mo:auto", "mo:planning", "mo:writing", "mo:goal"}


async def test_mode_command_without_session_returns_hint(tmp_path: Path) -> None:
    """Without a session_map entry for this chat, /mode hints to send
    a message first — buttons would have nothing to mutate."""
    empty_map = SessionMap.load(tmp_path / "empty.json")
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, _ = _make_gateway(empty_map, sends)
    reply = await dispatch(gateway, "999", "mode", "")
    assert reply is not None
    assert "send a message first" in reply
    # No keyboard sent
    assert not [p for m, p in sends if m == "sendMessage"]


# ---- callback handler: mode ----


async def test_mode_callback_calls_update_session(session_map) -> None:
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)
    callback = {
        "id": "cb1",
        "data": "mo:planning",
        "from": {"id": 42, "username": "u"},
        "message": {"chat": {"id": 42}, "message_id": 7},
    }
    await gateway._handle_callback_query(callback)
    assert client.update_calls == [
        {
            "session_id": "sess-existing",
            "model": None,
            "mode": "planning",
            "provider": None,
        }
    ]
    # User got an ack
    acks = [p for m, p in sends if m == "answerCallbackQuery"]
    assert acks and "planning" in acks[0]["text"]


async def test_mode_callback_without_session_friendly_message(
    tmp_path: Path,
) -> None:
    """No session yet → user gets a hint, no daemon call."""
    empty_map = SessionMap.load(tmp_path / "empty.json")
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(empty_map, sends)
    callback = {
        "id": "cb1",
        "data": "mo:auto",
        "from": {"id": 99, "username": "u"},
        "message": {"chat": {"id": 99}, "message_id": 7},
    }
    await gateway._handle_callback_query(callback)
    assert client.update_calls == []
    acks = [p for m, p in sends if m == "answerCallbackQuery"]
    assert acks
    assert "send a message first" in acks[0]["text"]


# ---- M127: /model callbacks are gone — `m:` is silently dismissed ----


async def test_model_callback_prefix_is_silently_dismissed(session_map) -> None:
    """A stale `m:` tap (from an old picker message) must not crash or
    call the daemon — it's just acked."""
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)
    callback = {
        "id": "cb1",
        "data": "m:c0",
        "from": {"id": 42, "username": "u"},
        "message": {"chat": {"id": 42}, "message_id": 7},
    }
    await gateway._handle_callback_query(callback)
    assert client.update_calls == []
    assert [p for m, p in sends if m == "answerCallbackQuery"]


# ---- back-compat: existing v: prompts still work ----


async def test_v_prefix_still_routes_to_trust_prompt_handler(
    session_map,
) -> None:
    """The callback dispatcher must not break the existing
    trust/approval flow (v: prefix)."""
    from veles.channels.telegram import _PendingTelegramPrompt

    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)
    gateway._pending_prompts["pid-1"] = _PendingTelegramPrompt(
        run_id="r1",
        chat_id=42,
        message_id=99,
        kind="trust",
        short_to_key={"o": "once"},
    )
    callback = {
        "id": "cb1",
        "data": "v:pid-1:o",
        "from": {"id": 42, "username": "u"},
        "message": {"chat": {"id": 42}, "message_id": 99},
    }
    await gateway._handle_callback_query(callback)
    assert client.submit_calls == [
        {"run_id": "r1", "prompt_id": "pid-1", "choice": "once"}
    ]
    # update_session should NOT have been called
    assert client.update_calls == []
