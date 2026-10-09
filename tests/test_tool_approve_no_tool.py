"""M325: approving or loading a tool file that defines no `@tool` says so.

The reported failure, verbatim:

    $ veles tool approve word_freq --sha256 4ce278d6…
    approved word_freq.py (4ce278d6abbf…)          # exit 0
    $ veles tool list | grep word_freq
                                                   # empty — no tool, no reason

A human approved "a tool" that does not exist, and the next agent run saw neither
the tool nor an explanation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli import main
from veles.core.project import Project, init_project
from veles.core.tools.approvals import approve, file_sha256

_SCRIPT = "import argparse\n\n\ndef main():\n    argparse.ArgumentParser().parse_args()\n"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    p = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(p.root)
    return p


def _script(project: Project) -> Path:
    f = project.state_dir / "tools" / "word_freq.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(_SCRIPT, encoding="utf-8")
    return f


def test_approve_by_hash_warns_and_still_succeeds(project: Project, capsys) -> None:
    f = _script(project)
    assert main(["tool", "approve", "word_freq", "--sha256", file_sha256(f)]) == 0
    captured = capsys.readouterr()
    assert "approved word_freq.py" in captured.out
    assert "warning: word_freq.py defines no @tool function" in captured.err


def test_interactive_approve_warns_before_the_question(
    project: Project, capsys, monkeypatch
) -> None:
    _script(project)
    asked: list[str] = []
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "veles.cli._console.confirm", lambda prompt: asked.append(capsys.readouterr().err) or True
    )
    assert main(["tool", "approve", "word_freq"]) == 0
    assert "defines no @tool function" in asked[0]


def test_tool_list_names_the_file_and_the_reason(project: Project, capsys) -> None:
    approve(_script(project))
    assert main(["tool", "list"]) == 0
    assert "tool file word_freq.py NOT loaded: defines no @tool function" in (
        capsys.readouterr().err
    )


def test_an_agent_run_prints_it(project: Project, capsys) -> None:
    from veles.core.context import reset_active_project, set_active_project
    from veles.core.tools.registry import Registry
    from veles.runtime.registry import _load_file_tools

    approve(_script(project))
    token = set_active_project(project)
    try:
        _load_file_tools(Registry(), project)
    finally:
        reset_active_project(token)
    assert "warning: tool file word_freq.py not loaded: defines no @tool function" in (
        capsys.readouterr().err
    )
