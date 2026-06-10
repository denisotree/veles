"""`veles tool {list,show,promote}` command bodies (M120.5).

Each handler takes `(args, project)` and returns an int exit code in
the conventional pattern. The persistent catalogue (`tools` table in
`memory.db`) is the source of truth — we don't re-scan disk on every
invocation, because the daemon / CLI runtime already syncs file-based
tools at startup via `core/tools/loader.py`.

Side-effects:
- `list` / `show` are read-only.
- `promote` moves a `.py` file from `<project>/.veles/tools/` to
  `~/.veles/tools/`. The catalogue row's `scope` is rewritten in-place
  so the next daemon turn or CLI invocation sees the user-level tool
  immediately.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import shutil
import sys

from veles.core.memory import SessionStore
from veles.core.project import Project
from veles.core.tools.persistence import (
    ToolRecord,
    ToolTelemetry,
    get_tool,
    list_tools,
    telemetry,
    telemetry_batch,
)
from veles.core.user_paths import user_home


def cmd_tool(args: argparse.Namespace, project: Project) -> int:
    sub = args.tool_command
    if sub == "list":
        return _cmd_list(args, project)
    if sub == "show":
        return _cmd_show(args, project)
    if sub == "promote":
        return _cmd_promote(args, project)
    print(f"unknown tool subcommand: {sub!r}", file=sys.stderr)
    return 2


# ---------- list ----------


def _cmd_list(args: argparse.Namespace, project: Project) -> int:
    del args
    store = SessionStore(project.memory_db_path)
    conn = store._conn
    records = list_tools(conn)
    if not records:
        print("no tools catalogued yet.")
        return 0
    names = [r.name for r in records]
    tele = telemetry_batch(conn, names)
    # `name  scope  origin  uses  success%  last_used` — column widths
    # tuned to the typical 20-char tool name + 9-char scope max.
    print(_format_table(records, tele))
    return 0


def _format_table(
    records: list[ToolRecord], tele: dict[str, ToolTelemetry]
) -> str:
    name_w = max(len("name"), max(len(r.name) for r in records))
    scope_w = max(len("scope"), max(len(r.scope) for r in records))
    origin_w = max(len("origin"), max(len(r.origin) for r in records))
    header = (
        f"{'name':<{name_w}}  "
        f"{'scope':<{scope_w}}  "
        f"{'origin':<{origin_w}}  "
        f"{'uses':>5}  "
        f"{'ok%':>5}  "
        f"last_used"
    )
    rows = [header, "-" * len(header)]
    for r in records:
        t = tele[r.name]
        last = _fmt_ts(t.last_used_at) if t.last_used_at else "—"
        rate = f"{t.success_rate * 100:.0f}%" if t.use_count else "—"
        rows.append(
            f"{r.name:<{name_w}}  "
            f"{r.scope:<{scope_w}}  "
            f"{r.origin:<{origin_w}}  "
            f"{t.use_count:>5}  "
            f"{rate:>5}  "
            f"{last}"
        )
    return "\n".join(rows)


def _fmt_ts(ts: float) -> str:
    return _dt.datetime.fromtimestamp(ts, tz=_dt.UTC).strftime("%Y-%m-%d %H:%M")


# ---------- show ----------


def _cmd_show(args: argparse.Namespace, project: Project) -> int:
    name = args.name
    store = SessionStore(project.memory_db_path)
    conn = store._conn
    rec = get_tool(conn, name)
    if rec is None:
        print(f"no tool named {name!r} in catalogue.", file=sys.stderr)
        return 1
    t = telemetry(conn, name)
    print(f"name:        {rec.name}")
    print(f"scope:       {rec.scope}")
    print(f"origin:      {rec.origin}")
    if rec.description:
        print(f"description: {rec.description}")
    if rec.base_tool_id is not None:
        base = conn.execute(
            "SELECT name FROM tools WHERE id = ?", (rec.base_tool_id,)
        ).fetchone()
        if base:
            print(f"inherits:    {base['name']}")
    if rec.manifest_json:
        print(f"manifest:    {rec.manifest_json}")
    print("---")
    print(f"use_count:     {t.use_count}")
    print(f"success_count: {t.success_count}")
    print(f"error_count:   {t.error_count}")
    if t.use_count:
        print(f"success_rate:  {t.success_rate * 100:.1f}%")
    if t.last_used_at:
        print(f"last_used_at:  {_fmt_ts(t.last_used_at)}")
    if t.avg_latency_ms is not None:
        print(f"avg_latency:   {t.avg_latency_ms:.0f}ms")
    return 0


# ---------- promote ----------


def _cmd_promote(args: argparse.Namespace, project: Project) -> int:
    """Move <project>/.veles/tools/<name>.py → ~/.veles/tools/<name>.py
    and flip the catalogue row's scope to "user". The corresponding
    project-level row is dropped — exactly one row per name across the
    whole catalogue, mirroring how the loader resolves shadowing.
    """
    name = args.name
    project_tools_dir = project.state_dir / "tools"
    src = project_tools_dir / f"{name}.py"
    if not src.is_file():
        print(
            f"no project-level tool file at {src}; promote target must "
            "exist as a .py under <project>/.veles/tools/.",
            file=sys.stderr,
        )
        return 1

    user_tools_dir = user_home() / "tools"
    user_tools_dir.mkdir(parents=True, exist_ok=True)
    dst = user_tools_dir / f"{name}.py"
    if dst.exists():
        print(
            f"{dst} already exists. Refusing to overwrite. Move it "
            "aside or delete it first.",
            file=sys.stderr,
        )
        return 1

    if not args.yes:
        prompt = (
            f"Move {src} → {dst} (tool '{name}' becomes user-global)? [y/N] "
        )
        try:
            response = input(prompt).strip().lower()
        except EOFError:
            response = ""
        if response not in {"y", "yes"}:
            print("aborted.")
            return 0

    shutil.move(str(src), str(dst))

    # Update the catalogue. The next load_into_registry call will see
    # the file at the new path and refresh manifest_json; this
    # in-place scope flip is just for users who inspect right now.
    store = SessionStore(project.memory_db_path)
    store._conn.execute(
        "UPDATE tools SET scope = 'user', origin = 'manual', updated_at = ?"
        " WHERE name = ?",
        (_now(), name),
    )
    print(f"promoted {name}: {src} → {dst}")
    return 0


def _now() -> float:
    import time as _time

    return _time.time()
