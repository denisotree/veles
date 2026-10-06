"""Approval without a terminal (integrator report V-1/V-4, 2026-10-06): a deploy script
approves a module or a tool by the hash it reviewed — `--sha256` fails if the code
changed — while `--yes` without a TTY no longer approves whatever is on disk (an agent's
`run_shell` has no TTY either). Under pytest stdin is not a TTY, as in a container."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli import main
from veles.cli._project import _load_project_modules
from veles.core.project import Project, init_project
from veles.core.registry.hashing import tree_sha256
from veles.core.tools.approvals import file_sha256, is_approved

_MODULE = {
    "module.toml": '[module]\nname = "{name}"\ndescription = "d"\nentrypoint = "m.py:register"\n',
    "m.py": "def register(api):\n    api.add_hook('pre_turn', lambda **kw: None)\n",
}
_TOOL = (
    "from veles.core.tools.registry import tool\n\n"
    '@tool()\ndef hello() -> str:\n    """Hi."""\n    return "hi"\n'
)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    p = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(p.root)
    return p


def _module(project: Project, name: str) -> Path:
    d = project.modules_dir / name
    d.mkdir(parents=True)
    for rel, body in _MODULE.items():
        (d / rel).write_text(body.replace("{name}", name), encoding="utf-8")
    return d


def _tool(project: Project) -> Path:
    f = project.state_dir / "tools" / "hello.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(_TOOL, encoding="utf-8")
    return f


def test_module_show_prints_the_full_hash(project: Project, capsys) -> None:
    digest = tree_sha256(_module(project, "guard"))
    assert main(["module", "show", "guard"]) == 0
    assert digest in capsys.readouterr().out


def test_a_module_is_approved_by_its_reviewed_hash(project: Project) -> None:
    digest = tree_sha256(_module(project, "guard"))
    assert main(["module", "approve", "guard", "--sha256", digest]) == 0
    assert _load_project_modules(project).modules == ["guard"]


def test_a_changed_module_is_not_approved_by_an_old_hash(project: Project, capsys) -> None:
    d = _module(project, "guard")
    reviewed = tree_sha256(d)
    (d / "m.py").write_text(_MODULE["m.py"] + "# changed\n", encoding="utf-8")
    assert main(["module", "approve", "guard", "--sha256", reviewed]) == 1
    assert "changed" in capsys.readouterr().err
    assert _load_project_modules(project).modules == []


def test_module_approve_without_a_terminal_points_to_sha256(project: Project, capsys) -> None:
    _module(project, "guard")
    assert main(["module", "approve", "guard"]) == 1
    assert "--sha256" in capsys.readouterr().err


def test_module_approve_all_asks_for_each(project: Project, monkeypatch) -> None:
    from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer

    _module(project, "a")
    _module(project, "b")
    asked: list[str] = []
    token = set_critical_confirmer(lambda op, summary: asked.append(op) or True)
    try:
        assert main(["module", "approve", "--all"]) == 0
    finally:
        reset_critical_confirmer(token)
    assert asked == ["approve module a", "approve module b"]
    assert sorted(_load_project_modules(project).modules) == ["a", "b"]


def test_tool_approve_lists_the_full_hash(project: Project, capsys) -> None:
    f = _tool(project)
    assert main(["tool", "approve"]) == 0
    assert file_sha256(f) in capsys.readouterr().out


def test_a_tool_is_approved_by_its_reviewed_hash(project: Project) -> None:
    f = _tool(project)
    assert main(["tool", "approve", "hello", "--sha256", file_sha256(f)]) == 0
    assert is_approved(f)


def test_a_changed_tool_is_not_approved_by_an_old_hash(project: Project, capsys) -> None:
    f = _tool(project)
    reviewed = file_sha256(f)
    f.write_text(_TOOL + "# changed\n", encoding="utf-8")
    assert main(["tool", "approve", "hello", "--sha256", reviewed]) == 1
    assert "changed" in capsys.readouterr().err
    assert not is_approved(f)


def test_tool_approve_yes_needs_a_terminal(project: Project, capsys) -> None:
    """`--yes` without a TTY approved every file on disk — the agent's own included."""
    f = _tool(project)
    assert main(["tool", "approve", "--all", "--yes"]) == 1
    assert "--sha256" in capsys.readouterr().err
    assert not is_approved(f)


@pytest.mark.parametrize("kind", ["module", "tool"])
def test_the_agents_shell_cannot_approve(project: Project, monkeypatch, capsys, kind) -> None:
    """`--sha256` works without a TTY, so the agent's `run_shell` could read the hash and
    approve its own code; its commands carry VELES_AGENT_SHELL and approval refuses."""
    if kind == "module":
        digest = tree_sha256(_module(project, "guard"))
        argv = ["module", "approve", "guard"]
    else:
        digest = file_sha256(_tool(project))
        argv = ["tool", "approve", "hello"]
    monkeypatch.setenv("VELES_AGENT_SHELL", "1")
    assert main([*argv, "--sha256", digest]) == 1
    assert "agent" in capsys.readouterr().err
    assert _load_project_modules(project).modules == []
    assert not is_approved(project.state_dir / "tools" / "hello.py")


def test_run_shell_marks_its_commands(project: Project) -> None:
    from veles.core.context import reset_active_project, set_active_project
    from veles.core.tools.builtin.run_shell import run_shell

    token = set_active_project(project)
    try:
        out = run_shell('printf "<%s>" "$VELES_AGENT_SHELL"')
    finally:
        reset_active_project(token)
    assert out.startswith("<1>")


def test_promote_does_not_approve_an_unapproved_tool(project: Project, monkeypatch) -> None:
    """Promote carries an approval to the new path; it must not create one."""
    from veles.core.user_paths import user_home

    _tool(project)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert main(["tool", "promote", "hello", "--yes"]) == 0
    assert not is_approved(user_home() / "tools" / "hello.py")


def test_tool_approve_yes_still_works_at_a_terminal(project: Project, monkeypatch) -> None:
    f = _tool(project)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert main(["tool", "approve", "--all", "--yes"]) == 0
    assert is_approved(f)
