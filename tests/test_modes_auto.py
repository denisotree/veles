"""AutoMode — per-turn classifier + sub-dispatch.

Two surfaces to pin:

  - `classify(prompt, provider, model)` — a pure function over a
    fake provider. Maps response text → "plan" | "direct" with a
    permissive default. Errors degrade to "direct" (rather than
    forcing the user through planning on a flaky network).

  - `AutoMode.run_turn` — wraps `classify`, posts a `[auto → X]`
    SystemLine, then sub-dispatches to PlanningMode or WritingMode.
    Critically: the *sub-Mode* writes `state.last_mode_in_session`,
    not AutoMode (so mid-session mode-switch detection sees the
    effective mode, not "auto").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tests.conftest import FakeAgent as _FakeAgent
from veles.core.agent import RunResult
from veles.core.agent_events import SystemLine, TurnDone
from veles.core.modes import AutoMode, ModeContext
from veles.core.modes.auto import classify
from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.session_state import AppState


@dataclass
class _FakeProvider:
    """Records the messages it was called with; returns canned text."""

    canned_text: str = "direct"
    raise_on_call: bool = False
    seen_messages: list[Any] = field(default_factory=list)

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        del tools, model, max_tokens
        self.seen_messages.append(messages)
        if self.raise_on_call:
            raise RuntimeError("simulated provider failure")
        return ProviderResponse(
            text=self.canned_text,
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            finish_reason="stop",
        )


# ---- classifier (pure function) ----


def test_classify_returns_plan_on_exact_plan() -> None:
    p = _FakeProvider(canned_text="plan")
    assert classify("design X", p, "m") == "plan"


def test_classify_returns_plan_on_prefixed_plan() -> None:
    p = _FakeProvider(canned_text="Plan.\n")
    assert classify("design X", p, "m") == "plan"


def test_classify_returns_direct_on_direct() -> None:
    p = _FakeProvider(canned_text="direct")
    assert classify("read foo.py", p, "m") == "direct"


def test_classify_falls_back_to_direct_on_garbage() -> None:
    """Permissive default — unexpected output should not push the
    user through PlanningMode."""
    p = _FakeProvider(canned_text="???")
    assert classify("anything", p, "m") == "direct"


def test_classify_returns_direct_on_provider_error() -> None:
    """A network/provider error degrades to direct, not planning, so
    a flaky provider doesn't drag the user into read-only mode."""
    p = _FakeProvider(raise_on_call=True)
    assert classify("anything", p, "m") == "direct"


def test_classify_sends_user_prompt_to_provider() -> None:
    """The classifier sends the original prompt verbatim — no truncation,
    no rewriting. Lets the provider see the real intent."""
    p = _FakeProvider(canned_text="direct")
    classify("hello world", p, "m")
    msgs = p.seen_messages[0]
    user_messages = [m for m in msgs if m.role == "user"]
    assert any("hello world" in (m.content or "") for m in user_messages)


# ---- AutoMode.run_turn (sub-dispatch + SystemLine) ----


@dataclass
class _Recorder:
    state: AppState
    provider: _FakeProvider
    posted: list[Any] = field(default_factory=list)
    factory_calls: list[dict] = field(default_factory=list)

    def make_ctx(self) -> ModeContext:
        def factory(state: AppState, **kwargs) -> _FakeAgent:
            self.factory_calls.append(kwargs)
            return _FakeAgent(
                provider=self.provider,
                result=RunResult(text="ok", iterations=1, session_id="s-1"),
            )

        return ModeContext(
            state=self.state,
            project=None,  # type: ignore[arg-type]
            factory=factory,  # type: ignore[arg-type]
            post=self.posted.append,
            on_text=lambda _t: None,
            on_event=lambda _e: None,
        )


def _state(mode: str = "auto", last_mode: str | None = None) -> AppState:
    return AppState(
        session_id=None,
        provider_name="stub",
        model="m",
        mode=mode,  # type: ignore[arg-type]
        last_mode_in_session=last_mode,  # type: ignore[arg-type]
    )


def test_auto_mode_posts_routing_decision_to_chat() -> None:
    provider = _FakeProvider(canned_text="plan")
    rec = _Recorder(state=_state(), provider=provider)

    AutoMode().run_turn("design X", rec.make_ctx())

    system_lines = [m for m in rec.posted if isinstance(m, SystemLine)]
    assert len(system_lines) == 1
    assert system_lines[0].text == "[auto → plan]"


def test_auto_routes_direct_verdict_to_writing() -> None:
    """`direct` → WritingMode behaviour: no `<mode-switch-observation>`
    wrapper, `last_mode_in_session` is `"writing"` after the turn."""
    provider = _FakeProvider(canned_text="direct")
    rec = _Recorder(state=_state(), provider=provider)

    AutoMode().run_turn("what's in README", rec.make_ctx())

    assert rec.state.last_mode_in_session == "writing"
    # SystemLine appears once.
    sys_lines = [m for m in rec.posted if isinstance(m, SystemLine)]
    assert sys_lines and sys_lines[0].text == "[auto → direct]"
    # TurnDone fires after sub-dispatch.
    assert any(isinstance(m, TurnDone) for m in rec.posted)


def test_auto_routes_plan_verdict_to_planning() -> None:
    """`plan` → PlanningMode behaviour: `last_mode_in_session` is
    `"planning"` after the turn, so the next auto→plan turn doesn't
    re-inject the observation block."""
    provider = _FakeProvider(canned_text="plan")
    rec = _Recorder(state=_state(), provider=provider)

    AutoMode().run_turn("design migration M", rec.make_ctx())

    assert rec.state.last_mode_in_session == "planning"
    sys_lines = [m for m in rec.posted if isinstance(m, SystemLine)]
    assert sys_lines and sys_lines[0].text == "[auto → plan]"


def test_auto_does_not_set_last_mode_to_auto() -> None:
    """The crux of the advisor fix: AutoMode never overwrites
    `last_mode_in_session` with `"auto"`. The effective sub-Mode owns
    that field."""
    provider = _FakeProvider(canned_text="plan")
    rec = _Recorder(state=_state(), provider=provider)

    AutoMode().run_turn("p", rec.make_ctx())

    assert rec.state.last_mode_in_session != "auto"


def test_auto_factory_first_call_is_writing_for_scratch_provider() -> None:
    """AutoMode builds a throwaway agent with `mode_override="writing"`
    just for its provider reference, before deciding which sub-Mode to
    dispatch to. The actual sub-Mode then makes its own factory call."""
    provider = _FakeProvider(canned_text="direct")
    rec = _Recorder(state=_state(), provider=provider)

    AutoMode().run_turn("p", rec.make_ctx())

    # Two factory calls total: one for scratch provider, one for the
    # actual sub-Mode (Writing in this case).
    assert len(rec.factory_calls) == 2
    assert rec.factory_calls[0].get("mode_override") == "writing"
