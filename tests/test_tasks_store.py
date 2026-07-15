"""M166 — TasksStore: personal tasks + reminder-sweep query."""

from __future__ import annotations

from veles.core.tasks_store import TasksStore


def _store() -> TasksStore:
    return TasksStore(":memory:")


def test_add_and_get():
    s = _store()
    rec = s.add_task(title="buy milk", now=100)
    got = s.get_task(rec.id)
    assert got is not None
    assert got.title == "buy milk"
    assert got.state == "open"
    assert got.due_at is None
    assert got.reminded_at is None
    s.close()


def test_due_reminders_filters():
    s = _store()
    a = s.add_task(title="a", due_at=50, deliver_to="telegram:1", now=10)
    s.add_task(title="b", due_at=50, deliver_to=None, now=10)  # no target → excluded
    s.add_task(title="c", due_at=200, deliver_to="telegram:1", now=10)  # future → excluded
    s.add_task(title="d", deliver_to="telegram:1", now=10)  # no due → excluded
    due = s.due_reminders(now=100)
    assert [t.id for t in due] == [a.id]
    s.close()


def test_mark_reminded_is_idempotent():
    s = _store()
    a = s.add_task(title="a", due_at=50, deliver_to="telegram:1", now=10)
    assert len(s.due_reminders(100)) == 1
    s.mark_reminded(a.id, now=100)
    assert s.due_reminders(100) == []  # already delivered — never fires twice
    s.close()


def test_snooze_reopens_and_rearms():
    s = _store()
    a = s.add_task(title="a", due_at=50, deliver_to="telegram:1", now=10)
    s.mark_reminded(a.id, now=60)
    assert s.due_reminders(100) == []
    s.snooze(a.id, due_at=200, now=100)
    got = s.get_task(a.id)
    assert got is not None
    assert got.due_at == 200
    assert got.reminded_at is None
    assert got.state == "open"
    assert len(s.due_reminders(250)) == 1
    s.close()


def test_mark_done_excludes_from_reminders():
    s = _store()
    a = s.add_task(title="a", due_at=50, deliver_to="telegram:1", now=10)
    s.mark_done(a.id, now=70)
    assert s.due_reminders(100) == []
    got = s.get_task(a.id)
    assert got is not None
    assert got.state == "done"
    assert got.done_at == 70
    s.close()


def test_dream_upsert_is_idempotent_on_dedup_key():
    s = _store()
    a = s.upsert_dream_event(dedup_key="ev1", title="BC GAME live", due_at=200, now=10)
    b = s.upsert_dream_event(dedup_key="ev1", title="BC GAME live", due_at=200, now=20)
    assert a.id == b.id  # same row — no duplicate notice
    assert len(s.list_tasks(state=None)) == 1
    assert b.source == "dream"
    assert b.deliver_to is None  # target resolved at delivery, not creation
    s.close()


def test_dream_upsert_rearms_on_new_due_at():
    s = _store()
    a = s.upsert_dream_event(dedup_key="ev1", title="x", due_at=100, now=10)
    s.mark_reminded(a.id, now=110)
    assert s.due_reminders(300) == []  # delivered — dormant
    # event rescheduled to a later time → re-arm so it fires again
    s.upsert_dream_event(dedup_key="ev1", title="x", due_at=250, now=120)
    got = s.get_task(a.id)
    assert got is not None and got.due_at == 250 and got.reminded_at is None
    assert len(s.due_reminders(300)) == 1
    s.close()


def test_dream_upsert_unchanged_time_does_not_refire():
    s = _store()
    a = s.upsert_dream_event(dedup_key="ev1", title="x", due_at=100, now=10)
    s.mark_reminded(a.id, now=110)
    s.upsert_dream_event(dedup_key="ev1", title="x (edited body)", body="note", due_at=100, now=120)
    got = s.get_task(a.id)
    assert got is not None and got.reminded_at is not None  # still delivered
    assert s.due_reminders(300) == []
    s.close()


def test_due_reminders_admits_dream_with_null_target():
    s = _store()
    d = s.upsert_dream_event(dedup_key="ev1", title="dream due", due_at=50, now=10)
    s.add_task(title="user no-target", due_at=50, deliver_to=None, now=10)  # excluded
    due = s.due_reminders(now=100)
    assert [t.id for t in due] == [d.id]  # dream admitted despite NULL deliver_to
    s.close()


def test_list_tasks_source_filter():
    s = _store()
    s.add_task(title="manual", now=10)
    s.upsert_dream_event(dedup_key="ev1", title="auto", due_at=200, now=10)
    assert [t.title for t in s.list_tasks(source="user")] == ["manual"]
    assert [t.title for t in s.list_tasks(source="dream")] == ["auto"]
    s.close()


def test_list_filters_and_orders_by_due():
    s = _store()
    s.add_task(title="later", due_at=200, now=10)
    s.add_task(title="sooner", due_at=50, now=10)
    s.add_task(title="someday", now=10)  # no due → last
    open_titles = [t.title for t in s.list_tasks(state="open")]
    assert open_titles == ["sooner", "later", "someday"]
    # state filter
    done = s.add_task(title="finished", now=10)
    s.mark_done(done.id)
    assert [t.title for t in s.list_tasks(state="done")] == ["finished"]
    assert "finished" not in [t.title for t in s.list_tasks(state="open")]
    assert len(s.list_tasks(state=None)) == 4  # 'all'
    s.close()
