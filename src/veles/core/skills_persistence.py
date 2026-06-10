"""M121.1: persistence + inheritance for the `skills` / `skill_uses`
tables introduced in M119.

Sibling of `core/tools/persistence.py`. Same layered split: SKILL.md
frontmatter is the behavioural source of truth (description, body,
tools list), the SQL row is the *catalogue* — origin/scope/inheritance/
telemetry that survives across runs. Functions here:

- `upsert_skill(conn, skill)` syncs one `Skill` (from `core/skills.py`)
  into the catalogue row, resolving `extends` name → `base_skill_id`.
- `record_skill_use(conn, name, ok, latency_ms)` appends a `skill_uses`
  row so use_count / success_rate become aggregate queries.
- `inheritance_chain(conn, name)` walks the parent pointers via the
  same recursive-CTE pattern as tools.
- `resolve_inheritance(skill, by_name)` (pure Python, no DB) merges a
  Skill with its parents — child's tools / parameters override base
  ones at the same name, body is concatenated parent → child.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass

from veles.core.skills import Skill


@dataclass(frozen=True, slots=True)
class SkillRecord:
    id: int
    name: str
    scope: str
    base_skill_id: int | None
    description: str | None
    file_path: str | None


@dataclass(frozen=True, slots=True)
class SkillTelemetry:
    skill_name: str
    use_count: int
    success_count: int
    error_count: int
    success_rate: float
    last_used_at: float | None
    avg_latency_ms: float | None


# ---------- writes ----------


def upsert_skill(
    conn: sqlite3.Connection,
    skill: Skill,
    *,
    now: float | None = None,
) -> int:
    """Insert/refresh one skill row. Resolves `skill.extends` (a name
    string) into `base_skill_id` (an int FK); unknown base names are
    silently stored as NULL — same posture as tools'
    `upsert_tool`. Also syncs `skill_tool_refs` so each `tool` name in
    `skill.tools` that exists in the tools catalogue becomes a
    skill→tool edge. Tools that aren't catalogued (built-in only known
    to the in-memory Registry, never persisted) are silently skipped —
    the agent still calls them through the Registry; the catalogue
    just doesn't have a row to point at."""
    wall = time.time() if now is None else now
    base_id = (
        _id_for_name(conn, skill.extends) if skill.extends else None
    )
    frontmatter = json.dumps(
        {
            "tools": list(skill.tools),
            "parameters": list(skill.parameters),
            "max_iterations": skill.max_iterations,
            "extends": skill.extends,
        },
        sort_keys=True,
    )
    existing = conn.execute(
        "SELECT id FROM skills WHERE name = ?", (skill.name,)
    ).fetchone()
    if existing is None:
        cur = conn.execute(
            "INSERT INTO skills("
            " name, scope, base_skill_id, frontmatter_json,"
            " description, file_path, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                skill.name,
                skill.scope,
                base_id,
                frontmatter,
                skill.description,
                str(skill.path),
                wall,
                wall,
            ),
        )
        skill_id = int(cur.lastrowid or 0)
    else:
        skill_id = int(existing["id"])
        conn.execute(
            "UPDATE skills"
            " SET scope = ?, base_skill_id = ?, frontmatter_json = ?,"
            "     description = ?, file_path = ?, updated_at = ?"
            " WHERE id = ?",
            (
                skill.scope,
                base_id,
                frontmatter,
                skill.description,
                str(skill.path),
                wall,
                skill_id,
            ),
        )
    _sync_skill_tool_refs(conn, skill_id, skill.tools)
    return skill_id


def _sync_skill_tool_refs(
    conn: sqlite3.Connection, skill_id: int, tool_names: list[str]
) -> None:
    """Replace this skill's tool edges with the current list. Tools
    not in the catalogue are skipped (they may be in-memory builtins).
    Old edges to tools no longer mentioned are dropped — the table
    reflects the skill's *current* declared dependencies."""
    conn.execute(
        "DELETE FROM skill_tool_refs WHERE skill_id = ?", (skill_id,)
    )
    if not tool_names:
        return
    placeholders = ",".join("?" * len(tool_names))
    rows = conn.execute(
        f"SELECT id, name FROM tools WHERE name IN ({placeholders})",
        tool_names,
    ).fetchall()
    tool_id_by_name = {r["name"]: int(r["id"]) for r in rows}
    for name in tool_names:
        tid = tool_id_by_name.get(name)
        if tid is None:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO skill_tool_refs(skill_id, tool_id) VALUES (?, ?)",
            (skill_id, tid),
        )


