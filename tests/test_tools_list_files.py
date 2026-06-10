"""Tests for the builtin list_files tool (M124-perm-unify)."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.path_guard import SandboxViolation
from veles.core.project import init_project


@pytest.fixture
def project(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    p = init_project(root, name="t")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def test_lists_direct_children(project) -> None:
    from veles.core.tools.builtin.list_files import list_files

    (project.root / "a.py").write_text("x")
    (project.root / "b.txt").write_text("yy")
    out = list_files(path=str(project.root))
    assert "f\t1\ta.py" in out
    assert "f\t2\tb.txt" in out


def test_lists_recursive_with_glob(project) -> None:
    from veles.core.tools.builtin.list_files import list_files

    (project.root / "sub").mkdir()
    (project.root / "sub" / "x.py").write_text("z")
    out = list_files(path=str(project.root), glob="**/*.py")
    assert "x.py" in out


def test_hidden_skipped_by_default(project) -> None:
    from veles.core.tools.builtin.list_files import list_files

    (project.root / ".secret").write_text("x")
    (project.root / "visible").write_text("y")
    out = list_files(path=str(project.root))
    assert ".secret" not in out
    assert "visible" in out


def test_show_hidden_includes_dotfiles(project) -> None:
    from veles.core.tools.builtin.list_files import list_files

    (project.root / ".secret").write_text("x")
    out = list_files(path=str(project.root), show_hidden=True)
    assert ".secret" in out


def test_ignored_dirs_skipped(project) -> None:
    from veles.core.tools.builtin.list_files import list_files

    (project.root / "node_modules" / "lib").mkdir(parents=True)
    (project.root / "node_modules" / "lib" / "x.js").write_text("z")
    out = list_files(path=str(project.root), glob="**/*.js")
    assert "x.js" not in out


def test_max_results_truncates(project) -> None:
    from veles.core.tools.builtin.list_files import list_files

    for i in range(20):
        (project.root / f"f{i:02d}.txt").write_text("x")
    out = list_files(path=str(project.root), max_results=5)
    assert "truncated at 5" in out


def test_missing_path_returns_marker(project) -> None:
    from veles.core.tools.builtin.list_files import list_files

    out = list_files(path=str(project.root / "nope"))
    assert "no such path" in out


def test_sandbox_violation(project) -> None:
    from veles.core.tools.builtin.list_files import list_files

    with pytest.raises(SandboxViolation):
        list_files(path="/etc")


def test_single_file_listing(project) -> None:
    """When `path` is a file, returns one entry row directly."""
    from veles.core.tools.builtin.list_files import list_files

    f = project.root / "only.txt"
    f.write_text("abc")
    out = list_files(path=str(f))
    assert out.startswith("f\t3\t")
