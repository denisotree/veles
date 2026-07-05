"""`veles doctor` — health-check across user-global + active project (Tier δ, M59)."""

from __future__ import annotations

import argparse

from veles.core.doctor import repair_memory_fts, run_all
from veles.core.project import Project


def cmd_doctor(args: argparse.Namespace, project: Project | None) -> int:
    """Run every check and print the report.

    Returns 0 when no `error`-level result fired (warnings are tolerated by
    default — they're advisory). Pass `--strict` to treat warnings as
    failing too; useful for CI gating after a release. Pass `--fix` to run
    safe repairs (rebuild a broken memory recall index) before checking.
    """
    if getattr(args, "fix", False) and repair_memory_fts(project):
        print("fixed: rebuilt the memory recall (FTS) index")
    report = run_all(project)
    if getattr(args, "json", False):
        print(report.to_json())
    else:
        print(report.to_text())
    if report.has_errors:
        return 1
    if getattr(args, "strict", False) and report.has_warnings:
        return 1
    return 0
