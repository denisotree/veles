"""M122 MVP: spawn helper, plan/checkboxes, mini-report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.orchestration import (
    ROLE_PROMPTS,
    WorkerHandle,
    WorkerPlan,
    WorkerRole,
    WorkerStep,
    mini_report,
    spawn,
)

# ---- stub Agent ----


@dataclass
class _FakeUsage:
    prompt_tokens: int = 10
    completion_tokens: int = 5


@dataclass
class _FakeResult:
    text: str
    session_id: str = "sess-stub"
    usage: _FakeUsage = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.usage is None:
            self.usage = _FakeUsage()


class _FakeAgent:
    """Records what it was constructed with and returns a canned reply."""

    def __init__(self, *, system_prompt: str | None = None, reply: str = "ok") -> None:
        self.system_prompt = system_prompt
        self._reply = reply
        self.runs: list[str] = []

    def run(self, prompt: str) -> _FakeResult:
        self.runs.append(prompt)
        return _FakeResult(text=f"{self._reply}: {prompt}")


def _factory_for(reply: str = "ok"):
    captured: dict = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return _FakeAgent(
            system_prompt=kwargs.get("system_prompt"),
            reply=reply,
        )

    factory.captured = captured  # type: ignore[attr-defined]
    return factory


# ---- spawn ----


def test_spawn_uses_role_system_prompt() -> None:
    factory = _factory_for()
    handle = spawn("explorer", "find files", agent_factory=factory)
    assert handle.role == "explorer"
    assert handle.error is None
    # Factory got the explorer system prompt
    assert "explorer worker" in factory.captured["system_prompt"]
    # Agent.run was called with the worker prompt verbatim
    assert "find files" in handle.result


def test_spawn_parallel_propagates_caller_context_to_workers() -> None:
    """M148 follow-up: ThreadPoolExecutor threads start with a fresh context,
    so spawn_parallel must run each worker inside a copy of the caller's
    context — otherwise `current_budget()` / `current_project()` are None in
    the workers and `--max-tokens-total` silently doesn't apply."""
    from veles.core.context import (
        TokenBudget,
        current_budget,
        reset_budget,
        set_budget,
    )
    from veles.core.orchestration import spawn_parallel

    seen: list[int | None] = []

    class _CtxAgent:
        def run(self, prompt: str) -> _FakeResult:
            b = current_budget()
            seen.append(b.limit if b is not None else None)
            return _FakeResult(text="ok")

    def factory(**kwargs):
        return _CtxAgent()

    token = set_budget(TokenBudget(limit=12345))
    try:
        spawn_parallel([("explorer", "a"), ("explorer", "b")], agent_factory=factory)
    finally:
        reset_budget(token)

    assert seen == [12345, 12345]  # both parallel workers saw the caller's budget


def test_spawn_explicit_system_prompt_wins() -> None:
    factory = _factory_for()
    handle = spawn(
        "explorer",
        "find files",
        agent_factory=factory,
        system_prompt="custom prompt",
    )
    assert handle.error is None
    assert factory.captured["system_prompt"] == "custom prompt"


def test_spawn_carries_session_id_and_usage() -> None:
    factory = _factory_for()
    handle = spawn("writer", "synthesise", agent_factory=factory)
    assert handle.session_id == "sess-stub"
    assert handle.tokens_in == 10
    assert handle.tokens_out == 5


def test_spawn_catches_factory_exception() -> None:
    def broken_factory(**_kwargs):
        raise RuntimeError("boom")

    handle = spawn("advisor", "review", agent_factory=broken_factory)
    assert handle.result is None
    assert handle.error is not None
    assert "boom" in handle.error


def test_spawn_catches_run_exception() -> None:
    class _ExplodingAgent:
        def run(self, _prompt: str) -> None:
            raise RuntimeError("run-failed")

    def factory(**_kwargs):
        return _ExplodingAgent()

    handle = spawn("explorer", "x", agent_factory=factory)
    assert handle.error is not None
    assert "run-failed" in handle.error


def test_spawn_passes_factory_kwargs_through() -> None:
    factory = _factory_for()
    spawn(
        "writer",
        "go",
        agent_factory=factory,
        factory_kwargs={"max_iterations": 7, "model": "test-model"},
    )
    assert factory.captured["max_iterations"] == 7
    assert factory.captured["model"] == "test-model"


