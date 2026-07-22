"""M125: SQL-direct memory writers — `memory_save_insight` and
`memory_save_rule`.

M161: the `insights` SQL row is the *canonical* store — recall, aging
(`last_referenced_at`), and dream dedup all operate on it. On every
successful insert `save_insight_row` also renders a human-readable
markdown view under `.veles/memory/insights/` (best-effort,
regenerable from the row; see `core/memory/artefacts.py`).

Both tools resolve the active project via the same ContextVar pattern
that `wiki_tools.py` uses — no Project argument from the agent, no
path manipulation, no escape from the sandbox. Failures are surfaced
as `<error: ...>` strings (consistent with wiki_tools).
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING

from veles.core.context import current_project
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

if TYPE_CHECKING:
    from veles.core.project import Project

_RULE_KINDS = frozenset({"format", "do", "dont", "preference"})


def _resolve_project(project: Project | None) -> Project:
    proj = project if project is not None else current_project()
    if proj is None:
        raise RuntimeError("no active Veles project; run `veles init` and ensure cwd is inside it")
    return proj


def _open_store(project: Project | None = None):
    from veles.core.memory import SessionStore

    return SessionStore(_resolve_project(project).memory_db_path)


def save_insight_row(
    *,
    title: str,
    body: str,
    category: str,
    file_path: str = "",
    project: Project | None = None,
    confidence: float = 1.0,
) -> int:
    """Canonical insight writer — used by the @tool wrapper, the insight
    extractor, the TUI `/save`, and worker mini-reports.

    Inserts the SQL row (source of truth); on success renders the
    markdown view best-effort and backfills `file_path` with the view's
    project-relative path when the caller didn't supply one. Returns the
    row id, or 0 when the SQL write failed — callers must treat 0 as
    "insight not persisted".
    """
    try:
        proj = _resolve_project(project)
        store = _open_store(proj)
    except Exception:
        return 0
    try:
        cur = store._conn.execute(
            "INSERT INTO insights(title, body, category, file_path, created_at, confidence)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (title, body, category, file_path or None, time.time(), confidence),
        )
        rid = int(cur.lastrowid or 0)
        if rid and not file_path:
            view_rel = _render_view(proj, rid=rid, title=title, body=body)
            if view_rel:
                store._conn.execute(
                    "UPDATE insights SET file_path = ? WHERE id = ?", (view_rel, rid)
                )
        store._conn.commit()
        return rid
    except Exception:
        return 0
    finally:
        with contextlib.suppress(Exception):
            store._conn.close()


def _render_view(project: Project, *, rid: int, title: str, body: str) -> str | None:
    """Render `.veles/memory/insights/<slug>-<id>.md` from the row.

    Best-effort: a filesystem hiccup must not lose the SQL row. Returns
    the project-relative path, or None on failure."""
    try:
        from veles.core.memory.artefacts import write_insight_view
        from veles.core.slug import normalize_slug

        path = write_insight_view(
            project, slug=f"{normalize_slug(title)}-{rid}", title=title, body=body
        )
        return path.relative_to(project.root).as_posix()
    except Exception:
        return None


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
            "INSERT INTO rules(kind, body, source, created_at) VALUES (?, ?, ?, ?)",
            (kind, body, source, time.time()),
        )
        store._conn.commit()
        return int(cur.lastrowid or 0)
    except Exception:
        return 0
    finally:
        with contextlib.suppress(Exception):
            store._conn.close()


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["filesystem"])
def memory_save_insight(
    title: str, body: str, category: str = "insight", file_path: str = ""
) -> str:
    """Save a durable insight into the project's SQL memory.

    Use this when you've distilled a session into a finding the
    project would benefit from recalling later (curated session
    summary, recovery pattern, design decision). `category` groups
    related insights (e.g. `curated-session`, `recovery`,
    `architecture`); `file_path` is an optional pointer to a related
    page when one exists (left empty, it is backfilled with the
    rendered memory view's path).

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
