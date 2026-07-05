"""Plain dataclasses for cross-thread agent communication.

The agent loop runs in a worker thread (`AgentBridge.submit`). Streaming
text and typed events arrive there but must be applied to widgets on the
main event-loop thread. These types are deliberately thin wrappers:
routing keys plus the bare data needed to update one widget. No business
logic lives here.

Framework-agnostic on purpose: `core/` must not depend on `tui/` or
`textual`. Consumers that need Textual's message-routing (e.g.
`post_message` / `on_chat_delta`) wrap these dataclasses with a Textual
`Message` subclass at the UI layer instead of inheriting one here.
"""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.agent import RunResult
from veles.core.events import Event


@dataclass
class ChatDelta:
    """One streamed text chunk from the assistant's current turn."""

    text: str


@dataclass
class AgentEvent:
    """Typed event from the agent's event-listener side-channel.

    Phase 1 ignores these (no inspector yet). Phase 3 routes them to the
    inspector widget. Carrying them through Phase 1 keeps the bridge
    contract stable across phases.
    """

    event: Event


@dataclass
class TurnDone:
    """Agent loop finished cleanly; result attached for status display."""

    result: RunResult


@dataclass
class AgentError:
    """Agent loop raised; the exception is attached so the UI can show
    a panel without losing the traceback to logs."""

    exc: BaseException


@dataclass
class SystemLine:
    """Informational system-line for the chat log (e.g.
    `[auto → planning]` from AutoMode, `[goal achieved]` from
    GoalMode). Renders via `ChatLog.append_system`. Distinct from
    `ChatDelta` (assistant streaming) and `AgentError` (failure) so
    the dispatcher can route it without sniffing text."""

    text: str