def test_unknown_role_string_still_works() -> None:
    """Custom roles (not in `WorkerRole` enum) work — `spawn` just
    won't find a default system_prompt for them."""
    factory = _factory_for()
    handle = spawn("custom_researcher", "do x", agent_factory=factory)
    assert handle.error is None
    assert handle.role == "custom_researcher"
    # No default prompt for the custom role → factory got None
    assert factory.captured.get("system_prompt") is None


def test_role_prompts_cover_four_canonical_roles() -> None:
    for role in (
        WorkerRole.EXPLORER,
        WorkerRole.WRITER,
        WorkerRole.ADVISOR,
        WorkerRole.MANAGER,
    ):
        assert role.value in ROLE_PROMPTS
        assert ROLE_PROMPTS[role.value]


# ---- WorkerPlan ----


def test_worker_plan_checkbox_render() -> None:
    plan = WorkerPlan(objective="solve X")
    plan.add(WorkerStep(role="explorer", prompt="find Y"))
    plan.add(WorkerStep(role="writer", prompt="compose Z", status="done"))
    plan.add(WorkerStep(role="advisor", prompt="review", status="failed"))
    rendered = plan.render()
    assert "# Plan: solve X" in rendered
    assert "[ ] explorer" in rendered
    assert "[x] writer" in rendered
    assert "[!] advisor" in rendered


def test_worker_plan_to_json_roundtrip() -> None:
    plan = WorkerPlan(objective="task")
    plan.add(
        WorkerStep(
            role="explorer",
            prompt="find",
            rationale="need evidence first",
            status="in_progress",
            session_id="sess-e1",
            result_summary="found 3 files",
        )
    )
    payload = json.loads(plan.to_json())
    assert payload["objective"] == "task"
    assert len(payload["steps"]) == 1
    step = payload["steps"][0]
    assert step["role"] == "explorer"
    assert step["status"] == "in_progress"
    assert step["session_id"] == "sess-e1"
    assert step["result_summary"] == "found 3 files"


def test_worker_step_in_progress_renders_tilde() -> None:
    s = WorkerStep(role="writer", prompt="draft", status="in_progress")
    assert "[~]" in s.to_checkbox_line()


# ---- mini_report ----


@pytest.fixture()
def conn(tmp_path: Path):
    store = SessionStore(tmp_path / "memory.db")
    yield store._conn
    store._conn.close()


def test_mini_report_writes_insight_row(conn) -> None:
    rid = mini_report(
        conn,
        objective="solve X",
        what_was_done="explored files, wrote summary",
        why_this_decomposition="parallel evidence gathering then synthesis",
        challenges="evidence was thin in one corner",
    )
    assert rid > 0
    row = conn.execute("SELECT title, body, category FROM insights WHERE id = ?", (rid,)).fetchone()
    assert "solve X" in row["title"]
    assert "What was done" in row["body"]
    assert "Why this decomposition" in row["body"]
    assert "Challenges" in row["body"]
    assert row["category"] == "manager-report"


def test_mini_report_omits_challenges_when_empty(conn) -> None:
    rid = mini_report(
        conn,
        objective="quick task",
        what_was_done="single writer turn",
        why_this_decomposition="trivial decomposition",
    )
    row = conn.execute("SELECT body FROM insights WHERE id = ?", (rid,)).fetchone()
    assert "Challenges" not in row["body"]


def test_mini_report_findable_via_fts(conn) -> None:
    """Insight FTS triggers (M119) populate immediately."""
    mini_report(
        conn,
        objective="hierarchical orchestration test",
        what_was_done="ran three workers",
        why_this_decomposition="manager-spawn pattern",
    )
    rows = conn.execute(
        "SELECT title FROM insights_fts WHERE insights_fts MATCH ?",
        ("orchestration",),
    ).fetchall()
    assert any("orchestration" in r["title"] for r in rows)


# ---- WorkerHandle ----


def test_worker_handle_default_values() -> None:
    h = WorkerHandle(role="explorer", prompt="x")
    assert h.result is None
    assert h.error is None
    assert h.session_id is None
    assert h.tokens_in == 0
    assert h.tokens_out == 0


# ---- spawn_parallel (M122b) ----


def test_spawn_parallel_empty_returns_empty_list() -> None:
    from veles.core.orchestration import spawn_parallel

    out = spawn_parallel([], agent_factory=_factory_for())
    assert out == []


