"""`read_file` graceful-error behaviour.

A real Obsidian-vault migration (2026-07-07) surfaced raw `IsADirectoryError` /
`FileNotFoundError` as noisy `tool.error` lines when the agent called read_file
on a directory or a guessed path. Like the other FS primitives, read_file
should return an actionable `<error: ...>` marker the agent can recover from
(e.g. "use list_files") instead of raising.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.project import init_project
from veles.core.tools.builtin.read_file import read_file


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    p = init_project(tmp_path / "proj", name="proj", layout="llm-wiki")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def test_reads_a_real_file(project) -> None:
    (project.root / "note.md").write_text("hello\nworld\n", encoding="utf-8")
    out = read_file(str(project.root / "note.md"))
    assert "hello" in out and "world" in out


def test_directory_returns_actionable_error_not_raise(project) -> None:
    (project.root / "meetings").mkdir()
    out = read_file(str(project.root / "meetings"))
    assert out.startswith("<error:")
    assert "directory" in out.lower()
    assert "list_files" in out  # actionable hint


def test_missing_file_returns_error_not_raise(project) -> None:
    out = read_file(str(project.root / "RAW" / "ruview.md"))  # guessed path, doesn't exist
    assert out.startswith("<error:")
    assert "no such file" in out.lower() or "not found" in out.lower()
