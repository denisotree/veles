"""M157 — `[mcp.servers.*]` client config parsing tests.

(`tests/test_mcp_config.py` covers the MCP *server* side — the
claude-cli/gemini-cli descriptor builder; this file is the client.)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from veles.core.project import Project, init_project
from veles.mcp.config import (
    DEFAULT_CONNECT_TIMEOUT_S,
    DEFAULT_TIMEOUT_S,
    interpolate_env,
    load_disabled_tools,
    load_mcp_config,
)


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


def _write_config(project: Project, text: str) -> None:
    project.state_dir.mkdir(parents=True, exist_ok=True)
    (project.state_dir / "config.toml").write_text(text, encoding="utf-8")


# ---- happy paths ----


def test_no_config_file_yields_empty(project: Project) -> None:
    assert load_mcp_config(project) == {}


def test_no_mcp_section_yields_empty(project: Project) -> None:
    _write_config(project, '[provider]\ndefault = "openrouter"\n')
    assert load_mcp_config(project) == {}


def test_valid_stdio_server(project: Project) -> None:
    _write_config(
        project,
        """
[mcp.servers.files]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
env = { LOG_LEVEL = "debug" }
timeout_s = 60
connect_timeout_s = 5
""",
    )
    cfgs = load_mcp_config(project)
    assert set(cfgs) == {"files"}
    cfg = cfgs["files"]
    assert cfg.transport == "stdio"
    assert cfg.command == "npx"
    assert cfg.args == ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
    assert cfg.env == {"LOG_LEVEL": "debug"}
    assert cfg.timeout_s == 60.0
    assert cfg.connect_timeout_s == 5.0
    assert cfg.enabled is True


def test_valid_http_server_with_defaults(project: Project) -> None:
    _write_config(
        project,
        """
[mcp.servers.docs]
transport = "http"
url = "http://localhost:8000/mcp"
""",
    )
    cfg = load_mcp_config(project)["docs"]
    assert cfg.transport == "http"
    assert cfg.url == "http://localhost:8000/mcp"
    assert cfg.timeout_s == DEFAULT_TIMEOUT_S
    assert cfg.connect_timeout_s == DEFAULT_CONNECT_TIMEOUT_S


def test_disabled_server_kept_with_flag(project: Project) -> None:
    _write_config(
        project,
        """
[mcp.servers.off]
command = "echo"
enabled = false
""",
    )
    cfg = load_mcp_config(project)["off"]
    assert cfg.enabled is False


# ---- env interpolation ----


def test_env_interpolation_set_var(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("M157_TOKEN", "sekret")
    _write_config(
        project,
        """
[mcp.servers.gh]
command = "gh-mcp"
args = ["--token", "${M157_TOKEN}"]
env = { API_KEY = "${M157_TOKEN}" }
""",
    )
    cfg = load_mcp_config(project)["gh"]
    assert cfg.args == ["--token", "sekret"]
    assert cfg.env == {"API_KEY": "sekret"}


def test_env_interpolation_unset_var_warns_and_empties(
    project: Project, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("M157_MISSING", raising=False)
    with caplog.at_level(logging.WARNING, logger="veles.mcp.config"):
        assert interpolate_env("pre-${M157_MISSING}-post") == "pre--post"
    assert any("M157_MISSING" in rec.message for rec in caplog.records)


# ---- validation / skips ----


def test_unknown_transport_skipped(project: Project, caplog: pytest.LogCaptureFixture) -> None:
    _write_config(
        project,
        """
[mcp.servers.weird]
transport = "carrier-pigeon"
command = "coo"
""",
    )
    with caplog.at_level(logging.WARNING, logger="veles.mcp.config"):
        assert load_mcp_config(project) == {}
    assert any("unknown transport" in rec.message for rec in caplog.records)


def test_stdio_without_command_skipped(project: Project, caplog: pytest.LogCaptureFixture) -> None:
    _write_config(project, '[mcp.servers.nocmd]\nargs = ["x"]\n')
    with caplog.at_level(logging.WARNING, logger="veles.mcp.config"):
        assert load_mcp_config(project) == {}
    assert any("requires `command`" in rec.message for rec in caplog.records)


def test_http_without_url_skipped(project: Project, caplog: pytest.LogCaptureFixture) -> None:
    _write_config(project, '[mcp.servers.nourl]\ntransport = "sse"\n')
    with caplog.at_level(logging.WARNING, logger="veles.mcp.config"):
        assert load_mcp_config(project) == {}
    assert any("requires `url`" in rec.message for rec in caplog.records)


def test_bad_server_name_skipped(project: Project, caplog: pytest.LogCaptureFixture) -> None:
    _write_config(project, '[mcp.servers."has space"]\ncommand = "x"\n')
    with caplog.at_level(logging.WARNING, logger="veles.mcp.config"):
        assert load_mcp_config(project) == {}


def test_non_numeric_timeout_falls_back(project: Project) -> None:
    _write_config(
        project,
        """
[mcp.servers.t]
command = "x"
timeout_s = "soon"
""",
    )
    assert load_mcp_config(project)["t"].timeout_s == DEFAULT_TIMEOUT_S


# ---- disabled_tools ----


def test_disabled_tools_loaded(project: Project) -> None:
    _write_config(
        project,
        """
[mcp]
disabled_tools = { gh = ["delete_repo", "force_push"], docs = [] }

[mcp.servers.gh]
command = "gh-mcp"
""",
    )
    assert load_disabled_tools(project) == {
        "gh": ["delete_repo", "force_push"],
        "docs": [],
    }


def test_disabled_tools_absent_yields_empty(project: Project) -> None:
    _write_config(project, '[mcp.servers.gh]\ncommand = "gh-mcp"\n')
    assert load_disabled_tools(project) == {}
