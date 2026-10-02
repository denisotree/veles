"""`veles module` — install / remove / list / show project plugins (M24)."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from veles.core.critical_ops import confirm_critical
from veles.core.module_install import (
    ModuleInstallError,
    ModuleNotFoundError,
    install_module_from_source,
    remove_module,
)
from veles.core.modules import ModuleHandle, discover_modules, discover_modules_in
from veles.core.project import Project
from veles.core.text import shown
from veles.core.user_paths import user_home, user_modules_dir


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


def _in_own_scope(args: argparse.Namespace, project: Project, module_dir: Path) -> bool:
    """`module_dir` really sits in this scope's modules dir: only the scope root
    (`~/.veles`, the project root) is resolved, so a linked `.veles` or `modules` dir
    reaching into another project is caught. Prints the error when it is not."""
    base = user_home() if getattr(args, "user", False) else project.root
    own = base.resolve() / _modules_dir(args, project).relative_to(base)
    if module_dir.resolve().parent == own:
        return True
    print(
        f"error: {shown(module_dir)} resolves outside {shown(own)} through a symlink — "
        "refusing to act on another scope's module",
        file=sys.stderr,
    )
    return False


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
    project_names = {h.name for scope, h in rows if scope == "project"}
    seen: set[tuple[str, str]] = set()
    for scope, h in rows:
        version = h.manifest.version or "—"
        desc = shown(h.manifest.description)
        if len(desc) > 60:
            desc = desc[:57] + "..."
        # The same rules the loader applies (`core/module_loading.py`).
        if (scope, h.name) in seen:
            desc = f"[duplicate name — ignored: {shown(h.dir)}] {desc}"
        elif scope == "user" and h.name in project_names:
            desc = f"[shadowed by the project's] {desc}"
        seen.add((scope, h.name))
        print(f"{h.name:<20}  {scope:<8}  {shown(version):<10}  {desc}")
    return 0


def _find(modules_dir: Path, name: str, *, by_dir: bool = False) -> Path | None:
    """The dir of the one module in `modules_dir` whose manifest declares `name` (what
    `list` shows). Two dirs declaring it is ambiguous — refused, with the dirs listed, so
    a verb never acts on whichever dir happens to sort first. `by_dir` falls back to the
    directory name when no manifest matches (to remove a module whose manifest is broken)."""
    matches = [h.dir for h in discover_modules_in(modules_dir) if h.name == name]
    if len(matches) > 1:
        dirs = "\n".join(f"  {shown(d)}" for d in matches)
        print(
            f"error: {len(matches)} modules in {shown(modules_dir)} declare name {name!r}:\n"
            f"{dirs}\nreview them and remove the one you did not install",
            file=sys.stderr,
        )
        return None
    if matches:
        return matches[0]
    if by_dir and (modules_dir / name).is_dir():
        return modules_dir / name
    print(f"error: module {name!r} not found in {shown(modules_dir)}", file=sys.stderr)
    return None


def _show(args: argparse.Namespace, project: Project) -> int:
    module_dir = _find(_modules_dir(args, project), args.name)
    if module_dir is None:
        return 1
    text = (module_dir / "module.toml").read_text(encoding="utf-8")
    print("\n".join(shown(line) for line in text.splitlines()))
    return 0


def _add(args: argparse.Namespace, project: Project) -> int:
    """Copy/clone the source in first (unapproved files never load), show the user the
    hash of exactly those files, and approve that hash only — files swapped while the
    user was confirming are refused. A decline or failure removes the copy."""
    from veles.core.registry.gate import approve_module
    from veles.core.registry.hashing import tree_sha256

    try:
        handle = install_module_from_source(
            args.source, modules_dir=_modules_dir(args, project), name_override=args.name
        )
    except (ModuleInstallError, OSError, ValueError) as exc:
        print(f"error: {shown(exc)}", file=sys.stderr)
        return 1
    try:
        digest = tree_sha256(handle.dir)
        summary = (
            f"Source: {shown(args.source)}\nInstalled at: {shown(handle.dir)}\n"
            f"Files hash: {digest[:12]}\n"
            "Installing a module wires hook callbacks that run on every agent "
            "turn / tool dispatch. Review the files before confirming."
        )
        if not confirm_critical(f"install module from {shown(args.source)}", summary):
            shutil.rmtree(handle.dir, ignore_errors=True)
            print("<aborted>", file=sys.stderr)
            return 1
        project_root = None if getattr(args, "user", False) else project.root
        approve_module(
            handle.dir, name=handle.name, project_root=project_root, expected_sha256=digest
        )
    except (OSError, ValueError) as exc:
        shutil.rmtree(handle.dir, ignore_errors=True)
        print(f"error: {shown(exc)}", file=sys.stderr)
        return 1
    except BaseException:  # Ctrl-C at the confirmation: leave no unapproved copy behind
        shutil.rmtree(handle.dir, ignore_errors=True)
        raise
    print(f"<installed module {handle.name!r} at {shown(handle.dir)}>", file=sys.stderr)
    return 0


def _remove(args: argparse.Namespace, project: Project) -> int:
    from veles.cli._console import confirm

    modules_dir = _modules_dir(args, project)
    target = _find(modules_dir, args.name, by_dir=True)
    if target is None or not _in_own_scope(args, project, target):
        return 1
    if not args.yes and not confirm(f"Remove module {args.name!r} ({shown(target)})? [y/N]"):
        print("<aborted>", file=sys.stderr)
        return 1
    try:
        remove_module(target.name, modules_dir=modules_dir)
    except (ModuleNotFoundError, ModuleInstallError) as exc:
        print(f"error: {shown(exc)}", file=sys.stderr)
        return 1
    from veles.core.registry.records import drop_record

    drop_record(str(target.resolve()))
    print(f"<removed module {args.name!r}>", file=sys.stderr)
    return 0


def _approve(args: argparse.Namespace, project: Project) -> int:
    from veles.core.registry.gate import approve_module
    from veles.core.registry.hashing import tree_sha256

    module_dir = _find(_modules_dir(args, project), args.name)
    if module_dir is None or not _in_own_scope(args, project, module_dir):
        return 1
    try:
        digest = tree_sha256(module_dir)
        summary = (
            f"Module: {shown(module_dir)}\nFiles hash: {digest[:12]}\n"
            "Its code will run on every agent turn. Review it first."
        )
        if not confirm_critical(f"approve module {args.name}", summary):
            print("<aborted>", file=sys.stderr)
            return 1
        project_root = None if getattr(args, "user", False) else project.root
        approve_module(
            module_dir, name=args.name, project_root=project_root, expected_sha256=digest
        )
    except (OSError, ValueError) as exc:
        print(f"error: {shown(exc)}", file=sys.stderr)
        return 1
    print(f"<approved module {args.name!r}>", file=sys.stderr)
    return 0
