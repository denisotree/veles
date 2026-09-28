"""`veles registry` — connect registries, search, install, upgrade, verify, publish."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from veles.core.project import Project
from veles.core.registry.catalog import ResolveError, resolve, search
from veles.core.registry.config import (
    RegistryConfigError,
    add_source,
    cache_dir,
    get_source,
    list_sources,
    remove_source,
)
from veles.core.registry.install import (
    InstallError,
    install,
    installed_records,
    pip_hint,
    uninstall,
)
from veles.core.registry.maintenance import upgrade, verify
from veles.core.registry.repo import (
    RegistryRepoError,
    ensure_cache,
    fetched_at,
    head_commit,
    update,
)
from veles.core.registry.template import (
    TemplateError,
    init_registry,
    scaffold_extension,
    vendor_extension,
)
from veles.core.registry.validate import validate_registry

_ERRORS = (RegistryConfigError, RegistryRepoError, ResolveError, InstallError, TemplateError)


def cmd_registry(args: argparse.Namespace, project: Project | None) -> int:
    handler = _HANDLERS[args.registry_command]
    try:
        return handler(args, project)
    except _ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _add(args: argparse.Namespace, project: Project | None) -> int:
    source = add_source(args.url, name=args.name, ref=args.ref)
    ensure_cache(source)
    print(f"<connected registry {source.name!r}: {source.url}>", file=sys.stderr)
    return 0


def _remove(args: argparse.Namespace, project: Project | None) -> int:
    remove_source(args.name)
    print(f"<disconnected registry {args.name!r}>", file=sys.stderr)
    return 0


def _list(args: argparse.Namespace, project: Project | None) -> int:
    sources = list_sources()
    if not sources:
        print("(no registries connected)")
    for s in sources:
        cache = cache_dir(s.name)
        if (cache / ".git").is_dir():
            age = time.strftime("%Y-%m-%d %H:%M", time.localtime(fetched_at(cache)))
            state = f"{head_commit(cache)[:10]} fetched {age}"
        else:
            state = "not fetched"
        print(f"{s.name:<12} {s.url}  ref={s.ref or 'HEAD'}  [{state}]")
    return 0


def _update(args: argparse.Namespace, project: Project | None) -> int:
    sources = [get_source(args.name)] if args.name else list_sources()
    rc = 0
    for s in sources:
        try:
            print(f"{s.name}: {update(s)[:10]}")
        except RegistryRepoError as exc:
            print(f"{s.name}: error: {exc}", file=sys.stderr)
            rc = 1
    return rc


def _search(args: argparse.Namespace, project: Project | None) -> int:
    found, warnings = search(args.query, kind=args.kind, registry=args.registry)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if args.json:
        rows = [
            {"ref": f.ref, **{k: v for k, v in asdict(f.ext).items() if k not in ("dir", "source")}}
            for f in found
        ]
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
        return 0
    if not found:
        print("(nothing found)", file=sys.stderr)
    for f in found:
        flag = f"  [YANKED: {f.ext.yanked}]" if f.ext.yanked else ""
        print(f"{f.ref}  {f.ext.version}  {f.ext.kind}{flag}")
        print(f"  {f.ext.description}")
    return 0


def _install(args: argparse.Namespace, project: Project | None) -> int:
    found = resolve(args.spec)
    rec = install(found, project=project, user_scope=args.user, force=args.force)
    print(f"<installed {found.ref} {rec.version} at {rec.path}>", file=sys.stderr)
    hint = pip_hint(found)
    if hint:
        print(hint, file=sys.stderr)
    return 0


def _upgrade(args: argparse.Namespace, project: Project | None) -> int:
    names = (
        [args.name]
        if args.name
        else sorted({r.name for r in installed_records(project) if r.registry is not None})
    )
    for name in names:
        rec = upgrade(name, project=project)
        print(f"{name}: " + (f"upgraded to {rec.version}" if rec else "up to date"))
    return 0


def _uninstall(args: argparse.Namespace, project: Project | None) -> int:
    rec = uninstall(args.name, project=project)
    print(f"<removed {rec.kind} {rec.name!r}>", file=sys.stderr)
    return 0


def _verify(args: argparse.Namespace, project: Project | None) -> int:
    issues = verify(project)
    if not issues:
        print("all installed extensions match their records")
        return 0
    for i in issues:
        print(f"{i.problem:<10} {i.record.name}  {i.detail}")
    return 1 if any(i.problem in ("missing", "modified") for i in issues) else 0


def _validate(args: argparse.Namespace, project: Project | None) -> int:
    report = validate_registry(Path(args.path).resolve(), base=args.base, run_code=args.run_code)
    text = report.to_markdown()
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)
    return 0 if report.ok else 1


def _scaffold(args: argparse.Namespace, project: Project | None) -> int:
    dest = scaffold_extension(Path(args.root).resolve(), args.kind, args.name, group=args.group)
    print(f"<created {dest}>", file=sys.stderr)
    return 0


def _init(args: argparse.Namespace, project: Project | None) -> int:
    dest = init_registry(Path(args.dir).resolve(), name=args.name, ci=args.ci, public=args.public)
    print(f"<registry {args.name!r} created at {dest} — see its README.md>", file=sys.stderr)
    return 0


def _vendor(args: argparse.Namespace, project: Project | None) -> int:
    dest = vendor_extension(resolve(args.spec), Path(args.into).resolve(), group=args.group)
    print(f"<vendored into {dest} — commit it and open a PR in that registry>", file=sys.stderr)
    return 0


_HANDLERS = {
    "add": _add,
    "remove": _remove,
    "list": _list,
    "update": _update,
    "search": _search,
    "install": _install,
    "upgrade": _upgrade,
    "uninstall": _uninstall,
    "verify": _verify,
    "validate": _validate,
    "scaffold": _scaffold,
    "init": _init,
    "vendor": _vendor,
}
