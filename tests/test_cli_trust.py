"""M63 — `veles trust {list, set, revoke, clear}` CLI verb tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli.commands import trust as trust_cmd
from veles.core.project import Project, init_project
from veles.core.trust_store import TrustStore, user_trust_path

# User-home isolation is provided by the autouse `_hermetic_user_home`
# fixture in tests/conftest.py.


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


def _ns(**fields):
    return type("A", (), fields)()


# ---- list ----


def test_list_empty_both_scopes(project: Project, capsys) -> None:
    rc = trust_cmd.cmd_trust(_ns(trust_command="list"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "user-scope grants: (none)" in out
    assert "project-scope grants: (none)" in out


def test_list_no_project_shows_user_only(capsys) -> None:
    user = TrustStore.load(user_trust_path())
    user.grant("run_shell")
    rc = trust_cmd.cmd_trust(_ns(trust_command="list"), None)
    assert rc == 0
    out = capsys.readouterr().out
    assert "run_shell" in out
    assert "no active project" in out


def test_list_shows_both_scopes(project: Project, capsys) -> None:
    user = TrustStore.load(user_trust_path())
    user.grant("fetch_url")
    proj = TrustStore.load(project.trust_path)
    proj.grant("run_shell")
    rc = trust_cmd.cmd_trust(_ns(trust_command="list"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "fetch_url" in out
    assert "run_shell" in out


# ---- set ----


def test_set_project_scope(project: Project, capsys) -> None:
    args = _ns(trust_command="set", tool="run_shell", scope="project")
    rc = trust_cmd.cmd_trust(args, project)
    assert rc == 0
    assert "this project" in capsys.readouterr().out
    proj = TrustStore.load(project.trust_path)
    assert proj.is_granted("run_shell")


def test_set_user_scope(project: Project, capsys) -> None:
    args = _ns(trust_command="set", tool="fetch_url", scope="user")
    rc = trust_cmd.cmd_trust(args, project)
    assert rc == 0
    assert "user-wide" in capsys.readouterr().out
    user = TrustStore.load(user_trust_path())
    assert user.is_granted("fetch_url")


def test_set_project_without_active_project_refuses(capsys) -> None:
    args = _ns(trust_command="set", tool="run_shell", scope="project")
    rc = trust_cmd.cmd_trust(args, None)
    assert rc == 2
    assert "requires an active Veles project" in capsys.readouterr().err


# ---- revoke ----


def test_revoke_both_default(project: Project, capsys) -> None:
    user = TrustStore.load(user_trust_path())
    user.grant("run_shell")
    proj = TrustStore.load(project.trust_path)
    proj.grant("run_shell")
    args = _ns(trust_command="revoke", tool="run_shell", scope="both")
    rc = trust_cmd.cmd_trust(args, project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "user scope" in out
    assert "project scope" in out
    assert not TrustStore.load(user_trust_path()).is_granted("run_shell")
    assert not TrustStore.load(project.trust_path).is_granted("run_shell")


def test_revoke_user_only(project: Project, capsys) -> None:
    user = TrustStore.load(user_trust_path())
    user.grant("run_shell")
    proj = TrustStore.load(project.trust_path)
    proj.grant("run_shell")
    args = _ns(trust_command="revoke", tool="run_shell", scope="user")
    rc = trust_cmd.cmd_trust(args, project)
    assert rc == 0
    assert not TrustStore.load(user_trust_path()).is_granted("run_shell")
    assert TrustStore.load(project.trust_path).is_granted("run_shell")


def test_revoke_missing_grant_returns_1(project: Project, capsys) -> None:
    args = _ns(trust_command="revoke", tool="ghost", scope="both")
    rc = trust_cmd.cmd_trust(args, project)
    assert rc == 1
    assert "no grant" in capsys.readouterr().err


# ---- clear ----


def test_clear_all_scopes(project: Project, capsys) -> None:
    user = TrustStore.load(user_trust_path())
    user.grant("a")
    user.grant("b")
    proj = TrustStore.load(project.trust_path)
    proj.grant("x")
    args = _ns(trust_command="clear", scope="all")
    rc = trust_cmd.cmd_trust(args, project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "cleared all user-scope" in out
    assert "cleared all project-scope" in out


def test_clear_project_only(project: Project, capsys) -> None:
    user = TrustStore.load(user_trust_path())
    user.grant("a")
    proj = TrustStore.load(project.trust_path)
    proj.grant("x")
    args = _ns(trust_command="clear", scope="project")
    rc = trust_cmd.cmd_trust(args, project)
    assert rc == 0
    assert TrustStore.load(user_trust_path()).is_granted("a")
    assert not TrustStore.load(project.trust_path).is_granted("x")


def test_clear_empty_scope_returns_1(project: Project, capsys) -> None:
    args = _ns(trust_command="clear", scope="all")
    rc = trust_cmd.cmd_trust(args, project)
    assert rc == 1
    assert "no grants to clear" in capsys.readouterr().err
