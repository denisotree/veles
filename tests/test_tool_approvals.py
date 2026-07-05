"""M199 — human-approved hashes gate self-authored tool execution.

Self-authored tools run module-level code at import. The loader refuses to exec
a file whose SHA-256 isn't recorded as approved, so injection-dropped code never
runs. The approval store must live OUTSIDE the agent-writable sandbox, or the
same write_file that drops evil.py could self-approve it — that invariant is the
whole security property, so it gets its own test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.tools.approvals import approve, file_sha256, is_approved


def test_unapproved_file_is_not_approved(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("VALUE = 1\n")
    assert is_approved(f) is False


def test_approve_then_is_approved(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("VALUE = 1\n")
    approve(f)
    assert is_approved(f) is True


def test_modified_after_approval_is_not_approved(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("VALUE = 1\n")
    approve(f)
    f.write_text("VALUE = 2  # any edit after approval invalidates the hash\n")
    assert is_approved(f) is False
    assert file_sha256(f) != ""


def test_agent_cannot_write_the_approval_store(tmp_path: Path) -> None:
    """THE invariant: the approval store is outside the agent's write sandbox,
    so write_file/run_shell cannot self-approve a just-written tool. With an
    active project the sandbox is {project root, ~/.veles/skills, ~/.veles/
    locales} — the store under ~/.veles/ is in none of them."""
    from veles.core.context import reset_active_project, set_active_project
    from veles.core.path_guard import SandboxViolation, resolve_safe
    from veles.core.project import init_project
    from veles.core.tools.approvals import store_path

    project = init_project(tmp_path / "proj", name="t")
    token = set_active_project(project)
    try:
        with pytest.raises(SandboxViolation):
            resolve_safe(store_path())
    finally:
        reset_active_project(token)


def test_loader_does_not_execute_unapproved_file(tmp_path: Path) -> None:
    """An unapproved tool file must never be imported — its module-level code
    does not run. A file that raises on import proves exec never happened."""
    from veles.core.tools.loader import load_into_registry
    from veles.core.tools.registry import Registry

    tools = tmp_path / "tools"
    tools.mkdir()
    evil = tools / "evil.py"
    evil.write_text("raise RuntimeError('module code executed')\n")

    reg = Registry()
    report = load_into_registry(reg, project_tools_dir=tools)

    assert report.errors == ()  # never imported → no import error either
    assert any(evil.name in str(p) for p in report.unapproved)


def test_loader_loads_an_approved_file(tmp_path: Path) -> None:
    from veles.core.tools.loader import load_into_registry
    from veles.core.tools.registry import Registry

    tools = tmp_path / "tools"
    tools.mkdir()
    good = tools / "greet.py"
    good.write_text(
        "from veles.core.tools import tool\n\n\n"
        "@tool(name='greet', description='say hi')\n"
        "def greet():\n"
        "    return 'hi'\n"
    )
    approve(good)

    reg = Registry()
    report = load_into_registry(reg, project_tools_dir=tools)

    assert "greet" in reg.list_names()
    assert report.unapproved == ()