def test_spawn_parallel_preserves_input_order() -> None:
    """Each handle lines up with its spec by position — important when
    the manager wants `handles[0]` to be the explorer it asked for."""
    from veles.core.orchestration import WorkerSpec, spawn_parallel

    factory = _factory_for(reply="done")
    specs = [
        WorkerSpec(role="explorer", prompt="find A"),
        WorkerSpec(role="writer", prompt="write B"),
        WorkerSpec(role="advisor", prompt="review C"),
    ]
    handles = spawn_parallel(specs, agent_factory=factory)
    assert len(handles) == 3
    assert [h.role for h in handles] == ["explorer", "writer", "advisor"]
    assert [h.prompt for h in handles] == ["find A", "write B", "review C"]


def test_spawn_parallel_tuple_form_accepted() -> None:
    """Bare tuples work — 2-tuple, 3-tuple, 4-tuple all accepted."""
    from veles.core.orchestration import spawn_parallel

    factory = _factory_for()
    handles = spawn_parallel(
        [
            ("explorer", "find"),
            ("writer", "write", "custom-prompt"),
            ("advisor", "review", None, {"model": "x"}),
        ],
        agent_factory=factory,
    )
    assert [h.role for h in handles] == ["explorer", "writer", "advisor"]
    assert all(h.error is None for h in handles)


def test_spawn_parallel_tuple_bad_length_raises() -> None:
    from veles.core.orchestration import spawn_parallel

    with pytest.raises(ValueError):
        spawn_parallel([("only_one_field",)], agent_factory=_factory_for())


def test_spawn_parallel_isolates_errors() -> None:
    """If one worker's factory raises, the others still complete and
    the error is surfaced on the offending handle."""
    from veles.core.orchestration import WorkerSpec, spawn_parallel

    calls: list[str] = []

    def factory(**kwargs):
        role = kwargs.get("system_prompt", "")
        if "advisor" in role:
            raise RuntimeError("advisor down")
        calls.append(role[:20])
        return _FakeAgent(system_prompt=kwargs.get("system_prompt"))

    handles = spawn_parallel(
        [
            WorkerSpec(role="explorer", prompt="find"),
            WorkerSpec(role="advisor", prompt="review"),
            WorkerSpec(role="writer", prompt="write"),
        ],
        agent_factory=factory,
    )
    assert handles[0].error is None
    assert handles[1].error is not None
    assert "advisor down" in handles[1].error
    assert handles[2].error is None


def test_spawn_parallel_runs_concurrently() -> None:
    """Wall time for N slow workers in a pool of N should be roughly
    the slowest worker, not their sum."""
    import time as _time

    from veles.core.orchestration import WorkerSpec, spawn_parallel

    class _SlowAgent:
        def __init__(self, **_kw) -> None:
            pass

        def run(self, prompt: str):
            _time.sleep(0.1)
            return _FakeResult(text=prompt)

    def factory(**_kwargs):
        return _SlowAgent()

    specs = [WorkerSpec(role="explorer", prompt=f"task-{i}") for i in range(5)]
    t0 = _time.monotonic()
    handles = spawn_parallel(specs, agent_factory=factory)
    elapsed = _time.monotonic() - t0
    # 5 workers × 0.1s sleep, serially would be ~0.5s; in parallel
    # should be well under 0.3s (allows generous thread overhead).
    assert elapsed < 0.3, f"expected parallel execution, took {elapsed}s"
    assert len(handles) == 5
    assert all(h.error is None for h in handles)


def test_spawn_parallel_respects_max_concurrent_cap() -> None:
    """A bounded pool runs workers in parallel but never exceeds the cap.

    Observes the actual peak concurrency rather than wall-clock time —
    a timing assertion was flaky on slow/variable CI runners, where the
    scheduling overhead of two batches could exceed the budget for one.
    """
    import threading
    import time as _time

    from veles.core.orchestration import WorkerSpec, spawn_parallel

    lock = threading.Lock()
    active = 0
    peak = 0

    class _SlowAgent:
        def __init__(self, **_kw) -> None:
            pass

        def run(self, prompt: str):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            _time.sleep(0.05)
            with lock:
                active -= 1
            return _FakeResult(text=prompt)

    def factory(**_kwargs):
        return _SlowAgent()

    specs = [WorkerSpec(role="x", prompt=f"t-{i}") for i in range(6)]
    spawn_parallel(specs, agent_factory=factory, max_concurrent=2)
    # Cap honoured (never more than 2 at once) and the pool is genuinely
    # parallel (it actually reached the cap, not serialised to 1).
    assert peak == 2, f"expected peak concurrency of exactly 2, saw {peak}"
