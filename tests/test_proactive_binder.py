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

    sid = _channel_session_map(state, "telegram").get("telegram:42")
    assert sid is not None  # the agent opened a session itself
    msgs = state.store.load_messages(sid)
    assert any(m.role == "assistant" and "BC GAME live" in (m.content or "") for m in msgs)


async def test_binder_reuses_existing_session(state):
    existing = state.store.create_session()
    _channel_session_map(state, "telegram").set("telegram:42", existing)

    await make_proactive_binder(state)("telegram:42", "⏰ standup")

    # same session — no new one minted, notice recorded there
    assert _channel_session_map(state, "telegram").get("telegram:42") == existing
    msgs = state.store.load_messages(existing)
    assert any(m.role == "assistant" and "standup" in (m.content or "") for m in msgs)


async def test_binder_ignores_malformed_target(state):
    # No ':' → not a chat target; must not raise or create anything.
    await make_proactive_binder(state)("local", "⏰ x")
    assert _channel_session_map(state, "local").get("local") is None
