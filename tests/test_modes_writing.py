"""WritingMode — the Phase-1 isomorphic refactor of the bridge's
`agent.run` call.

We don't need Textual at all here; `Mode.run_turn` only touches the
`ModeContext` callbacks. A fake `Agent` and fake `factory` exercise
every contract the bridge relies on:

  - factory is called with the current AppState
  - agent.run is called with the prompt + both side channels
  - session_id created on the first turn is mirrored back to AppState
  - exactly one TurnDone is posted with the RunResult
  - the RunResult inside TurnDone is the same object the agent returned
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tests.conftest import FakeAgent as _FakeAgent
from veles.core.agent import RunResult
from veles.core.modes import ModeContext, WritingMode
from veles.tui.messages import TurnDone
from veles.tui.state import AppState


@dataclass
class _Recorder:
    state: AppState
    project: object = None
    posted: list[Any] = field(default_factory=list)
    factory_calls: list[AppState] = field(default_factory=list)

    def make_ctx(self, agent: _FakeAgent) -> ModeContext:
        def factory(state: AppState) -> _FakeAgent:
            self.factory_calls.append(state)
            return agent

        def post(msg: Any) -> None:
            self.posted.append(msg)

        return ModeContext(
            state=self.state,
            project=self.project,  # type: ignore[arg-type]
            factory=factory,  # type: ignore[arg-type]
            post=post,
            on_text=lambda _t: None,
            on_event=lambda _e: None,
        )


def _state(*, session_id: str | None = None) -> AppState:
    return AppState(session_id=session_id, provider_name="stub", model="m")


def test_writing_mode_delegates_to_factory_and_agent_run() -> None:
    """WritingMode calls factory(state) once and agent.run(prompt) once,
    forwarding both streaming callbacks."""
    state = _state()
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s1"))
    rec = _Recorder(state=state)
    ctx = rec.make_ctx(agent)

    WritingMode().run_turn("hello", ctx)

    assert len(rec.factory_calls) == 1
    assert rec.factory_calls[0] is state
    assert agent.seen_prompt == "hello"
    # The bridge's on_text / on_event are passed through verbatim.
    assert agent.seen_on_text is ctx.on_text
    assert agent.seen_on_event is ctx.on_event


def test_writing_mode_posts_exactly_one_turn_done() -> None:
    state = _state()
    result = RunResult(text="reply", iterations=2, session_id="s9")
    agent = _FakeAgent(result=result)
    rec = _Recorder(state=state)

    WritingMode().run_turn("hi", rec.make_ctx(agent))

    assert len(rec.posted) == 1
    msg = rec.posted[0]
    assert isinstance(msg, TurnDone)
    assert msg.result is result


def test_writing_mode_propagates_new_session_id_into_state() -> None:
    """First-turn session_id mints flow back to AppState so the next
    turn resumes the same SessionStore row."""
    state = _state(session_id=None)
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="fresh-1"))

    WritingMode().run_turn("p", _Recorder(state=state).make_ctx(agent))

    assert state.session_id == "fresh-1"


def test_writing_mode_does_not_overwrite_existing_session_id() -> None:
    """If AppState already has a session_id, agent's reported id never
    overrides it — slash `/load` and friends own that field."""
    state = _state(session_id="external")
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="other"))

    WritingMode().run_turn("p", _Recorder(state=state).make_ctx(agent))

    assert state.session_id == "external"


def test_writing_mode_records_itself_in_last_mode_in_session() -> None:
    """Each Mode tracks the effective mode it just ran with, so the
    next turn's mid-session mode-switch check sees the truth. Without
    this, AutoMode → WritingMode would leave `last_mode_in_session`
    pointing at `"auto"` and PlanningMode's wrapper would re-fire next
    time auto routed to planning."""
    state = _state()
    state.last_mode_in_session = None
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s1"))

    WritingMode().run_turn("p", _Recorder(state=state).make_ctx(agent))

    assert state.last_mode_in_session == "writing"


def test_writing_mode_wraps_prompt_on_switch_from_planning() -> None:
    """Switching planning → writing must inject a mode-switch observation so
    the model knows the planning restriction is lifted — otherwise it keeps
    parroting its own earlier 'switch to writing first' refusals from history."""
    state = _state()
    state.last_mode_in_session = "planning"  # type: ignore[assignment]
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s1"))

    WritingMode().run_turn("Реализуй план", _Recorder(state=state).make_ctx(agent))

    body = agent.seen_prompt or ""
    assert "<mode-switch-observation>" in body
    assert "writing" in body
    assert "lifted" in body.lower()  # the restriction-lifted note
    assert "Реализуй план" in body  # the user's actual request still present


def test_writing_mode_no_wrap_when_already_writing() -> None:
    state = _state()
    state.last_mode_in_session = "writing"  # type: ignore[assignment]
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s1"))

    WritingMode().run_turn("hi", _Recorder(state=state).make_ctx(agent))

    assert "<mode-switch-observation>" not in (agent.seen_prompt or "")


def test_writing_mode_no_wrap_on_first_turn() -> None:
    state = _state()
    state.last_mode_in_session = None
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id="s1"))

    WritingMode().run_turn("hi", _Recorder(state=state).make_ctx(agent))

    assert "<mode-switch-observation>" not in (agent.seen_prompt or "")


def test_writing_mode_propagates_none_session_id_safely() -> None:
    """If the agent never assigns a session_id (e.g. SessionStore
    disabled), AppState stays at None — no crash, no mutation."""
    state = _state(session_id=None)
    agent = _FakeAgent(result=RunResult(text="ok", iterations=1, session_id=None))

    WritingMode().run_turn("p", _Recorder(state=state).make_ctx(agent))

    assert state.session_id is None
