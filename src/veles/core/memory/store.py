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
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from veles.core.memory import InsightHit, SessionStore, TurnHit

logger = logging.getLogger(__name__)

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
        self._owns_sync = True
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="veles-sqlite")

    @classmethod
    def wrapping(cls, store: SessionStore) -> SqliteStore:
        """Put the port in front of a `SessionStore` someone else opened.

        The call sites that still construct their own store (see the ratchet)
        hand it to `MemoryRouter`, which needs the port shape; opening a second
        connection to the same file just to get that shape would be a second
        connection to the same file. `close()` on a wrapper leaves the borrowed
        store alone — closing something the caller opened is how a `finally`
        block two frames up starts failing."""
        self = cls.__new__(cls)
        self._sync = store
        self._owns_sync = False
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="veles-sqlite")
        return self

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
        if self._owns_sync:
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


class RemoteStore:
    """Learned facts from an external engine, conversation state still local.

    The split is not a compromise, it is the shape of the data. Insights are
    the thing that grows without bound and wants an engine with a real index
    behind it — measured, local brute-force vector recall stops fitting the
    turn budget around 48k of them, and a million would need ~3 GB resident
    *per tenant*. Sessions and turns are per-conversation state that a remote
    memory engine has no notion of and no reason to hold.

    So: `search_insights` goes out, everything else stays on the local file.

    `knn_insights` deliberately returns nothing. The remote engine does its own
    semantic matching inside `search_insights` — handing it a vector Veles
    computed with a different model would be asking the wrong question, and
    silently returning worse answers is the failure this codebase keeps trying
    to avoid.
    """

    def __init__(self, provider: object, local: SqliteStore) -> None:
        self._provider = provider
        self._local = local

    async def search_insights(self, query: str, *, limit: int) -> list[InsightHit]:
        def call() -> list[InsightHit]:
            hits = self._provider.recall(query, limit=limit)  # type: ignore[attr-defined]
            # Rank ordering is the provider's; position stands in for it, the
            # same convention `rerank` already applies across sources.
            return [
                InsightHit(
                    id=-1,  # not a local row id; nothing may touch or hide it
                    title=hit.title,
                    body=hit.summary,
                    rank=float(position),
                    ts=hit.ts if hit.ts is not None else time.time(),
                    confidence=hit.confidence,
                )
                for position, hit in enumerate(hits)
            ]

        return await asyncio.to_thread(call)

    async def knn_insights(self, query_vec: list[float], *, limit: int) -> list[InsightHit]:
        return []

    async def search_turns(self, query: str, *, limit: int, since: float | None) -> list[TurnHit]:
        return await self._local.search_turns(query, limit=limit, since=since)

    async def touch_insights(self, ids: list[int], at: float) -> None:
        # Remote hits carry id -1: aging applies to local rows only, and a
        # negative id must never reach an UPDATE.
        local = [i for i in ids if i >= 0]
        if local:
            await self._local.touch_insights(local, at)

    async def close(self) -> None:
        await self._local.close()

    @property
    def sync(self) -> SessionStore:
        return self._local.sync


def open_store(project: Project) -> MemoryStore:
    """Open the memory store for `project` — the single place a backend is
    chosen.

    `[memory.store] backend = "sqlite" | "remote"`, defaulting to `sqlite`, so
    a project without the section behaves exactly as before. `remote` needs an
    external provider configured (`[memory.external]`); with none, it falls
    back to local rather than starting a project with no memory at all, and
    says so.
    """
    local = SqliteStore(project.memory_db_path)
    if _configured_backend(project) != "remote":
        return local

    from veles.core.memory.providers import build_extra_providers

    providers = build_extra_providers()
    if not providers:
        logger.warning(
            "[memory.store] backend = 'remote' but no [memory.external] provider is "
            "configured; falling back to the local store"
        )
        return local
    if len(providers) > 1:
        logger.warning(
            "remote store uses the first configured provider (%s); the rest stay "
            "recall-only sources",
            getattr(providers[0], "name", "?"),
        )
    return RemoteStore(providers[0], local)


def _configured_backend(project: Project) -> str:
    try:
        from veles.core.project_config import get_section, load_project_config

        raw = get_section(load_project_config(project), "memory", "store").get("backend")
    except Exception:
        return "sqlite"
    return str(raw).strip().lower() if isinstance(raw, str) else "sqlite"


__all__ = ["MemoryStore", "RemoteStore", "SqliteStore", "open_store"]
