"""M131: cooperative turn cancellation.

`Agent.run` runs on a TUI worker thread that can't be force-killed, so a
stop request (Ctrl+C) must be honoured cooperatively: the agent checks a
shared `CancelToken` between iterations and between streamed events and
unwinds with a clean `stopped_reason="cancelled"` result instead of an
error — so the worker returns promptly and process shutdown stays clean.

Invariants checked here:
  1. `CancelToken.check()` raises `TurnCancelled` only after `cancel()`.
  2. A stop requested mid-stream stops within one chunk and yields a
     cancelled result (not all chunks are delivered).
  3. A pre-cancelled token short-circuits before the provider is called
     (between-iteration checkpoint).
  4. With no active token the run is unaffected (default behaviour).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import pytest

from veles.core.agent import Agent
from veles.core.cancel import (
    CancelToken,
    TurnCancelled,
    reset_cancel_token,
    set_cancel_token,
)
from veles.core.provider import (
    ProviderResponse,
    StreamEnd,
    TextDelta,
    TokenUsage,
)
from veles.core.tools.registry import Registry


def _usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10)


def _final(text: str) -> ProviderResponse:
    return ProviderResponse(text=text, tool_calls=[], usage=_usage(), finish_reason="stop")


@dataclass
class _GatedStreamProvider:
    """Yields one chunk, then blocks on `gate` before yielding more — so a
    test can cancel deterministically mid-stream, after the first delta is
    delivered but before the rest."""

    gate: threading.Event
    name: str = "stub"
    supports_tools: bool = True
    supports_streaming: bool = True

    def create_message(self, *a, **k):  # noqa: ANN002, ANN003
        raise NotImplementedError

    def stream_message(self, messages, tools=None, *, model, max_tokens=4096):  # noqa: ANN001
        del messages, tools, model, max_tokens
        yield TextDelta(text="a")
        self.gate.wait(timeout=10.0)
        yield TextDelta(text="b")
        yield StreamEnd(response=_final("ab"))


@dataclass
class _ExplodingProvider:
    """Fails if the agent ever calls it — used to prove a short-circuit."""

    name: str = "stub"
    supports_tools: bool = True
    supports_streaming: bool = True

    def create_message(self, *a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("provider must not be called after cancel")

    def stream_message(self, *a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("provider must not be called after cancel")


@dataclass
class _OneShotProvider:
    name: str = "stub"
    supports_tools: bool = True
    supports_streaming: bool = False

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):  # noqa: ANN001
        del messages, tools, model, max_tokens
        return _final("done")

    def stream_message(self, *a, **k):  # noqa: ANN002, ANN003
        raise NotImplementedError


def _agent(provider) -> Agent:  # noqa: ANN001
    return Agent(provider, Registry(), model="m", max_iterations=5)


# ---- 1. token primitives ----


def test_cancel_token_check_raises_only_after_cancel():
    token = CancelToken()
    assert token.cancelled is False
    token.check()  # no-op
    token.cancel()
    assert token.cancelled is True
    with pytest.raises(TurnCancelled):
        token.check()


# ---- 2. mid-stream cancellation ----


def test_active_stream_cancellation_stops_delivery():
    gate = threading.Event()
    token = CancelToken()
    provider = _GatedStreamProvider(gate=gate)
    seen: list[str] = []
    first = threading.Event()

    def on_text(t: str) -> None:
        seen.append(t)
        first.set()

    def _canceller() -> None:
        first.wait(timeout=5.0)
        token.cancel()
        gate.set()  # unblock the generator so it can't hang the pump

    canceller = threading.Thread(target=_canceller)
    canceller.start()
    ctx = set_cancel_token(token)
    try:
        result = _agent(provider).run("hi", on_text_delta=on_text)
    finally:
        reset_cancel_token(ctx)
        gate.set()
        canceller.join()

    assert result.stopped_reason == "cancelled"
    # Cancellation landed mid-stream: the gated second chunk is never
    # delivered to the consumer (robust regardless of scrubber buffering).
    assert "b" not in seen


# ---- 2b. STALLED stream (the actual reported bug) ----


@dataclass
class _StalledStreamProvider:
    """Blocks *before* yielding any event — simulates a model that's
    "thinking" with no tokens flowing, the scenario where a naive
    between-events check never fires and the worker hangs."""

    started: threading.Event
    release: threading.Event
    name: str = "stub"
    supports_tools: bool = True
    supports_streaming: bool = True

    def create_message(self, *a, **k):  # noqa: ANN002, ANN003
        raise NotImplementedError

    def stream_message(self, messages, tools=None, *, model, max_tokens=4096):  # noqa: ANN001
        del messages, tools, model, max_tokens
        self.started.set()
        # Stall until released (or a generous safety timeout). A correct
        # implementation cancels long before this fires.
        self.release.wait(timeout=10.0)
        yield StreamEnd(response=_final("late"))


def test_stalled_stream_cancels_promptly():
    """The reported M131 bug: with the stream stalled pre-first-token,
    cancellation must still unwind the run in well under a second."""
    started = threading.Event()
    release = threading.Event()
    token = CancelToken()
    provider = _StalledStreamProvider(started=started, release=release)

    def _canceller() -> None:
        # Wait until the agent is actually inside the stalled stream, then
        # request cancellation from another thread (as the UI thread does).
        assert started.wait(timeout=5.0)
        time.sleep(0.05)
        token.cancel()

    canceller = threading.Thread(target=_canceller)
    canceller.start()
    ctx = set_cancel_token(token)
    t0 = time.monotonic()
    try:
        result = _agent(provider).run("hi", on_text_delta=lambda _t: None)
    finally:
        reset_cancel_token(ctx)
        release.set()  # let the daemon pump thread exit
        canceller.join()
    elapsed = time.monotonic() - t0

    assert result.stopped_reason == "cancelled"
    assert elapsed < 1.0, f"cancel took {elapsed:.2f}s — stalled stream not interruptible"


# ---- 3. between-iteration short-circuit ----


def test_precancelled_token_skips_provider_call():
    token = CancelToken()
    token.cancel()
    ctx = set_cancel_token(token)
    try:
        result = _agent(_ExplodingProvider()).run("hi", on_text_delta=lambda _t: None)
    finally:
        reset_cancel_token(ctx)
    assert result.stopped_reason == "cancelled"


# ---- 4. no token → unaffected ----


def test_no_token_runs_normally():
    result = _agent(_OneShotProvider()).run("hi")
    assert result.stopped_reason == "completed"
    assert result.text == "done"
