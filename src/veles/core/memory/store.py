"""The storage port: what recall needs, independent of where it is stored (M264).

Before this, `SessionStore(project.memory_db_path)` was constructed in 43 places
and its raw `sqlite3.Connection` was reached into from ~90 more. Every one of
those sites assumes the backend is a local SQLite file, which is what made any
other backend impossible — not SQLite itself. A file per tenant is a legitimate
architecture at scale (Turso, libSQL and D1 are all that shape); what is not
legitimate is having no seam at which to choose.

`MemoryStore` is that seam, and it is deliberately **narrow**: the read and
write operations a non-SQLite backend could plausibly serve. Telemetry tables,
FTS repair and `PRAGMA` work stay SQLite-specific and reach the connection
through `SqliteStore.raw()`, which says in its name that the caller has stepped
outside the port.

Async because the port must be able to be a network call (see `aio` for why the
callers stay synchronous). `SqliteStore` runs its work on a single dedicated
thread: `sqlite3.threadsafety` is 3 on CPython 3.13 so sharing the connection is
permitted, but serialising through one worker keeps write ordering obvious and
costs nothing — the parallelism that matters is between *sources* (files, FTS,
a remote provider), not between statements on one SQLite file.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from veles.core.memory import InsightHit, SessionStore, TurnHit

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    from veles.core.project import Project


@runtime_checkable
class MemoryStore(Protocol):
    """One project's (one tenant's) memory, wherever it lives."""

    async def search_insights(self, query: str, *, limit: int) -> list[InsightHit]: ...

    async def knn_insights(self, query_vec: list[float], *, limit: int) -> list[InsightHit]: ...

    async def search_turns(
        self, query: str, *, limit: int, since: float | None
    ) -> list[TurnHit]: ...

    async def touch_insights(self, ids: list[int], at: float) -> None: ...

    async def close(self) -> None: ...


class SqliteStore:
    """The default implementation: one SQLite file, the way Veles has always
    stored memory. Wraps `SessionStore` rather than replacing it — the sync
    class is still the one that knows the schema, and duplicating that
    knowledge to get an async signature would be the worst of both."""

    def __init__(self, db_path: Path | str) -> None:
        self._sync = SessionStore(db_path)
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="veles-sqlite")

    async def _run(self, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._pool, lambda: fn(*args, **kwargs))

    async def search_insights(self, query: str, *, limit: int) -> list[InsightHit]:
        return await self._run(self._sync.search_insights, query, limit=limit)

    async def knn_insights(self, query_vec: list[float], *, limit: int) -> list[InsightHit]:
        return await self._run(self._sync.knn_insights, query_vec, limit=limit)

    async def search_turns(self, query: str, *, limit: int, since: float | None) -> list[TurnHit]:
        return await self._run(self._sync.search_turns, query, limit=limit, since=since)

    async def touch_insights(self, ids: list[int], at: float) -> None:
        await self._run(self._sync.touch_insights, ids, at)

    async def close(self) -> None:
        await self._run(self._sync.close)
        self._pool.shutdown(wait=True)

    def raw(self) -> sqlite3.Connection:
        """The underlying connection, for the SQLite-only work that has no
        business in the port: FTS repair, `PRAGMA`, telemetry tables. Named so
        that a reader can see the caller has left the abstraction on purpose —
        the ~90 reach-throughs this replaces said nothing at all."""
        return self._sync._conn

    @property
    def sync(self) -> SessionStore:
        """Escape hatch for synchronous call sites not yet ported. Temporary by
        construction: it disappears as the remaining sites move onto the port."""
        return self._sync


def open_store(project: Project) -> SqliteStore:
    """Open the memory store for `project`.

    The single place a backend is chosen. Today there is one, and the signature
    already says `project` rather than a path so that choosing a different one
    never requires touching a call site again.
    """
    return SqliteStore(project.memory_db_path)


__all__ = ["MemoryStore", "SqliteStore", "open_store"]
