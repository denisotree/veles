"""M121b: pattern detector — surface skill candidates from session
tool-use history.

Contract (VISION §5.5): when a workflow cluster recurs 3+ times, the
agent proposes formalising it as a skill. This module ships the
detection half; the suggestion / approval flow lives in the curator
(M121c).

Strategy (token-based, no embeddings — M121b1):

1. Project each session into its **tool-call sequence** —
   `(tool_name, ok)` tuples in invocation order, drawn from
   `tool_uses`. Sessions with fewer than `min_calls` calls are
   skipped (a single tool call isn't a "process").
2. Hash each sequence to a canonical key (just the tool name list
   for the MVP — ok/error is recorded but not part of the key, so
   "wiki_search + wiki_read_page" matches whether or not one of the
   calls errored).
3. GROUP BY the key and surface clusters with `repetitions >=
   min_repetitions`. Sort by repetition count descending.

What this catches: skills that are already de-facto formalised in
the user's workflow (the same `find→read→summarise` triplet hit five
times). What it misses: clusters that differ in tool arity but share
intent (M121b2 embedding ranking covers that once embeddings are
populated for prompts).

Functions:
- `detect_patterns(conn, ..)` returns `list[Pattern]` sorted by
  repetition count.
- `Pattern` carries the tool sequence, the count, and a sample of
  session_ids so the suggestion UI can link back to context.
"""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Pattern:
    """One detected cluster — a tool-call sequence the user ran
    multiple times.

    - `tools`: ordered list of tool names that defines the cluster
    - `repetitions`: how many sessions produced this exact sequence
    - `sample_sessions`: up to 5 session_ids from the cluster, useful
      for the suggestion UI to show "you ran this in session X, Y, Z"
    - `latest_at`: most recent invocation across the cluster (epoch)
    """

    tools: tuple[str, ...]
    repetitions: int
    sample_sessions: tuple[str, ...] = field(default_factory=tuple)
    latest_at: float | None = None


def detect_patterns(
    conn: sqlite3.Connection,
    *,
    min_repetitions: int = 3,
    min_calls: int = 2,
    max_calls: int = 12,
    sample_size: int = 5,
) -> list[Pattern]:
    """Find tool-call sequences that repeated across at least
    `min_repetitions` distinct sessions.

    - `min_calls`: ignore sessions with shorter sequences (a single
      `read_file` isn't a process worth formalising).
    - `max_calls`: ignore sessions with very long sequences (those
      are usually exploratory turns, not the kind of canned recipe
      that benefits from a skill).
    - `sample_size`: how many sample session_ids to attach per
      pattern. Capped to keep the API response bounded.
    """
    # Pull each session's tool-call sequence in invocation order.
    # We GROUP BY session in Python because SQLite's GROUP_CONCAT
    # ordering is implementation-defined for our SQLite version.
    rows = conn.execute(
        """
        SELECT u.session_id, t.name AS tool_name, u.invoked_at
        FROM tool_uses u
        JOIN tools t ON t.id = u.tool_id
        WHERE u.session_id IS NOT NULL
        ORDER BY u.session_id, u.invoked_at
        """
    ).fetchall()
    if not rows:
        return []

    sessions: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in rows:
        sessions[row["session_id"]].append((row["tool_name"], row["invoked_at"]))

    # Bucket by sequence (tool-name tuple). Skip sessions outside the
    # call-count window — they're not the recipes we're after.
    buckets: dict[tuple[str, ...], list[tuple[str, float]]] = defaultdict(list)
    for session_id, calls in sessions.items():
        if not (min_calls <= len(calls) <= max_calls):
            continue
        key = tuple(c[0] for c in calls)
        last_at = max(c[1] for c in calls)
        buckets[key].append((session_id, last_at))

    patterns: list[Pattern] = []
    for tools, members in buckets.items():
        if len(members) < min_repetitions:
            continue
        # Newest sessions first when truncating sample list, so the
        # suggestion UI shows recent context.
        members_sorted = sorted(members, key=lambda m: m[1], reverse=True)
        sample = tuple(m[0] for m in members_sorted[:sample_size])
        latest = members_sorted[0][1] if members_sorted else None
        patterns.append(
            Pattern(
                tools=tools,
                repetitions=len(members),
                sample_sessions=sample,
                latest_at=latest,
            )
        )

    # Most repeated first; ties broken by most-recent session.
    patterns.sort(key=lambda p: (-p.repetitions, -(p.latest_at or 0.0)))
    return patterns


