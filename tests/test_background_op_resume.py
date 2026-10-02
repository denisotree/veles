"""M204 Phase 2: the daemon notify/resume path of a background-op job.

When a structured one-shot job (e.g. the wiki module's `kind="ingest"`)
completes, the daemon notifies the originating chat and RESUMES the session
(a queued follow-up turn) — or degrades to notify-only when no session is
mapped or the resume-depth cap is hit (auto-resume loop guard).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from veles.core.context import current_resume_depth
from veles.core.project import init_project


@pytest.fixture(autouse=True)
def _isolated_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    return home


def _project(tmp_path: Path):
    return init_project(tmp_path / "proj", name="bg")


# ---- notify + resume ----


class _FakeRouter:
    def __init__(self) -> None:
        self.delivered: list[tuple[str, str]] = []

    async def deliver(self, target: str, text: str):
        self.delivered.append((target, text))
        return {}


@dataclass
class _FakeState:
    project: Any
    agent_factory: Any
    delivery_router: Any
    session_name: str | None = None
    post_turn_hook: Any = None
    subagent_factory: Any = None
    runs: dict = field(default_factory=dict)
    session_locks: dict = field(default_factory=dict)

    def add_run(self, handle) -> None:
        self.runs[handle.run_id] = handle

    def session_lock(self, session_id: str) -> asyncio.Lock:
        return self.session_locks.setdefault(session_id, asyncio.Lock())


def _job(project, *, deliver_to: str, resume_depth: int = 0):
    from veles.core.jobs_store import JobsStore

    store = JobsStore(project.memory_db_path)
    rec = store.add_job(
        name="ingest docs",
        prompt="",
        schedule_expr="once:+0s",
        kind="ingest",
        params={"source": "/v/docs", "glob": "*", "resume_depth": resume_depth},
        deliver_to=deliver_to,
    )
    store.close()
    return rec


def test_no_session_mapped_degrades_to_notify_only(tmp_path: Path) -> None:
    from veles.daemon.background_ops import make_on_op_finished

    project = _project(tmp_path)
    router = _FakeRouter()
    state = _FakeState(project=project, agent_factory=None, delivery_router=router)
    job = _job(project, deliver_to="telegram:999")

    asyncio.run(make_on_op_finished(state)(job, "Ingested 3/3 file(s)."))
    assert len(router.delivered) == 1
    target, text = router.delivered[0]
    assert target == "telegram:999" and "3/3" in text


def test_mapped_session_resumes_and_delivers_final_text(tmp_path: Path) -> None:
    from veles.channels.session_map import SessionMap, channel_session_path
    from veles.daemon.background_ops import make_on_op_finished

    project = _project(tmp_path)
    router = _FakeRouter()
    seen: dict = {}

    class _ResumeAgent:
        def run(self, prompt, on_text_delta=None, event_listener=None):
            seen["prompt"] = prompt
            seen["resume_depth"] = current_resume_depth()

            class _RR:
                text = "Готово: вики пополнена, продолжаю."
                iterations = 1
                stopped_reason = "completed"
                session_id = "sess-1"

            return _RR()

    def agent_factory(session_id, *, prompt=None):
        seen["session_id"] = session_id
        # The real build runs memory recall, which the M264 bridge refuses to
        # do on a running event loop — the resume agent must be built off it.
        try:
            asyncio.get_running_loop()
            seen["built_on_loop"] = True
        except RuntimeError:
            seen["built_on_loop"] = False
        return _ResumeAgent()

    smap = SessionMap.load(channel_session_path("telegram"))
    smap.set("12345", "sess-1")  # keyed as the gateway keys a chat (M278)
    smap.save()

    state = _FakeState(project=project, agent_factory=agent_factory, delivery_router=router)
    job = _job(project, deliver_to="telegram:12345")

    asyncio.run(make_on_op_finished(state)(job, "Ingested 3/3 file(s)."))
    assert seen["built_on_loop"] is False
    # Resumed INTO the mapped session with an untrusted-wrapped summary seed…
    assert seen["session_id"] == "sess-1"
    assert "3/3" in seen["prompt"] and "untrusted" in seen["prompt"].lower()
    assert seen["resume_depth"] == 1  # the resume turn carries depth+1
    # …and the resumed turn's own output IS the notification.
    assert len(router.delivered) == 1
    target, text = router.delivered[0]
    assert target == "telegram:12345" and "продолжаю" in text


def test_resume_into_a_stale_session_follows_the_session_the_factory_allocated(
    tmp_path: Path,
) -> None:
    """The chat's map can outlive its session row (a DB reset). The agent factory
    then allocates a fresh session; the resume turn must run, lock and be recorded
    under that session, and the chat must be re-pointed to it — otherwise the
    resumed answer lands in a session the chat never reads again."""
    from veles.channels.session_map import SessionMap, channel_session_path
    from veles.daemon.background_ops import make_on_op_finished

    project = _project(tmp_path)
    router = _FakeRouter()

    class _FreshAgent:
        session_id = "sess-fresh"

        def run(self, prompt, on_text_delta=None, event_listener=None):
            class _RR:
                text = "resumed"
                iterations = 1
                stopped_reason = "completed"
                session_id = "sess-fresh"

            return _RR()

    def agent_factory(session_id, *, prompt=None):
        assert session_id == "sess-stale"
        return _FreshAgent()

    smap = SessionMap.load(channel_session_path("telegram"))
    smap.set("12345", "sess-stale")

    state = _FakeState(project=project, agent_factory=agent_factory, delivery_router=router)
    job = _job(project, deliver_to="telegram:12345")
    asyncio.run(make_on_op_finished(state)(job, "Ingested 1/1 file(s)."))

    (handle,) = state.runs.values()
    assert handle.session_id == "sess-fresh"
    assert "sess-fresh" in state.session_locks and "sess-stale" not in state.session_locks
    assert SessionMap.load(channel_session_path("telegram")).get("12345") == "sess-fresh"


def test_resume_depth_cap_degrades_to_notify_only(tmp_path: Path) -> None:
    from veles.channels.session_map import SessionMap, channel_session_path
    from veles.daemon.background_ops import make_on_op_finished

    project = _project(tmp_path)
    router = _FakeRouter()

    def agent_factory(session_id, *, prompt=None):  # pragma: no cover
        raise AssertionError("depth-capped completion must NOT resume")

    smap = SessionMap.load(channel_session_path("telegram"))
    smap.set("12345", "sess-1")  # keyed as the gateway keys a chat (M278)
    smap.save()

    state = _FakeState(project=project, agent_factory=agent_factory, delivery_router=router)
    job = _job(project, deliver_to="telegram:12345", resume_depth=1)  # already a resume child

    asyncio.run(make_on_op_finished(state)(job, "Ingested 1/1 file(s)."))
    assert len(router.delivered) == 1  # notified, not resumed
