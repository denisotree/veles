"""Textual `Message` wrappers around `veles.core.agent_events`.

`core/` must stay decoupled from `textual` (see `agent_events.py`'s module
docstring), but `App.post_message` requires a real `textual.message.Message`
instance — it checks for bookkeeping attributes (`_prevent`, `_sender`, …)
that `Message.__init__`/`__post_init__` install, and raises otherwise (see
`MessagePump.post_message`). Framework-agnostic code (the agent loop, the
Mode implementations under `core/modes/`) constructs the plain dataclasses
from `core.agent_events`; `AgentBridge.post` (in `bridge.py`) converts them
to the matching class here — same field names, `Message` added as a base —
right before handing them to `post_message`. This module is the one place
in the codebase where that conversion happens.

Field shapes are kept identical to `core.agent_events` on purpose so the
conversion in `bridge.py` is a mechanical `wire_cls(**vars(data_instance))`.
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
    """Typed event from the agent's event-listener side-channel."""

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
    GoalMode). Renders via `ChatLog.append_system`."""

    text: str
