"""M120.5: `veles tool {list,show,promote}` CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli.commands.tool import cmd_tool
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.tools.persistence import (
    get_tool,
    record_use,
    upsert_tool,
)
from veles.core.tools.registry import ToolEntry


# ---- helpers ----


def _entry(name: str, description: str = "") -> ToolEntry:
    return ToolEntry(
        name=name,
        description=description or f"tool {name}",
        parameter_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda **_kw: "",
        is_async=False,
    )


def _ns(**fields):
    return type("A", (), fields)()


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture()
def project(tmp_path: Path):
    p = init_project(tmp_path / "proj", name="proj")
    yield p


# ---- list ----


def test_list_with_empty_catalogue(project, capsys) -> None:
    rc = cmd_tool(_ns(tool_command="list"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "no tools" in out.lower()


def test_list_prints_catalogued_tools(project, capsys) -> None:
    store = SessionStore(project.memory_db_path)
    upsert_tool(store._conn, _entry("alpha"), scope="builtin", origin="builtin")
    upsert_tool(
        store._conn, _entry("custom"), scope="project", origin="agent-generated"
    )
    record_use(store._conn, tool_name="alpha", ok=True, latency_ms=10)
    record_use(store._conn, tool_name="alpha", ok=False, latency_ms=5)
    store._conn.close()

    rc = cmd_tool(_ns(tool_command="list"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha" in out
    assert "custom" in out
    assert "builtin" in out
    assert "project" in out
    # alpha has 2 uses with 50% success
    assert "2" in out
    assert "50%" in out


# ---- show ----


def test_show_unknown_returns_error(project, capsys) -> None:
    rc = cmd_tool(_ns(tool_command="show", name="ghost"), project)
    assert rc == 1
    err = capsys.readouterr().err
    assert "ghost" in err


def test_show_prints_metadata_and_telemetry(project, capsys) -> None:
    store = SessionStore(project.memory_db_path)
    upsert_tool(
        store._conn,
        _entry("inspector", description="inspect things"),
        scope="builtin",
        origin="builtin",
    )
    record_use(store._conn, tool_name="inspector", ok=True, latency_ms=15)
    store._conn.close()

    rc = cmd_tool(_ns(tool_command="show", name="inspector"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "inspector" in out
    assert "inspect things" in out
    assert "builtin" in out
    assert "use_count" in out
    assert "1" in out  # one use recorded


def test_show_renders_inheritance_chain(project, capsys) -> None:
    store = SessionStore(project.memory_db_path)
    upsert_tool(store._conn, _entry("io_base"))
    upsert_tool(
        store._conn,
        _entry("write_log"),
        scope="project",
        origin="agent-generated",
        base_tool_name="io_base",
    )
    store._conn.close()

    rc = cmd_tool(_ns(tool_command="show", name="write_log"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "inherits" in out
    assert "io_base" in out


# ---- promote ----


def test_promote_missing_file_errors(project, capsys) -> None:
    rc = cmd_tool(
        _ns(tool_command="promote", name="missing", yes=True), project
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "no project-level tool" in err.lower()


def test_promote_moves_file_and_updates_scope(
    project, isolated_home: Path, capsys
) -> None:
    """File moves from project to user dir; catalogue row's scope flips
    to 'user' and origin to 'manual'."""
    project_tools = project.state_dir / "tools"
    project_tools.mkdir(parents=True, exist_ok=True)
    tool_file = project_tools / "demo.py"
    tool_file.write_text("# stub\n", encoding="utf-8")

    store = SessionStore(project.memory_db_path)
    upsert_tool(
        store._conn, _entry("demo"), scope="project", origin="agent-generated"
    )
    store._conn.close()

    rc = cmd_tool(
        _ns(tool_command="promote", name="demo", yes=True), project
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "promoted" in out

    # File moved out of project, into user dir
    assert not tool_file.exists()
    user_dest = isolated_home / ".veles" / "tools" / "demo.py"
    assert user_dest.is_file()

    # Catalogue scope flipped
    store2 = SessionStore(project.memory_db_path)
    rec = get_tool(store2._conn, "demo")
    assert rec is not None
    assert rec.scope == "user"
    assert rec.origin == "manual"


def test_promote_refuses_to_overwrite_existing_user_file(
    project, isolated_home: Path, capsys
) -> None:
    project_tools = project.state_dir / "tools"
    project_tools.mkdir(parents=True, exist_ok=True)
    (project_tools / "demo.py").write_text("# project version\n", encoding="utf-8")
    user_dir = isolated_home / ".veles" / "tools"
    user_dir.mkdir(parents=True)
    (user_dir / "demo.py").write_text("# pre-existing user version\n", encoding="utf-8")

    rc = cmd_tool(
        _ns(tool_command="promote", name="demo", yes=True), project
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "already exists" in err.lower()
    # Project file untouched
    assert (project_tools / "demo.py").is_file()


def test_promote_prompt_n_aborts(
    project, isolated_home: Path, capsys, monkeypatch
) -> None:
    project_tools = project.state_dir / "tools"
    project_tools.mkdir(parents=True, exist_ok=True)
    (project_tools / "demo.py").write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    rc = cmd_tool(
        _ns(tool_command="promote", name="demo", yes=False), project
    )
    assert rc == 0
    assert "aborted" in capsys.readouterr().out.lower()
    # File untouched
    assert (project_tools / "demo.py").is_file()


def test_promote_yes_flag_bypasses_prompt(
    project, isolated_home: Path, capsys, monkeypatch
) -> None:
    project_tools = project.state_dir / "tools"
    project_tools.mkdir(parents=True, exist_ok=True)
    (project_tools / "demo.py").write_text("# stub\n", encoding="utf-8")

    def _boom(_prompt: str) -> str:
        raise AssertionError("input() must not be invoked when --yes is set")

    monkeypatch.setattr("builtins.input", _boom)
    rc = cmd_tool(
        _ns(tool_command="promote", name="demo", yes=True), project
    )
    assert rc == 0
    user_dest = isolated_home / ".veles" / "tools" / "demo.py"
    assert user_dest.is_file()
