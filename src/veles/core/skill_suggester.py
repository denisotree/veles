"""M121c part 2: surface skill suggestions from the pattern detector
into the curator loop.

`detect_patterns` (M121b) finds repeated tool-call sequences across
sessions. M121c wires it into the curator flow: after each curator
pass, `surface_skill_suggestions` runs the detector and writes any
fresh clusters (≥3 reps that we haven't already surfaced) as
`insights` rows with category `"skill-suggestion"`. The agent's
existing `/save` flow + the insights FTS then make them discoverable.

We dedup on the canonical tool-sequence key — once a suggestion for
`(wiki_search, wiki_read_page)` is in `insights`, the next curator
pass won't re-surface it.
"""

from __future__ import annotations

import logging
import sqlite3
import time

from veles.core.skill_pattern_detector import (
    Pattern,
    detect_patterns_semantic,
    suggest_skill_name,
)

logger = logging.getLogger(__name__)


SKILL_SUGGESTION_CATEGORY = "skill-suggestion"


def surface_skill_suggestions(
    conn: sqlite3.Connection,
    *,
    min_repetitions: int = 3,
    now: float | None = None,
) -> list[Pattern]:
    """Run the pattern detector and persist any new clusters as
    `insights` rows. Returns the list of patterns that were newly
    surfaced (already-known clusters are skipped). Never raises —
    a failure logs and returns []."""
    wall = time.time() if now is None else now
    try:
        # M121b2: embedding-aware detection — near-duplicate tool sequences
        # (same intent, different arity/order) cluster into one suggestion when
        # an embedding adapter is registered; transparently falls back to the
        # exact-token detector otherwise (so the default stays unchanged).
        patterns = detect_patterns_semantic(conn, min_repetitions=min_repetitions)
    except sqlite3.Error as exc:
        logger.info("skill suggestion: pattern detection failed: %s", exc)
        return []
    if not patterns:
        return []
    fresh: list[Pattern] = []
    for pattern in patterns:
        title = _suggestion_title(pattern)
        # Dedup by title — once we've written
        # `Skill suggestion: <tools>` we don't re-surface it.
        existing = conn.execute(
            "SELECT 1 FROM insights WHERE title = ? AND category = ?",
            (title, SKILL_SUGGESTION_CATEGORY),
        ).fetchone()
        if existing is not None:
            continue
        body = _render_suggestion(pattern)
        conn.execute(
            "INSERT INTO insights(title, body, category, created_at)"
            " VALUES (?, ?, ?, ?)",
            (title, body, SKILL_SUGGESTION_CATEGORY, wall),
        )
        fresh.append(pattern)
    return fresh


def _suggestion_title(pattern: Pattern) -> str:
    """Stable title used as dedup key. Format ties tools together so
    `(a, b, c)` and `(a, b)` get distinct titles."""
    return f"Skill suggestion: {' → '.join(pattern.tools)}"


def _render_suggestion(pattern: Pattern) -> str:
    name = suggest_skill_name(pattern)
    sessions = "\n".join(f"- `{sid}`" for sid in pattern.sample_sessions[:5])
    return (
        f"You've run this tool sequence **{pattern.repetitions} times** "
        f"across sessions:\n\n"
        f"`{' → '.join(pattern.tools)}`\n\n"
        f"Consider formalising as a skill named `{name}` "
        f"(or pick your own). Sample sessions where it ran:\n\n"
        f"{sessions or '(none recorded)'}"
    )


__all__ = [
    "SKILL_SUGGESTION_CATEGORY",
    "surface_skill_suggestions",
]
