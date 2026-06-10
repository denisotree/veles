"""File-backed snapshot of `TokenBudget` for cross-process propagation.

Used when a parent Veles command delegates to claude-cli/gemini-cli: the
parent saves a snapshot before the delegate runs, the MCP child process
loads it on startup and re-saves after each `tools/call`, and the parent
reconciles the child's contribution back into its own budget on exit.

Single writer at any time: the parent only writes before/after the
delegate (and never during, because it is blocked reading delegate stdout
without making LLM calls of its own); the child writes once per tools/call
inside that window. No locking required for the single-user model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    limit: int
    consumed: int


def load(path: Path) -> BudgetSnapshot | None:
    """Read snapshot from `path`. Returns None if missing or unreadable."""
    from veles.core.io_utils import load_optional_json

    data = load_optional_json(path)
    if not isinstance(data, dict):
        return None
    try:
        return BudgetSnapshot(limit=int(data["limit"]), consumed=int(data["consumed"]))
    except (KeyError, ValueError, TypeError) as exc:
        _log.warning("budget snapshot at %s malformed: %s", path, exc)
        return None


def save_atomic(path: Path, snapshot: BudgetSnapshot) -> None:
    """Write snapshot atomically via tempfile + os.replace."""
    from veles.core.io_utils import atomic_write_json

    atomic_write_json(path, {"limit": snapshot.limit, "consumed": snapshot.consumed})