def get_skill_tool_refs(conn: sqlite3.Connection, skill_name: str) -> list[str]:
    """Return tool names this skill depends on, as catalogued. Useful
    for validation ('does every declared tool exist?') and for the
    inheritance UI ('what does this skill actually call?')."""
    rows = conn.execute(
        """
        SELECT t.name FROM skill_tool_refs r
        JOIN tools t ON t.id = r.tool_id
        WHERE r.skill_id = (SELECT id FROM skills WHERE name = ?)
        ORDER BY t.name
        """,
        (skill_name,),
    ).fetchall()
    return [r["name"] for r in rows]


def record_skill_use(
    conn: sqlite3.Connection,
    *,
    skill_name: str,
    ok: bool,
    latency_ms: int | None = None,
    error_kind: str | None = None,
    session_id: str | None = None,
    now: float | None = None,
) -> int:
    """Append to `skill_uses`. Silent no-op (returns 0) when the skill
    isn't catalogued — early dispatch shouldn't crash on a missing row."""
    wall = time.time() if now is None else now
    skill_id = _id_for_name(conn, skill_name)
    if skill_id is None:
        return 0
    cur = conn.execute(
        "INSERT INTO skill_uses("
        " skill_id, session_id, invoked_at, ok, latency_ms, error_kind"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (skill_id, session_id, wall, 1 if ok else 0, latency_ms, error_kind),
    )
    return int(cur.lastrowid or 0)


# ---------- reads ----------


def get_skill(conn: sqlite3.Connection, name: str) -> SkillRecord | None:
    row = conn.execute(
        "SELECT id, name, scope, base_skill_id, description, file_path"
        " FROM skills WHERE name = ?",
        (name,),
    ).fetchone()
    return _row_to_record(row) if row else None


