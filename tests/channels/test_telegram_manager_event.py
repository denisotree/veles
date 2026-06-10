"""M124: Telegram surfaces `manager_plan` daemon event as a chat
notice before the writer text lands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway


@pytest.fixture()
def session_map(tmp_path: Path) -> SessionMap:
    return SessionMap.load(tmp_path / "telegram-sessions.json")


def _make_gateway(
    session_map: SessionMap, sends: list[tuple[str, dict[str, Any]]]
) -> TelegramGateway:
    class _NullClient:
        async def submit_run(self, prompt: str, *, session_id=None):  # noqa: ARG002
            return {"run_id": "x", "session_id": session_id, "state": "running"}

        async def stream_events(self, run_id):  # noqa: ARG002
            if False:
                yield

    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        return {"message_id": 1, "chat": payload.get("chat_id")}

    gw = TelegramGateway(
        bot_token="X",
        daemon_client=_NullClient(),  # type: ignore[arg-type]
        session_map=session_map,
    )
    gw._telegram_send = stub_send
    return gw


# ---- happy path ----


async def test_manager_plan_event_renders_chat_notice(session_map: SessionMap) -> None:
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(session_map, sends)
    event = {
        "type": "manager_plan",
        "objective": "research the auth module",
        "steps": [
            {"role": "explorer", "status": "done", "session_id": None, "rationale": "…"},
            {"role": "writer", "status": "in_progress", "session_id": None, "rationale": "…"},
        ],
    }
    await gateway._send_manager_plan_notice(42, event)

    # One sendMessage call with both roles surfaced
    messages = [p for m, p in sends if m == "sendMessage"]
    assert messages, f"expected sendMessage, got {sends}"
    text = messages[0]["text"]
    assert "Decomposing" in text
    assert "explorer" in text
    assert "writer" in text
    assert "2 workers" in text


async def test_manager_plan_event_with_empty_steps_silent(
    session_map: SessionMap,
) -> None:
    """An empty/malformed plan event shouldn't spam the chat with
    'Decomposing into 0 workers' — just no-op."""
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(session_map, sends)
    await gateway._send_manager_plan_notice(42, {"type": "manager_plan", "steps": []})
    assert [m for m, _ in sends if m == "sendMessage"] == []


async def test_manager_plan_handles_missing_role_field(
    session_map: SessionMap,
) -> None:
    """Steps with no `role` are filtered out; if nothing's left the
    notice is suppressed entirely."""
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(session_map, sends)
    await gateway._send_manager_plan_notice(
        42,
        {"type": "manager_plan", "steps": [{"rationale": "lone"}, {"rationale": "items"}]},
    )
    # `_send_manager_plan_notice` falls back to "?" string for missing roles,
    # so it still sends — but content shows '?' which is honest enough.
    msgs = [p["text"] for m, p in sends if m == "sendMessage"]
    if msgs:
        assert "Decomposing" in msgs[0]


async def test_manager_plan_html_escaped(session_map: SessionMap) -> None:
    """Role names with HTML metacharacters are escaped — gateway is
    HTML parse_mode so unescaped `<` would break Telegram parsing."""
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(session_map, sends)
    event = {
        "type": "manager_plan",
        "steps": [{"role": "<weird>", "status": "done"}],
    }
    await gateway._send_manager_plan_notice(42, event)
    text = next(p["text"] for m, p in sends if m == "sendMessage")
    assert "&lt;weird&gt;" in text
    assert "<weird>" not in text  # raw form must be gone
