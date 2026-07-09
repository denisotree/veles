"""M120.2: file-based tool loader.

We don't import a real Veles project — we fake `project/.veles/tools/`
and `user/.veles/tools/` directories with stub Python files, point the
loader at them, and verify what landed in the `Registry` and in the
`tools` table.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.tools.loader import LoadedTool, load_into_registry
from veles.core.tools.persistence import get_tool, list_tools
from veles.core.tools.registry import Registry


@pytest.fixture()
def conn(tmp_path: Path):
    store = SessionStore(tmp_path / "memory.db")
    yield store._conn
    store._conn.close()


def _write_tool(directory: Path, filename: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(body, encoding="utf-8")
    # M199: these tests exercise loading mechanics, which now require a human
    # approval before the loader will exec a self-authored file. Approve here so
    # the fixture represents an already-reviewed tool. (The gate itself — that an
    # UNapproved file is skipped — is covered in tests/test_tool_approvals.py.)
    from veles.core.tools.approvals import approve

    approve(path)
    return path


_BODY_HELLO = '''
from veles.core.tools.registry import tool

@tool()
def hello() -> str:
    """Say hi."""
    return "hi"
'''

_BODY_GREET = '''
from veles.core.tools.registry import tool

@tool()
def greet(name: str = "world") -> str:
    """Greet someone."""
    return f"hi {name}"
'''

_BODY_BROKEN = """
this is not valid python
"""


# ---- empty / missing dirs ----


def test_load_with_no_dirs_is_noop(tmp_path: Path) -> None:
    registry = Registry()
    report = load_into_registry(registry, project_tools_dir=None, user_tools_dir=None)
    assert report.loaded == ()
    assert report.errors == ()


def test_load_skips_nonexistent_directories(tmp_path: Path) -> None:
    """A path that doesn't exist isn't an error — there's no project
    tools yet, that's fine."""
    registry = Registry()
    report = load_into_registry(
        registry,
        project_tools_dir=tmp_path / "missing",
        user_tools_dir=tmp_path / "also_missing",
    )
    assert report.loaded == ()
    assert report.errors == ()


def test_load_skips_dunder_files(tmp_path: Path) -> None:
    """`_private.py` and `__init__.py` are not user tools."""
    project_tools = tmp_path / "project" / ".veles" / "tools"
    _write_tool(project_tools, "__init__.py", "")
    _write_tool(project_tools, "_helper.py", _BODY_HELLO)

    registry = Registry()
    report = load_into_registry(registry, project_tools_dir=project_tools)
    assert report.loaded == ()


# ---- happy path ----


def test_project_tool_loaded_and_registered(tmp_path: Path) -> None:
    project_tools = tmp_path / "project" / ".veles" / "tools"
    _write_tool(project_tools, "hello.py", _BODY_HELLO)

    registry = Registry()
    report = load_into_registry(registry, project_tools_dir=project_tools)
    assert len(report.loaded) == 1
    assert report.loaded[0].entry.name == "hello"
    assert report.loaded[0].scope == "project"
    assert report.loaded[0].origin == "agent-generated"
    # Registry can dispatch it
    assert registry.dispatch("hello", {}) == "hi"


def test_user_tool_loaded_and_registered(tmp_path: Path) -> None:
    user_tools = tmp_path / "user" / "tools"
    _write_tool(user_tools, "greet.py", _BODY_GREET)

    registry = Registry()
    report = load_into_registry(registry, user_tools_dir=user_tools)
    assert len(report.loaded) == 1
    assert report.loaded[0].scope == "user"
    assert report.loaded[0].origin == "manual"
    assert registry.dispatch("greet", {"name": "Veles"}) == "hi Veles"


def test_both_dirs_loaded(tmp_path: Path) -> None:
    project_tools = tmp_path / "project" / ".veles" / "tools"
    user_tools = tmp_path / "user" / "tools"
    _write_tool(project_tools, "hello.py", _BODY_HELLO)
    _write_tool(user_tools, "greet.py", _BODY_GREET)

    registry = Registry()
    report = load_into_registry(
        registry,
        project_tools_dir=project_tools,
        user_tools_dir=user_tools,
    )
    names = {lt.entry.name for lt in report.loaded}
    assert names == {"hello", "greet"}
    # scopes are tracked separately
    by_name = {lt.entry.name: lt.scope for lt in report.loaded}
    assert by_name["hello"] == "project"
    assert by_name["greet"] == "user"


