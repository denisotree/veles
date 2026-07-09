"""M167b — job_add / job_list / job_remove tools (module-resident since M204)."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import (
    reset_active_project,
    reset_origin,
    set_active_project,
    set_origin,
)
from veles.core.jobs_store import JobsStore
from veles.core.project import init_project
from veles.modules.agentops.tools import job_add, job_list, job_remove


@pytest.fixture()
def project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    p = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def _jobs(project):
    s = JobsStore(project.memory_db_path)
    try:
        return s.list_jobs(include_disabled=True)
    finally:
        s.close()


def test_job_add_creates_recurring_job(project):
    out = job_add("morning digest", "list today's tasks", "daily@09:00")
    assert "scheduled job" in out
    jobs = _jobs(project)
    assert len(jobs) == 1
    assert jobs[0].schedule.display() == "daily@09:00"
    assert jobs[0].prompt == "list today's tasks"


def test_job_add_defaults_deliver_to_from_origin(project):
    token = set_origin("telegram:777")
    try:
        job_add("d", "p", "weekdays@18:00")
    finally:
        reset_origin(token)
    assert _jobs(project)[0].deliver_to == "telegram:777"


def test_job_add_validates_schedule(project):
    out = job_add("d", "p", "every monday lol")
    assert "error" in out.lower()
    assert _jobs(project) == []  # nothing scheduled on a bad schedule


def test_job_add_requires_name_and_prompt(project):
    assert "required" in job_add("", "p", "daily@09:00")
    assert "required" in job_add("n", "", "daily@09:00")


def test_job_list_and_remove(project):
    job_add("watch db", "check db health", "every:2h")
    jid = _jobs(project)[0].id
    assert "watch db" in job_list()
    assert "removed" in job_remove(jid)
    assert _jobs(project) == []


def test_job_remove_unknown(project):
    assert "no job" in job_remove("job-nope")


def test_job_add_is_sensitive_for_trust_ladder():
    from veles.core.tools.registry import registry

    entry = registry.get("job_add")
    assert entry.sensitive is True  # creating a recurring autonomous run is gated
