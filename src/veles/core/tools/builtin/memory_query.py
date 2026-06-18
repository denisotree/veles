"""M169: read-only SQL over the project's memory.db.

`memory_save_insight` / `memory_save_rule` only INSERT — the agent could
*write* to its memory but never read back what it (or the learning loop)
recorded. `memory_query` closes that: a single read-only SELECT against
memory.db so the agent can consult its own insights, rules, telemetry
(tool_uses / skill_uses), tasks, jobs, and session log on demand.

Read-only is enforced two ways: a SELECT/WITH-only prefix guard, and
`PRAGMA query_only = ON` on the connection (SQLite rejects any write with
SQLITE_READONLY). `sqlite3.execute` already runs one statement at a time, so
statement-stacking can't sneak a write past the prefix check.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from veles.core.context import current_project
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool


def _cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("|", r"\|")
    return text[:200] + ("…" if len(text) > 200 else "")


@tool(risk_class=RiskClass.SEARCH_ONLY, side_effects=[])
def memory_query(sql: str, max_rows: int = 50) -> str:
    """Run a read-only SQL SELECT against the project's memory.db.

    Use this to read back what you (or the learning loop) recorded. Only a
    single `SELECT` (or `WITH … SELECT`) is allowed — writes are rejected and
    the connection is opened read-only. Discover tables with
    `SELECT name FROM sqlite_master WHERE type='table'`.

    Useful tables: `insights(title, body, category, created_at,
    last_referenced_at)`, `rules(kind, body, source)`, `tasks(title, due_at,
    state, deliver_to)`, `jobs`, `tool_uses`, `skill_uses`, `sessions`,
    `turns(session_id, role, content)`. Returns a markdown table (capped at
    `max_rows`, default 50, max 500).
    """
    project = current_project()
    if project is None:
        return "<error: no active project>"
    db_path = Path(project.memory_db_path)
    if not db_path.exists():
        return "<error: project memory.db not found>"

    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return "<error: empty query>"
    low = stripped.lower()
    if not (low.startswith("select") or low.startswith("with")):
        return "<error: only read-only SELECT queries are allowed>"
    max_rows = max(1, min(max_rows, 500))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        rows = conn.execute(stripped).fetchmany(max_rows + 1)
    except sqlite3.Error as exc:
        return f"<error: {exc}>"
    finally:
        conn.close()

    if not rows:
        return "(no rows)"
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    cols = list(rows[0].keys())
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(row[c]) for c in cols) + " |")
    out = "\n".join(lines)
    if truncated:
        out += f"\n\n_(truncated to {max_rows} rows)_"
    return out
