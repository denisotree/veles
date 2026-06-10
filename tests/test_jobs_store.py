"""M75 — JobsStore CRUD + due-job query + run lifecycle."""

from __future__ import annotations

import time

import pytest

from veles.core.jobs_store import JobsStore


@pytest.fixture()
def store():
    s = JobsStore(":memory:")
    yield s
    s.close()


def test_add_and_get(store: JobsStore):
    rec = store.add_job(name="t1", prompt="say hi", schedule_expr="30m")
    fetched = store.get_job(rec.id)
    assert fetched is not None
    assert fetched.name == "t1"
    assert fetched.schedule.kind == "interval"
    assert fetched.enabled is True
    assert fetched.state == "scheduled"


def test_add_empty_name_or_prompt_rejected(store: JobsStore):
    with pytest.raises(ValueError):
        store.add_job(name="", prompt="x", schedule_expr="1h")
    with pytest.raises(ValueError):
        store.add_job(name="t", prompt="", schedule_expr="1h")


def test_add_invalid_schedule_propagates(store: JobsStore):
    with pytest.raises(ValueError):
        store.add_job(name="t", prompt="x", schedule_expr="garbage")


def test_list_orders_newest_first(store: JobsStore):
    a = store.add_job(name="a", prompt="x", schedule_expr="1h", now=1000)
    b = store.add_job(name="b", prompt="x", schedule_expr="1h", now=2000)
    ids = [r.id for r in store.list_jobs()]
    assert ids == [b.id, a.id]


def test_due_jobs_returns_only_overdue_enabled(store: JobsStore):
    a = store.add_job(name="a", prompt="x", schedule_expr="30m", now=100)
    # b is one-shot in the future, not due
    store.add_job(name="b", prompt="x", schedule_expr="2030-01-01T12:00", now=100)
    # a's next_run is 100 + 1800 = 1900; querying at 2000 includes it.
    due_now = store.due_jobs(2000.0)
    assert [r.id for r in due_now] == [a.id]
    # before 1900 nothing is due
    assert store.due_jobs(1500.0) == []


def test_due_jobs_excludes_paused(store: JobsStore):
    rec = store.add_job(name="a", prompt="x", schedule_expr="30m", now=100)
    store.update_job(rec.id, enabled=False)
    assert store.due_jobs(99999.0) == []


def test_update_job_rejects_unknown_columns(store: JobsStore):
    rec = store.add_job(name="t", prompt="x", schedule_expr="1h")
    with pytest.raises(ValueError):
        store.update_job(rec.id, evil_column="boom")


def test_update_job_sets_enabled_boolean(store: JobsStore):
    rec = store.add_job(name="t", prompt="x", schedule_expr="1h")
    store.update_job(rec.id, enabled=False)
    assert store.get_job(rec.id).enabled is False
    store.update_job(rec.id, enabled=True)
    assert store.get_job(rec.id).enabled is True


def test_trigger_job_sets_next_run_at(store: JobsStore):
    rec = store.add_job(name="t", prompt="x", schedule_expr="30m", now=100)
    original_next = store.get_job(rec.id).next_run_at
    now = time.time()
    store.trigger_job(rec.id, now=now)
    assert store.get_job(rec.id).next_run_at == now
    assert store.get_job(rec.id).next_run_at != original_next


def test_delete_job_cascades_runs(store: JobsStore):
    rec = store.add_job(name="t", prompt="x", schedule_expr="1h")
    rid = store.mark_run_started(job_id=rec.id)
    store.mark_run_finished(run_id=rid, status="ok")
    assert len(store.list_runs(rec.id)) == 1
    store.delete_job(rec.id)
    assert store.get_job(rec.id) is None
    assert store.list_runs(rec.id) == []


def test_mark_run_lifecycle(store: JobsStore):
    rec = store.add_job(name="t", prompt="x", schedule_expr="1h")
    rid = store.mark_run_started(job_id=rec.id, started_at=1000.0)
    store.mark_run_finished(
        run_id=rid,
        status="ok",
        iterations=3,
        output_path="/tmp/out.md",
        finished_at=1010.0,
    )
    runs = store.list_runs(rec.id)
    assert len(runs) == 1
    r = runs[0]
    assert r.run_id == rid
    assert r.status == "ok"
    assert r.iterations == 3
    assert r.output_path == "/tmp/out.md"
    assert r.started_at == 1000.0
    assert r.finished_at == 1010.0


def test_list_runs_orders_newest_first(store: JobsStore):
    rec = store.add_job(name="t", prompt="x", schedule_expr="1h")
    r1 = store.mark_run_started(job_id=rec.id, started_at=1000.0)
    r2 = store.mark_run_started(job_id=rec.id, started_at=2000.0)
    runs = store.list_runs(rec.id)
    assert [r.run_id for r in runs] == [r2, r1]
