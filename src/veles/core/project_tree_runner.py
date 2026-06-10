"""M118b: Scanner triggers for the project_tree cache.

The `project_tree.Scanner` from M118 is mtime-incremental: a re-scan
on an unchanged tree is cheap (one stat per entry, zero writes). That
makes "scan on every `veles run` boot" affordable — we don't need a
filesystem watcher, just a thin call site here.

`scan_project_tree(project)` is the public seam. Callers:
- `init_project` (M118c): one full scan right after the skeleton lands
  so the cache isn't empty on first `veles run`.
- `cli/_runtime.py::_make_agent_for_run` (M118b): re-scan on every
  agent bootstrap. Fast on warm trees; produces fresh `project_tree`
  rows for `relevant()` to query.

Errors are caught and logged — a partially-readable tree shouldn't
abort the agent's startup. The Scanner itself already swallows
per-entry OSErrors; this wrapper handles the connection-level cases.
"""

from __future__ import annotations

import logging
import sqlite3

from veles.core.memory import SessionStore
from veles.core.project import Project
from veles.core.project_tree import ScanReport, Scanner

logger = logging.getLogger(__name__)


def scan_project_tree(project: Project) -> ScanReport | None:
    """Run one Scanner pass against `project.memory_db_path`.
    Returns the report or None on failure (logged). Safe to call
    repeatedly — the scanner is idempotent on unchanged trees."""
    try:
        store = SessionStore(project.memory_db_path)
        conn = store._conn
    except sqlite3.Error as exc:
        logger.info("project_tree scan skipped: cannot open db: %s", exc)
        return None
    try:
        report = Scanner(project.root, conn).scan()
        logger.debug(
            "project_tree scan: scanned=%d added=%d updated=%d removed=%d",
            report.scanned,
            report.added,
            report.updated,
            report.removed,
        )
        return report
    except Exception as exc:  # noqa: BLE001
        logger.info("project_tree scan failed: %s", exc)
        return None


__all__ = ["scan_project_tree"]
