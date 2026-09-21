"""One event loop for the memory layer, callable from synchronous code (M264).

The memory port is async (`store.MemoryStore`) while everything that uses it —
`Agent.run`, the CLI, the curator — is synchronous, and making *those* async is
a separate programme entirely: the provider SDKs are synchronous, tool dispatch
is synchronous, and the daemon already gets its concurrency by running the whole
agent in `asyncio.to_thread`. None of that is needed for what async buys here,
which is two concrete things:

1. the recall collectors run concurrently under **one** deadline instead of
   five sequential trips, so a slow source is cut rather than summed;
2. a network-backed store can exist at all without blocking the calling thread
   for an unbounded time.

So: the port is async-native, and this module is the bridge. One loop per
process, on its own thread, started lazily — not `asyncio.run()` per call,
which would build and tear down a loop on the hot path.

When the agent does become asynchronous, callers `await` the port directly and
this module is deleted. That is the point of paying for the bridge now rather
than writing a synchronous port that would have to be rewritten.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any

_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    with _lock:
        if _loop is not None and not _loop.is_closed():
            return _loop
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=loop.run_forever,
            name="veles-memory-loop",
            daemon=True,  # never holds up interpreter exit; nothing here outlives the process
        )
        thread.start()
        _loop, _thread = loop, thread
        return loop


def submit[T](coro: Coroutine[Any, Any, T], *, timeout: float | None = None) -> T:
    """Run `coro` on the memory loop and block until it finishes.

    `timeout` is the caller's deadline, not a suggestion: on expiry the
    coroutine is cancelled and `TimeoutError` is raised, so a slow backend costs
    a bounded amount of the turn rather than all of it.

    Calling this from inside a running event loop raises instead of blocking it
    — that is a deadlock in the making, and the caller should be awaiting the
    port directly.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        coro.close()
        raise RuntimeError(
            "memory.aio.submit() called from inside an event loop; await the "
            "MemoryStore coroutine directly instead of blocking this loop"
        )

    loop = _ensure_loop()
    if threading.current_thread() is _thread:
        coro.close()
        raise RuntimeError("memory.aio.submit() called from the memory loop thread")

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout)
    except TimeoutError:
        future.cancel()
        raise


def shutdown() -> None:
    """Stop the loop. Only tests need this — in a real process the loop is a
    daemon thread that dies with the interpreter."""
    global _loop, _thread
    with _lock:
        loop, thread = _loop, _thread
        _loop = _thread = None
    if loop is None:
        return
    loop.call_soon_threadsafe(loop.stop)
    if thread is not None:
        thread.join(timeout=5.0)
    loop.close()


__all__ = ["shutdown", "submit"]
