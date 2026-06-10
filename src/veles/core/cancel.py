"""Cooperative turn cancellation — break a blocking agent turn from another thread.

`Agent.run` is synchronous and, in the TUI, runs on a worker thread
(`App.run_worker(..., thread=True)`). Python threads can't be force-killed,
and Textual cannot cancel a *thread* worker — so the only way to stop an
in-flight turn (e.g. on Ctrl+C) is cooperatively: the UI thread flips a
shared flag, and the agent loop checks it at safe points (between iterations
and between streamed events) and bails with `TurnCancelled`.

The carrier is a plain `threading.Event` wrapped in `CancelToken` — a
ContextVar alone can't cross threads, so the *object* is shared (its `.cancel()`
is called from the UI thread) while a ContextVar (`current_cancel_token`)
merely delivers the same object into the worker thread's context so the agent
can read it without a signature change, mirroring `current_budget()` /
`current_project()`.
"""

from __future__ import annotations

import threading
from contextvars import ContextVar, Token


class TurnCancelled(Exception):
    """Raised inside the agent loop when the active CancelToken is set.

    Caught by `Agent.run`, which turns it into a `RunResult` with
    `stopped_reason="cancelled"` — a user-initiated stop is a clean
    outcome, not an error.
    """


class CancelToken:
    """Thread-safe one-shot cancellation flag for a single agent turn.

    `cancel()` is safe to call from any thread (it's `threading.Event.set`).
    The agent thread polls `cancelled` / calls `check()` at safe points.
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        """Raise `TurnCancelled` if cancellation has been requested."""
        if self._event.is_set():
            raise TurnCancelled


_cancel_token: ContextVar[CancelToken | None] = ContextVar(
    "veles_cancel_token", default=None
)


def current_cancel_token() -> CancelToken | None:
    return _cancel_token.get()


def set_cancel_token(token: CancelToken | None) -> Token:
    return _cancel_token.set(token)


def reset_cancel_token(token: Token) -> None:
    _cancel_token.reset(token)
