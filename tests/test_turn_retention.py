"""M257: raw `turns` are prunable, the `insights` mined from them are not.

Retention model decided 2026-09-18. `turns` is the transcript — the bulkiest
part of `memory.db` and the only one that grows without bound. `insights` and
`rules` are what the transcript was read *for*. So the transcript is disposable
and the product is permanent.

**The gate that makes that safe** is `CuratorState.last_curated_at`: a session
the curator has not swept yet is never pruned, however old. Without it, pruning
by age alone would destroy a transcript *before* anything was extracted from
it — losing the raw material and never producing the insight, which is strictly
worse than the growth it was meant to fix. Most of the tests below exist for
that one property.
"""

from __future__ import annotations

import time
from pathlib import Path

from veles.core.memory import SessionStore
from veles.core.provider import Message

DAY = 86400.0


def _session(store: SessionStore, *, age_days: float, turns: int = 3) -> str:
    """A session whose activity is `age_days` old, with `turns` messages."""
    sid = store.create_session(title=f"aged-{age_days}")
    for i in range(turns):
        store.append_turn(sid, Message(role="user", content=f"secret marker {sid} #{i}"))
    when = time.time() - age_days * DAY
    store._conn.execute("UPDATE sessions SET last_activity_at = ? WHERE id = ?", (when, sid))
    store._conn.commit()
    return sid


def _turn_count(store: SessionStore, sid: str) -> int:
    row = store._conn.execute("SELECT COUNT(*) FROM turns WHERE session_id = ?", (sid,)).fetchone()
    return int(row[0])


def test_old_and_curated_turns_are_removed(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        old = _session(store, age_days=200)
        removed = store.prune_turns(
            older_than=time.time() - 90 * DAY,
            curated_before=time.time(),  # curator has swept everything
        )
        assert removed == 3
        assert _turn_count(store, old) == 0
    finally:
        store.close()


def test_recent_turns_survive(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        recent = _session(store, age_days=1)
        store.prune_turns(older_than=time.time() - 90 * DAY, curated_before=time.time())
        assert _turn_count(store, recent) == 3
    finally:
        store.close()


def test_an_uncurated_session_is_never_pruned(tmp_path: Path) -> None:
    """The load-bearing guarantee. This session is ancient, but the curator has
    not reached it — pruning it would throw away the transcript before anything
    had been learned from it."""
    store = SessionStore(tmp_path / "m.db")
    try:
        ancient = _session(store, age_days=999)
        removed = store.prune_turns(
            older_than=time.time() - 90 * DAY,
            curated_before=time.time() - 1000 * DAY,  # curator is far behind
        )
        assert removed == 0
        assert _turn_count(store, ancient) == 3
    finally:
        store.close()


def test_the_session_row_survives_its_turns(tmp_path: Path) -> None:
    """Bodies go, metadata stays — `veles sessions list` keeps showing history
    instead of the run vanishing from it."""
    store = SessionStore(tmp_path / "m.db")
    try:
        sid = _session(store, age_days=200)
        store.prune_turns(older_than=time.time() - 90 * DAY, curated_before=time.time())
        assert any(s.id == sid for s in store.list_sessions(limit=50))
    finally:
        store.close()


def test_insights_are_never_touched(tmp_path: Path) -> None:
    """The whole point of the hybrid: the product outlives the raw material."""
    store = SessionStore(tmp_path / "m.db")
    try:
        _session(store, age_days=400)
        store._conn.execute(
            "INSERT INTO insights(title, body, category, created_at)"
            " VALUES ('kept', 'what we learned', 'general', ?)",
            (time.time() - 400 * DAY,),
        )
        store._conn.commit()

        store.prune_turns(older_than=time.time() - 90 * DAY, curated_before=time.time())

        rows = store._conn.execute("SELECT title FROM insights").fetchall()
        assert [r[0] for r in rows] == ["kept"]
    finally:
        store.close()


def test_the_fts_index_does_not_outlive_the_rows(tmp_path: Path) -> None:
    """`turns_fts` has delete triggers; if they ever stopped firing, search
    would return hits pointing at rows that are gone."""
    store = SessionStore(tmp_path / "m.db")
    try:
        sid = _session(store, age_days=200)
        hits = store._conn.execute(
            "SELECT COUNT(*) FROM turns_fts WHERE turns_fts MATCH 'marker'"
        ).fetchone()[0]
        assert hits == 3, "precondition: the transcript is indexed"

        store.prune_turns(older_than=time.time() - 90 * DAY, curated_before=time.time())

        after = store._conn.execute(
            "SELECT COUNT(*) FROM turns_fts WHERE turns_fts MATCH 'marker'"
        ).fetchone()[0]
        assert after == 0
        assert _turn_count(store, sid) == 0
    finally:
        store.close()


def test_the_stricter_of_the_two_cutoffs_wins(tmp_path: Path) -> None:
    """Age says prune, the curator cursor says not yet — the cursor wins."""
    store = SessionStore(tmp_path / "m.db")
    try:
        sid = _session(store, age_days=100)
        store.prune_turns(
            older_than=time.time() - 90 * DAY,  # eligible by age
            curated_before=time.time() - 120 * DAY,  # not yet curated
        )
        assert _turn_count(store, sid) == 3
    finally:
        store.close()


# ---- the dream step around it ----


def test_dream_step_skips_before_the_curator_has_ever_run(tmp_path, monkeypatch) -> None:
    """A fresh project has `last_curated_at = 0`. Nothing has been mined, so
    nothing may be dropped — even with pruning explicitly switched on."""
    from veles.core.dreaming import DreamResult, _step_prune_turns
    from veles.core.project import init_project
    from veles.core.project_config import save_project_config

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="p")
    save_project_config(project, {"memory": {"turn_retention_days": 90}})
    store = SessionStore(project.memory_db_path)
    try:
        sid = _session(store, age_days=999)
    finally:
        store.close()

    result = DreamResult()
    _step_prune_turns(project, result)

    assert any("curator has not run" in n for n in result.notes)
    store = SessionStore(project.memory_db_path)
    try:
        assert _turn_count(store, sid) == 3
    finally:
        store.close()


def test_pruning_is_off_by_default(tmp_path, monkeypatch) -> None:
    """The default deletes nothing. A framework does not get to remove a user's
    history because they upgraded — the loss would be silent and irreversible,
    and nobody opted into it. Pruning happens only when asked for."""
    from veles.core.curator_state import CuratorState, save_atomic
    from veles.core.dreaming import DreamResult, _dream_state_path, _step_prune_turns
    from veles.core.project import init_project

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="p")
    # Curator has swept everything, so the ONLY thing keeping the transcript
    # alive is the default being off.
    save_atomic(_dream_state_path(project), CuratorState(last_curated_at=time.time()))
    store = SessionStore(project.memory_db_path)
    try:
        sid = _session(store, age_days=999)
    finally:
        store.close()

    result = DreamResult()
    _step_prune_turns(project, result)

    assert any("off" in n for n in result.notes)
    store = SessionStore(project.memory_db_path)
    try:
        assert _turn_count(store, sid) == 3
    finally:
        store.close()


