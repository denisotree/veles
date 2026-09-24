"""Read-only views of memory for the inspectors (M264c).

`/insights` and `/rules` exist twice — once in the REPL, once in the Telegram
channel — and each had written its own SQL against a connection reached out of
someone else's store. Four copies of two queries, and four places that would
have to change together the next time a column moved. `insights.hidden_reason`
(M260) already landed in only one of them.

So the queries live here, once, and the surfaces keep what actually differs:
how a row is rendered for a terminal or for HTML.

**These are deliberately local reads.** They answer "what does this project's
memory file hold", which is a diagnostic question about an installation, not a
recall question about a tenant — an inspector that silently showed a remote
engine's rows would be answering something the user did not ask. They take a
`sqlite3.Connection`, which the caller gets from `store.raw()`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

# Inspectors show the hidden rows too: "why did the agent stop using this?" is
# only answerable if what left recall is visible next to what stayed (M260).
_INSIGHT_COLUMNS = "id, title, category, created_at, hidden_at, hidden_reason"
_RULE_COLUMNS = "id, kind, body, source, created_at"


@dataclass(frozen=True, slots=True)
class InsightRow:
    id: int
    title: str
    category: str | None
    created_at: float | None
    hidden_at: float | None
    hidden_reason: str | None

    @property
    def hidden(self) -> bool:
        return self.hidden_at is not None


@dataclass(frozen=True, slots=True)
class RuleRow:
    id: int
    kind: str
    body: str
    source: str | None
    created_at: float | None


def recent_insights(
    conn: sqlite3.Connection, *, category: str | None = None, limit: int = 10
) -> list[InsightRow]:
    """Newest insights first, optionally filtered to one category."""
    where = " WHERE category = ?" if category else ""
    params: tuple[object, ...] = (category, limit) if category else (limit,)
    rows = conn.execute(
        f"SELECT {_INSIGHT_COLUMNS} FROM insights{where} ORDER BY created_at DESC, id DESC LIMIT ?",
        params,
    ).fetchall()
    return [
        InsightRow(
            id=int(r["id"]),
            title=r["title"] or "",
            category=r["category"],
            created_at=r["created_at"],
            hidden_at=r["hidden_at"],
            hidden_reason=r["hidden_reason"],
        )
        for r in rows
    ]


def recent_rules(
    conn: sqlite3.Connection, *, kind: str | None = None, limit: int = 10
) -> list[RuleRow]:
    """Newest rules first, optionally filtered to one kind."""
    where = " WHERE kind = ?" if kind else ""
    params: tuple[object, ...] = (kind, limit) if kind else (limit,)
    rows = conn.execute(
        f"SELECT {_RULE_COLUMNS} FROM rules{where} ORDER BY created_at DESC, id DESC LIMIT ?",
        params,
    ).fetchall()
    return [
        RuleRow(
            id=int(r["id"]),
            kind=r["kind"] or "",
            body=r["body"] or "",
            source=r["source"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


__all__ = ["InsightRow", "RuleRow", "recent_insights", "recent_rules"]
