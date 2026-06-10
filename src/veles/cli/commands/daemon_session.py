"""`veles daemon session {create,list,delete}` — named daemon sessions (M135).

Additive to the legacy single daemon (`veles daemon start/stop/...`): a project
can declare several named daemon sessions, each with its own settings, tracked
in the project's `runtime_sessions` table (`RuntimeSessionStore`, M134) with the
declarative settings written to `config.toml` `[daemon.<name>]` — the
source-of-truth a future `start --name <name>` (and a restart) re-reads.

Delete is **soft**: the row is hidden from listings but kept so its history can
still feed curator/dreaming, and the `[daemon.<name>]` config block is removed
so a re-create starts clean. This module never touches the legacy global-pid
daemon lifecycle.
"""

from __future__ import annotations

import argparse
import sys

from veles.core.project_config import load_project_config, save_project_config
from veles.core.runtime_sessions import RuntimeSessionExists, RuntimeSessionStore


def cmd_daemon_session(args: argparse.Namespace) -> int:
    verb = getattr(args, "daemon_session_command", None)
    if verb == "create":
        return _create(args)
    if verb == "list":
        return _list(args)
    if verb == "delete":
        return _delete(args)
    print(f"error: unknown daemon session subcommand: {verb!r}", file=sys.stderr)
    return 2


def _resolve_project():
    from veles.cli import _resolve_active_project

    project = _resolve_active_project(argparse.Namespace())
    if project is None:
        print(
            "error: no Veles project found here. Run `veles init` first.",
            file=sys.stderr,
        )
    return project


def _create(args: argparse.Namespace) -> int:
    project = _resolve_project()
    if project is None:
        return 2
    name = args.name.strip()
    if not name:
        print("error: session name must be non-empty.", file=sys.stderr)
        return 2

    store = RuntimeSessionStore(project.memory_db_path)
    try:
        # Port distinctness: two live daemon sessions can't share a bind port
        # (they'd collide on startup). Fail loud at declaration time.
        if args.port is not None:
            clash = next(
                (s for s in store.list(kind="daemon") if s.port == args.port), None
            )
            if clash is not None:
                print(
                    f"error: port {args.port} already used by daemon session "
                    f"{clash.name!r}.",
                    file=sys.stderr,
                )
                return 2
        try:
            rec = store.create(
                name,
                "daemon",
                model=args.model,
                provider=args.provider,
                host=args.host,
                port=args.port,
                mode=args.mode,
            )
        except RuntimeSessionExists:
            print(
                f"error: daemon session {name!r} already exists "
                f"(use `veles daemon session delete {name}` first).",
                file=sys.stderr,
            )
            return 2
    finally:
        store.close()

    # Persist the declarative settings to [daemon.<name>] (restart source-of-truth).
    cfg = load_project_config(project)
    daemon = cfg.setdefault("daemon", {})
    if not isinstance(daemon, dict):
        daemon = {}
        cfg["daemon"] = daemon
    block: dict = {}
    if args.host:
        block["host"] = args.host
    if args.port is not None:
        block["port"] = args.port
    if args.model:
        block["model"] = args.model
    if args.provider:
        block["provider"] = args.provider
    if args.mode:
        block["mode"] = args.mode
    daemon[name] = block
    save_project_config(project, cfg)

    print(f"created daemon session {name!r} ({rec.id})")
    print(f"  settings → [daemon.{name}] in {project.name}/.veles/config.toml")
    return 0


def _list(args: argparse.Namespace) -> int:
    project = _resolve_project()
    if project is None:
        return 2
    store = RuntimeSessionStore(project.memory_db_path)
    try:
        rows = store.list(kind="daemon", include_deleted=bool(getattr(args, "all", False)))
    finally:
        store.close()
    if not rows:
        print("(no named daemon sessions; create one with `veles daemon session create <name>`)")
        return 0
    name_w = max(len(r.name) for r in rows)
    for r in rows:
        flags = " (deleted)" if r.deleted else ""
        model = r.model or "—"
        provider = r.provider or "—"
        port = r.port if r.port is not None else "—"
        print(
            f"  {r.name:<{name_w}}  {r.status:<8}  {provider}:{model}  "
            f"port={port}{flags}"
        )
    return 0


def _delete(args: argparse.Namespace) -> int:
    project = _resolve_project()
    if project is None:
        return 2
    name = args.name.strip()
    store = RuntimeSessionStore(project.memory_db_path)
    try:
        rec = store.get_by_name(name, kind="daemon")
        if rec is None:
            print(f"error: no daemon session named {name!r}.", file=sys.stderr)
            return 1
        store.soft_delete(rec.id)
    finally:
        store.close()

    # Drop the [daemon.<name>] config block so a re-create starts clean.
    cfg = load_project_config(project)
    daemon = cfg.get("daemon")
    if isinstance(daemon, dict) and name in daemon and isinstance(daemon[name], dict):
        del daemon[name]
        save_project_config(project, cfg)

    print(f"deleted daemon session {name!r} (kept in DB for history)")
    return 0
