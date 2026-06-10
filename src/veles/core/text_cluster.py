"""Generic TF-IDF cosine clustering (M142).

Factored out of `skill_dedup` (M61) so insight dedup (M142) and skill dedup
share one deps-free clusterer instead of two copies of the same TF-IDF + union-
find. The math is unchanged from M61; the only generalisation is that this
operates on plain `list[str]` and returns *index* clusters, leaving the
domain-specific wrapping (SkillCluster, insight rows) to the caller.

`cluster_texts(texts, *, threshold)` → `list[(indices, mean_score)]`, only
clusters of ≥2, sorted by descending cohesion.
"""

from __future__ import annotations

import math
import re
from typing import Callable

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "from", "into", "this", "that", "page",
        "skill", "tool", "use", "uses", "used", "using", "when", "what",
        "where", "how", "via", "are", "you", "your",
    }
)

_DEFAULT_THRESHOLD = 0.50


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 2 and t not in _STOPWORDS]


def _term_freqs(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tokens(text):
        out[t] = out.get(t, 0) + 1
    return out


def tfidf_vectors(texts: list[str]) -> list[dict[str, float]]:
    """TF-IDF weight vectors (one dict per input text). Smooth IDF, never zero."""
    if not texts:
        return []
    freqs = [_term_freqs(t) for t in texts]
    doc_count = len(freqs)
    df: dict[str, int] = {}
    for tf in freqs:
        for term in tf:
            df[term] = df.get(term, 0) + 1
    idf = {term: math.log((1 + doc_count) / (1 + n)) + 1.0 for term, n in df.items()}
    return [{term: count * idf.get(term, 0.0) for term, count in tf.items()} for tf in freqs]


def sparse_cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[t] * b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def cluster_indices(
    n: int, similarity: Callable[[int, int], float], threshold: float
) -> list[tuple[list[int], float]]:
    """Union-find cluster over pairwise `similarity(i, j) >= threshold`.

    Returns `(sorted_indices, mean_pairwise_score)` per cluster of ≥2, sorted
    by descending cohesion. Mean-pairwise keeps tight clusters above sprawling
    chains where the threshold barely held one edge."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    edges: list[tuple[int, int, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            sim = similarity(i, j)
            if sim >= threshold:
                edges.append((i, j, sim))
                union(i, j)

    by_root: dict[int, list[int]] = {}
    for i in range(n):
        by_root.setdefault(find(i), []).append(i)

    clusters: list[tuple[list[int], float]] = []
    for indices in by_root.values():
        if len(indices) < 2:
            continue
        idx_set = set(indices)
        intra = [sim for i, j, sim in edges if i in idx_set and j in idx_set]
        if not intra:
            continue
        clusters.append((sorted(indices), sum(intra) / len(intra)))
    clusters.sort(key=lambda c: (-c[1], c[0]))
    return clusters


def cluster_texts(
    texts: list[str], *, threshold: float = _DEFAULT_THRESHOLD
) -> list[tuple[list[int], float]]:
    """TF-IDF cosine clustering of `texts`. Deterministic, no external API."""
    if len(texts) < 2:
        return []
    vectors = tfidf_vectors(texts)
    return cluster_indices(
        len(texts), lambda i, j: sparse_cosine(vectors[i], vectors[j]), threshold
    )


__all__ = ["cluster_indices", "cluster_texts", "sparse_cosine", "tfidf_vectors", "tokens"]
