"""M141: scored reranking replaces the round-robin merge. Pure-function unit
tests — no DB, synthetic hits."""

from __future__ import annotations

from veles.core.memory.rerank import (
    DEFAULT_HALF_LIFE_SEC,
    RerankWeights,
    recency_score,
    rerank,
)
from veles.core.memory.router import RecallHit


def _hit(rel_path: str, *, ts: float | None = None, decay: float = 1.0) -> RecallHit:
    return RecallHit(rel_path=rel_path, title=rel_path, summary=rel_path, ts=ts, decay=decay)


# ---- recency_score ----


def test_recency_now_is_max() -> None:
    assert recency_score(1000.0, 1000.0, DEFAULT_HALF_LIFE_SEC) == 1.0


def test_recency_half_life_is_half() -> None:
    now = 1_000_000.0
    assert recency_score(now - DEFAULT_HALF_LIFE_SEC, now, DEFAULT_HALF_LIFE_SEC) == 0.5


def test_recency_none_is_timeless() -> None:
    # absence of a timestamp = timeless curated content, not stale
    assert recency_score(None, 1000.0, DEFAULT_HALF_LIFE_SEC) == 1.0


# ---- rerank ----


def test_rerank_timeless_wiki_beats_stale_turn() -> None:
    now = 1_000_000.0
    wiki = _hit("wiki/curated", ts=None)  # timeless → recency 1.0
    stale_turn = _hit("turn:s:1", ts=now - 10 * DEFAULT_HALF_LIFE_SEC)  # recency ≈ 0
    out = rerank([[wiki], [stale_turn]], now=now, limit=5)
    assert out[0].rel_path == "wiki/curated"


def test_rerank_curated_wiki_wins_tie_against_fresh_turn() -> None:
    """Equally-relevant + equally-fresh → curated wiki leads (first stream).
    Preserves the M55 "curated knowledge leads" intent; guards against burying
    the wiki layer under raw turns (M141 design decision)."""
    now = 1_000_000.0
    wiki = _hit("wiki/curated", ts=None)  # timeless → 1.0
    fresh_turn = _hit("turn:s:1", ts=now)  # fresh → 1.0
    out = rerank([[wiki], [fresh_turn]], now=now, limit=5)
    assert out[0].rel_path == "wiki/curated"


def test_rerank_fresh_turn_beats_lower_relevance_wiki() -> None:
    now = 1_000_000.0
    # wiki page at position 1 (relevance 0.5) loses to a fresh turn at position 0
    wiki_top = _hit("wiki/a", ts=None)
    wiki_second = _hit("wiki/b", ts=None)
    fresh_turn = _hit("turn:s:1", ts=now)
    out = rerank([[wiki_top, wiki_second], [fresh_turn]], now=now, limit=5)
    assert out[0].rel_path == "wiki/a"  # top wiki still leads
    assert out[1].rel_path == "turn:s:1"  # fresh turn beats the 2nd wiki page
    assert out[2].rel_path == "wiki/b"


def test_rerank_respects_relevance_within_recency_tie() -> None:
    now = 1_000_000.0
    # same ts → recency ties; position 0 beats position 1 on relevance
    top = _hit("wiki/a", ts=now)
    second = _hit("wiki/b", ts=now)
    out = rerank([[top, second]], now=now, limit=5)
    assert [h.rel_path for h in out] == ["wiki/a", "wiki/b"]


def test_rerank_stale_hit_sinks() -> None:
    now = 1_000_000.0
    fresh = _hit("turn:fresh", ts=now)
    ancient = _hit("turn:ancient", ts=now - 10 * DEFAULT_HALF_LIFE_SEC)
    out = rerank([[ancient, fresh]], now=now, limit=5)
    assert out[0].rel_path == "turn:fresh"


def test_rerank_respects_limit() -> None:
    now = 1_000_000.0
    hits = [_hit(f"turn:{i}", ts=now) for i in range(10)]
    out = rerank([hits], now=now, limit=3)
    assert len(out) == 3


def test_rerank_custom_weights_zero_recency_keeps_relevance_order() -> None:
    now = 1_000_000.0
    w = RerankWeights(relevance=1.0, recency=0.0, decay=0.0)
    fresh_second = _hit("a", ts=now)
    stale_first = _hit("b", ts=now - 10 * DEFAULT_HALF_LIFE_SEC)
    # one stream, stale_first at position 0 → with no recency weight it stays first
    out = rerank([[stale_first, fresh_second]], now=now, limit=5, weights=w)
    assert [h.rel_path for h in out] == ["b", "a"]