def suggest_skill_name(pattern: Pattern) -> str:
    """Generate a kebab-case skill name from the tool sequence —
    `wiki_search → wiki_read_page → fetch_url` becomes
    `wiki-search-read-fetch`. Truncates to 60 chars."""
    # Strip common prefixes / underscores to keep the name compact.
    head = ""
    parts: list[str] = []
    for name in pattern.tools:
        # Drop the prefix that's shared with the previous tool to
        # keep names short.
        stem = name.replace("_", "-")
        if head and stem.startswith(head + "-"):
            stem = stem[len(head) + 1 :]
        else:
            head = stem.split("-", 1)[0]
        parts.append(stem)
    name = "-".join(parts)[:60].strip("-")
    return name or "unnamed-pattern"


def detect_patterns_semantic(
    conn: sqlite3.Connection,
    *,
    min_repetitions: int = 3,
    min_calls: int = 2,
    max_calls: int = 12,
    sample_size: int = 5,
    similarity_threshold: float = 0.85,
) -> list[Pattern]:
    """Embedding-aware sibling of `detect_patterns`.

    The token-based default clusters sessions only when their tool
    sequences match **exactly**. That misses near-duplicates like
    `(wiki_search, wiki_read_page)` vs `(wiki_search, read_file,
    wiki_read_page)` — different sequences, same intent.

    Semantic clustering embeds each session's "tool fingerprint"
    (joined tool names) and groups by cosine similarity above
    `similarity_threshold`. When no embedding adapter is
    registered — or the adapter raises — falls back transparently
    to `detect_patterns` so the user always gets *some* signal.
    """
    from veles.modules import EmbeddingError, get_embedding_adapter

    adapter = get_embedding_adapter()
    if adapter is None:
        return detect_patterns(
            conn,
            min_repetitions=min_repetitions,
            min_calls=min_calls,
            max_calls=max_calls,
            sample_size=sample_size,
        )

    rows = conn.execute(
        """
        SELECT u.session_id, t.name AS tool_name, u.invoked_at
        FROM tool_uses u
        JOIN tools t ON t.id = u.tool_id
        WHERE u.session_id IS NOT NULL
        ORDER BY u.session_id, u.invoked_at
        """
    ).fetchall()
    if not rows:
        return []

    from collections import defaultdict

    sessions: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in rows:
        sessions[row["session_id"]].append((row["tool_name"], row["invoked_at"]))

    # Build (session_id, tool_seq, last_at, fingerprint_text) for
    # in-window sessions, keep raw tool tuples for output.
    candidates: list[tuple[str, tuple[str, ...], float]] = []
    for session_id, calls in sessions.items():
        if not (min_calls <= len(calls) <= max_calls):
            continue
        seq = tuple(c[0] for c in calls)
        last_at = max(c[1] for c in calls)
        candidates.append((session_id, seq, last_at))
    if not candidates:
        return []

    fingerprints = [" ".join(c[1]) for c in candidates]
    try:
        vecs = adapter.embed(fingerprints)
    except EmbeddingError:
        return detect_patterns(
            conn,
            min_repetitions=min_repetitions,
            min_calls=min_calls,
            max_calls=max_calls,
            sample_size=sample_size,
        )

    # Greedy clustering: walk candidates in order; assign each to the
    # first cluster whose centroid is within `similarity_threshold`,
    # otherwise start a new cluster. Centroid = first member's vector
    # (simple; sufficient for the cluster sizes Veles sees).
    clusters: list[dict] = []  # {"centroid": vec, "members": list[idx]}
    for i, vec in enumerate(vecs):
        placed = False
        for cluster in clusters:
            if _cosine_sim(vec, cluster["centroid"]) >= similarity_threshold:
                cluster["members"].append(i)
                placed = True
                break
        if not placed:
            clusters.append({"centroid": vec, "members": [i]})

    patterns: list[Pattern] = []
    for cluster in clusters:
        member_indices = cluster["members"]
        if len(member_indices) < min_repetitions:
            continue
        # Pick the cluster's most-frequent tool sequence as the
        # canonical Pattern.tools (the cluster might contain
        # variants like (a, b) and (a, b, c)).
        seqs = [candidates[i][1] for i in member_indices]
        canonical = max(set(seqs), key=seqs.count)
        members_sorted = sorted(
            (candidates[i] for i in member_indices),
            key=lambda c: c[2],
            reverse=True,
        )
        sample = tuple(c[0] for c in members_sorted[:sample_size])
        latest = members_sorted[0][2] if members_sorted else None
        patterns.append(
            Pattern(
                tools=canonical,
                repetitions=len(member_indices),
                sample_sessions=sample,
                latest_at=latest,
            )
        )

    patterns.sort(key=lambda p: (-p.repetitions, -(p.latest_at or 0.0)))
    return patterns


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]. Same helper shape as
    `project_tree._cosine` — kept local to avoid a cross-module
    import for one math function."""
    import math

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = math.fsum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(math.fsum(x * x for x in a))
    nb = math.sqrt(math.fsum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


__all__ = [
    "Pattern",
    "detect_patterns",
    "detect_patterns_semantic",
    "suggest_skill_name",
]
