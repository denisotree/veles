"""`veles add` — read a source and write a wiki page via agent (M85).

The canonical name; `veles ingest` remains as a deprecated alias and
both delegate to the shared runner in `cli.commands.ingest`."""

from __future__ import annotations

import argparse

from veles.cli.commands.ingest import _run_batch_ingest_cli, _run_ingest_cli
from veles.core.project import Project


def cmd_add(args: argparse.Namespace, project: Project) -> int:
    if getattr(args, "recursive", False):
        return _run_batch_ingest_cli(args, project, source=args.source)
    return _run_ingest_cli(args, project, source=args.source)
