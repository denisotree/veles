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
        app.active_goal_id = _live_goal(state, chat.active_goal_id)

        streamed: list[str] = []
        done: list[RunResult] = []
        driving = [False]  # set while a goal runs on its own (M280b)

        def text(delta: str) -> None:
            streamed.append(delta)
            on_text(delta)

        def post(msg: Any) -> None:
            if isinstance(msg, TurnDone):
                done.append(msg.result)
            elif isinstance(msg, ChatDelta):
                text(msg.text)
            elif isinstance(msg, SystemLine):
                # While a goal drives itself the turn lasts minutes: its phase
                # lines are progress, which a channel shows as they happen.
                post_event({"type": "notice", "text": msg.text, "live": driving[0]})
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
        goal_before = app.active_goal_id
        get_mode(mode_name).run_turn(prompt, ctx)
        outcome = None
        if mode_name == "goal":
            # GoalMode clears `active_goal_id` when a goal ends, so keep the id.
            goal_id = app.active_goal_id or goal_before
            outcome = _drive_if_ready(state, ctx, driving, goal_id)

        chat.last_mode_in_session = app.last_mode_in_session
        chat.active_goal_id = app.active_goal_id
        if app.mode != mode_name:
            chat.mode = None if app.mode == "auto" else app.mode

        if outcome is not None:
            return RunResult(
                text=outcome, iterations=0, stopped_reason="synthetic", session_id=session_id
            )
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


def _drive_if_ready(
    state: DaemonState, ctx: Any, driving: list[bool], goal_id: str | None
) -> str | None:
    """Run the chat's goal to an end if this turn left it in a phase that needs
    no one — plan, execute, check. That is right after the user confirms the
    plan, and also any later message to a goal that stopped (stalled, turn cap)
    — which is how a chat resumes one. Interview and confirm are conversation,
    so those turns just answer. Returns the text that ends the turn, or None.
    A goal that ended within the turn itself (a resumed CHECK that says done)
    gets the same closing line as one that ended during the drive.

    Inside the run, not in the background (the user's choice): approval
    prompts reach the chat as buttons only while a run is being streamed. The
    goal's lock (M276) keeps a `veles goal resume` on the host and this chat
    from driving one goal twice."""
    from veles.core.file_lock import LockHeld, file_lock
    from veles.core.goal import goals_dir, read_goal
    from veles.core.modes.goal_driver import drive_goal

    goal = read_goal(state.project.state_dir, goal_id) if goal_id else None
    if goal is None:
        return None
    if goal.status in ("completed", "cancelled"):
        last = goal.progress[-1].description if goal.progress else ""
        head = "✅ Goal done" if goal.status == "completed" else "Goal cancelled"
        return f"{head} — {last}" if last else head
    if goal.status != "active" or goal.current_phase not in _AUTONOMOUS:
        return None
    try:
        with file_lock(goals_dir(state.project.state_dir) / f"{goal_id}.lock", blocking=False):
            driving[0] = True
            try:
                outcome = drive_goal(ctx, goal_id)
            finally:
                driving[0] = False
    except LockHeld:
        return "This goal is already running elsewhere (e.g. `veles goal` on the host)."
    if outcome.completed:
        return f"✅ Goal done — {outcome.reason}"
    if outcome.status == "cancelled":
        return f"Goal cancelled — {outcome.reason}"
    return f"Goal stopped — {outcome.reason}. Send /goal resume to continue it."


_AUTONOMOUS = ("plan", "execute", "check")


def _live_goal(state: DaemonState, goal_id: str | None) -> str | None:
    """The chat's goal only while it is still active. GoalMode itself never
    looks at a goal's status, so a goal finished or cancelled outside the
    turn (`/goal cancel`, the host's `veles goal cancel`) would otherwise have
    its phases run again by the chat's next goal-mode message — which should
    start a new goal instead."""
    from veles.core.goal import read_goal

    goal = read_goal(state.project.state_dir, goal_id) if goal_id else None
    return goal_id if goal is not None and goal.status == "active" else None


__all__ = ["make_mode_turn"]
