"""M325: writing a tool file tells the model, in the same turn, whether it is one.

The reported failure: a model that never called `tool_authoring` wrote an argparse
script into `.veles/tools/` with `write_file`, ran it with `run_shell`, and told
the user "tool created" — Veles said nothing, and the registry stayed empty. Even a
correct `@tool` file loads only after a human approves it, which the model did not
know either.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import veles.core.tools.builtin  # noqa: F401  (fires registration)
from veles.core.context import reset_active_project, set_active_project
from veles.core.project import Project, init_project
from veles.core.tools.loader import tool_file_problem
from veles.core.tools.registry import registry

_TOOL = '''from veles.core.tools.registry import tool


@tool()
def word_freq(path: str, top: int = 10) -> str:
    """Top-N words."""
    return ""
'''

_SCRIPT = """import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()


if __name__ == "__main__":
    main()
"""


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(project)
    yield project
    reset_active_project(token)


def _write(path: str, content: str) -> str:
    return registry.get("write_file").handler(path=path, content=content)


def test_a_script_in_the_tools_dir_is_flagged(project: Project) -> None:
    out = _write(str(project.state_dir / "tools" / "word_freq.py"), _SCRIPT)
    assert "word_freq.py defines no @tool function" in out
    assert "veles tool approve word_freq" in out


def test_a_real_tool_gets_only_the_approval_note(project: Project) -> None:
    out = _write(str(project.state_dir / "tools" / "word_freq.py"), _TOOL)
    assert "warning" not in out
    assert "veles tool approve word_freq" in out


def test_other_files_are_unchanged(project: Project) -> None:
    out = _write(str(project.root / "notes.py"), _SCRIPT)
    assert out.startswith("wrote") and "\n" not in out
    helper = _write(str(project.state_dir / "tools" / "_helpers.py"), _SCRIPT)
    assert "\n" not in helper  # `_`-files are never loaded, so nothing to say


def test_an_edit_that_adds_the_decorator_clears_the_warning(project: Project) -> None:
    path = project.state_dir / "tools" / "word_freq.py"
    _write(str(path), _TOOL.replace("@tool()\n", ""))
    out = registry.get("edit_file").handler(
        path=str(path), old_string="def word_freq", new_string="@tool()\ndef word_freq"
    )
    assert "warning" not in out
    assert "veles tool approve word_freq" in out


@pytest.mark.parametrize(
    "decorator", ["@tool", "@tool()", "@tool(sensitive=True)", "@registry.tool()"]
)
def test_tool_decorator_spellings(decorator: str) -> None:
    assert tool_file_problem(f"{decorator}\ndef f() -> str:\n    return ''\n") is None


def test_async_tools_count() -> None:
    assert tool_file_problem("@tool()\nasync def f() -> str:\n    return ''\n") is None


def test_a_nested_tool_does_not_count() -> None:
    """The loader registers at import, so only a module-level function matters."""
    src = "def outer():\n    @tool()\n    def inner():\n        pass\n"
    assert tool_file_problem(src) == "defines no @tool function"


def test_a_syntax_error_is_named() -> None:
    problem = tool_file_problem("def broken(:\n")
    assert problem is not None and problem.startswith("does not parse (line 1")
