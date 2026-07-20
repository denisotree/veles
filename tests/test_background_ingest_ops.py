"""M204 Phase 2: async-by-context `wiki_add` + the daemon notify/resume path.

Under a chat/daemon context (origin set) a recursive `wiki_add` must NOT run
inline — it submits a STRUCTURED one-shot job (`kind="ingest"`, `once:+0s`,
`deliver_to=<concrete origin>`) and returns immediately. When the job
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

from veles.core.context import (
    current_resume_depth,
    reset_active_project,
    reset_origin,
    set_active_project,
    set_origin,
)
from veles.core.orchestration.delegation import (
    reset_subagent_factory,
    set_subagent_factory,
)
from veles.core.project import init_project
from veles.modules.wiki.tools import wiki_add


@pytest.fixture(autouse=True)
def _isolated_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    return home


# ---- wiki_add async predicate ----


@dataclass
class _Recorder:
    built: list[Any] = field(default_factory=list)

    def factory(self, *, system_prompt: str, tools: list[str]):
        @dataclass
        class _StubAgent:
            system_prompt: str
            tools: list[str]

            def run(self, prompt: str, **_kw: Any):
                @dataclass
                class _RR:
                    text: str = "ok"
                    session_id: str | None = "w1"
                    usage: Any = None

                return _RR()

        a = _StubAgent(system_prompt=system_prompt, tools=list(tools))
        self.built.append(a)
        return a


def _project(tmp_path: Path):
    return init_project(tmp_path / "proj", name="bg")


def test_recursive_with_origin_submits_structured_job(tmp_path: Path) -> None:
    project = _project(tmp_path)
    ptok = set_active_project(project)
    otok = set_origin("telegram:12345")
    rec = _Recorder()
    ftok = set_subagent_factory(rec.factory)
    try:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("a", encoding="utf-8")
        out = wiki_add(str(docs), recursive=True)
        assert "background" in out.lower()
        assert rec.built == []  # nothing ran inline

        from veles.core.jobs_store import JobsStore

        store = JobsStore(project.memory_db_path)
        jobs = [store.get_job(j.id) for j in store.list_jobs()]
        store.close()
        assert len(jobs) == 1
        job = jobs[0]
        assert job is not None
        assert job.kind == "ingest"
        assert job.schedule.kind == "once"
        assert job.deliver_to == "telegram:12345"  # CONCRETE origin, never "origin"
        assert job.params is not None
        assert job.params["source"] == str(docs)
        assert job.params["resume_depth"] == 0
    finally:
        reset_subagent_factory(ftok)
        reset_origin(otok)
        reset_active_project(ptok)


def test_recursive_without_origin_runs_inline(tmp_path: Path) -> None:
    project = _project(tmp_path)
    ptok = set_active_project(project)
    rec = _Recorder()
    ftok = set_subagent_factory(rec.factory)
    try:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("a", encoding="utf-8")
        wiki_add(str(docs), recursive=True)
        assert len(rec.built) == 1  # ran inline (REPL path)
    finally:
        reset_subagent_factory(ftok)
        reset_active_project(ptok)


def test_single_file_with_origin_stays_inline(tmp_path: Path) -> None:
    project = _project(tmp_path)
    ptok = set_active_project(project)
    otok = set_origin("telegram:12345")
    rec = _Recorder()
    ftok = set_subagent_factory(rec.factory)
    try:
        f = tmp_path / "a.md"
        f.write_text("a", encoding="utf-8")
        wiki_add(str(f))
        assert len(rec.built) == 1  # single file is fast — no background job
    finally:
        reset_subagent_factory(ftok)
        reset_origin(otok)
        reset_active_project(ptok)


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
        return _ResumeAgent()

    smap = SessionMap.load(channel_session_path("telegram"))
    smap.set("telegram:12345", "sess-1")
    smap.save()

    state = _FakeState(project=project, agent_factory=agent_factory, delivery_router=router)
    job = _job(project, deliver_to="telegram:12345")

    asyncio.run(make_on_op_finished(state)(job, "Ingested 3/3 file(s)."))
    # Resumed INTO the mapped session with an untrusted-wrapped summary seed…
    assert seen["session_id"] == "sess-1"
    assert "3/3" in seen["prompt"] and "untrusted" in seen["prompt"].lower()
    assert seen["resume_depth"] == 1  # the resume turn carries depth+1
    # …and the resumed turn's own output IS the notification.
    assert len(router.delivered) == 1
    target, text = router.delivered[0]
    assert target == "telegram:12345" and "продолжаю" in text


def test_resume_depth_cap_degrades_to_notify_only(tmp_path: Path) -> None:
    from veles.channels.session_map import SessionMap, channel_session_path
    from veles.daemon.background_ops import make_on_op_finished

    project = _project(tmp_path)
    router = _FakeRouter()

    def agent_factory(session_id, *, prompt=None):  # pragma: no cover
        raise AssertionError("depth-capped completion must NOT resume")

    smap = SessionMap.load(channel_session_path("telegram"))
    smap.set("telegram:12345", "sess-1")
    smap.save()

    state = _FakeState(project=project, agent_factory=agent_factory, delivery_router=router)
    job = _job(project, deliver_to="telegram:12345", resume_depth=1)  # already a resume child

    asyncio.run(make_on_op_finished(state)(job, "Ingested 1/1 file(s)."))
    assert len(router.delivered) == 1  # notified, not resumed
