"""M118c: the run system prompt carries a ranked "relevant files" block,
sourced from `project_tree` via `relevant_semantic` (embedding-ranked with an
adapter, token-ranked fallback otherwise)."""

from __future__ import annotations

from pathlib import Path

from veles.cli._runtime import _relevant_paths_block, build_run_system_prompt
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.project_tree import ensure_table


def _seed_tree(project, rows: list[tuple[str, str, str]]) -> None:
    store = SessionStore(project.memory_db_path)
    try:
        ensure_table(store._conn)
        for rel, kind, tag in rows:
            store._conn.execute(
                "INSERT OR REPLACE INTO project_tree"
                "(rel_path, kind, parent_path, semantic_tag, mtime, size, last_scanned_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (rel, kind, None, tag, 0.0, 0, 0.0),
            )
        store._conn.commit()
    finally:
        store.close()


def test_relevant_paths_block_ranks_matching_path(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_tree(
        project,
        [
            ("src/auth.py", "file", "authentication module"),
            ("src/billing.py", "file", "billing module"),
        ],
    )
    block = _relevant_paths_block(project, "fix the auth login bug")
    assert block is not None
    assert "<relevant-files>" in block
    assert "src/auth.py" in block


def test_relevant_paths_block_none_for_empty_query(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_tree(project, [("src/auth.py", "file", "auth")])
    assert _relevant_paths_block(project, "   ") is None


def test_build_run_system_prompt_includes_relevant_files(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_tree(project, [("src/auth.py", "file", "authentication module")])
    sp = build_run_system_prompt(project, prompt="fix auth login bug")
    assert sp is not None
    assert "<relevant-files>" in sp
    assert "src/auth.py" in sp
