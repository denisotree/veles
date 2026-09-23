"""M118b: Scanner triggers for the project_tree cache.

The `project_tree.Scanner` from M118 is mtime-incremental: a re-scan
on an unchanged tree is cheap (one stat per entry, zero writes). That
makes "scan on every `veles run` boot" affordable — we don't need a
filesystem watcher, just a thin call site here.

`scan_project_tree(project)` is the public seam. Its one caller today is
`init_project`, which runs a full scan right after the skeleton lands so the
cache isn't empty on the first `veles run`. The per-run re-scan this module
was written for is not wired: the agent-build path that called it is gone.

Errors are caught and logged — a partially-readable tree shouldn't
abort the agent's startup. The Scanner itself already swallows
per-entry OSErrors; this wrapper handles the connection-level cases.
"""

from __future__ import annotations

import logging
import sqlite3

from veles.core.project import Project
from veles.core.project_tree import Scanner, ScanReport

logger = logging.getLogger(__name__)


def scan_project_tree(project: Project) -> ScanReport | None:
    """Run one Scanner pass against `project.memory_db_path`.
    Returns the report or None on failure (logged). Safe to call
    repeatedly — the scanner is idempotent on unchanged trees."""
    from veles.core.memory.store import local_connection

    try:
        # M264c: the connection is closed on the way out now. It never was —
        # this function opened a store per scan and dropped it on the floor.
        with local_connection(project) as conn:
            report = Scanner(project.root, conn).scan()
        logger.debug(
            "project_tree scan: scanned=%d added=%d updated=%d removed=%d",
            report.scanned,
            report.added,
            report.updated,
            report.removed,
        )
        return report
    except sqlite3.Error as exc:
        logger.info("project_tree scan skipped: cannot open db: %s", exc)
        return None
    except Exception as exc:
        logger.info("project_tree scan failed: %s", exc)
        return None


__all__ = ["scan_project_tree"]
