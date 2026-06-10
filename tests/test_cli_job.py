"""M75 — `veles job` CLI subcommands (add/list/show/pause/trigger/history)."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli.commands import job as job_cmd
from veles.core.jobs_store import JobsStore
from veles.core.project import Project, init_project


def _ns(**fields):
    return type("A", (), fields)()


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="jtest")


def test_add_creates_and_lists(project: Project, capsys) -> None:
    rc = job_cmd.cmd_job(
        _ns(
            job_command="add",
            name="daily",
            schedule="30m",
            prompt="say hi",
            repeat=None,
            context_from=None,
            deliver_to=None,
        ),
        project,
    )
    assert rc == 0
    assert "created job" in capsys.readouterr().out
    rc = job_cmd.cmd_job(_ns(job_command="list", json=False), project)
    assert rc == 0
    assert "daily" in capsys.readouterr().out


def test_list_empty(project: Project, capsys) -> None:
    rc = job_cmd.cmd_job(_ns(job_command="list", json=False), project)
    assert rc == 0
    assert "no jobs" in capsys.readouterr().out


def test_show_by_id(project: Project, capsys) -> None:
    store = JobsStore(project.memory_db_path)
    rec = store.add_job(name="t", prompt="x", schedule_expr="1h")
    store.close()
    rc = job_cmd.cmd_job(_ns(job_command="show", id=rec.id), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert rec.id in out


def test_pause_then_resume(project: Project, capsys) -> None:
    store = JobsStore(project.memory_db_path)
    rec = store.add_job(name="t", prompt="x", schedule_expr="1h")
    store.close()
    rc = job_cmd.cmd_job(_ns(job_command="pause", id=rec.id), project)
    assert rc == 0
    rc = job_cmd.cmd_job(_ns(job_command="resume", id=rec.id), project)
    assert rc == 0


def test_trigger(project: Project, capsys) -> None:
    store = JobsStore(project.memory_db_path)
    rec = store.add_job(name="t", prompt="x", schedule_expr="1h")
    store.close()
    rc = job_cmd.cmd_job(_ns(job_command="trigger", id=rec.id), project)
    assert rc == 0
    assert "triggered" in capsys.readouterr().out


def test_history_empty(project: Project, capsys) -> None:
    store = JobsStore(project.memory_db_path)
    rec = store.add_job(name="t", prompt="x", schedule_expr="1h")
    store.close()
    rc = job_cmd.cmd_job(_ns(job_command="history", id=rec.id, limit=10), project)
    assert rc == 0
    assert "no runs" in capsys.readouterr().out


def test_remove(project: Project, capsys) -> None:
    store = JobsStore(project.memory_db_path)
    rec = store.add_job(name="t", prompt="x", schedule_expr="1h")
    store.close()
    rc = job_cmd.cmd_job(_ns(job_command="remove", id=rec.id), project)
    assert rc == 0
    # second remove → not found
    rc = job_cmd.cmd_job(_ns(job_command="remove", id=rec.id), project)
    assert rc == 1


def test_unknown_subcommand_returns_2(project: Project) -> None:
    rc = job_cmd.cmd_job(_ns(job_command="nope"), project)
    assert rc == 2


def test_add_rejects_bad_schedule(project: Project, capsys) -> None:
    rc = job_cmd.cmd_job(
        _ns(
            job_command="add",
            name="x",
            schedule="garbage",
            prompt="x",
            repeat=None,
            context_from=None,
            deliver_to=None,
        ),
        project,
    )
    assert rc == 1
    assert "error" in capsys.readouterr().err
