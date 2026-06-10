"""`veles export` / `veles import` — bundle pack/unpack (M45)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from veles.core.export import (
    ExportError,
    export_full,
    export_template,
    import_bundle,
)
from veles.core.export import (
    ImportError as VelesImportError,
)
from veles.core.project import Project


def cmd_export(args: argparse.Namespace, project: Project) -> int:
    bundle_path = Path(args.path).expanduser()
    try:
        if args.export_command == "full":
            export_full(project, bundle_path)
        elif args.export_command == "template":
            export_template(project, bundle_path)
        else:
            print(
                f"error: unknown export subcommand {args.export_command!r}",
                file=sys.stderr,
            )
            return 2
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"<exported {project.name!r} ({args.export_command}) to {bundle_path}>",
        file=sys.stderr,
    )
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    bundle_path = Path(args.path).expanduser()
    target = Path(args.into).expanduser() if args.into else Path.cwd()
    try:
        project = import_bundle(bundle_path, target, force=args.force)
    except VelesImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"<imported {project.name!r} into {project.root}>",
        file=sys.stderr,
    )
    return 0
