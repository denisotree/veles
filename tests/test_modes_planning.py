"""PlanningMode — orchestration layer over the existing Planning State
plumbing.

The Permission Engine already has thorough coverage in
`tests/test_planning_mode.py` (rule denies mutations, allows reads,
resets after a run, etc.). These tests focus on the PlanningMode-
specific *bridge* responsibilities:

  - flips `mode_override="planning"` on the factory call so the factory
    builds an Agent with `plan_mode=True` and the planning toolset
  - wraps mid-session prompts with `<mode-switch-observation>` so the
    model sees the new mode's rules even when the constructor system
    prompt is no longer being re-emitted
  - leaves fresh-session prompts unwrapped (the factory's job is to
    bake the system block into the constructor prompt)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tests.conftest import FakeAgent as _FakeAgent
from veles.core.agent import RunResult
from veles.core.agent_events import TurnDone
from veles.core.modes import ModeContext, PlanningMode
from veles.core.session_state import AppState


@dataclass
class _Recorder:
    state: AppState
    project: object = None
    posted: list[Any] = field(default_factory=list)
    factory_calls: list[tuple[AppState, dict]] = field(default_factory=list)

    def make_ctx(self, agent: _FakeAgent) -> ModeContext:
        def factory(state: AppState, **kwargs) -> _FakeAgent:
            self.factory_calls.append((state, kwargs))
            return agent

        return ModeContext(
            state=self.state,
            project=self.project,  # type: ignore[arg-type]
            factory=factory,  # type: ignore[arg-type]
            post=self.posted.append,
            on_text=lambda _t: None,
            on_event=lambda _e: None,
        )


def _state(*, session_id: str | None = None, last_mode: str | None = None) -> AppState:
    return AppState(
        session_id=session_id,
        provider_name="stub",
        model="m",
        mode="planning",
        last_mode_in_session=last_mode,  # type: ignore[arg-type]
    )


def test_planning_mode_passes_mode_override_to_factory() -> None:
    """The factory call signals `planning` so the REPL's per-turn Agent
    factory picks the planning toolset registry and enables `plan_mode=True`."""
    state = _state()
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s1"))
    rec = _Recorder(state=state)

    PlanningMode().run_turn("plan X", rec.make_ctx(agent))

    assert len(rec.factory_calls) == 1
    _, kwargs = rec.factory_calls[0]
    assert kwargs.get("mode_override") == "planning"


def test_planning_mode_posts_exactly_one_turn_done() -> None:
    state = _state()
    result = RunResult(text="ok", iterations=1, session_id="s9")
    agent = _FakeAgent(result=result)
    rec = _Recorder(state=state)

    PlanningMode().run_turn("plan it", rec.make_ctx(agent))

    assert len(rec.posted) == 1
    msg = rec.posted[0]
    assert isinstance(msg, TurnDone)
    assert msg.result is result


def test_planning_mode_does_not_wrap_prompt_on_fresh_session() -> None:
    """Fresh sessions (`session_id is None`) get the system block baked
    into the constructor prompt by the factory — Mode must not also
    inject it into the user prompt or the model sees it twice."""
    state = _state(session_id=None, last_mode=None)
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s1"))

    PlanningMode().run_turn("plan now", _Recorder(state=state).make_ctx(agent))

    assert agent.seen_prompt == "plan now"
    assert "<mode-switch-observation>" not in (agent.seen_prompt or "")


def test_planning_mode_wraps_prompt_on_mid_session_mode_switch() -> None:
    """When the user toggled to planning mid-session, the next prompt
    carries an observation block so the model sees the new rules."""
    state = _state(session_id="s-1", last_mode="writing")
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s-1"))

    PlanningMode().run_turn("plan it", _Recorder(state=state).make_ctx(agent))

    body = agent.seen_prompt or ""
    assert "<mode-switch-observation>" in body
    assert "Active mode is now: planning" in body
    # The original prompt is still present after the observation block.
    assert body.endswith("plan it")


def test_planning_mode_does_not_wrap_when_already_in_planning() -> None:
    """Two consecutive planning turns: only the first needed the block,
    the model has already adapted by the second."""
    state = _state(session_id="s-1", last_mode="planning")
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s-1"))

    PlanningMode().run_turn("continue", _Recorder(state=state).make_ctx(agent))

    assert agent.seen_prompt == "continue"


def test_planning_mode_does_not_wrap_when_last_mode_unknown() -> None:
    """First turn of a resumed session: `last_mode_in_session` is None
    because we don't know what mode the previous TUI invocation used.
    Don't speculate — skip the wrapper. The factory still picked the
    planning registry, so behaviour is correct from this turn on."""
    state = _state(session_id="s-1", last_mode=None)
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s-1"))

    PlanningMode().run_turn("plan it", _Recorder(state=state).make_ctx(agent))

    assert "<mode-switch-observation>" not in (agent.seen_prompt or "")


def test_planning_mode_propagates_new_session_id_into_state() -> None:
    state = _state(session_id=None)
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="fresh-1"))

    PlanningMode().run_turn("plan", _Recorder(state=state).make_ctx(agent))

    assert state.session_id == "fresh-1"


def test_planning_mode_records_itself_in_last_mode_in_session() -> None:
    """Same contract as WritingMode: each Mode writes its own name so
    AutoMode's sub-dispatch tracks the effective mode, not `"auto"`."""
    state = _state()
    state.last_mode_in_session = None
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s-1"))

    PlanningMode().run_turn("p", _Recorder(state=state).make_ctx(agent))

    assert state.last_mode_in_session == "planning"


def test_planning_mode_has_non_empty_system_block() -> None:
    """The system block is the contract with the model — must not regress
    to empty (otherwise the factory's `if mode.system_block.strip()`
    branch silently disables planning guidance for fresh sessions)."""
    block = PlanningMode().system_block
    assert block.strip()
    assert "PLANNING mode" in block
    assert "create_plan" in block


def test_planning_mode_forwards_raw_query_to_factory_for_recall() -> None:
    """M191: PlanningMode forwards the raw user prompt to the factory as
    `query=` so the per-turn system prompt injects <memory-context> recall."""
    state = _state(session_id="s0", last_mode="writing")  # forces prompt wrapping
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s1"))
    rec = _Recorder(state=state)

    PlanningMode().run_turn("design the wiki structure", rec.make_ctx(agent))

    assert rec.factory_calls[0][1].get("query") == "design the wiki structure"
