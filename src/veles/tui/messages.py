"""Textual `Message` subclasses for cross-thread communication.

The agent loop runs in a worker thread (`AgentBridge.submit`). Streaming
text and typed events arrive there but must be applied to widgets on the
main event-loop thread. The pattern is:

    app.call_from_thread(app.post_message, ChatDelta("…"))

— `post_message` is thread-safe; consumers handle the message via
`on_chat_delta` (Textual auto-routes by class name).

These types are deliberately thin wrappers: routing keys plus the bare
data needed to update one widget. No business logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.message import Message

from veles.core.agent import RunResult
from veles.core.events import Event


@dataclass
class ChatDelta(Message):
    """One streamed text chunk from the assistant's current turn."""

    text: str


@dataclass
class AgentEvent(Message):
    """Typed event from the agent's event-listener side-channel.

    Phase 1 ignores these (no inspector yet). Phase 3 routes them to the
    inspector widget. Carrying them through Phase 1 keeps the bridge
    contract stable across phases.
    """

    event: Event


@dataclass
class TurnDone(Message):
    """Agent loop finished cleanly; result attached for status display."""

    result: RunResult


@dataclass
class AgentError(Message):
    """Agent loop raised; the exception is attached so the UI can show
    a panel without losing the traceback to logs."""

    exc: BaseException


@dataclass
class SystemLine(Message):
    """Informational system-line for the chat log (e.g.
    `[auto → planning]` from AutoMode, `[goal achieved]` from
    GoalMode). Renders via `ChatLog.append_system`. Distinct from
    `ChatDelta` (assistant streaming) and `AgentError` (failure) so
    the dispatcher can route it without sniffing text."""

    text: str
