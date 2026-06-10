"""`veles module` — install / remove / list / show project plugins (M24)."""

from __future__ import annotations

import argparse
import sys

from veles.core.critical_ops import confirm_critical
from veles.core.module_install import (
    ModuleInstallError,
    ModuleNotFoundError,
    install_module_from_source,
    remove_module,
)
from veles.core.module_install import _derive_name as _derive_module_name
from veles.core.modules import discover_modules
from veles.core.project import Project


def cmd_module(args: argparse.Namespace, project: Project) -> int:
    if args.module_command == "list":
        return _list(project)
    if args.module_command == "show":
        return _show(project, args.name)
    if args.module_command == "add":
        return _add(args, project)
    if args.module_command == "remove":
        return _remove(args, project)
    return 2


def _list(project: Project) -> int:
    handles = discover_modules(project)
    if not handles:
        print("(no modules)")
        return 0
    print(f"{'name':<20}  {'version':<10}  description")
    for h in handles:
        version = h.manifest.version or "—"
        desc = h.manifest.description
        if len(desc) > 60:
            desc = desc[:57] + "..."
        print(f"{h.name:<20}  {version:<10}  {desc}")
    return 0


def _show(project: Project, name: str) -> int:
    for h in discover_modules(project):
        if h.name == name:
            print((h.dir / "module.toml").read_text(encoding="utf-8"))
            return 0
    print(f"error: module {name!r} not found in {project.modules_dir}", file=sys.stderr)
    return 1


def _add(args: argparse.Namespace, project: Project) -> int:
    target_name = args.name or _derive_module_name(args.source)
    target = project.modules_dir / target_name
    summary = (
        f"Source: {args.source}\n"
        f"Target: {target}\n"
        "Installing a module wires hook callbacks that run on every agent "
        "turn / tool dispatch. Review the source before confirming."
    )
    if not confirm_critical(f"install module from {args.source}", summary):
        print("<aborted>", file=sys.stderr)
        return 1
    try:
        handle = install_module_from_source(args.source, project=project, name_override=args.name)
    except ModuleInstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"<installed module {handle.name!r} at {handle.dir}>", file=sys.stderr)
    return 0


def _remove(args: argparse.Namespace, project: Project) -> int:
    from veles.cli import _confirm  # back-import (deferred)

    target = project.modules_dir / args.name
    if not args.yes and not _confirm(f"Remove module {args.name!r} ({target})? [y/N]"):
        print("<aborted>", file=sys.stderr)
        return 1
    try:
        remove_module(args.name, project=project)
    except ModuleNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"<removed module {args.name!r}>", file=sys.stderr)
    return 0
