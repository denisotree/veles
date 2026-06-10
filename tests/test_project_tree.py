"""M118: Project structure cache — scanner + recall API."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from veles.core.project_tree import (
    Scanner,
    TreeEntry,
    ensure_table,
    relevant,
)


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    ensure_table(c)
    return c


def _make_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir()
    (root / "src" / "veles").mkdir()
    (root / "src" / "veles" / "core.py").write_text("print(1)\n")
    (root / "src" / "veles" / "agent.py").write_text("print(2)\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_core.py").write_text("def test_x(): pass\n")
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("# Guide\n")
    (root / "README.md").write_text("# Hi\n")
    (root / "pyproject.toml").write_text("[project]\n")
    return root


# ---- ensure_table / schema ----


def test_ensure_table_idempotent(conn: sqlite3.Connection) -> None:
    ensure_table(conn)
    ensure_table(conn)  # second call must not raise
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='project_tree'"
    ).fetchall()
    assert len(rows) == 1


def test_schema_has_expected_columns(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(project_tree)").fetchall()}
    assert {
        "rel_path",
        "kind",
        "parent_path",
        "semantic_tag",
        "mtime",
        "size",
        "last_scanned_at",
    } <= cols


# ---- scanner: first scan ----


def test_first_scan_records_every_file_and_dir(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    report = Scanner(root, conn).scan()
    assert report.scanned > 0
    assert report.added > 0
    assert report.updated == 0
    assert report.removed == 0
    rows = conn.execute("SELECT rel_path, kind FROM project_tree").fetchall()
    paths = {r["rel_path"]: r["kind"] for r in rows}
    assert paths.get("src") == "dir"
    assert paths.get("src/veles") == "dir"
    assert paths.get("src/veles/core.py") == "file"
    assert paths.get("tests/test_core.py") == "file"
    assert paths.get("docs/guide.md") == "file"
    assert paths.get("README.md") == "file"
    assert paths.get("pyproject.toml") == "file"


def test_scan_skips_always_excluded_dirs(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    (root / ".veles").mkdir()
    (root / ".veles" / "memory.db").write_text("x")
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("x")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "lib.js").write_text("x")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "x.pyc").write_text("x")

    Scanner(root, conn).scan()
    rows = conn.execute("SELECT rel_path FROM project_tree").fetchall()
    paths = {r["rel_path"] for r in rows}
    for excluded in (".veles", ".git", "node_modules", "__pycache__"):
        assert not any(p.startswith(excluded) for p in paths), excluded


def test_scan_honours_gitignore(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    (root / ".gitignore").write_text("*.log\ntmp/\n")
    (root / "out.log").write_text("noise")
    (root / "keep.txt").write_text("keep")
    (root / "tmp").mkdir()
    (root / "tmp" / "junk.txt").write_text("noise")

    Scanner(root, conn).scan()
    paths = {
        r["rel_path"] for r in conn.execute("SELECT rel_path FROM project_tree").fetchall()
    }
    assert "keep.txt" in paths
    assert "out.log" not in paths
    assert "tmp/junk.txt" not in paths


def test_parent_path_set_for_nested_files(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    row = conn.execute(
        "SELECT parent_path FROM project_tree WHERE rel_path = ?",
        ("src/veles/core.py",),
    ).fetchone()
    assert row["parent_path"] == "src/veles"
    row = conn.execute(
        "SELECT parent_path FROM project_tree WHERE rel_path = ?", ("README.md",)
    ).fetchone()
    assert row["parent_path"] is None


# ---- scanner: semantic tagging ----


def test_semantic_tagger_classifies_top_level_dirs(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    tags = {
        r["rel_path"]: r["semantic_tag"]
        for r in conn.execute(
            "SELECT rel_path, semantic_tag FROM project_tree WHERE kind = 'dir'"
        ).fetchall()
    }
    assert tags.get("src") == "src"
    assert tags.get("tests") == "tests"
    assert tags.get("docs") == "docs"


def test_top_level_files_get_doc_or_config_tag(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    rows = conn.execute(
        "SELECT rel_path, semantic_tag FROM project_tree WHERE kind = 'file'"
    ).fetchall()
    tags = {r["rel_path"]: r["semantic_tag"] for r in rows}
    assert tags.get("README.md") == "docs"
    assert tags.get("pyproject.toml") == "config"


# ---- scanner: incremental ----


def test_second_scan_no_changes_yields_no_updates(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    report = Scanner(root, conn).scan()
    assert report.added == 0
    assert report.updated == 0
    assert report.removed == 0


def test_modified_file_triggers_update(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    # Touch a file with a new mtime
    target = root / "src" / "veles" / "core.py"
    import os
    import time

    new_mtime = time.time() + 100
    os.utime(target, (new_mtime, new_mtime))

    report = Scanner(root, conn).scan()
    assert report.updated >= 1
    assert report.added == 0


def test_deleted_file_pruned_from_cache(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    (root / "docs" / "guide.md").unlink()

    report = Scanner(root, conn).scan()
    assert report.removed >= 1
    rows = conn.execute(
        "SELECT 1 FROM project_tree WHERE rel_path = ?",
        ("docs/guide.md",),
    ).fetchall()
    assert rows == []


# ---- recall API ----


def test_relevant_returns_top_matches_by_token(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    hits = relevant(conn, "agent.py", limit=5)
    assert hits
    # `agent.py` exact filename should rank in the top 3
    rel_paths = [h.rel_path for h in hits[:3]]
    assert "src/veles/agent.py" in rel_paths


def test_relevant_uses_semantic_tag(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    hits = relevant(conn, "docs", limit=10)
    rel_paths = {h.rel_path for h in hits}
    # docs/ directory and README.md (tagged 'docs') should both be present.
    assert "docs" in rel_paths or "docs/guide.md" in rel_paths
    assert "README.md" in rel_paths


def test_relevant_empty_query_returns_nothing(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    assert relevant(conn, "", limit=5) == []


def test_relevant_respects_limit(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    # add many files to inflate the candidate set
    for i in range(20):
        (root / f"extra{i}.py").write_text("x\n")
    Scanner(root, conn).scan()
    hits = relevant(conn, "extra", limit=3)
    assert len(hits) == 3


def test_relevant_returns_typed_entries(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    hits = relevant(conn, "src core", limit=5)
    for h in hits:
        assert isinstance(h, TreeEntry)
        assert h.kind in {"file", "dir"}