def test_explicit_zero_also_prunes_nothing(tmp_path, monkeypatch) -> None:
    """Writing the default out explicitly behaves the same as omitting it."""
    from veles.core.curator_state import CuratorState, save_atomic
    from veles.core.dreaming import DreamResult, _dream_state_path, _step_prune_turns
    from veles.core.project import init_project
    from veles.core.project_config import save_project_config

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="p")
    save_project_config(project, {"memory": {"turn_retention_days": 0}})
    save_atomic(_dream_state_path(project), CuratorState(last_curated_at=time.time()))
    store = SessionStore(project.memory_db_path)
    try:
        sid = _session(store, age_days=999)
    finally:
        store.close()

    result = DreamResult()
    _step_prune_turns(project, result)

    assert any("off" in n for n in result.notes)
    store = SessionStore(project.memory_db_path)
    try:
        assert _turn_count(store, sid) == 3
    finally:
        store.close()


def test_dream_step_prunes_and_reports(tmp_path, monkeypatch) -> None:
    from veles.core.curator_state import CuratorState, save_atomic
    from veles.core.dreaming import DreamResult, _dream_state_path, _step_prune_turns
    from veles.core.project import init_project

    from veles.core.project_config import save_project_config

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="p")
    save_project_config(project, {"memory": {"turn_retention_days": 90}})
    save_atomic(_dream_state_path(project), CuratorState(last_curated_at=time.time()))
    store = SessionStore(project.memory_db_path)
    try:
        sid = _session(store, age_days=200)
    finally:
        store.close()

    result = DreamResult()
    _step_prune_turns(project, result)

    assert any("prune_turns: 3 turn(s)" in n for n in result.notes)
    store = SessionStore(project.memory_db_path)
    try:
        assert _turn_count(store, sid) == 0
    finally:
        store.close()
