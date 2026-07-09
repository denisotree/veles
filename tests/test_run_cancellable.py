"""`run_cancellable` — interrupt a blocking call when the turn is cancelled.

Without it, a cooperative cancel only takes effect *between* iterations of the
agent loop; a single blocking `provider.create_message` (a slow model, a big
context, a hung socket) runs to completion first — so Ctrl+C could sit for the
full 120s HTTP timeout, ×N parallel workers. Running the call on a daemon thread
and polling lets the loop bail within one poll interval on any task.
"""

from __future__ import annotations

import threading
import time

import pytest

from veles.core.cancel import CancelToken, TurnCancelled, run_cancellable


def test_returns_result_normally() -> None:
    assert run_cancellable(lambda: 42, CancelToken()) == 42


def test_no_token_is_a_direct_call() -> None:
    assert run_cancellable(lambda: 7, None) == 7


def test_propagates_the_call_s_exception() -> None:
    def boom():
        raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        run_cancellable(boom, CancelToken())


def test_cancel_during_a_slow_call_unwinds_promptly() -> None:
    tok = CancelToken()

    def slow():
        time.sleep(5)  # a hung/slow provider call
        return "done"

    threading.Timer(0.2, tok.cancel).start()
    t0 = time.monotonic()
    with pytest.raises(TurnCancelled):
        run_cancellable(slow, tok, poll=0.05)
    # unwound on cancel, NOT after the full 5s blocking call
    assert time.monotonic() - t0 < 2.0


def test_already_cancelled_never_starts_waiting() -> None:
    tok = CancelToken()
    tok.cancel()

    def slow():
        time.sleep(5)
        return "done"

    t0 = time.monotonic()
    with pytest.raises(TurnCancelled):
        run_cancellable(slow, tok, poll=0.05)
    assert time.monotonic() - t0 < 1.0
