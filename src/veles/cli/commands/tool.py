"""`veles tool {list,show,promote}` command bodies (M120.5).

Each handler takes `(args, project)` and returns an int exit code in
the conventional pattern.

**What `list`/`show` report (M251).** The live `Registry` — the same
builtin + file-based toolset the agent is handed — with telemetry from
`memory.db` overlaid where it exists. They used to report the `tools`
table alone, which answered a different question than the one they get
asked: `tool list` is the first thing you run to check whether the agent
can see its tools, and it replied `no tools catalogued yet` in exactly the
state being checked. Two reasons it was empty — builtins are never
catalogued by design, and `cli/_runtime.py` called `load_into_registry`
with no `conn`, so file-based tools were not catalogued either, despite
this docstring having claimed they were since M120.5.

Deliberately NOT covered here, because each would mean paying a real cost
for a listing: skills (`veles skill list`) and MCP servers, which would
have to be connected to enumerate (`veles mcp list`).

Side-effects:
- `list` / `show` are read-only apart from the catalogue sync that
  `load_into_registry(conn=…)` performs for file-based tools.
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
from dataclasses import dataclass
from pathlib import Path

from veles.core.memory.store import local_connection
from veles.core.project import Project
from veles.core.tools.persistence import (
    ToolTelemetry,
    get_tool,
    telemetry,
    telemetry_batch,
)
from veles.core.tools.registry import Registry
from veles.core.user_paths import user_home


@dataclass(frozen=True, slots=True)
class LiveTool:
    """One tool as the agent would see it, plus where it came from."""

    name: str
    scope: str  # builtin | project | user
    origin: str  # builtin | agent-generated | manual
    description: str


def _live_tools(project: Project, conn) -> tuple[list[LiveTool], tuple[Path, ...]]:
    """Build the agent's builtin + file-based toolset and report it.

    Mirrors `cli/_runtime.py::_load_skills` for the parts that need no
    provider: the layout's content engines decide which builtins exist, then
    file-based project/user tools load on top.

    **The registry handed to the loader must be a copy.** `load_into_registry`
    mutates it — `loader.py` pops a builtin that a project tool shadows — and
    the builtin registry is a module-level singleton. Passing it directly would
    strip builtins from the live process, so `veles tool list` typed inside a
    REPL session would change the agent's own toolset.
    """
    from veles.core.layout.engines import wiki_enabled
    from veles.core.tools import registry as builtin_registry
    from veles.core.tools.loader import load_into_registry
    from veles.core.tools.toolsets import TOOLSETS

    # M163: wiki tools exist only when the layout pack enables the engine —
    # importing the module is what registers them, so the gate is the import.
    if wiki_enabled(project):
        import veles.modules.wiki.tools
    import veles.modules.agentops.tools  # noqa: F401

    gated: set[str] = set() if wiki_enabled(project) else set(TOOLSETS.get("engine-wiki", ()))
    live: Registry = builtin_registry.subset(
        [n for n in builtin_registry.list_names() if n not in gated]
    )
    scopes: dict[str, tuple[str, str]] = dict.fromkeys(live.list_names(), ("builtin", "builtin"))

    report = load_into_registry(
        live,
        project_tools_dir=project.state_dir / "tools",
        user_tools_dir=user_home() / "tools",
        # M251: the sync `cli/_runtime.py` never performed, so a file-based
        # tool finally gets a catalogue row (and therefore telemetry).
        conn=conn,
    )
    for lt in report.loaded:
        scopes[lt.entry.name] = (lt.scope, lt.origin)

    tools = [
        LiveTool(
            name=name,
            scope=scopes[name][0],
            origin=scopes[name][1],
            description=live.get(name).description,
        )
        for name in sorted(live.list_names())
    ]
    return tools, report.unapproved


def cmd_tool(args: argparse.Namespace, project: Project) -> int:
    sub = args.tool_command
    if sub == "list":
        return _cmd_list(args, project)
    if sub == "show":
        return _cmd_show(args, project)
    if sub == "promote":
        return _cmd_promote(args, project)
    if sub == "approve":
        return _cmd_approve(args, project)
    print(f"unknown tool subcommand: {sub!r}", file=sys.stderr)
    return 2


# ---------- approve (M199) ----------


def _list_tool_py(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix == ".py" and not p.name.startswith("_")
    )


def _cmd_approve(args: argparse.Namespace, project: Project) -> int:
    """Review and human-approve self-authored tool files so the loader will
    execute them (M199). Until approved, `.veles/tools/*.py` are skipped — their
    module-level code never runs. Approval records the file's current SHA-256 in
    `~/.veles/tool-approvals.json` (outside the agent's write sandbox)."""
    from veles.core.tools.approvals import approve, is_approved

    candidates = _list_tool_py(project.state_dir / "tools") + _list_tool_py(user_home() / "tools")
    unapproved = [p for p in candidates if not is_approved(p)]
    if not unapproved:
        print("all self-authored tool files are already approved.")
        return 0

    if getattr(args, "all", False):
        targets = unapproved
    elif getattr(args, "name", None):
        targets = [p for p in unapproved if p.stem == args.name]
        if not targets:
            print(f"no unapproved tool file named {args.name!r}.", file=sys.stderr)
            return 1
    else:
        print("unapproved tool files (pass a name or --all to approve):")
        for p in unapproved:
            print(f"  {p.stem}  ({p})")
        return 0

    for f in targets:
        print(f"\n===== {f} =====")
        print(f.read_text())
        print("=" * (len(str(f)) + 12))
        from veles.cli import _confirm

        if not getattr(args, "yes", False) and not _confirm(
            f"Approve '{f.name}' to execute its code at load? [y/N]"
        ):
            print(f"skipped {f.name}")
            continue
        sha = approve(f)
        print(f"approved {f.name} ({sha[:12]}…)")
    return 0


# ---------- list ----------


def _cmd_list(args: argparse.Namespace, project: Project) -> int:
    del args
    with local_connection(project) as conn:
        records, unapproved = _live_tools(project, conn)
        conn.commit()
        tele = telemetry_batch(conn, [r.name for r in records])
    if not records:
        print("no tools available — the builtin registry is empty, which is a bug.")
        return 0
    # `name  scope  origin  uses  success%  last_used` — column widths
    # tuned to the typical 20-char tool name + 9-char scope max.
    print(_format_table(records, tele))
    print(
        f"\n{len(records)} tools visible to the agent here. "
        "Skills: `veles skill list`. MCP servers: `veles mcp list`."
    )
    if unapproved:
        # M199 skips an unapproved file's import entirely, so the agent never
        # sees the tool OR a refusal. `tool list` is where you come looking.
        names = ", ".join(sorted(p.stem for p in unapproved))
        print(
            f"{len(unapproved)} self-authored tool file(s) NOT loaded (unapproved): {names} — "
            "run `veles tool approve <name>` (or --all) to enable them.",
            file=sys.stderr,
        )
    return 0


def _format_table(records: list[LiveTool], tele: dict[str, ToolTelemetry]) -> str:
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
    """Identity from the live registry, telemetry + inheritance from the
    catalogue (M251). Looking identity up in the catalogue alone made `show`
    tell the same lie as `list`: a working builtin has no row there, so
    `veles tool show read_file` answered "no tool named 'read_file'"."""
    name = args.name
    with local_connection(project) as conn:
        live, _ = _live_tools(project, conn)
        conn.commit()
        entry = next((t for t in live if t.name == name), None)
        if entry is None:
            print(f"no tool named {name!r} available in this project.", file=sys.stderr)
            return 1
        t = telemetry(conn, name)
        rec = get_tool(conn, name)
        print(f"name:        {entry.name}")
        print(f"scope:       {entry.scope}")
        print(f"origin:      {entry.origin}")
        if entry.description:
            print(f"description: {entry.description}")
        if rec is not None and rec.base_tool_id is not None:
            base = conn.execute(
                "SELECT name FROM tools WHERE id = ?", (rec.base_tool_id,)
            ).fetchone()
            if base:
                print(f"inherits:    {base['name']}")
        if rec is not None and rec.manifest_json:
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
            f"{dst} already exists. Refusing to overwrite. Move it aside or delete it first.",
            file=sys.stderr,
        )
        return 1

    from veles.cli import _confirm

    if not args.yes and not _confirm(
        f"Move {src} → {dst} (tool '{name}' becomes user-global)? [y/N]"
    ):
        print("aborted.")
        return 0

    shutil.move(str(src), str(dst))
    # M199: promote is a human action on an already-reviewed tool — carry the
    # approval to the new path so the user-level loader still runs it (the
    # approval store is keyed by absolute path, which the move changed).
    from veles.core.tools.approvals import approve

    approve(dst)

    # Update the catalogue. The next load_into_registry call will see
    # the file at the new path and refresh manifest_json; this
    # in-place scope flip is just for users who inspect right now.
    with local_connection(project) as conn:
        # M264c: the catalogue write is committed now. It never was — the store
        # was opened, written to, and dropped without a commit or a close, so
        # the scope flip this prints about was rolled back on the way out.
        conn.execute(
            "UPDATE tools SET scope = 'user', origin = 'manual', updated_at = ? WHERE name = ?",
            (_now(), name),
        )
        conn.commit()
    print(f"promoted {name}: {src} → {dst}")
    return 0


def _now() -> float:
    import time as _time

    return _time.time()
