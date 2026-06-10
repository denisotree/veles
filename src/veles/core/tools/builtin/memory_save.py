"""M125: SQL-direct memory writers — `memory_save_insight` and
`memory_save_rule`.

The curator and ad-hoc learning passes need to land their extractions
in queryable SQL (M119 `insights` / `rules` tables), not just in wiki
markdown. Wiki pages are durable artefacts; SQL rows are the index
that `/insights`, `/rules`, FTS lookup, and the recall pipeline use to
surface the same content fast.

Both tools resolve the active project via the same ContextVar pattern
that `wiki_tools.py` uses — no Project argument from the agent, no
path manipulation, no escape from the sandbox. Failures are surfaced
as `<error: ...>` strings (consistent with wiki_tools).
"""

from __future__ import annotations

import time

from veles.core.context import current_project
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

_RULE_KINDS = frozenset({"format", "do", "dont", "preference"})


def _open_store():
    proj = current_project()
    if proj is None:
        raise RuntimeError(
            "no active Veles project; run `veles init` and ensure cwd is inside it"
        )
    from veles.core.memory import SessionStore

    return SessionStore(proj.memory_db_path)


def save_insight_row(
    *, title: str, body: str, category: str, file_path: str = ""
) -> int:
    """Programmatic helper used by curator hooks and the insight
    extractor — same path the @tool wraps, but no string return.
    Returns the inserted row id, or 0 on failure (best-effort)."""
    try:
        store = _open_store()
    except Exception:
        return 0
    try:
        cur = store._conn.execute(
            "INSERT INTO insights(title, body, category, file_path, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (title, body, category, file_path or None, time.time()),
        )
        store._conn.commit()
        return int(cur.lastrowid or 0)
    except Exception:
        return 0
    finally:
        try:
            store._conn.close()
        except Exception:
            pass


def save_rule_row(*, kind: str, body: str, source: str) -> int:
    """Programmatic helper. `kind` must be one of
    `format` / `do` / `dont` / `preference` (M119 schema CHECK)."""
    if kind not in _RULE_KINDS:
        return 0
    try:
        store = _open_store()
    except Exception:
        return 0
    try:
        cur = store._conn.execute(
            "INSERT INTO rules(kind, body, source, created_at)"
            " VALUES (?, ?, ?, ?)",
            (kind, body, source, time.time()),
        )
        store._conn.commit()
        return int(cur.lastrowid or 0)
    except Exception:
        return 0
    finally:
        try:
            store._conn.close()
        except Exception:
            pass


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["filesystem"])
def memory_save_insight(
    title: str, body: str, category: str = "insight", file_path: str = ""
) -> str:
    """Save a durable insight into the project's SQL memory.

    Use this when you've distilled a session into a finding the
    project would benefit from recalling later (curated session
    summary, recovery pattern, design decision). `category` groups
    related insights (e.g. `curated-session`, `recovery`,
    `architecture`); `file_path` is optional pointer to the
    corresponding wiki page when one exists.

    Returns a short confirmation with the row id.
    """
    rid = save_insight_row(title=title, body=body, category=category, file_path=file_path)
    if rid == 0:
        return "<error: failed to save insight (no active project or db error)>"
    return f"saved insight #{rid} ({category})"


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["filesystem"])
def memory_save_rule(kind: str, body: str, source: str = "extracted") -> str:
    """Save a behavioral rule the agent should follow in future runs.

    `kind` must be one of: `format` (response shape), `do` (always do),
    `dont` (never do), `preference` (user taste). `body` is the rule
    text in plain language. `source` is the origin
    (`explicit-feedback`, `extracted`, `session-<id>`, etc).

    Rules surface back to the agent via the M22 recall pipeline and
    `/rules` slash inspector. Returns the row id on success.
    """
    rid = save_rule_row(kind=kind, body=body, source=source)
    if rid == 0:
        return (
            f"<error: failed to save rule (invalid kind {kind!r} or db error). "
            f"Valid kinds: format, do, dont, preference>"
        )
    return f"saved rule #{rid} ({kind})"
