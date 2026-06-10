"""M120c: end-to-end agent-generated tool lifecycle.

The full VISION §5.4 contract requires the agent to:
1. Recognise a repeating need ("the user asked X kind of thing 3
   times now").
2. Generate a clean python tool, write it to `<cwd>/.veles/tools/`.
3. Have the next agent session pick it up automatically and call it
   without further user setup.

A genuine "LLM writes the script" check needs a live provider — too
flaky for the regression suite. What we test here is everything
*around* that LLM step, simulating the file write as if the LLM had
done it. The lifecycle that matters:

- The `tool_authoring` skill is discoverable via the builtin skills
  mount (M120b).
- A `.py` file dropped into `<project>/.veles/tools/` by the agent
  gets picked up by the loader (M120.2) on the next bootstrap.
- The persistence layer (M120.1) records the new tool's scope and
  origin.
- The tool is dispatchable through the in-memory `Registry`.
- Telemetry from a real invocation (`record_use`) lands so the
  `veles tool show` / `list` surfaces work.
- `veles tool promote` flips the catalogue scope and moves the file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli.commands.tool import cmd_tool
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.skills import mount_builtin_skills
from veles.core.tools.loader import load_into_registry
from veles.core.tools.persistence import (
    get_tool,
    list_tools,
    record_use,
    telemetry,
)
from veles.core.tools.registry import Registry


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def _ns(**fields):
    return type("A", (), fields)()


# The body an LLM would produce by following `tool_authoring`'s
# SKILL.md instructions. Self-contained, typed, decorated.
_AGENT_GENERATED_TOOL = '''
"""Count occurrences of a substring in a string."""

from __future__ import annotations

from veles.core.tools.registry import tool


@tool()
def count_substrings(haystack: str, needle: str) -> int:
    """Return how many non-overlapping times `needle` appears in `haystack`.

    Use when you need a quick count without spawning a shell. Returns 0
    when `needle` is empty.
    """
    if not needle:
        return 0
    return haystack.count(needle)
'''


# ---- the lifecycle ----


def test_tool_authoring_skill_is_discoverable() -> None:
    """Step 0: the builtin skill exists so the agent can invoke it."""
    skills = mount_builtin_skills()
    names = {s.name for s in skills}
    assert "tool_authoring" in names


def test_agent_generated_file_loads_into_registry(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Step 1: a .py file the agent wrote becomes a registered tool."""
    project = init_project(tmp_path / "proj", name="proj")
    tools_dir = project.state_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "count_substrings.py").write_text(_AGENT_GENERATED_TOOL, encoding="utf-8")

    registry = Registry()
    store = SessionStore(project.memory_db_path)
    report = load_into_registry(
        registry,
        project_tools_dir=tools_dir,
        conn=store._conn,
    )

    assert any(lt.entry.name == "count_substrings" for lt in report.loaded)
    assert "count_substrings" in registry.list_names()


def test_loaded_tool_dispatchable(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Step 2: agent calls the loaded tool through the registry's
    dispatch path. Returns the function's actual result."""
    project = init_project(tmp_path / "proj", name="proj")
    tools_dir = project.state_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "count_substrings.py").write_text(_AGENT_GENERATED_TOOL, encoding="utf-8")

    registry = Registry()
    load_into_registry(registry, project_tools_dir=tools_dir)

    result = registry.dispatch(
        "count_substrings", {"haystack": "abcabcabc", "needle": "abc"}
    )
    # `dispatch` returns the str form
    assert result == "3"


