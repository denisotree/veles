"""M166 — task_add / task_list / task_done / task_snooze tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import (
    reset_active_project,
    reset_origin,
    set_active_project,
    set_origin,
)
from veles.core.project import init_project
from veles.core.tasks_store import TasksStore
from veles.core.tools.builtin.task_tools import task_add, task_done, task_list, task_snooze


@pytest.fixture()
def project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    p = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def _tasks(project):
    store = TasksStore(project.memory_db_path)
    try:
        return store.list_tasks(state=None)
    finally:
        store.close()


def test_task_add_basic(project):
    out = task_add("buy milk")
    assert "added task" in out
    tasks = _tasks(project)
    assert len(tasks) == 1
    assert tasks[0].title == "buy milk"
    assert tasks[0].due_at is None


def test_task_add_relative_due_sets_timestamp(project):
    task_add("ping", due_at="+2h")
    t = _tasks(project)[0]
    assert t.due_at is not None  # parsed +2h into an absolute ts


def test_task_add_defaults_deliver_to_from_origin(project):
    token = set_origin("telegram:999")
    try:
        task_add("remind me", due_at="+1h")
    finally:
        reset_origin(token)
    assert _tasks(project)[0].deliver_to == "telegram:999"


def test_task_add_explicit_deliver_to_overrides_origin(project):
    token = set_origin("telegram:999")
    try:
        task_add("x", due_at="+1h", deliver_to="telegram:111")
    finally:
        reset_origin(token)
    assert _tasks(project)[0].deliver_to == "telegram:111"


def test_task_add_no_origin_no_target(project):
    task_add("orphan", due_at="+1h")  # no origin set
    assert _tasks(project)[0].deliver_to is None


def test_task_add_bad_due_is_error(project):
    out = task_add("x", due_at="whenever")
    assert "not understood" in out
    assert _tasks(project) == []  # nothing persisted


def test_task_list(project):
    task_add("alpha")
    task_add("beta")
    out = task_list()
    assert "alpha" in out
    assert "beta" in out


def test_task_done(project):
    task_add("done me")
    tid = _tasks(project)[0].id
    assert "marked done" in task_done(tid)
    store = TasksStore(project.memory_db_path)
    try:
        assert store.get_task(tid).state == "done"
    finally:
        store.close()


def test_task_done_unknown_id(project):
    assert "no task" in task_done("task-nope")


def test_task_snooze(project):
    task_add("x", due_at="+1h")
    tid = _tasks(project)[0].id
    assert "snoozed" in task_snooze(tid, "+1d")


# ---- M208: input validation (the open_claw reminder incident) ----


def test_task_add_rejects_malformed_deliver_to(project):
    out = task_add("x", due_at="+1h", deliver_to="chat")
    assert "<error" in out
    assert "deliver_to" in out
    assert _tasks(project) == []  # nothing persisted


def test_task_add_accepts_valid_explicit_targets(project):
    assert "added task" in task_add("a", deliver_to="telegram:111")
    assert "added task" in task_add("b", deliver_to="local")


def test_task_add_resolves_origin_keyword_to_concrete_origin(project):
    token = set_origin("telegram:999")
    try:
        assert "added task" in task_add("c", due_at="+1h", deliver_to="origin")
    finally:
        reset_origin(token)
    assert _tasks(project)[0].deliver_to == "telegram:999"


def test_task_add_rejects_past_due(project):
    out = task_add("x", due_at="2020-01-09T11:00:00Z")
    assert "<error" in out
    assert "in the past" in out
    assert "current time" in out  # tells the model what "now" is so it recomputes
    assert _tasks(project) == []


def test_task_snooze_rejects_past_until(project):
    task_add("x", due_at="+1h")
    t = _tasks(project)[0]
    out = task_snooze(t.id, "2020-01-09T11:00:00Z")
    assert "<error" in out
    assert "in the past" in out
    assert _tasks(project)[0].due_at == t.due_at  # unchanged
