"""M204 Phase 4: the agent-callable `research` tool (modules/agentops).

Thin wrapper — the kernel stays in `core/orchestration/research.py`
(`run_deep_research`). Inline in a REPL turn (plan → parallel explore →
synthesize via `current_subagent_factory()`); under a chat/daemon turn it
submits a structured `kind="research"` job and reports back via the same
notify+resume path as `wiki_add`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import (
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
from veles.modules.agentops.tools import research


@pytest.fixture(autouse=True)
def _isolated_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    return home


class _ScriptedAgent:
    """Planner (tool-less) answers with angles; explorers return evidence;
    the writer synthesises."""

    def __init__(self, system_prompt: str, tools: list[str] | None, seen: list) -> None:
        self._system = system_prompt or ""
        self.tools = tools
        self._seen = seen

    def run(self, prompt: str, **_kw):
        from veles.core.agent import RunResult

        self._seen.append((self._system, self.tools, prompt))
        if "writer worker" in self._system:
            text = "FINAL REPORT: everything is connected."
        elif "explorer worker" in self._system:
            text = "EVIDENCE: passage [https://s.test]"
        else:  # the planner
            text = '["angle 1", "angle 2"]'
        return RunResult(text=text, iterations=1, stopped_reason="completed")


def _factory(seen: list):
    def factory(*, system_prompt=None, tools=None, **_kw):
        return _ScriptedAgent(system_prompt or "", tools, seen)

    return factory


def test_inline_research_plans_explores_and_returns_report(tmp_path: Path) -> None:
    seen: list = []
    tok = set_subagent_factory(_factory(seen))
    try:
        out = research("How does X work?")
        assert "FINAL REPORT" in out
        # planner ran tool-less; explorers got the research toolset
        planner_calls = [s for s in seen if s[1] == []]
        assert planner_calls, "planner must run with NO tools"
        explorer_tools = [s[1] for s in seen if s[1]]
        assert explorer_tools and all("web_search" in t for t in explorer_tools)
    finally:
        reset_subagent_factory(tok)


def test_research_without_factory_errors() -> None:
    out = research("q")
    assert out.startswith("<error")


def test_research_with_origin_submits_structured_job(tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="r")
    ptok = set_active_project(project)
    otok = set_origin("telegram:777")
    seen: list = []
    ftok = set_subagent_factory(_factory(seen))
    try:
        out = research("How does X work?")
        assert "background" in out.lower()
        assert seen == []  # nothing ran inline

        from veles.core.jobs_store import JobsStore

        store = JobsStore(project.memory_db_path)
        jobs = store.list_jobs()
        store.close()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.kind == "research"
        assert job.deliver_to == "telegram:777"
        assert job.params is not None and job.params["question"] == "How does X work?"
    finally:
        reset_subagent_factory(ftok)
        reset_origin(otok)
        reset_active_project(ptok)


def test_toolset_membership() -> None:
    from veles.core.tools.toolsets import TOOLSETS

    assert "research" in TOOLSETS["run"]
    assert "research" not in TOOLSETS["ingest"]  # sensitive agent-op: [run] only
    assert "research" not in TOOLSETS["builtin"]
    # The explorer toolset is declared declaratively for the daemon's scoped factory.
    assert "web_search" in TOOLSETS["research"] and "run_shell" not in TOOLSETS["research"]


def test_research_kind_handler_drives_the_kernel(tmp_path: Path, monkeypatch) -> None:
    from veles.daemon.background_ops import make_research_kind_handler

    project = init_project(tmp_path / "proj", name="r")
    seen: list = []

    import veles.daemon.background_ops as bg

    monkeypatch.setattr(
        bg, "_scoped_factory_for", lambda args, project, store, toolset: _factory(seen)
    )

    import argparse

    handler = make_research_kind_handler(
        argparse.Namespace(model="m", provider="openrouter"), project=project, store=None
    )

    from types import SimpleNamespace

    job = SimpleNamespace(params={"question": "How does X work?", "max_subquestions": 2})
    out = handler(job)
    assert "FINAL REPORT" in out
    assert seen  # kernel actually ran through the factory
