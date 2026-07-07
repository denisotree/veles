"""The REPL's streamed output must never run the terminal write ON the event
loop.

Confirmed root cause of the reported REPL "freeze" (HUD timer + spinner stop,
Esc goes dead) during heavy turns: prompt_toolkit's stock `StdoutProxy` writes
via `run_in_terminal(..., in_executor=False)` — i.e. the actual `write()` runs
on the event-loop thread. When a turn streams output faster than the terminal
can drain it, the OS output buffer fills, `write()` blocks, and the whole loop
freezes. `_NonBlockingStdoutProxy` runs the write in an executor thread instead,
so a slow write blocks only a pool thread and the UI stays live and cancellable.
"""

from __future__ import annotations

from veles.cli.repl import terminal as term


class _ImmediateLoop:
    """Runs `call_soon_threadsafe` callbacks inline so the test can observe what
    the proxy schedules without spinning a real event loop."""

    def call_soon_threadsafe(self, cb) -> None:
        cb()


def test_streamed_write_is_scheduled_off_the_event_loop(monkeypatch) -> None:
    captured: list[bool] = []
    monkeypatch.setattr(
        term, "run_in_terminal", lambda fn, in_executor: captured.append(in_executor)
    )
    proxy = term._NonBlockingStdoutProxy(raw=True)
    try:
        proxy._write_and_flush(_ImmediateLoop(), "streamed migration output")
    finally:
        proxy.close()
    # in_executor=True → the blocking terminal write runs in a pool thread, NOT
    # on the event loop, so a slow terminal can't freeze the REPL.
    assert captured == [True]


def test_no_loop_writes_directly(monkeypatch) -> None:
    """With no running app/loop (headless), the proxy writes immediately — no
    run_in_terminal, same as prompt_toolkit's own fallback."""
    monkeypatch.setattr(
        term, "run_in_terminal", lambda *a, **k: (_ for _ in ()).throw(AssertionError("used loop"))
    )
    written: list[str] = []
    proxy = term._NonBlockingStdoutProxy(raw=True)
    monkeypatch.setattr(proxy._output, "write_raw", lambda t: written.append(t))
    monkeypatch.setattr(proxy._output, "flush", lambda: None)
    monkeypatch.setattr(proxy._output, "enable_autowrap", lambda: None)
    try:
        proxy._write_and_flush(None, "direct")
    finally:
        proxy.close()
    assert written == ["direct"]
