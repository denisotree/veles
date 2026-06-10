"""Streaming response consumer, extracted from agent.py in M156.

`consume_stream` drives one provider streaming call to completion: scrubbed
text deltas go to `on_text_delta`, reasoning deltas become `ThinkingDelta`
events (never chat text — M133), and cancellation stays responsive via a
daemon pump thread even when the stream stalls before yielding (M131).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from veles.core.cancel import current_cancel_token
from veles.core.context_scrubber import MemoryContextScrubber
from veles.core.events import ThinkingDelta
from veles.core.provider import (
    Provider,
    ProviderResponse,
    ReasoningDelta,
    StreamEnd,
    TextDelta,
)
from veles.core.trace import now_iso


def consume_stream(
    provider: Provider,
    *,
    history,
    tools: list[dict] | None,
    model: str,
    max_tokens: int,
    on_text_delta: Callable[[str], None],
    emit_event: Callable[[object], None],
    session_id: str | None,
) -> tuple[ProviderResponse, int]:
    """Consume one streaming provider call; return (response, ttft_ms).

    TTFT is measured from stream start to the first non-empty TextDelta,
    which is what users actually feel as latency. 0 when the stream never
    emits text (tool-only response).
    """
    scrubber = MemoryContextScrubber()
    stream_started = time.monotonic()
    state = {"response": None, "ttft_ms": 0}

    def _handle(event) -> None:
        if isinstance(event, TextDelta):
            if state["ttft_ms"] == 0 and event.text:
                state["ttft_ms"] = int((time.monotonic() - stream_started) * 1000)
            cleaned = scrubber.feed(event.text)
            if cleaned:
                on_text_delta(cleaned)
        elif isinstance(event, ReasoningDelta):
            # M133: reasoning never goes to on_text_delta (chat) — only
            # to the typed-event stream, so the inspector can show the
            # model's thinking without it leaking into the answer.
            if event.text:
                emit_event(
                    ThinkingDelta(
                        ts=now_iso(),
                        session_id=session_id,
                        text=event.text,
                    )
                )
        elif isinstance(event, StreamEnd):
            state["response"] = event.response

    cancel = current_cancel_token()
    stream = provider.stream_message(
        history, tools=tools, model=model, max_tokens=max_tokens
    )
    if cancel is None:
        # Fast path — no cancellation requested, iterate inline.
        for event in stream:
            _handle(event)
    else:
        _consume_cancellable(stream, _handle, cancel)

    tail = scrubber.finalize()
    if tail:
        on_text_delta(tail)
    response = state["response"]
    if response is None:
        raise RuntimeError("provider stream ended without StreamEnd event")
    return response, state["ttft_ms"]


def _consume_cancellable(stream, handle, cancel) -> None:
    """Drive a blocking provider stream so cancellation stays responsive
    even when the stream stalls *before* yielding a chunk.

    The reported M131 bug: a model "thinking" with no tokens flowing
    leaves the worker blocked inside the SDK's socket read, so a
    between-events check never runs and Ctrl+C can't unwind — asyncio's
    shutdown then joins the stuck (non-daemon) worker and a 3rd Ctrl+C
    throws. Fix: pump the stream on a *daemon* thread and poll a queue
    with a short timeout, checking the cancel token each tick. On cancel
    the consume loop returns immediately (raising `TurnCancelled`); the
    pump thread may still be blocked in the read, but being a daemon it
    can't hold up interpreter shutdown, and the SDK's own read timeout
    eventually reaps its socket.
    """
    import queue
    import threading

    from veles.core.provider import StreamEnd as _StreamEnd

    q: queue.Queue = queue.Queue(maxsize=256)
    _SENTINEL = object()

    def _pump() -> None:
        try:
            for event in stream:
                q.put(("ev", event))
            q.put(("end", _SENTINEL))
        except BaseException as exc:  # noqa: BLE001 - forwarded to consumer
            q.put(("err", exc))

    t = threading.Thread(target=_pump, name="veles-stream-pump", daemon=True)
    t.start()
    while True:
        cancel.check()  # raises TurnCancelled → caller unwinds cleanly
        try:
            kind, payload = q.get(timeout=0.1)
        except queue.Empty:
            continue
        if kind == "err":
            raise payload
        if kind == "end":
            return
        # Re-check: cancellation may have been requested *during* the
        # blocking get, after an event was already queued. A stop must
        # take priority over delivering one more buffered chunk.
        cancel.check()
        handle(payload)
        if isinstance(payload, _StreamEnd):
            return
