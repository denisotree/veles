"""M76 — `veles dream` CLI command."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli.commands import dream as dream_cmd
from veles.core.project import Project, init_project


def _ns(**fields):
    base = {
        "include_consolidation": False,
        "dry_run": False,
        "skip_insights": True,  # avoid needing a provider
        "skip_dedup": False,
        "skip_promote": False,
        "skip_lint": False,
        "provider": "openrouter",
        "consolidation_model": None,
    }
    base.update(fields)
    return type("A", (), base)()


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="dtest")


def test_dream_runs_and_prints_summary(project: Project, capsys) -> None:
    rc = dream_cmd.cmd_dream(_ns(), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "dream:" in out


def test_dry_run_does_not_persist(project: Project, capsys) -> None:
    rc = dream_cmd.cmd_dream(_ns(dry_run=True), project)
    assert rc == 0
    # state file should not be created
    state_path = project.state_dir / "curator.state.json"
    assert not state_path.exists()


def test_skip_all_steps(project: Project, capsys) -> None:
    rc = dream_cmd.cmd_dream(
        _ns(skip_insights=True, skip_dedup=True, skip_promote=True, skip_lint=True),
        project,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "insights=0" in out
    assert "lint=0" in out
