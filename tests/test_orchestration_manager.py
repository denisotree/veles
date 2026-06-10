"""M122c: manager orchestrator — runtime decomposition with the
no-telephone-game and manager-never-writes invariants enforced."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from veles.core.orchestration import (
    ManagerRunResult,
    PlanContractError,
    WorkerPlan,
    WorkerStep,
    assert_plan_valid,
    build_default_plan,
    decompose_and_run,
    needs_decomposition,
)


# ---- stub Agent ----


@dataclass
class _FakeUsage:
    prompt_tokens: int = 5
    completion_tokens: int = 5


@dataclass
class _FakeResult:
    text: str
    session_id: str
    usage: _FakeUsage = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.usage is None:
            self.usage = _FakeUsage()


class _RoleAgent:
    """Returns a role-specific canned reply tagged with the prompt
    head so tests can verify which prompt landed in which agent."""

    _counter = [0]

    def __init__(self, *, system_prompt: str | None = None) -> None:
        self.system_prompt = system_prompt or ""
        self._counter[0] += 1
        self.session_id = f"sess-{self._counter[0]:04d}"

    def run(self, prompt: str) -> _FakeResult:
        # Tag reply with role + first 30 chars of prompt for assertion
        role = "writer" if "writer worker" in self.system_prompt else (
            "explorer" if "explorer worker" in self.system_prompt else "other"
        )
        return _FakeResult(
            text=f"[{role}] sees: {prompt[:50]}",
            session_id=self.session_id,
        )


def _role_factory():
    """Standard factory: every call returns a fresh _RoleAgent with
    whatever system_prompt was passed."""

    def make(**kwargs: Any) -> _RoleAgent:
        return _RoleAgent(system_prompt=kwargs.get("system_prompt"))

    return make


# ---- needs_decomposition heuristic ----


def test_short_prompt_does_not_need_decomposition() -> None:
    assert not needs_decomposition("what is 2+2?")
    assert not needs_decomposition("fix this bug")


def test_long_prompt_needs_decomposition() -> None:
    long_prompt = "I want to understand " * 10  # well over 80 chars
    assert needs_decomposition(long_prompt)


def test_research_keyword_triggers_decomposition() -> None:
    assert needs_decomposition("research the new feature")
    assert needs_decomposition("compare two approaches")
    assert needs_decomposition("investigate the failure")


# ---- M122c worker-to-worker session hand-off ----


def test_session_digest_loader_renders_transcript() -> None:
    from types import SimpleNamespace

    from veles.core.orchestration import make_session_digest_loader

    msgs = [
        SimpleNamespace(role="system", content="sys prompt", tool_calls=[]),
        SimpleNamespace(role="user", content="find X", tool_calls=[]),
        SimpleNamespace(
            role="assistant", content="", tool_calls=[SimpleNamespace(name="read_file")]
        ),
        SimpleNamespace(role="assistant", content="found it in a.py", tool_calls=[]),
    ]
    store = SimpleNamespace(
        session_exists=lambda sid: True, load_messages=lambda sid: msgs
    )
    digest = make_session_digest_loader(store)("s1")
    assert "[user] find X" in digest
    assert "(tool calls: read_file)" in digest
    assert "found it in a.py" in digest
    assert "sys prompt" not in digest  # system turns filtered out


def test_session_digest_loader_none_for_missing_or_empty() -> None:
    from types import SimpleNamespace

    from veles.core.orchestration import make_session_digest_loader

    missing = SimpleNamespace(session_exists=lambda sid: False, load_messages=lambda sid: [])
    assert make_session_digest_loader(missing)("s1") is None
    assert make_session_digest_loader(missing)(None) is None


def test_decompose_passes_session_transcript_to_writer() -> None:
    """With a session_loader wired, the writer's prompt carries the explorer's
    full session transcript (read by id), not just the pasted final text."""

    def loader(sid):
        return f"DIGEST({sid})" if sid else None

    result = decompose_and_run(
        "research the thing thoroughly",
        agent_factory=_role_factory(),
        session_loader=loader,
    )
    writer_handle = result.handles[-1]
    assert writer_handle.role == "writer"
    assert "Session transcript" in writer_handle.prompt
    assert "DIGEST(sess-" in writer_handle.prompt


def test_decompose_without_loader_still_pastes_result() -> None:
    """No loader → backward-compatible: writer prompt has the pasted output,
    no transcript section."""
    result = decompose_and_run(
        "research the thing thoroughly", agent_factory=_role_factory()
    )
    writer_handle = result.handles[-1]
    assert "Session transcript" not in writer_handle.prompt
    assert "Output from explorer" in writer_handle.prompt


def test_keyword_match_overrides_length() -> None:
    """Even a short prompt with a research keyword should decompose."""
    assert needs_decomposition("research it")


# ---- build_default_plan ----


def test_default_plan_has_explorer_then_writer() -> None:
    plan = build_default_plan("user task")
    roles = [s.role for s in plan.steps]
    assert roles == ["explorer", "writer"]


def test_default_plan_objective_truncated() -> None:
    plan = build_default_plan("x" * 500)
    assert len(plan.objective) <= 120


def test_default_plan_explorer_carries_user_prompt() -> None:
    plan = build_default_plan("find the bug in module X")
    explorer = plan.steps[0]
    assert "find the bug in module X" in explorer.prompt


# ---- assert_plan_valid ----


def test_valid_plan_passes() -> None:
    plan = build_default_plan("task")
    assert_plan_valid(plan)  # no exception


def test_plan_without_writer_rejected() -> None:
    plan = WorkerPlan(objective="t")
    plan.add(WorkerStep(role="explorer", prompt="x"))
    with pytest.raises(PlanContractError) as ei:
        assert_plan_valid(plan)
    assert "writer" in str(ei.value).lower()


def test_plan_with_manager_step_rejected() -> None:
    plan = WorkerPlan(objective="t")
    plan.add(WorkerStep(role="manager", prompt="x"))
    plan.add(WorkerStep(role="writer", prompt="y"))
    with pytest.raises(PlanContractError) as ei:
        assert_plan_valid(plan)
    assert "manager" in str(ei.value).lower()


# ---- decompose_and_run end-to-end ----


def test_decompose_and_run_returns_writer_output() -> None:
    factory = _role_factory()
    result = decompose_and_run("a research task", agent_factory=factory)
    assert isinstance(result, ManagerRunResult)
    assert result.error is None
    assert result.final_text is not None
    assert "[writer]" in result.final_text


def test_decompose_and_run_runs_both_workers() -> None:
    factory = _role_factory()
    result = decompose_and_run("research the project", agent_factory=factory)
    # 2 workers: explorer + writer
    assert len(result.handles) == 2
    roles = [h.role for h in result.handles]
    assert roles == ["explorer", "writer"]


def test_writer_receives_explorer_raw_output_verbatim() -> None:
    """No-telephone-game: writer's prompt contains the explorer's
    *raw* result string, not a manager paraphrase."""
    factory = _role_factory()
    result = decompose_and_run("explore X", agent_factory=factory)
    writer_handle = result.handles[1]
    explorer_handle = result.handles[0]
    # Writer was invoked with a prompt that quotes explorer output.
    # Our _RoleAgent.run records the *prompt* it saw in its reply.
    # The writer's reply head shows the prompt; check that the
    # explorer's output text is referenced inside.
    assert explorer_handle.result is not None
    assert writer_handle.result is not None
    # The reply text shows the writer received a prompt that contained
    # the explorer's role marker — the verbatim payload made it through.
    # Direct check: writer's prompt (preserved on the handle) embeds
    # the explorer's session id and output.
    assert "explorer" in writer_handle.prompt.lower()
    assert explorer_handle.result in writer_handle.prompt


def test_plan_status_reflects_completion() -> None:
    factory = _role_factory()
    result = decompose_and_run("research task", agent_factory=factory)
    # Both steps should be marked done
    for step in result.plan.steps:
        assert step.status == "done", (step.role, step.status)
    # session_ids carried through
    assert all(s.session_id is not None for s in result.plan.steps)


def test_writer_failure_surfaced_on_result() -> None:
    """When the writer raises, the orchestrator reports the error
    rather than crashing the manager."""

    class _BadWriter:
        def __init__(self, **kwargs: Any) -> None:
            self.system_prompt = kwargs.get("system_prompt", "")

        def run(self, prompt: str):
            if "writer worker" in self.system_prompt:
                raise RuntimeError("writer down")
            return _FakeResult(text=f"explored: {prompt[:30]}", session_id="x")

    def factory(**kwargs):
        return _BadWriter(**kwargs)

    result = decompose_and_run("research task", agent_factory=factory)
    assert result.final_text is None
    assert result.error is not None
    assert "writer down" in result.error


def test_explorer_failure_does_not_block_writer() -> None:
    """If the explorer errors, the writer still runs — it sees the
    failure note in its prompt and decides how to respond. The
    manager doesn't paper over the error."""

    class _BadExplorer:
        def __init__(self, **kwargs: Any) -> None:
            self.system_prompt = kwargs.get("system_prompt", "")

        def run(self, prompt: str):
            if "explorer worker" in self.system_prompt:
                raise RuntimeError("explorer down")
            return _FakeResult(
                text=f"[writer saw failure?] head: {prompt[:80]}",
                session_id="w1",
            )

    def factory(**kwargs):
        return _BadExplorer(**kwargs)

    result = decompose_and_run("research task", agent_factory=factory)
    # Writer ran despite explorer error
    assert result.final_text is not None
    # Writer's prompt mentions the failure
    writer_handle = result.handles[1]
    assert "failed" in writer_handle.prompt.lower()


