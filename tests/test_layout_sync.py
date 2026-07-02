"""`veles layout sync` — re-apply the pack scaffold to an existing project.

`apply_scaffold` runs only at init; when a pack later gains categories (e.g. the
wiki pack's diary/tasks/projects), existing projects need `sync` to materialise
them on disk (so they're visible in the injected workspace map).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pytest

from veles.cli.commands.layout import cmd_layout
from veles.core.context import reset_active_project, set_active_project
from veles.core.layout import clear_engine_cache
from veles.core.project import init_project


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    p = init_project(tmp_path / "proj", name="proj", layout="llm-wiki")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def test_sync_recreates_missing_category_dir(project, capsys) -> None:
    # Simulate a project inited before the pack gained the diary category.
    shutil.rmtree(project.root / "wiki" / "diary")
    assert not (project.root / "wiki" / "diary").is_dir()

    rc = cmd_layout(argparse.Namespace(layout_command="sync"), project)
    assert rc == 0
    assert (project.root / "wiki" / "diary").is_dir()
    assert (project.root / "wiki" / "projects").is_dir()
    assert "created" in capsys.readouterr().out


def test_sync_idempotent_when_in_sync(project, capsys) -> None:
    cmd_layout(argparse.Namespace(layout_command="sync"), project)  # first: everything present
    capsys.readouterr()
    rc = cmd_layout(argparse.Namespace(layout_command="sync"), project)
    assert rc == 0
    assert "already in sync" in capsys.readouterr().out


def test_sync_preserves_project_agents_md_title(project) -> None:
    # sync must NOT re-title AGENTS.md to the layout name (regression: passing
    # layout_name as the scaffold `name`).
    agents = (project.root / "AGENTS.md").read_text(encoding="utf-8")
    cmd_layout(argparse.Namespace(layout_command="sync"), project)
    assert (project.root / "AGENTS.md").read_text(encoding="utf-8") == agents


def test_layout_command_registered() -> None:
    from veles.cli._parsers import build_parser

    parser = build_parser()
    ns = parser.parse_args(["layout", "sync"])
    assert ns.command == "layout" and ns.layout_command == "sync"


def test_bad_subcommand_returns_two(project) -> None:
    assert cmd_layout(argparse.Namespace(layout_command="bogus"), project) == 2