# ---- shadowing / override ----


def test_project_tool_shadows_builtin(tmp_path: Path) -> None:
    """An existing builtin `hello` in the Registry gets displaced by a
    project file of the same name. Override recorded in the report."""
    from veles.core.tools.registry import ToolEntry

    registry = Registry()
    # Pre-existing "builtin" (simulated)
    registry.register(
        ToolEntry(
            name="hello",
            description="builtin hi",
            parameter_schema={"type": "object", "properties": {}, "required": []},
            handler=lambda **_kw: "builtin",
            is_async=False,
        )
    )

    project_tools = tmp_path / "project" / ".veles" / "tools"
    _write_tool(project_tools, "hello.py", _BODY_HELLO)
    report = load_into_registry(registry, project_tools_dir=project_tools)

    assert any(name == "hello" for name, _ in report.overridden)
    # Dispatch now goes through the project tool, not the builtin
    assert registry.dispatch("hello", {}) == "hi"


def test_project_shadows_user_when_both_present(tmp_path: Path) -> None:
    """Same name in both project and user dirs: project wins, user is
    reported as overridden."""
    body_project = '''
from veles.core.tools.registry import tool

@tool()
def echo() -> str:
    """project version."""
    return "project"
'''
    body_user = '''
from veles.core.tools.registry import tool

@tool()
def echo() -> str:
    """user version."""
    return "user"
'''
    project_tools = tmp_path / "project" / ".veles" / "tools"
    user_tools = tmp_path / "user" / "tools"
    _write_tool(project_tools, "echo.py", body_project)
    _write_tool(user_tools, "echo.py", body_user)

    registry = Registry()
    report = load_into_registry(
        registry,
        project_tools_dir=project_tools,
        user_tools_dir=user_tools,
    )
    assert registry.dispatch("echo", {}) == "project"
    # User scope override is recorded so the agent log isn't silent.
    assert any(scope == "project" for _, scope in report.overridden)


# ---- errors ----


def test_broken_python_file_recorded_as_error(tmp_path: Path) -> None:
    project_tools = tmp_path / "project" / ".veles" / "tools"
    _write_tool(project_tools, "broken.py", _BODY_BROKEN)
    _write_tool(project_tools, "hello.py", _BODY_HELLO)

    registry = Registry()
    report = load_into_registry(registry, project_tools_dir=project_tools)
    # The good file still loaded
    assert any(lt.entry.name == "hello" for lt in report.loaded)
    # The broken one is captured
    assert any("broken.py" in name for name, _ in report.errors)


# ---- persistence sync ----


def test_loaded_tool_landed_in_database(tmp_path: Path, conn) -> None:
    project_tools = tmp_path / "project" / ".veles" / "tools"
    _write_tool(project_tools, "hello.py", _BODY_HELLO)

    registry = Registry()
    load_into_registry(
        registry,
        project_tools_dir=project_tools,
        conn=conn,
    )
    rec = get_tool(conn, "hello")
    assert rec is not None
    assert rec.scope == "project"
    assert rec.origin == "agent-generated"


def test_load_does_not_write_to_db_when_conn_omitted(tmp_path: Path, conn) -> None:
    project_tools = tmp_path / "project" / ".veles" / "tools"
    _write_tool(project_tools, "hello.py", _BODY_HELLO)

    registry = Registry()
    load_into_registry(registry, project_tools_dir=project_tools, conn=None)
    # No row in the catalogue — registry-only mode.
    assert list_tools(conn) == []


def test_returned_loaded_tools_carry_source_path(tmp_path: Path) -> None:
    project_tools = tmp_path / "project" / ".veles" / "tools"
    src = _write_tool(project_tools, "hello.py", _BODY_HELLO)

    registry = Registry()
    report = load_into_registry(registry, project_tools_dir=project_tools)
    assert len(report.loaded) == 1
    lt = report.loaded[0]
    assert isinstance(lt, LoadedTool)
    assert lt.source == src
