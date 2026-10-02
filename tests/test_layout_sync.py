"""`veles layout sync` — re-apply the pack scaffold to an existing project.

`apply_scaffold` runs only at init; when a pack later gains directories,
existing projects need `sync` to materialise them on disk (so they're visible in
the injected workspace map). (Wiki categories are tested with the wiki module.)
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
    pack = tmp_path / "home" / ".veles" / "layouts" / "dirs"
    pack.mkdir(parents=True)
    (pack / "layout.toml").write_text(
        '[layout]\nname = "dirs"\n[layout.scaffold]\ndirs = ["notes", "notes/diary"]\n',
        encoding="utf-8",
    )
    p = init_project(tmp_path / "proj", name="proj", layout="dirs")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def test_sync_recreates_a_missing_scaffold_dir(project, capsys) -> None:
    shutil.rmtree(project.root / "notes" / "diary")
    rc = cmd_layout(argparse.Namespace(layout_command="sync"), project)
    assert rc == 0
    assert (project.root / "notes" / "diary").is_dir()
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
