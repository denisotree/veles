"""M157 — `veles mcp {list,test}` CLI verb tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli.commands import mcp as mcp_cmd
from veles.core.project import Project, init_project


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


def _ns(**fields):
    return type("A", (), fields)()


def _write_config(project: Project, text: str) -> None:
    project.state_dir.mkdir(parents=True, exist_ok=True)
    (project.state_dir / "config.toml").write_text(text, encoding="utf-8")


# ---- list ----


def test_list_no_config_friendly_message(project: Project, capsys) -> None:
    rc = mcp_cmd.cmd_mcp(_ns(mcp_command="list", connect_timeout=5.0), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "no MCP servers configured" in out
    assert "[mcp.servers.<name>]" in out


def test_list_nonexistent_command_shows_failed_rc0(project: Project, capsys) -> None:
    _write_config(
        project,
        """
[mcp.servers.ghost]
command = "/nonexistent/veles-m157-no-such-binary"
connect_timeout_s = 10
""",
    )
    rc = mcp_cmd.cmd_mcp(_ns(mcp_command="list", connect_timeout=10.0), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "ghost" in out
    assert "failed" in out


def test_list_disabled_server_marked(project: Project, capsys) -> None:
    _write_config(
        project,
        """
[mcp.servers.off]
command = "echo"
enabled = false
""",
    )
    rc = mcp_cmd.cmd_mcp(_ns(mcp_command="list", connect_timeout=5.0), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "off" in out
    assert "disabled" in out


# ---- test ----


def test_test_unknown_server_rc2(project: Project, capsys) -> None:
    _write_config(project, '[mcp.servers.known]\ncommand = "echo"\n')
    rc = mcp_cmd.cmd_mcp(_ns(mcp_command="test", server="mystery"), project)
    assert rc == 2
    err = capsys.readouterr().err
    assert "mystery" in err
    assert "known" in err


def test_test_connect_failure_rc1(project: Project, capsys) -> None:
    _write_config(
        project,
        """
[mcp.servers.ghost]
command = "/nonexistent/veles-m157-no-such-binary"
connect_timeout_s = 10
""",
    )
    rc = mcp_cmd.cmd_mcp(_ns(mcp_command="test", server="ghost"), project)
    assert rc == 1
    assert "could not connect" in capsys.readouterr().err


def test_test_disabled_server_rc1(project: Project, capsys) -> None:
    _write_config(
        project,
        """
[mcp.servers.off]
command = "echo"
enabled = false
""",
    )
    rc = mcp_cmd.cmd_mcp(_ns(mcp_command="test", server="off"), project)
    assert rc == 1
    assert "disabled" in capsys.readouterr().err


# ---- parser wiring ----


def test_parser_accepts_mcp_verbs() -> None:
    from veles.cli._parsers import build_parser

    parser = build_parser()
    args = parser.parse_args(["mcp", "list"])
    assert args.command == "mcp"
    assert args.mcp_command == "list"
    args = parser.parse_args(["mcp", "test", "gh"])
    assert args.mcp_command == "test"
    assert args.server == "gh"
