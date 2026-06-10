"""Mode protocol and per-turn context.

A `Mode` orchestrates one user prompt. The bridge constructs a
`ModeContext` carrying:
  * `state`   — the shared AppState (modes may mutate `session_id`,
                `last_mode_in_session`, etc.)
  * `project` — active project (for plan/goal artifact paths)
  * `factory` — builds an `Agent` from the current state. The signature
                stays minimal in Phase 1 (state → Agent); later phases
                extend the factory to accept `plan_mode`, `registry_name`,
                `extra_system` overrides for PlanningMode and friends.
  * `post`    — thread-safe message dispatcher to the Textual app. Modes
                call `post(TurnDone(result))` exactly once.
  * `on_text` — streaming-text sink, passed through to `agent.run`.
  * `on_event`— typed-event sink, passed through to `agent.run`.

Modes never import Textual; they communicate only through `post`. This
keeps them unit-testable with a fake `post` callback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Protocol

if TYPE_CHECKING:
    from veles.core.agent import Agent
    from veles.core.events import Event
    from veles.core.project import Project
    from veles.tui.state import AppState


AgentFactory = Callable[["AppState"], "Agent"]
PostFn = Callable[[Any], None]
TextSink = Callable[[str], None]
EventSink = Callable[["Event"], None]


@dataclass(slots=True)
class ModeContext:
    state: "AppState"
    project: "Project"
    factory: AgentFactory
    post: PostFn
    on_text: TextSink
    on_event: EventSink


class Mode(Protocol):
    name: str
    label: str
    system_block: str
    """Mode-specific system-prompt addendum, appended to the project's
    AGENTS.md-derived system prompt for fresh sessions, and injected as
    a user-role observation on a mid-session mode change. Empty for
    modes that don't tune model behaviour (Writing)."""

    def run_turn(self, prompt: str, ctx: ModeContext) -> None:
        """Execute one user prompt. Must post exactly one TurnDone (or
        AgentError on failure) before returning. May make multiple
        `agent.run` calls; only the last RunResult is surfaced."""
        ...


def wrap_mode_switch_observation(
    prompt: str, mode_name: str, system_block: str
) -> str:
    """When the active mode changed mid-session, the next user prompt
    is prefixed with a one-shot observation block. The Agent doesn't
    re-emit its constructor system prompt on resumed sessions
    (`agent.py:336-339`), so this is how a fresh mode gets a chance to
    inform the model without restarting the SessionStore row."""
    if not system_block.strip():
        return prompt
    return (
        f"<mode-switch-observation>\n"
        f"Active mode is now: {mode_name}.\n"
        f"{system_block.strip()}\n"
        f"</mode-switch-observation>\n\n"
        f"{prompt}"
    )