def test_tool_catalogued_with_correct_scope_and_origin(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Step 3: persistence layer records scope/origin so `veles tool
    list` shows it as agent-generated and project-scoped."""
    project = init_project(tmp_path / "proj", name="proj")
    tools_dir = project.state_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "count_substrings.py").write_text(_AGENT_GENERATED_TOOL, encoding="utf-8")

    registry = Registry()
    store = SessionStore(project.memory_db_path)
    load_into_registry(registry, project_tools_dir=tools_dir, conn=store._conn)

    rec = get_tool(store._conn, "count_substrings")
    assert rec is not None
    assert rec.scope == "project"
    assert rec.origin == "agent-generated"
    # Description came from the function's docstring head
    assert rec.description and rec.description.startswith("Return how many")


def test_telemetry_accumulates_after_invocations(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Step 4: every dispatch increments use_count via record_use; the
    catalogue's success_rate / last_used reflect actual usage."""
    project = init_project(tmp_path / "proj", name="proj")
    tools_dir = project.state_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "count_substrings.py").write_text(_AGENT_GENERATED_TOOL, encoding="utf-8")

    registry = Registry()
    store = SessionStore(project.memory_db_path)
    load_into_registry(registry, project_tools_dir=tools_dir, conn=store._conn)

    for ok in (True, True, False):
        record_use(
            store._conn,
            tool_name="count_substrings",
            ok=ok,
            latency_ms=10,
        )
    t = telemetry(store._conn, "count_substrings")
    assert t.use_count == 3
    assert t.success_count == 2
    assert t.success_rate == pytest.approx(2 / 3)


def test_promote_round_trip(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Step 5: `veles tool promote <name>` moves the file to user
    scope and rewrites the catalogue row. Tools survive across
    projects after promotion (the next project's loader picks them
    up from the user dir)."""
    project = init_project(tmp_path / "proj", name="proj")
    tools_dir = project.state_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    src = tools_dir / "count_substrings.py"
    src.write_text(_AGENT_GENERATED_TOOL, encoding="utf-8")

    registry = Registry()
    store = SessionStore(project.memory_db_path)
    load_into_registry(registry, project_tools_dir=tools_dir, conn=store._conn)
    store._conn.close()

    # Promote (skipping confirmation)
    rc = cmd_tool(_ns(tool_command="promote", name="count_substrings", yes=True), project)
    assert rc == 0

    # File moved out of project, into user dir
    assert not src.exists()
    user_path = isolated_home / ".veles" / "tools" / "count_substrings.py"
    assert user_path.is_file()

    # Catalogue scope flipped to "user"
    store2 = SessionStore(project.memory_db_path)
    rec = get_tool(store2._conn, "count_substrings")
    assert rec is not None
    assert rec.scope == "user"
    assert rec.origin == "manual"
    store2._conn.close()

    # A second project picks the promoted tool up from the user dir
    project2 = init_project(tmp_path / "proj2", name="proj2")
    registry2 = Registry()
    store_b = SessionStore(project2.memory_db_path)
    load_into_registry(
        registry2,
        project_tools_dir=project2.state_dir / "tools",
        user_tools_dir=isolated_home / ".veles" / "tools",
        conn=store_b._conn,
    )
    assert "count_substrings" in registry2.list_names()
    rec_in_b = get_tool(store_b._conn, "count_substrings")
    assert rec_in_b is not None
    assert rec_in_b.scope == "user"


# ---- the full surface ----


def test_full_lifecycle_in_one_go(
    isolated_home: Path, tmp_path: Path
) -> None:
    """The condensed VISION §5.4 success path:
    write → load → dispatch → telemetry → catalogue → promote."""
    project = init_project(tmp_path / "proj", name="proj")
    tools_dir = project.state_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "count_substrings.py").write_text(_AGENT_GENERATED_TOOL, encoding="utf-8")

    registry = Registry()
    store = SessionStore(project.memory_db_path)
    load_into_registry(registry, project_tools_dir=tools_dir, conn=store._conn)

    # Dispatch and record telemetry as a realistic agent would
    output = registry.dispatch(
        "count_substrings", {"haystack": "the quick brown fox", "needle": " "}
    )
    record_use(
        store._conn, tool_name="count_substrings", ok=True, latency_ms=2
    )

    assert output == "3"  # three spaces in "the quick brown fox"
    rows = list_tools(store._conn)
    assert any(r.name == "count_substrings" for r in rows)
    t = telemetry(store._conn, "count_substrings")
    assert t.use_count == 1 and t.success_count == 1
