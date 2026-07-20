"""M166 — origin plumbing: the originating chat reaches the tool context.

A `task_add` in Telegram must default its reminder target to that chat. The
chat id flows gateway → submit_run → run_agent_in_background, which sets the
`current_origin` ContextVar before the worker thread so the agent's tools see
it. (task_add reading it is covered in test_task_tools.py.)
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from veles.channels.in_process_backend import InProcessRunBackend
from veles.core.agent import RunResult
from veles.core.context import current_origin
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.runner import new_run_handle, run_agent_in_background
from veles.daemon.state import DaemonState


class _OriginRecordingAgent:
    def __init__(self, sink):
        self._sink = sink

    def run(self, prompt, on_text_delta=None, event_listener=None):
        # Runs inside the to_thread worker — proves the ContextVar propagated.
        self._sink["origin"] = current_origin()
        return RunResult(text="ok", iterations=1, session_id="s1")


async def test_origin_reaches_worker_context():
    sink: dict = {}
    handle = new_run_handle(session_id="s1")
    await run_agent_in_background(
        handle, agent=_OriginRecordingAgent(sink), prompt="q", origin="telegram:42"
    )
    assert sink["origin"] == "telegram:42"


async def test_no_origin_is_none():
    sink: dict = {}
    handle = new_run_handle(session_id="s1")
    await run_agent_in_background(handle, agent=_OriginRecordingAgent(sink), prompt="q")
    assert sink["origin"] is None


async def test_origin_reset_after_run():
    sink: dict = {}
    handle = new_run_handle(session_id="s1")
    await run_agent_in_background(
        handle, agent=_OriginRecordingAgent(sink), prompt="q", origin="telegram:42"
    )
    assert current_origin() is None  # not leaked into the calling context


async def test_in_process_backend_threads_origin(tmp_path: Path):
    project = init_project(tmp_path, name=None, force=False)
    store = SessionStore(project.memory_db_path)
    sink: dict = {}

    def factory(session_id, *, prompt=None):
        return _OriginRecordingAgent(sink)

    state = DaemonState(
        project=project,
        store=store,
        token_store=TokenStore.load(),
        agent_factory=factory,
        started_at=0.0,
    )
    backend = InProcessRunBackend(state)
    try:
        res = await backend.submit_run("q", session_id=None, origin="telegram:99")
        handle = state.get_run(res["run_id"])
        await asyncio.wait_for(handle.done.wait(), timeout=2.0)
        assert sink["origin"] == "telegram:99"
    finally:
        store.close()
