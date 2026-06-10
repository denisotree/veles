"""M120.1: persistence layer over the M119 `tools` / `tool_uses` tables.

The in-memory `Registry` (in `core/tools/registry.py`) keeps the
authoritative *behavioural* spec of each tool — handler, parameter
schema, side-effects. This module is its on-disk *catalogue*: rows in
`memory.db` that carry origin/scope/inheritance/telemetry and survive
across runs.

Functions here never construct tools themselves. They sync the
catalogue with whatever the Registry already knows, and they record
every dispatch as a `tool_uses` row so `use_count` / `success_rate` /
`last_used` are aggregate queries instead of YAML frontmatter writes.

Why split this out: keeps `registry.py` free of SQL. The Registry can
still run on `:memory:` databases (tests, ephemeral sessions) when
nobody calls into `persistence`; and a future M120b can layer a
sqlite-vec embedding column on top without touching the dispatch path.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from veles.core.tools.registry import ToolEntry


@dataclass(frozen=True, slots=True)
class ToolRecord:
    """One row of the `tools` table, projected into Python."""

    id: int
    name: str
    scope: str
    origin: str
    base_tool_id: int | None
    description: str | None
    manifest_json: str | None


@dataclass(frozen=True, slots=True)
class ToolTelemetry:
    """Aggregated metrics for one tool. Mirrors what the YAML frontmatter
    used to track for skills (M-R1 era) but as live SQL queries."""

    tool_name: str
    use_count: int
    success_count: int
    error_count: int
    success_rate: float  # success_count / use_count, or 0.0 when use_count == 0
    last_used_at: float | None
    avg_latency_ms: float | None


# ---------- writes ----------


def upsert_tool(
    conn: sqlite3.Connection,
    entry: ToolEntry,
    *,
    scope: str = "builtin",
    origin: str = "builtin",
    base_tool_name: str | None = None,
    now: float | None = None,
) -> int:
    """Insert or update one tool row from a `ToolEntry`. Returns the id.

    Designed to be safe to call on every Registry sync — if the row
    exists, we update mutable columns (description, scope, base_tool_id,
    manifest) but keep `id` and `created_at` stable. The `name` column
    is UNIQUE, so this is a natural-key upsert.
    """
    wall = time.time() if now is None else now
    base_id = (
        _id_for_name(conn, base_tool_name) if base_tool_name else None
    )
    manifest = json.dumps(
        {
            "side_effects": entry.side_effects,
            "timeout_s": entry.timeout_s,
            "max_result_chars": entry.max_result_chars,
            "sensitive": entry.sensitive,
            "risk_class": entry.risk_class.value if entry.risk_class else None,
            "commit_of": entry.commit_of,
        },
        sort_keys=True,
    )
    existing = conn.execute(
        "SELECT id FROM tools WHERE name = ?", (entry.name,)
    ).fetchone()
    if existing is None:
        cur = conn.execute(
            "INSERT INTO tools("
            " name, scope, origin, base_tool_id, manifest_json,"
            " description, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.name,
                scope,
                origin,
                base_id,
                manifest,
                entry.description,
                wall,
                wall,
            ),
        )
        return int(cur.lastrowid or 0)
    tool_id = int(existing["id"])
    conn.execute(
        "UPDATE tools"
        " SET scope = ?, origin = ?, base_tool_id = ?,"
        "     manifest_json = ?, description = ?, updated_at = ?"
        " WHERE id = ?",
        (scope, origin, base_id, manifest, entry.description, wall, tool_id),
    )
    return tool_id


def record_use(
    conn: sqlite3.Connection,
    *,
    tool_name: str,
    ok: bool,
    latency_ms: int | None = None,
    error_kind: str | None = None,
    session_id: str | None = None,
    turn_id: int | None = None,
    now: float | None = None,
) -> int:
    """Append one row to `tool_uses`. Silently no-op (returns 0) when
    the tool isn't catalogued — the dispatch path can run before the
    Registry sync (during bootstrap), and we don't want to crash a
    valid call just to satisfy referential integrity."""
    wall = time.time() if now is None else now
    tool_id = _id_for_name(conn, tool_name)
    if tool_id is None:
        return 0
    cur = conn.execute(
        "INSERT INTO tool_uses("
        " tool_id, session_id, turn_id, invoked_at, ok, latency_ms, error_kind"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tool_id, session_id, turn_id, wall, 1 if ok else 0, latency_ms, error_kind),
    )
    return int(cur.lastrowid)


# ---------- reads ----------


def get_tool(conn: sqlite3.Connection, name: str) -> ToolRecord | None:
    row = conn.execute(
        "SELECT id, name, scope, origin, base_tool_id, description, manifest_json"
        " FROM tools WHERE name = ?",
        (name,),
    ).fetchone()
    return _row_to_record(row) if row else None


def list_tools(
    conn: sqlite3.Connection,
    *,
    scope: str | None = None,
    origin: str | None = None,
) -> list[ToolRecord]:
    """List tools in the catalogue, optionally filtered. Sorted by name
    (the registry sorts that way too — keeps prompt-cache invariants)."""
    clauses: list[str] = []
    params: list[Any] = []
    if scope is not None:
        clauses.append("scope = ?")
        params.append(scope)
    if origin is not None:
        clauses.append("origin = ?")
        params.append(origin)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT id, name, scope, origin, base_tool_id, description, manifest_json"
        f" FROM tools{where} ORDER BY name",
        params,
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def telemetry(conn: sqlite3.Connection, name: str) -> ToolTelemetry:
    """Return aggregate metrics for `name`. Returns zeros (rather than
    raising) when the tool is unknown — callers usually want a chart
    that shows "no uses" instead of a 404."""
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS use_count,
            COALESCE(SUM(ok), 0) AS success_count,
            COALESCE(SUM(1 - ok), 0) AS error_count,
            MAX(invoked_at) AS last_used_at,
            AVG(latency_ms) AS avg_latency_ms
        FROM tool_uses
        WHERE tool_id = (SELECT id FROM tools WHERE name = ?)
        """,
        (name,),
    ).fetchone()
    use_count = int(row["use_count"]) if row else 0
    success_count = int(row["success_count"]) if row else 0
    error_count = int(row["error_count"]) if row else 0
    rate = success_count / use_count if use_count else 0.0
    return ToolTelemetry(
        tool_name=name,
        use_count=use_count,
        success_count=success_count,
        error_count=error_count,
        success_rate=rate,
        last_used_at=row["last_used_at"] if row else None,
        avg_latency_ms=row["avg_latency_ms"] if row else None,
    )


