"""M225 — a follow-up message supersedes the turn already in flight.

The debounce window only merges messages that arrive within a couple of
seconds. Typing a comment, switching chats and forwarding a post takes
longer, so the second message used to open its own turn and the model
answered each half separately. Now the in-flight run is cancelled and the
new turn answers for both: the cancelled turn's user message is already
persisted in the session, so the model still sees it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway
from veles.channels.telegram._delivery import _TurnOutcome


@pytest.fixture()
def session_map(tmp_path: Path) -> SessionMap:
    return SessionMap.load(tmp_path / "telegram-sessions.json")


class _Backend:
    """Records submits and cancels. `cancellable` False models a backend
    whose run already finished (nothing to cancel)."""

    def __init__(self, *, cancellable: bool = True) -> None:
        self.submitted: list[str] = []
        self.cancelled: list[str] = []
        self.cancellable = cancellable

    async def submit_run(self, prompt: str, *, session_id=None, origin=None):
        self.submitted.append(prompt)
        return {"run_id": f"run-{len(self.submitted)}", "session_id": session_id}

    async def stream_events(self, run_id):
        if False:
            yield

    async def cancel_run(self, run_id: str) -> bool:
        self.cancelled.append(run_id)
        return self.cancellable


def _make_gateway(
    session_map: SessionMap, sends: list[tuple[str, dict[str, Any]]], backend: Any
) -> TelegramGateway:
    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        if method == "sendMessage":
            return {"message_id": 99}
        return {"ok": True}

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=backend,  # type: ignore[arg-type]
        session_map=session_map,
    )
    gateway._telegram_send = stub_send
    return gateway


async def test_follow_up_cancels_the_in_flight_run(session_map: SessionMap) -> None:
    backend = _Backend()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(session_map, sends, backend)
    # A turn is in flight for this chat: lock held, run published.
    lock = asyncio.Lock()
    await lock.acquire()
    gateway._chat_locks["42"] = lock
    gateway._active_runs["42"] = "run-in-flight"

    task = asyncio.create_task(
        gateway._run_turn_serial(42, "42", "the forwarded post", trigger_id=7)
    )
    await asyncio.sleep(0)  # let it reach the lock
    assert backend.cancelled == ["run-in-flight"]
    # Superseding replaces the "you're queued" ack — no 👀, no queued text.
    assert not [m for m, _ in sends if m == "setMessageReaction"]
    lock.release()
    await task
    assert backend.submitted == ["the forwarded post"]


async def test_falls_back_to_queued_ack_when_cancel_refused(session_map: SessionMap) -> None:
    """Backend says the run is already past cancelling → old behaviour:
    acknowledge the wait and queue behind the lock."""
    backend = _Backend(cancellable=False)
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(session_map, sends, backend)
    lock = asyncio.Lock()
    await lock.acquire()
    gateway._chat_locks["42"] = lock
    gateway._active_runs["42"] = "run-in-flight"

    task = asyncio.create_task(gateway._run_turn_serial(42, "42", "follow-up", trigger_id=7))
    await asyncio.sleep(0)
    assert backend.cancelled == ["run-in-flight"]
    assert [m for m, _ in sends if m == "setMessageReaction"]
    lock.release()
    await task


async def test_no_cancel_without_an_active_run(session_map: SessionMap) -> None:
    backend = _Backend()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(session_map, sends, backend)
    lock = asyncio.Lock()
    await lock.acquire()
    gateway._chat_locks["42"] = lock  # busy, but no run published yet

    task = asyncio.create_task(gateway._run_turn_serial(42, "42", "hi", trigger_id=7))
    await asyncio.sleep(0)
    assert backend.cancelled == []
    assert [m for m, _ in sends if m == "setMessageReaction"]
    lock.release()
    await task


async def test_active_run_published_and_cleared(
    session_map: SessionMap, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _Backend()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(session_map, sends, backend)
    seen: list[str | None] = []

    async def spy_drain(self, run_id, chat_id, message_id=None):
        seen.append(self._active_runs.get("42"))
        return _TurnOutcome(text="done", session_id="s1", error=None)

    monkeypatch.setattr(TelegramGateway, "_drain_stream", spy_drain)
    await gateway._run_turn(42, "42", "hello")
    assert seen == ["run-1"]  # visible to a follow-up while streaming
    assert "42" not in gateway._active_runs  # and cleared afterwards


async def test_cancelled_turn_deletes_its_placeholder(session_map: SessionMap) -> None:
    """A superseded turn renders nothing — the replacement answers for
    both — but the session mapping it learned must survive."""
    backend = _Backend()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(session_map, sends, backend)

    await gateway._deliver(
        42, "42", 99, _TurnOutcome(text=None, session_id="s9", error=None, cancelled=True)
    )
    assert [p for m, p in sends if m == "deleteMessage"] == [{"chat_id": 42, "message_id": 99}]
    assert not [m for m, _ in sends if m == "editMessageText"]
    assert session_map.get("42") == "s9"
