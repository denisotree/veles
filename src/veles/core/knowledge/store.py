"""KnowledgeStore: token-overlap search over curated notes + live skeleton.

Right-sized for a curated set of tens of entries — no FTS index, no embeddings,
deterministic and offline. The `SCORE_THRESHOLD` gate is what makes the recall
surface self-gating: a generic coding query scores below it and yields nothing,
so normal turns are never polluted with Veles docs.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass

from veles.core.knowledge.notes import Note, load_notes
from veles.core.knowledge.skeleton import SkeletonEntry, build_skeleton

_TOKEN_RE = re.compile(r"[a-z0-9_]+")
# "veles" is dropped: every entry is about Veles, so it is not discriminative.
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "to",
        "in",
        "of",
        "how",
        "do",
        "i",
        "is",
        "it",
        "for",
        "and",
        "with",
        "my",
        "me",
        "on",
        "can",
        "what",
        "this",
        "that",
        "veles",
        "you",
        "your",
        "when",
        "where",
        "which",
        "use",
        "using",
        "get",
    }
)

SCORE_THRESHOLD = 3
_TITLE_WEIGHT = 3
_BODY_WEIGHT = 1


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1}


@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    source: str  # "note" | "skeleton"
    ref: str
    title: str
    body: str
    score: int


@dataclass(frozen=True, slots=True)
class _Indexed:
    hit_ref: str
    source: str
    title: str
    body: str
    title_tokens: frozenset[str]
    body_tokens: frozenset[str]


class KnowledgeStore:
    def __init__(self, notes: list[Note], skeleton: list[SkeletonEntry]) -> None:
        self._entries: list[_Indexed] = []
        self._by_ref: dict[str, _Indexed] = {}
        self._by_title: dict[str, _Indexed] = {}
        for n in notes:
            self._add(
                ref=n.slug,
                source="note",
                title=n.title,
                body=n.body,
                title_text=n.title + " " + " ".join(n.topics),
                body_text=n.body,
            )
        for e in skeleton:
            self._add(
                ref=f"{e.kind}:{e.name}",
                source="skeleton",
                title=e.name,
                body=e.summary,
                title_text=e.name + " " + " ".join(e.aliases),
                body_text=e.summary,
            )

    def _add(
        self, *, ref: str, source: str, title: str, body: str, title_text: str, body_text: str
    ) -> None:
        idx = _Indexed(
            hit_ref=ref,
            source=source,
            title=title,
            body=body,
            title_tokens=frozenset(_tokens(title_text)),
            body_tokens=frozenset(_tokens(body_text)),
        )
        self._entries.append(idx)
        self._by_ref.setdefault(ref, idx)
        self._by_title.setdefault(title.lower(), idx)

    def _score(self, q: set[str], e: _Indexed) -> int:
        title_hits = len(q & e.title_tokens)
        body_hits = len(q & e.body_tokens)
        return _TITLE_WEIGHT * title_hits + _BODY_WEIGHT * body_hits

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeHit]:
        q = _tokens(query)
        if not q:
            return []
        scored: list[tuple[int, _Indexed]] = []
        for e in self._entries:
            s = self._score(q, e)
            if s >= SCORE_THRESHOLD:
                scored.append((s, e))
        # Highest score first; ties keep insertion order (notes before skeleton).
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            KnowledgeHit(source=e.source, ref=e.hit_ref, title=e.title, body=e.body, score=s)
            for s, e in scored[:limit]
        ]

    def get(self, topic: str) -> KnowledgeHit | None:
        key = topic.strip()
        idx = self._by_ref.get(key) or self._by_title.get(key.lower())
        if idx is None:
            return None
        return KnowledgeHit(
            source=idx.source, ref=idx.hit_ref, title=idx.title, body=idx.body, score=0
        )


@functools.lru_cache(maxsize=1)
def get_default_store() -> KnowledgeStore:
    """Process-cached store from packaged notes + the live skeleton."""
    return KnowledgeStore(load_notes(), build_skeleton())
