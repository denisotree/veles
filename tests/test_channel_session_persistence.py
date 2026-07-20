"""Daemon-half of the channel session-continuity fix.

For a brand-new chat the caller submits `session_id=None`; the agent
factory allocates the session eagerly. The backend must adopt that real
id onto the handle BEFORE the run starts, so `started` (and a later
`error`) carry it and the gateway can persist the chat→session mapping
even when the turn fails — otherwise the next message would open a fresh,
empty session (the amnesia symptom).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from veles.channels.in_process_backend import InProcessRunBackend
from veles.core.agent import RunResult
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.state import DaemonState


class _StubAgent:
    """Mimics the factory's eager allocation: a new chat (input None) gets
    a fresh session id exposed via `.session_id` before `run()`."""

    def __init__(self, session_id: str, *, fail: bool = False) -> None:
        self.session_id = session_id
        self._fail = fail

    def run(self, prompt, on_text_delta=None):
        if self._fail:
            raise RuntimeError("boom")
        return RunResult(text="ok", iterations=1, session_id=self.session_id)


def _make_state(tmp_path: Path, *, fail: bool = False) -> tuple[DaemonState, SessionStore]:
    project = init_project(tmp_path, name=None, force=False)
    store = SessionStore(project.memory_db_path)

    def factory(session_id, *, prompt=None):
        # Fresh id when the caller passed None — the eager-allocation case.
        return _StubAgent(session_id or "fresh-sid", fail=fail)

    state = DaemonState(
        project=project,
        store=store,
        token_store=TokenStore.load(),
        agent_factory=factory,
        started_at=0.0,
    )
    return state, store


async def test_started_event_carries_created_session_id(tmp_path: Path) -> None:
    state, store = _make_state(tmp_path)
    backend = InProcessRunBackend(state)
    try:
        res = await backend.submit_run("q", session_id=None)
        handle = state.get_run(res["run_id"])
        assert handle is not None
        # Adopted synchronously, before the run task even starts.
        assert handle.session_id == "fresh-sid"
        await asyncio.wait_for(handle.done.wait(), timeout=2.0)
        started = next(e for e in handle.events if e.get("type") == "started")
        assert started["session_id"] == "fresh-sid"
    finally:
        store.close()


async def test_error_event_carries_session_id(tmp_path: Path) -> None:
    state, store = _make_state(tmp_path, fail=True)
    backend = InProcessRunBackend(state)
    try:
        res = await backend.submit_run("q", session_id=None)
        handle = state.get_run(res["run_id"])
        assert handle is not None
        await asyncio.wait_for(handle.done.wait(), timeout=2.0)
        error = next(e for e in handle.events if e.get("type") == "error")
        # The mapping-bearing id survives the failure so the chat continues
        # the same session next turn rather than starting empty.
        assert error["session_id"] == "fresh-sid"
    finally:
        store.close()
