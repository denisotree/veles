"""File-backed cursor for the `veles curate` command.

Tracks the high-water mark on `sessions.last_activity_at` so each curate
run only processes sessions that arrived after the previous run. Lives at
`<project>/.veles/curator.state.json`. Missing or corrupted file loads as
default (`last_curated_at=0.0`) — the next curate run will sweep every
session in the store, which is the desired bootstrap behavior.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CuratorState:
    last_curated_at: float = 0.0
    sessions_curated_total: int = 0
    # M76 dreaming: cursors for the post-turn + deep idle dream loops.
    last_post_turn_dream_at: float = 0.0
    last_deep_dream_at: float = 0.0
    dream_count: int = 0
    # Poison-pill guard (2026-07-08): per-session consecutive curation failures.
    # A session failing `_CURATE_MAX_ATTEMPTS` times is skipped (cursor advances
    # past it) instead of blocking the whole curator queue forever.
    failed_attempts: dict[str, int] = field(default_factory=dict)


def load(path: Path) -> CuratorState:
    """Read state from `path`. Returns default state if missing or unreadable."""
    from veles.core.io_utils import load_optional_json

    d = load_optional_json(path)
    if not isinstance(d, dict):
        return CuratorState()
    try:
        raw_failed = d.get("failed_attempts", {})
        failed = (
            {str(k): int(v) for k, v in raw_failed.items()} if isinstance(raw_failed, dict) else {}
        )
        return CuratorState(
            last_curated_at=float(d.get("last_curated_at", 0.0)),
            sessions_curated_total=int(d.get("sessions_curated_total", 0)),
            last_post_turn_dream_at=float(d.get("last_post_turn_dream_at", 0.0)),
            last_deep_dream_at=float(d.get("last_deep_dream_at", 0.0)),
            dream_count=int(d.get("dream_count", 0)),
            failed_attempts=failed,
        )
    except (ValueError, TypeError) as exc:
        _log.warning("curator state at %s malformed: %s — defaulting", path, exc)
        return CuratorState()


def save_atomic(path: Path, state: CuratorState) -> None:
    """Write state atomically via tempfile + os.replace."""
    from veles.core.io_utils import atomic_write_json

    atomic_write_json(
        path,
        {
            "last_curated_at": state.last_curated_at,
            "sessions_curated_total": state.sessions_curated_total,
            "last_post_turn_dream_at": state.last_post_turn_dream_at,
            "last_deep_dream_at": state.last_deep_dream_at,
            "dream_count": state.dream_count,
            "failed_attempts": state.failed_attempts,
        },
    )
