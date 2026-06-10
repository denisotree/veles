"""M142: the dream cycle dedupes near-duplicate insights via supersede-links in
`insight_refs`, and the insight step caps transcripts per cycle."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from veles.core.dreaming import (
    _MAX_TRANSCRIPTS_PER_CYCLE,
    DreamResult,
    _step_insight_dedup,
    _step_insights,
)
from veles.core.project import init_project


def _insert(project, *, title: str, body: str, ts: float) -> int:
    conn = sqlite3.connect(str(project.memory_db_path))
    try:
        cur = conn.execute(
            "INSERT INTO insights(title, body, category, created_at, last_referenced_at)"
            " VALUES (?, ?, 'curated-session', ?, ?)",
            (title, body, ts, ts),
        )
        conn.commit()
        return int(cur.lastrowid or 0)
    finally:
        conn.close()


def _refs(project) -> list[tuple[int, int]]:
    conn = sqlite3.connect(str(project.memory_db_path))
    try:
        return [
            (int(r[0]), int(r[1]))
            for r in conn.execute(
                "SELECT from_insight_id, to_insight_id FROM insight_refs"
            ).fetchall()
        ]
    finally:
        conn.close()


def test_insight_dedup_links_duplicate_to_canonical(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    # two near-duplicates (one more recently referenced → canonical) + 1 unrelated
    old = _insert(
        project,
        title="nginx tuning",
        body="bump nginx worker_connections to handle more concurrent sockets",
        ts=100.0,
    )
    recent = _insert(
        project,
        title="nginx tuning v2",
        body="increase nginx worker_connections for concurrent socket handling",
        ts=999.0,
    )
    _insert(project, title="lunch", body="sandwiches and coffee on the menu today", ts=500.0)

    result = DreamResult()
    _step_insight_dedup(project, result, dry_run=False)

    refs = _refs(project)
    # the older duplicate is superseded by the more-recently-referenced one
    assert refs == [(old, recent)]


def test_insight_dedup_idempotent(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _insert(project, title="a", body="bump nginx worker_connections concurrent sockets", ts=100.0)
    _insert(project, title="b", body="increase nginx worker_connections concurrent sockets", ts=200.0)
    _step_insight_dedup(project, DreamResult(), dry_run=False)
    _step_insight_dedup(project, DreamResult(), dry_run=False)
    assert len(_refs(project)) == 1  # INSERT OR IGNORE → no duplicate ref


def test_insight_dedup_dry_run_writes_nothing(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _insert(project, title="a", body="bump nginx worker_connections concurrent sockets", ts=100.0)
    _insert(project, title="b", body="increase nginx worker_connections concurrent sockets", ts=200.0)
    _step_insight_dedup(project, DreamResult(), dry_run=True)
    assert _refs(project) == []


def test_deep_dream_cycle_runs_insight_dedup(tmp_path: Path) -> None:
    """The deep cycle (include_consolidation=True) invokes the dedup step even
    without a provider — it's LLM-free."""
    from veles.core.dreaming import dream_cycle

    project = init_project(tmp_path / "p", name="p")
    _insert(project, title="a", body="bump nginx worker_connections concurrent sockets", ts=100.0)
    _insert(project, title="b", body="increase nginx worker_connections concurrent sockets", ts=200.0)
    result = dream_cycle(project, include_consolidation=True)
    assert result.insight_dedup_clusters == 1
    assert _refs(project) == [(1, 2)]


def test_post_turn_cycle_skips_insight_dedup(tmp_path: Path) -> None:
    """The cheap post-turn cycle (include_consolidation=False) must not dedup."""
    from veles.core.dreaming import dream_cycle

    project = init_project(tmp_path / "p", name="p")
    _insert(project, title="a", body="bump nginx worker_connections concurrent sockets", ts=100.0)
    _insert(project, title="b", body="increase nginx worker_connections concurrent sockets", ts=200.0)
    dream_cycle(project, include_consolidation=False)
    assert _refs(project) == []


def test_insight_step_caps_transcripts(tmp_path: Path, monkeypatch) -> None:
    """The insight step never processes more than the per-cycle cap, and logs
    the drop."""
    import veles.core.insight_extractor as ie

    project = init_project(tmp_path / "p", name="p")
    processed: list[str] = []

    def fake_make_extractor(*, provider, model, project):
        def _extract(history, session_id):
            processed.append(session_id)
            return 0

        return _extract

    monkeypatch.setattr(ie, "make_insight_extractor", fake_make_extractor)

    def loader():
        for i in range(_MAX_TRANSCRIPTS_PER_CYCLE + 50):
            yield (f"s{i}", [])

    result = DreamResult()
    _step_insights(project, object(), "model", loader, result)

    assert len(processed) == _MAX_TRANSCRIPTS_PER_CYCLE
    assert any("transcript" in n for n in result.notes)
