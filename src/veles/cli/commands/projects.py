"""`veles project` — global multi-project registry (M33)."""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

from veles.core.project import ProjectNotFound, load_project
from veles.core.project_registry import Registry as ProjectRegistry


def cmd_project(args: argparse.Namespace) -> int:
    """Multi-project registry CLI — list, add, remove, switch."""
    reg = ProjectRegistry.load()
    sub = args.project_command
    if sub == "list":
        entries = reg.list_entries()
        if not entries:
            print("(no projects registered)")
            return 0
        for e in entries:
            iso = (
                _dt.datetime.fromtimestamp(e.last_active_at, tz=_dt.UTC).isoformat()
                if e.last_active_at
                else "—"
            )
            print(f"{e.slug:<24} {iso:<28} {e.path}")
        return 0
    if sub == "add":
        path = Path(args.path).resolve()
        try:
            project = load_project(path)
        except ProjectNotFound as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        entry = reg.add(project, slug=args.slug)
        reg.save()
        print(f"added '{entry.slug}' -> {entry.path}")
        return 0
    if sub == "remove":
        try:
            removed = reg.remove(args.slug)
        except KeyError:
            print(f"error: no project named {args.slug!r} in registry", file=sys.stderr)
            return 2
        reg.save()
        print(f"removed '{removed.slug}' (was {removed.path})")
        return 0
    if sub == "switch":
        entry = reg.get(args.slug)
        if entry is None:
            print(f"error: no project named {args.slug!r} in registry", file=sys.stderr)
            return 2
        reg.touch(args.slug)
        reg.save()
        print(entry.path)
        return 0
    print(f"error: unknown project subcommand {sub!r}", file=sys.stderr)
    return 2
