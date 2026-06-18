"""M168 — edit_file: surgical string-replace with a uniqueness guard.

`write_file` only overwrites whole files; `edit_file` changes one matched
region, so the agent can correct a dbt model / script / monitoring query
without regenerating it. The match must be unique unless `replace_all` is
set, so the agent can't silently edit the wrong line. Writes obey the same
sandbox + writable-zone gating as write_file (shared `_fs_write_guard`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.project import init_project
from veles.core.tools.builtin.edit_file import edit_file


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture()
def project(isolated_home: Path, tmp_path: Path):
    p = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def _wiki_file(project, name: str, body: str) -> Path:
    target = project.root / "wiki" / "concepts" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


# ---- happy path ----


def test_replaces_unique_match(project) -> None:
    f = _wiki_file(project, "a.md", "interval = 30\nname = x\n")
    msg = edit_file(str(f), "interval = 30", "interval = 60")
    assert "edited" in msg
    assert "1 replacement" in msg
    assert f.read_text(encoding="utf-8") == "interval = 60\nname = x\n"


def test_only_matched_region_changes(project) -> None:
    f = _wiki_file(project, "b.md", "line1\nTARGET\nline3\n")
    edit_file(str(f), "TARGET", "REPLACED")
    assert f.read_text(encoding="utf-8") == "line1\nREPLACED\nline3\n"


def test_replace_all(project) -> None:
    f = _wiki_file(project, "c.md", "x = 1\nx = 1\nx = 1\n")
    msg = edit_file(str(f), "x = 1", "x = 2", replace_all=True)
    assert "3 replacements" in msg
    assert f.read_text(encoding="utf-8") == "x = 2\nx = 2\nx = 2\n"


# ---- guards ----


def test_not_found_is_error(project) -> None:
    f = _wiki_file(project, "d.md", "hello\n")
    msg = edit_file(str(f), "absent", "x")
    assert "not found" in msg
    assert f.read_text(encoding="utf-8") == "hello\n"  # unchanged


def test_ambiguous_match_refused_without_replace_all(project) -> None:
    f = _wiki_file(project, "e.md", "dup\ndup\n")
    msg = edit_file(str(f), "dup", "x")
    assert "appears 2 times" in msg
    assert f.read_text(encoding="utf-8") == "dup\ndup\n"  # unchanged


def test_missing_file_is_error(project) -> None:
    target = project.root / "wiki" / "concepts" / "nope.md"
    msg = edit_file(str(target), "a", "b")
    assert "does not exist" in msg


def test_identical_strings_refused(project) -> None:
    f = _wiki_file(project, "g.md", "same\n")
    msg = edit_file(str(f), "same", "same")
    assert "identical" in msg
    assert f.read_text(encoding="utf-8") == "same\n"


def test_empty_old_string_refused(project) -> None:
    f = _wiki_file(project, "h.md", "body\n")
    msg = edit_file(str(f), "", "x")
    assert "empty" in msg


# ---- shared write-guard applies to edits too ----


def test_readonly_zone_refused(project) -> None:
    """An existing file in a read-only zone (sources/ under llm-wiki)
    cannot be edited — proves edit_file shares write_file's zone guard."""
    src = project.root / "sources" / "raw.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("original\n", encoding="utf-8")  # placed directly, bypassing the tool
    msg = edit_file(str(src), "original", "tampered")
    assert "refused" in msg
    assert "writable zones" in msg
    assert src.read_text(encoding="utf-8") == "original\n"  # untouched
