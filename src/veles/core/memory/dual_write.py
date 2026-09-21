"""Hand a newly-saved insight to the external memory engine (M265).

The contract, chosen deliberately over the alternatives:

**The local row is the source of truth.** Writing straight through to a remote
engine would give one copy and no divergence, and would also mean that losing
the network loses the memory — for a framework whose local-first behaviour is
an invariant (`project_memory_no_loss`), that trade is the wrong way round.

**The external write is best-effort.** It must not fail a turn: the fact is
already safely stored, and an exception here would turn a successful insight
into a failed agent run.

**Best-effort has to leave a trace, or it means "sometimes never".** Every row
carries `synced_at`; a write that did not happen leaves it NULL, and the dream
cycle offers those rows again. That is the whole difference between a dual
write and a write that silently is not one.

Providers opt in by having `ingest` — see `memory.provider`. A deployment with
no external engine configured pays one `build_extra_providers()` call that
returns an empty list, and nothing else.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veles.core.project import Project

logger = logging.getLogger(__name__)

# How many unsynced insights one resync pass offers. Bounded for the same
# reason the dream cycle bounds everything else: a backlog must drain over
# several cycles rather than turning one idle moment into a long network burst.
_RESYNC_BATCH = 50


def _ingesting_providers() -> list[object]:
    from veles.core.memory.provider import IngestingMemoryProvider
    from veles.core.memory.providers import build_extra_providers

    return [p for p in build_extra_providers() if isinstance(p, IngestingMemoryProvider)]


def push_insight(
    project: Project,
    *,
    insight_id: int,
    title: str,
    body: str,
    providers: list[object] | None = None,
) -> bool:
    """Offer one insight to every ingesting provider. Returns True when at
    least one accepted it, and stamps `synced_at` in that case.

    `providers` is for callers pushing more than one row: building the list
    parses `~/.veles/config.toml` and constructs every adapter, which is fine
    once per save and wasteful fifty times per resync pass.

    Never raises: the caller has already stored the fact."""
    providers = _ingesting_providers() if providers is None else providers
    if not providers:
        return False

    accepted = False
    for provider in providers:
        try:
            accepted = bool(provider.ingest(title, body, insight_id=insight_id)) or accepted  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning(
                "memory dual-write: %s rejected insight #%d (%s: %s)",
                getattr(provider, "name", type(provider).__name__),
                insight_id,
                type(exc).__name__,
                exc,
            )
    if accepted:
        _stamp_synced(project, [insight_id])
    return accepted


def _stamp_synced(project: Project, ids: list[int]) -> None:
    import sqlite3
    import time

    if not ids:
        return
    try:
        conn = sqlite3.connect(str(project.memory_db_path))
        try:
            with conn:
                conn.executemany(
                    "UPDATE insights SET synced_at = ? WHERE id = ?",
                    [(time.time(), i) for i in ids],
                )
        finally:
            conn.close()
    except sqlite3.Error as exc:
        # The fact is stored and the engine has it; only the bookkeeping
        # failed, so the worst case is offering the same row again later.
        logger.warning("memory dual-write: could not stamp synced_at (%s)", exc)


def resync_pending(project: Project, *, limit: int = _RESYNC_BATCH) -> int:
    """Offer insights that never reached the external engine. Returns how many
    were accepted this pass.

    Runs from the dream cycle, where the rest of the background memory work
    already lives — not from the turn, which has no business retrying someone
    else's outage."""
    import sqlite3

    providers = _ingesting_providers()
    if not providers:
        return 0
    try:
        conn = sqlite3.connect(str(project.memory_db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, title, body FROM insights"
                " WHERE synced_at IS NULL AND hidden_at IS NULL"
                " ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return 0

    accepted = 0
    for row in rows:
        if push_insight(
            project,
            insight_id=int(row["id"]),
            title=row["title"] or "",
            body=row["body"] or "",
            providers=providers,
        ):
            accepted += 1
    return accepted


__all__ = ["push_insight", "resync_pending"]