def telemetry_batch(
    conn: sqlite3.Connection, names: list[str]
) -> dict[str, ToolTelemetry]:
    """Bulk variant. One SQL round-trip per call instead of len(names)."""
    if not names:
        return {}
    placeholders = ",".join("?" * len(names))
    rows = conn.execute(
        f"""
        SELECT
            t.name AS tool_name,
            COUNT(u.id) AS use_count,
            COALESCE(SUM(u.ok), 0) AS success_count,
            COALESCE(SUM(1 - u.ok), 0) AS error_count,
            MAX(u.invoked_at) AS last_used_at,
            AVG(u.latency_ms) AS avg_latency_ms
        FROM tools t
        LEFT JOIN tool_uses u ON u.tool_id = t.id
        WHERE t.name IN ({placeholders})
        GROUP BY t.id
        """,
        names,
    ).fetchall()
    out: dict[str, ToolTelemetry] = {}
    for row in rows:
        use_count = int(row["use_count"])
        success_count = int(row["success_count"])
        rate = success_count / use_count if use_count else 0.0
        out[row["tool_name"]] = ToolTelemetry(
            tool_name=row["tool_name"],
            use_count=use_count,
            success_count=success_count,
            error_count=int(row["error_count"]),
            success_rate=rate,
            last_used_at=row["last_used_at"],
            avg_latency_ms=row["avg_latency_ms"],
        )
    # Names that don't exist in the catalogue get zero records — keeps
    # the caller's loop uniform.
    for name in names:
        if name not in out:
            out[name] = ToolTelemetry(
                tool_name=name,
                use_count=0,
                success_count=0,
                error_count=0,
                success_rate=0.0,
                last_used_at=None,
                avg_latency_ms=None,
            )
    return out


def inheritance_chain(conn: sqlite3.Connection, name: str) -> list[ToolRecord]:
    """Walk `name → base_tool_id` chain via recursive CTE. Returns the
    chain in descent order: index 0 is `name`, index 1 is its base, etc.

    Returns an empty list when `name` doesn't exist. Cycles (shouldn't
    happen, but defence in depth) are clipped at depth 10 by the CTE.
    """
    rows = conn.execute(
        """
        WITH RECURSIVE chain(id, name, scope, origin, base_tool_id,
                             description, manifest_json, depth) AS (
            SELECT id, name, scope, origin, base_tool_id,
                   description, manifest_json, 0
            FROM tools WHERE name = ?
            UNION ALL
            SELECT t.id, t.name, t.scope, t.origin, t.base_tool_id,
                   t.description, t.manifest_json, c.depth + 1
            FROM tools t
            JOIN chain c ON t.id = c.base_tool_id
            WHERE c.depth < 10
        )
        SELECT id, name, scope, origin, base_tool_id,
               description, manifest_json
        FROM chain ORDER BY depth
        """,
        (name,),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


# ---------- internals ----------


def _id_for_name(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute("SELECT id FROM tools WHERE name = ?", (name,)).fetchone()
    return int(row["id"]) if row else None


def _row_to_record(row: sqlite3.Row) -> ToolRecord:
    return ToolRecord(
        id=int(row["id"]),
        name=row["name"],
        scope=row["scope"],
        origin=row["origin"],
        base_tool_id=row["base_tool_id"],
        description=row["description"],
        manifest_json=row["manifest_json"],
    )


__all__ = [
    "ToolRecord",
    "ToolTelemetry",
    "get_tool",
    "inheritance_chain",
    "list_tools",
    "record_use",
    "telemetry",
    "telemetry_batch",
    "upsert_tool",
]
