"""M141: scored reranking of recall hits (M223 made it the sole merge — the old
round-robin fallback is gone).

A fixed round-robin cycle across sources can't let a fresh, on-point turn outrank
a stale wiki page. This module scores every hit and sorts, so recency and
confidence actually move results. It's the retrieval-side half of the article's
"memory rot" thesis.

Score per hit:

    score = w_rel · relevance + w_recency · recency + w_conf · confidence

- **relevance** is *position-based* per source: `1/(1+pos)`. FTS BM25 ranks
  aren't comparable across tables (wiki vs turns vs insights), so we use each
  source's own ordering — the #1 hit of every source gets relevance 1.0, the
  #2 gets 0.5, etc. This sidesteps the cross-table scale problem entirely.
- **recency** is exponential decay on the hit's `ts`: 1.0 at age 0, 0.5 at one
  half-life, →0 for ancient. `ts=None` (curated wiki, external) → **1.0**:
  absence of a timestamp means *timeless*, not stale. Curated, lint-checked
  wiki pages are distilled knowledge that doesn't rot like a raw chat turn, so
  they're never recency-penalised. Consequence (deliberate, M141): a top wiki
  hit ties an equally-relevant fresh turn and wins on stream order (wiki is the
  first stream) — preserving the M55 "curated knowledge leads" intent — while
  *stale* turns still sink and a fresh turn still beats a lower-relevance wiki
  page.
- **confidence** is the hit's provenance confidence in [0,1] (M218 gives
  insights a real one: 1.0 user-asserted, 0.6 inferred-from-recovery; every
  other source is a neutral 1.0). The weight is small on purpose — it breaks
  ties and gently sinks low-trust insights, but a real relevance gap always
  wins. This is the M215 "re-add a term when a real writer lands" moment: the
  dead always-1.0 `decay` term is gone, and `confidence` is the genuine signal
  that replaces it.

Pure functions, no DB, no router import (router imports this) — hits are
duck-typed on `.ts` / `.confidence`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

DEFAULT_HALF_LIFE_SEC = 14 * 86_400.0  # 14 days


@dataclass(frozen=True, slots=True)
class RerankWeights:
    relevance: float = 1.0
    recency: float = 0.6
    confidence: float = 0.25


DEFAULT_WEIGHTS = RerankWeights()

_H = TypeVar("_H")


def recency_score(ts: float | None, now: float, half_life_sec: float) -> float:
    """Exponential recency in [0, 1]. `None` → 1.0 (timeless, not stale)."""
    if ts is None:
        return 1.0
    age = max(0.0, now - ts)
    return 0.5 ** (age / half_life_sec)


def rerank[H](
    streams: list[list[_H]],
    *,
    now: float,
    limit: int,
    weights: RerankWeights = DEFAULT_WEIGHTS,
    half_life_sec: float = DEFAULT_HALF_LIFE_SEC,
) -> list[_H]:
    """Flatten per-source streams into one list ranked by blended score.

    `streams` are per-source, each already ordered best-first — position within
    a stream is the relevance signal. Ties break on insertion order (stable),
    so equal-score hits keep source priority (wiki before insights before
    turns, matching the caller's stream order)."""
    scored: list[tuple[float, int, _H]] = []
    for stream in streams:
        for pos, hit in enumerate(stream):
            rel = 1.0 / (1.0 + pos)
            rec = recency_score(getattr(hit, "ts", None), now, half_life_sec)
            conf = float(getattr(hit, "confidence", 1.0))
            score = weights.relevance * rel + weights.recency * rec + weights.confidence * conf
            scored.append((score, len(scored), hit))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [hit for _, _, hit in scored[:limit]]


__all__ = [
    "DEFAULT_HALF_LIFE_SEC",
    "DEFAULT_WEIGHTS",
    "RerankWeights",
    "recency_score",
    "rerank",
]
