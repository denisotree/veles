"""M214 (A4) — proactive notices bind to the chat's session.

The delivered reminder is recorded as an assistant turn so a user reply
continues a conversation that knows the reminder was sent; when the chat has no
session yet, the binder opens one ("the agent created a session itself").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.background_ops import make_proactive_binder
from veles.daemon.server import _channel_session_map
from veles.daemon.state import DaemonState


@pytest.fixture()
def state(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)
    st = DaemonState(
        project=project,
        store=store,
        token_store=TokenStore.load(),
        agent_factory=lambda *a, **kw: None,
        started_at=0.0,
    )
    yield st
    store.close()


async def test_binder_opens_session_when_chat_has_none(state):
    binder = make_proactive_binder(state)
    await binder("telegram:42", "⏰ BC GAME live")

    # Keyed as the gateway keys a chat — `str(chat_id)` — not by the target
    # string; pre-M278 the binder used "telegram:42", which the gateway never reads.
    sid = _channel_session_map(state, "telegram").get("42")
    assert sid is not None  # the agent opened a session itself
    msgs = state.store.load_messages(sid)
    assert any(m.role == "assistant" and "BC GAME live" in (m.content or "") for m in msgs)


async def test_binder_reuses_existing_session(state):
    existing = state.store.create_session()
    _channel_session_map(state, "telegram").set("42", existing)  # as the gateway writes it

    await make_proactive_binder(state)("telegram:42", "⏰ standup")

    # same session — no new one minted, notice recorded there
    assert _channel_session_map(state, "telegram").get("42") == existing
    msgs = state.store.load_messages(existing)
    assert any(m.role == "assistant" and "standup" in (m.content or "") for m in msgs)


async def test_the_chats_next_message_continues_the_bound_session(state):
    """The contract that matters, end to end: after a notice is bound to chat
    42, the gateway's next message from chat 42 goes to that same session. The
    gateway gets the very map the daemon hands it (`_start_channel_runners`).
    Pre-M278 the binder keyed "telegram:42" while the gateway reads "42", so
    this message started a fresh session with no record of the notice."""
    from veles.channels.telegram import TelegramGateway

    submitted: list[str | None] = []

    class _Client:
        async def submit_run(self, prompt, *, session_id=None, origin=None):
            submitted.append(session_id)
            return {"run_id": "r1", "session_id": session_id, "state": "running"}

        async def stream_events(self, run_id):
            yield {"type": "completed", "text": "ok", "session_id": submitted[-1]}

        async def submit_prompt_answer(self, run_id, prompt_id, choice):
            raise NotImplementedError

    await make_proactive_binder(state)("telegram:42", "⏰ standup at 10")

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=_Client(),
        session_map=_channel_session_map(state, "telegram"),
    )

    async def _send(method, payload):
        return {"message_id": 1, "chat": payload.get("chat_id")}

    gateway._telegram_send = _send  # type: ignore[method-assign]
    await gateway._handle_update(
        {"update_id": 1, "message": {"chat": {"id": 42, "type": "private"}, "text": "moved?"}}
    )
    await gateway._flush_buffer("42")

    assert len(submitted) == 1 and submitted[0] is not None
    msgs = state.store.load_messages(submitted[0])
    assert any("standup at 10" in (m.content or "") for m in msgs)


async def test_binder_ignores_malformed_target(state):
    # No ':' → not a chat target; must not raise or create anything.
    await make_proactive_binder(state)("local", "⏰ x")
    assert _channel_session_map(state, "local").get("local") is None
