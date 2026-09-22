"""Run one daemon turn through an agent mode (M280).

The REPL drives a turn as `get_mode(state.mode).run_turn(prompt, ctx)`; the
daemon ran a bare `agent.run`, so a chat's `/mode` choice was stored and never
used. This adapts the REPL's `ModeContext` contract to a daemon run:

- **state** — an `AppState` seeded from the session's `ChatModeState` and
  written back after the turn (the fields a mode may change: last mode used,
  active goal, and `mode` itself — GoalMode returns to "auto" when a goal ends,
  which for a chat means back to its default).
- **factory** — the daemon's agent factory with the turn's session id fixed.
  A mode builds several agents per turn (AutoMode's scratch agent, GoalMode's
  phases); none of them may mint a session of its own.
- **post** — `ChatDelta` is text (GoalMode's confirmation line goes this way,
  not through `on_text`), `SystemLine` becomes a `notice` event, `TurnDone`
  is the turn's result, `AgentError` is raised for the runner to report.

A phase-transition turn ends with a synthetic result whose text may be the
advisor's raw JSON (GoalMode's CHECK); what the chat sees instead is exactly
what the turn streamed, possibly nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from veles.core.agent import RunResult
from veles.daemon.runner import TurnFn
from veles.daemon.state import ChatModeState, DaemonState


def make_mode_turn(state: DaemonState, *, session_id: str, prompt: str) -> TurnFn:
    """A `turn` for `run_agent_in_background` that runs `prompt` in the
    session's current agent mode."""
    chat = state.chat_modes.setdefault(session_id, ChatModeState())

    def turn(
        on_text: Callable[[str], None],
        on_event: Callable[[Any], None],
        post_event: Callable[[dict[str, Any]], None],
    ) -> RunResult:
        from veles.core.agent_events import AgentError, ChatDelta, SystemLine, TurnDone
        from veles.core.modes import ModeContext, get_mode
        from veles.core.session_state import AppState

        app = AppState(
            session_id=session_id,
            provider_name=state.provider or "",
            model=state.default_model or "",
        )
        app.mode = chat.mode  # type: ignore[assignment]
        app.last_mode_in_session = chat.last_mode_in_session  # type: ignore[assignment]
        app.active_goal_id = chat.active_goal_id

        streamed: list[str] = []
        done: list[RunResult] = []

        def text(delta: str) -> None:
            streamed.append(delta)
            on_text(delta)

        def post(msg: Any) -> None:
            if isinstance(msg, TurnDone):
                done.append(msg.result)
            elif isinstance(msg, ChatDelta):
                text(msg.text)
            elif isinstance(msg, SystemLine):
                post_event({"type": "notice", "text": msg.text})
            elif isinstance(msg, AgentError):
                raise msg.exc

        def factory(st, *, mode_override=None, extra_system=None, query=None, toolless=False):
            return state.agent_factory(
                st.session_id,
                prompt=query,
                mode=mode_override or st.mode,
                extra_system=extra_system,
                toolless=toolless,
            )

        ctx = ModeContext(
            state=app,
            project=state.project,
            factory=factory,
            post=post,
            on_text=text,
            on_event=on_event,
        )
        mode_name = app.mode
        get_mode(mode_name).run_turn(prompt, ctx)

        chat.last_mode_in_session = app.last_mode_in_session
        chat.active_goal_id = app.active_goal_id
        if app.mode != mode_name:
            chat.mode = None if app.mode == "auto" else app.mode

        if not done:
            raise RuntimeError(f"agent mode {mode_name!r} ended the turn without a result")
        result = done[-1]
        if result.stopped_reason == "synthetic":
            return RunResult(
                text="".join(streamed),
                iterations=0,
                stopped_reason="synthetic",
                session_id=session_id,
            )
        if result.session_id is None:
            result.session_id = session_id
        return result

    return turn


__all__ = ["make_mode_turn"]