def test_custom_plan_builder_honoured() -> None:
    """Callers can pass their own `plan_builder` to override the
    default 2-worker shape."""

    def three_worker_plan(prompt: str) -> WorkerPlan:
        plan = WorkerPlan(objective=prompt[:50])
        plan.add(WorkerStep(role="explorer", prompt=f"explore: {prompt}"))
        plan.add(WorkerStep(role="advisor", prompt=f"review: {prompt}"))
        plan.add(WorkerStep(role="writer", prompt="<replaced>"))
        return plan

    factory = _role_factory()
    result = decompose_and_run(
        "research task",
        agent_factory=factory,
        plan_builder=three_worker_plan,
    )
    assert len(result.handles) == 3
    assert [h.role for h in result.handles] == ["explorer", "advisor", "writer"]


def test_plan_without_writer_via_custom_builder_rejected() -> None:
    """The contract check fires for custom builders too."""

    def bad_builder(prompt: str) -> WorkerPlan:
        plan = WorkerPlan(objective=prompt)
        plan.add(WorkerStep(role="explorer", prompt="x"))
        return plan

    factory = _role_factory()
    result = decompose_and_run(
        "task", agent_factory=factory, plan_builder=bad_builder
    )
    assert result.final_text is None
    assert result.error is not None
    assert "writer" in result.error.lower()


def test_factory_kwargs_flow_through() -> None:
    """`factory_kwargs` reaches every spawn — useful for pinning
    model/max_iterations per manager invocation."""
    captured: list[dict] = []

    def factory(**kwargs):
        captured.append(dict(kwargs))
        return _RoleAgent(system_prompt=kwargs.get("system_prompt"))

    decompose_and_run(
        "research task",
        agent_factory=factory,
        factory_kwargs={"model": "test-model", "max_iterations": 7},
    )
    # Both workers received the kwarg
    assert len(captured) >= 2
    for kw in captured:
        assert kw.get("model") == "test-model"
        assert kw.get("max_iterations") == 7
