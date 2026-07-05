"""M192 — vector embeddings for the `insights` recall source.

`embeddings_blob` had no production writer, so semantic recall was impossible.
This module embeds insights that lack a vector so `MemoryRouter` can KNN over
them. It runs off the hot path (the dream/curator cycle calls `backfill_*`),
never on the per-turn recall path — embedding round-trips must not block prompt
assembly. Superseded insights (dream dedup, `insight_refs`) are skipped: embeds
should be spent only on the survivor set that recall actually surfaces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from veles.core.memory.vector import ensure_embeddings_table, upsert_embedding

if TYPE_CHECKING:
    from veles.core.memory import SessionStore


class _Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _insight_embedding_text(title: str, body: str) -> str:
    """Text fed to the embedder — title then body, matching what FTS indexes."""
    return f"{title}\n{body}".strip()


def backfill_insight_embeddings(
    store: SessionStore,
    adapter: _Embedder,
    *,
    limit: int = 64,
) -> int:
    """Embed up to `limit` insights that have no embedding yet, skipping
    superseded rows. Returns the number embedded. Idempotent: a fully-embedded
    survivor set yields 0. Best-effort — a single embed failure aborts the batch
    without raising (recall keeps working on FTS)."""
    ensure_embeddings_table(store._conn)
    rows = store._conn.execute(
        "SELECT i.id, i.title, i.body FROM insights i"
        " LEFT JOIN embeddings_blob e"
        "   ON e.ref_kind = 'insight' AND e.ref_id = i.id"
        " WHERE e.id IS NULL"
        "   AND i.id NOT IN (SELECT from_insight_id FROM insight_refs)"
        " ORDER BY i.id LIMIT ?",
        (limit,),
    ).fetchall()
    if not rows:
        return 0

    texts = [_insight_embedding_text(r["title"] or "", r["body"] or "") for r in rows]
    try:
        vectors = adapter.embed(texts)
    except Exception:
        return 0
    if len(vectors) != len(rows):
        return 0

    embedded = 0
    for row, vec in zip(rows, vectors, strict=True):
        if not vec:
            continue
        upsert_embedding(store._conn, ref_kind="insight", ref_id=int(row["id"]), vec=vec)
        embedded += 1
    store._conn.commit()
    return embedded


def embed_survivor_insights(project, *, limit: int = 64) -> int:
    """M192: dream/curator entry point — embed un-embedded survivor insights.

    Runs off the per-turn recall hot path. Gated on a LOCAL adapter: insight
    bodies are project content and must not reach a cloud embedder. Returns the
    count embedded (0 when there is no local adapter). Opens and closes its own
    store so callers don't need one.
    """
    from veles.core.memory import SessionStore
    from veles.modules.embedding import get_local_embedding_adapter

    adapter = get_local_embedding_adapter()
    if adapter is None:
        return 0
    store = SessionStore(project.memory_db_path)
    try:
        return backfill_insight_embeddings(store, adapter, limit=limit)
    finally:
        store.close()
