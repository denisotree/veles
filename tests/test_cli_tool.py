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


def _write_project_tool(project, name: str, description: str = "a project tool") -> Path:
    """Put an approved file-based tool in the project, the way the agent would."""
    from veles.core.tools.approvals import approve

    tools_dir = project.state_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    path = tools_dir / f"{name}.py"
    path.write_text(
        "from veles.core.tools.registry import tool\n\n\n"
        f'@tool(name="{name}", description="{description}")\n'
        "def handler(text: str) -> str:\n"
        '    """Echo."""\n'
        "    return text\n",
        encoding="utf-8",
    )
    approve(path)
    return path


def test_list_reports_builtins_not_the_catalogue(project, capsys) -> None:
    """M251: the catalogue is empty here, exactly as in the container that
    reported `no tools catalogued yet` — but the agent can see its builtins,
    so the command must say so."""
    rc = cmd_tool(_ns(tool_command="list"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "read_file" in out
    assert "builtin" in out
    assert "no tools" not in out.lower()


def test_list_includes_file_based_tools_with_scope(project, isolated_home, capsys) -> None:
    _write_project_tool(project, "echo_back")
    rc = cmd_tool(_ns(tool_command="list"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "echo_back" in out
    assert "project" in out


def test_list_does_not_mutate_the_global_registry(project, isolated_home) -> None:
    """`load_into_registry` pops a builtin that a project tool shadows, and the
    builtin registry is a module-level singleton — so listing must work on a
    copy, or `veles tool list` inside a REPL would strip the agent's own
    tools."""
    from veles.core.tools import registry as builtin_registry

    _write_project_tool(project, "read_file")  # deliberately shadows a builtin
    before = sorted(builtin_registry.list_names())
    cmd_tool(_ns(tool_command="list"), project)
    assert sorted(builtin_registry.list_names()) == before


def test_list_warns_about_unapproved_files(project, isolated_home, capsys) -> None:
    """M199 skips an unapproved file's import entirely — the agent sees neither
    the tool nor a refusal. `tool list` is where you come looking for it."""
    tools_dir = project.state_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "sketchy.py").write_text("x = 1\n", encoding="utf-8")

    rc = cmd_tool(_ns(tool_command="list"), project)
    assert rc == 0
    err = capsys.readouterr().err
    assert "sketchy" in err
    assert "unapproved" in err


def test_list_catalogues_file_based_tools(project, isolated_home) -> None:
    """The sync `cli/_runtime.py` never performed: after listing, the file-based
    tool has a catalogue row, so telemetry has somewhere to land."""
    from veles.core.tools.persistence import get_tool

    _write_project_tool(project, "echo_back")
    cmd_tool(_ns(tool_command="list"), project)

    store = SessionStore(project.memory_db_path)
    try:
        rec = get_tool(store._conn, "echo_back")
    finally:
        store.close()
    assert rec is not None
    assert rec.scope == "project"


# ---- show ----


def test_show_unknown_returns_error(project, capsys) -> None:
    rc = cmd_tool(_ns(tool_command="show", name="ghost"), project)
    assert rc == 1
    err = capsys.readouterr().err
    assert "ghost" in err


def test_show_works_for_a_builtin(project, capsys) -> None:
    """M251: identity comes from the live registry. Reading it from the
    catalogue made `show` repeat `list`'s lie — a working builtin has no row
    there, so `veles tool show read_file` answered "no tool named …"."""
    rc = cmd_tool(_ns(tool_command="show", name="read_file"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "read_file" in out
    assert "builtin" in out
    assert "use_count" in out


def test_show_prints_telemetry(project, isolated_home, capsys) -> None:
    _write_project_tool(project, "inspector", description="inspect things")
    cmd_tool(_ns(tool_command="list"), project)  # catalogues it
    capsys.readouterr()

    store = SessionStore(project.memory_db_path)
    record_use(store._conn, tool_name="inspector", ok=True, latency_ms=15)
    store._conn.commit()
    store.close()

    rc = cmd_tool(_ns(tool_command="show", name="inspector"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "inspect things" in out
    assert "project" in out
    assert "use_count:     1" in out


def test_show_renders_inheritance_chain(project, isolated_home, capsys) -> None:
    """Inheritance lives only in the catalogue, so `show` still overlays it —
    the live registry supplies identity, the catalogue the relationships."""
    _write_project_tool(project, "write_log")
    cmd_tool(_ns(tool_command="list"), project)  # catalogues write_log
    capsys.readouterr()

    store = SessionStore(project.memory_db_path)
    upsert_tool(store._conn, _entry("io_base"))
    upsert_tool(
        store._conn,
        _entry("write_log"),
        scope="project",
        origin="agent-generated",
        base_tool_name="io_base",
    )
    store._conn.commit()
    store.close()

    rc = cmd_tool(_ns(tool_command="show", name="write_log"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "inherits" in out
    assert "io_base" in out


# ---- promote ----


def test_promote_missing_file_errors(project, capsys) -> None:
    rc = cmd_tool(_ns(tool_command="promote", name="missing", yes=True), project)
    assert rc == 1
    err = capsys.readouterr().err
    assert "no project-level tool" in err.lower()


def test_promote_moves_file_and_updates_scope(project, isolated_home: Path, capsys) -> None:
    """File moves from project to user dir; catalogue row's scope flips
    to 'user' and origin to 'manual'."""
    project_tools = project.state_dir / "tools"
    project_tools.mkdir(parents=True, exist_ok=True)
    tool_file = project_tools / "demo.py"
    tool_file.write_text("# stub\n", encoding="utf-8")

    store = SessionStore(project.memory_db_path)
    upsert_tool(store._conn, _entry("demo"), scope="project", origin="agent-generated")
    store._conn.close()

    rc = cmd_tool(_ns(tool_command="promote", name="demo", yes=True), project)
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

    rc = cmd_tool(_ns(tool_command="promote", name="demo", yes=True), project)
    assert rc == 1
    err = capsys.readouterr().err
    assert "already exists" in err.lower()
    # Project file untouched
    assert (project_tools / "demo.py").is_file()


def test_promote_prompt_n_aborts(project, isolated_home: Path, capsys, monkeypatch) -> None:
    project_tools = project.state_dir / "tools"
    project_tools.mkdir(parents=True, exist_ok=True)
    (project_tools / "demo.py").write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    rc = cmd_tool(_ns(tool_command="promote", name="demo", yes=False), project)
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
    rc = cmd_tool(_ns(tool_command="promote", name="demo", yes=True), project)
    assert rc == 0
    user_dest = isolated_home / ".veles" / "tools" / "demo.py"
    assert user_dest.is_file()
