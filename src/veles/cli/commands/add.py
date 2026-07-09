"""`veles add` — read a source and route its topics into the wiki (M85, M203).

The canonical (and only) name — the `veles ingest` alias was removed in
M117c-removal. Delegates to the shared runner in `cli.commands.ingest`."""

from __future__ import annotations

import argparse

from veles.cli.commands.ingest import _run_batch_ingest_cli, _run_ingest_cli
from veles.core.project import Project


def cmd_add(args: argparse.Namespace, project: Project) -> int:
    if getattr(args, "recursive", False):
        return _run_batch_ingest_cli(args, project, source=args.source)
    return _run_ingest_cli(args, project, source=args.source)
