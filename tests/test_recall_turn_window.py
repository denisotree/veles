"""M193 — raw turns must not silently fall out of recall before they're distilled.

`_collect_turns` applies a 30-day recency window on the assumption the curator
already folded older turns into insights. If curation never ran, that window
silently drops the only copy of the memory. Until the first curator/dream pass,
recall must keep the full turn history.
"""

from __future__ import annotations

import time
from pathlib import Path

from veles.core.curator_state import CuratorState, save_atomic
from veles.core.memory import SessionStore
from veles.core.memory.router import MemoryRouter
from veles.core.project import init_project


def _seed_old_turn(project, content: str, *, age_days: float) -> None:
    store = SessionStore(project.memory_db_path)
    try:
        at = time.time() - age_days * 86_400
        store._conn.execute(
            "INSERT OR IGNORE INTO sessions(id, created_at, last_activity_at) VALUES(?, ?, ?)",
            ("s1", at, at),
        )
        store._conn.execute(
            "INSERT INTO turns(session_id, seq, role, content, created_at) VALUES(?, ?, ?, ?, ?)",
            ("s1", 0, "user", content, at),
        )
        store._conn.commit()
    finally:
        store.close()


def _recall_text(project, query: str) -> str:
    store = SessionStore(project.memory_db_path)
    try:
        hits = MemoryRouter(project, store=store).recall(query)
    finally:
        store.close()
    return " ".join(f"{h.title} {h.summary}" for h in hits)


def test_recall_keeps_old_turns_when_never_curated(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _seed_old_turn(project, "kubernetes rollout strategy notes", age_days=40)

    assert "kubernetes" in _recall_text(project, "kubernetes")


def test_recall_applies_window_after_curation(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _seed_old_turn(project, "kubernetes rollout strategy notes", age_days=40)
    # A curator pass has run → older turns are assumed distilled, window applies.
    save_atomic(
        project.state_dir / "curator.state.json",
        CuratorState(last_curated_at=time.time(), sessions_curated_total=1),
    )

    assert "kubernetes" not in _recall_text(project, "kubernetes")
