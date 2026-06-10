"""Tests for the builtin search_files tool (M124-perm-unify).

Cover both backends:
- ripgrep path (monkeypatch shutil.which to return a fake binary,
  monkeypatch subprocess.run to fabricate output) — proves we shell
  out and parse output correctly.
- pure-Python fallback (monkeypatch shutil.which to None) — proves we
  rglob+re.search without depending on rg.

Plus: sandbox violation, regex error, max_results cap, ignored dirs,
large-file skip.
"""

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


@pytest.fixture
def no_rg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the python fallback by hiding `rg` from PATH."""
    monkeypatch.setattr(
        "veles.core.tools.builtin.search_files.shutil.which",
        lambda name: None if name == "rg" else name,
    )


# ---- pure Python fallback ----


def test_python_finds_match(project, no_rg) -> None:
    from veles.core.tools.builtin.search_files import search_files

    (project.root / "a.py").write_text("hello = 1\ntodo: refactor\n")
    out = search_files("todo", path=str(project.root))
    assert "a.py:2:todo: refactor" in out


def test_python_no_match_returns_marker(project, no_rg) -> None:
    from veles.core.tools.builtin.search_files import search_files

    (project.root / "a.py").write_text("only this line\n")
    assert search_files("nothing-here", path=str(project.root)) == "<no matches>"


def test_python_case_insensitive(project, no_rg) -> None:
    from veles.core.tools.builtin.search_files import search_files

    (project.root / "a.py").write_text("TODO: fix\n")
    out = search_files("todo", path=str(project.root), case_insensitive=True)
    assert "TODO: fix" in out


def test_python_ignores_hardcoded_dirs(project, no_rg) -> None:
    from veles.core.tools.builtin.search_files import search_files

    (project.root / ".git").mkdir()
    (project.root / ".git" / "config").write_text("MARKER\n")
    (project.root / "node_modules" / "lib").mkdir(parents=True)
    (project.root / "node_modules" / "lib" / "x.js").write_text("MARKER\n")
    (project.root / "good.txt").write_text("MARKER\n")
    out = search_files("MARKER", path=str(project.root))
    assert "good.txt" in out
    assert ".git" not in out
    assert "node_modules" not in out


def test_python_max_results_caps_output(project, no_rg) -> None:
    from veles.core.tools.builtin.search_files import search_files

    (project.root / "many.txt").write_text("\n".join(["match"] * 50))
    out = search_files("match", path=str(project.root), max_results=10)
    assert out.count("many.txt:") == 10
    assert "truncated at 10" in out


def test_python_skips_large_files(project, no_rg) -> None:
    from veles.core.tools.builtin.search_files import search_files

    big = project.root / "big.txt"
    big.write_bytes(b"MARKER\n" * (300 * 1024))  # ~2 MiB
    out = search_files("MARKER", path=str(project.root))
    # The big file is skipped → no matches.
    assert out == "<no matches>"


def test_invalid_regex_returns_error_marker(project, no_rg) -> None:
    from veles.core.tools.builtin.search_files import search_files

    out = search_files("(unclosed", path=str(project.root))
    assert out.startswith("<invalid regex")


def test_sandbox_violation_blocks_outside_path(project, no_rg) -> None:
    from veles.core.tools.builtin.search_files import search_files

    with pytest.raises(SandboxViolation):
        search_files("anything", path="/etc")


def test_missing_path_returns_marker(project, no_rg) -> None:
    from veles.core.tools.builtin.search_files import search_files

    out = search_files("anything", path=str(project.root / "absent"))
    assert "no such path" in out


# ---- ripgrep backend ----


def test_ripgrep_path_invokes_rg(
    project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When rg is available, search_files shells out to it and folds
    absolute paths back to project-relative."""
    import subprocess as _subprocess
    import veles.core.tools.builtin.search_files as mod

    (project.root / "a.py").write_text("todo\n")

    monkeypatch.setattr(mod.shutil, "which", lambda name: "/fake/rg" if name == "rg" else None)

    captured: dict[str, object] = {}

    def fake_run(cmd, **kw):  # noqa: ANN001
        captured["cmd"] = cmd
        # Simulate rg's output: absolute_path:lineno:content
        abs_path = str(project.root / "a.py")
        return _subprocess.CompletedProcess(
            cmd, 0, stdout=f"{abs_path}:1:todo\n", stderr=""
        )

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    out = mod.search_files("todo", path=str(project.root))
    assert out == "a.py:1:todo"
    cmd = captured["cmd"]
    assert "--regexp" in cmd
    assert "--line-number" in cmd


def test_ripgrep_oserror_falls_back_to_python(
    project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crashing rg shouldn't abort the search — Python fallback runs."""
    import veles.core.tools.builtin.search_files as mod

    (project.root / "a.py").write_text("hello\n")

    monkeypatch.setattr(mod.shutil, "which", lambda name: "/fake/rg" if name == "rg" else None)

    def boom(*_a, **_kw):
        raise OSError("simulated rg crash")

    monkeypatch.setattr(mod.subprocess, "run", boom)

    out = mod.search_files("hello", path=str(project.root))
    assert "a.py:1:hello" in out