def list_skills(
    conn: sqlite3.Connection, *, scope: str | None = None
) -> list[SkillRecord]:
    if scope is None:
        rows = conn.execute(
            "SELECT id, name, scope, base_skill_id, description, file_path"
            " FROM skills ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, scope, base_skill_id, description, file_path"
            " FROM skills WHERE scope = ? ORDER BY name",
            (scope,),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


def skill_telemetry(conn: sqlite3.Connection, name: str) -> SkillTelemetry:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS use_count,
            COALESCE(SUM(ok), 0) AS success_count,
            COALESCE(SUM(1 - ok), 0) AS error_count,
            MAX(invoked_at) AS last_used_at,
            AVG(latency_ms) AS avg_latency_ms
        FROM skill_uses
        WHERE skill_id = (SELECT id FROM skills WHERE name = ?)
        """,
        (name,),
    ).fetchone()
    use_count = int(row["use_count"]) if row else 0
    success = int(row["success_count"]) if row else 0
    return SkillTelemetry(
        skill_name=name,
        use_count=use_count,
        success_count=success,
        error_count=int(row["error_count"]) if row else 0,
        success_rate=(success / use_count) if use_count else 0.0,
        last_used_at=row["last_used_at"] if row else None,
        avg_latency_ms=row["avg_latency_ms"] if row else None,
    )


def inheritance_chain(
    conn: sqlite3.Connection, name: str
) -> list[SkillRecord]:
    """Walk the `name → base_skill_id` chain (recursive CTE, depth ≤ 10).
    Returns chain in descent order: `name` at index 0, its base at 1,
    grandparent at 2, ..."""
    rows = conn.execute(
        """
        WITH RECURSIVE chain(id, name, scope, base_skill_id,
                             description, file_path, depth) AS (
            SELECT id, name, scope, base_skill_id,
                   description, file_path, 0
            FROM skills WHERE name = ?
            UNION ALL
            SELECT s.id, s.name, s.scope, s.base_skill_id,
                   s.description, s.file_path, c.depth + 1
            FROM skills s
            JOIN chain c ON s.id = c.base_skill_id
            WHERE c.depth < 10
        )
        SELECT id, name, scope, base_skill_id, description, file_path
        FROM chain ORDER BY depth
        """,
        (name,),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


# ---------- pure-Python inheritance resolver ----------


def resolve_inheritance(
    skill: Skill, by_name: dict[str, Skill]
) -> Skill:
    """Merge `skill` with its `extends` chain into a single
    *flattened* Skill. Pure Python — works on `Skill` objects from
    `discover_skills`, no DB needed. Useful for runtime invocation
    when the agent dispatches a child skill but expects to see the
    union of the chain's tools/parameters.

    Merge policy (child overrides parent on collision):
      - description: child wins
      - body: parent + "\\n\\n" + child  (parent context first)
      - tools: union, child order preserved at the end
      - parameters: child overrides by `name` field; un-overridden
        parent params kept in original order
      - extends: cleared on the flattened result (chain is collapsed)
      - max_iterations: child's value, falling back to parent if child
        left the default

    Cycles or unknown parents stop the walk silently — the chain
    flattens up to whatever we successfully resolved.
    """
    chain: list[Skill] = []
    visited: set[str] = set()
    cursor: Skill | None = skill
    while cursor is not None and cursor.name not in visited:
        chain.append(cursor)
        visited.add(cursor.name)
        if cursor.extends is None:
            break
        cursor = by_name.get(cursor.extends)

    if len(chain) == 1:
        return skill  # nothing to merge

    # Walk parent → child (reverse of chain) so child overrides apply
    # last. The chain is collected child-first, so reverse it.
    descending = list(reversed(chain))
    base = descending[0]
    merged_tools: list[str] = list(base.tools)
    merged_params: list[dict] = list(base.parameters)
    merged_body = base.body
    merged_desc = base.description
    merged_max_iter = base.max_iterations
    for child in descending[1:]:
        # tools: extend with new names from child
        for t in child.tools:
            if t not in merged_tools:
                merged_tools.append(t)
        # parameters: dict-merge by `name`
        merged_params = _merge_parameters(merged_params, child.parameters)
        # body concatenation
        if child.body.strip():
            merged_body = (merged_body.rstrip() + "\n\n" + child.body).strip()
        if child.description:
            merged_desc = child.description
        if child.max_iterations:
            merged_max_iter = child.max_iterations

    leaf = chain[0]
    return Skill(
        name=leaf.name,
        description=merged_desc,
        body=merged_body,
        path=leaf.path,
        tools=merged_tools,
        max_iterations=merged_max_iter,
        use_count=leaf.use_count,
        last_used=leaf.last_used,
        parameters=merged_params,
        success_count=leaf.success_count,
        error_count=leaf.error_count,
        last_error_at=leaf.last_error_at,
        scope=leaf.scope,
        extends=None,  # the flattened skill no longer extends anything
    )


def _merge_parameters(
    base: list[dict], child: list[dict]
) -> list[dict]:
    out: list[dict] = []
    child_by_name = {p.get("name"): p for p in child if isinstance(p, dict)}
    overridden: set[str] = set()
    for p in base:
        name = p.get("name") if isinstance(p, dict) else None
        if name and name in child_by_name:
            out.append(child_by_name[name])
            overridden.add(name)
        else:
            out.append(p)
    for p in child:
        name = p.get("name") if isinstance(p, dict) else None
        if name and name not in overridden and name not in {
            p2.get("name") for p2 in base if isinstance(p2, dict)
        }:
            out.append(p)
    return out


# ---------- internals ----------


def _id_for_name(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
    return int(row["id"]) if row else None


def _row_to_record(row: sqlite3.Row) -> SkillRecord:
    return SkillRecord(
        id=int(row["id"]),
        name=row["name"],
        scope=row["scope"],
        base_skill_id=row["base_skill_id"],
        description=row["description"],
        file_path=row["file_path"],
    )


__all__ = [
    "SkillRecord",
    "SkillTelemetry",
    "get_skill",
    "get_skill_tool_refs",
    "inheritance_chain",
    "list_skills",
    "record_skill_use",
    "resolve_inheritance",
    "skill_telemetry",
    "upsert_skill",
]
