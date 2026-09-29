"""`veles module` — install / remove / list / show project plugins (M24)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from veles.core.critical_ops import confirm_critical
from veles.core.module_install import (
    ModuleInstallError,
    ModuleNotFoundError,
    derive_module_name,
    install_module_from_source,
    remove_module,
)
from veles.core.modules import ModuleHandle, discover_modules, discover_modules_in
from veles.core.project import Project
from veles.core.user_paths import user_modules_dir


def cmd_module(args: argparse.Namespace, project: Project) -> int:
    if args.module_command == "list":
        return _list(args, project)
    if args.module_command == "show":
        return _show(args, project)
    if args.module_command == "add":
        return _add(args, project)
    if args.module_command == "remove":
        return _remove(args, project)
    if args.module_command == "approve":
        return _approve(args, project)
    return 2


def _modules_dir(args: argparse.Namespace, project: Project) -> Path:
    return user_modules_dir() if getattr(args, "user", False) else project.modules_dir


def _list(args: argparse.Namespace, project: Project) -> int:
    rows: list[tuple[str, ModuleHandle]] = [
        ("user", h) for h in discover_modules_in(user_modules_dir())
    ]
    if not getattr(args, "user", False):
        rows += [("project", h) for h in discover_modules(project)]
    if not rows:
        print("(no modules)")
        return 0
    print(f"{'name':<20}  {'scope':<8}  {'version':<10}  description")
    for scope, h in rows:
        version = h.manifest.version or "—"
        desc = h.manifest.description
        if len(desc) > 60:
            desc = desc[:57] + "..."
        print(f"{h.name:<20}  {scope:<8}  {version:<10}  {desc}")
    return 0


def _show(args: argparse.Namespace, project: Project) -> int:
    modules_dir = _modules_dir(args, project)
    for h in discover_modules_in(modules_dir):
        if h.name == args.name:
            print((h.dir / "module.toml").read_text(encoding="utf-8"))
            return 0
    print(f"error: module {args.name!r} not found in {modules_dir}", file=sys.stderr)
    return 1


def _add(args: argparse.Namespace, project: Project) -> int:
    modules_dir = _modules_dir(args, project)
    target_name = args.name or derive_module_name(args.source)
    target = modules_dir / target_name
    summary = (
        f"Source: {args.source}\n"
        f"Target: {target}\n"
        "Installing a module wires hook callbacks that run on every agent "
        "turn / tool dispatch. Review the source before confirming."
    )
    if not confirm_critical(f"install module from {args.source}", summary):
        print("<aborted>", file=sys.stderr)
        return 1
    from veles.core.registry.gate import approve_module

    try:
        handle = install_module_from_source(
            args.source, modules_dir=modules_dir, name_override=args.name
        )
        project_root = None if getattr(args, "user", False) else project.root
        approve_module(handle.dir, name=handle.name, project_root=project_root)
    except (ModuleInstallError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"<installed module {handle.name!r} at {handle.dir}>", file=sys.stderr)
    return 0


def _remove(args: argparse.Namespace, project: Project) -> int:
    from veles.cli._console import confirm

    modules_dir = _modules_dir(args, project)
    target = modules_dir / args.name
    if not args.yes and not confirm(f"Remove module {args.name!r} ({target})? [y/N]"):
        print("<aborted>", file=sys.stderr)
        return 1
    try:
        remove_module(args.name, modules_dir=modules_dir)
    except ModuleNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    from veles.core.registry.records import drop_record

    drop_record(str(target.resolve()))
    print(f"<removed module {args.name!r}>", file=sys.stderr)
    return 0


def _approve(args: argparse.Namespace, project: Project) -> int:
    from veles.core.registry.gate import approve_module
    from veles.core.registry.hashing import tree_sha256

    modules_dir = _modules_dir(args, project)
    handle = next((h for h in discover_modules_in(modules_dir) if h.name == args.name), None)
    if handle is None:
        print(f"error: module {args.name!r} not found in {modules_dir}", file=sys.stderr)
        return 1
    try:
        digest = tree_sha256(handle.dir)
        summary = (
            f"Module: {handle.dir}\nFiles hash: {digest[:12]}\n"
            "Its code will run on every agent turn. Review it first."
        )
        if not confirm_critical(f"approve module {args.name}", summary):
            print("<aborted>", file=sys.stderr)
            return 1
        project_root = None if getattr(args, "user", False) else project.root
        approve_module(
            handle.dir, name=handle.name, project_root=project_root, expected_sha256=digest
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"<approved module {args.name!r}>", file=sys.stderr)
    return 0
