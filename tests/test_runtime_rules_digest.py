"""M139: the run system prompt carries the house-rules digest in its stable
(cacheable) part — before any volatile per-turn block."""

from __future__ import annotations

import time
from pathlib import Path

from veles.cli._runtime import build_run_system_prompt
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.project_tree import ensure_table


def _seed_rule(project, *, kind: str, body: str) -> None:
    store = SessionStore(project.memory_db_path)
    try:
        store._conn.execute(
            "INSERT INTO rules(kind, body, source, created_at) VALUES (?, ?, ?, ?)",
            (kind, body, "extracted", time.time()),
        )
        store._conn.commit()
    finally:
        store.close()


def _seed_tree_path(project, rel: str, tag: str) -> None:
    store = SessionStore(project.memory_db_path)
    try:
        ensure_table(store._conn)
        store._conn.execute(
            "INSERT OR REPLACE INTO project_tree"
            "(rel_path, kind, parent_path, semantic_tag, mtime, size, last_scanned_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rel, "file", None, tag, 0.0, 0, 0.0),
        )
        store._conn.commit()
    finally:
        store.close()


def test_build_run_system_prompt_includes_rules_digest(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_rule(project, kind="preference", body="answer in metric units")
    sp = build_run_system_prompt(project, prompt="anything")
    assert sp is not None
    assert "answer in metric units" in sp


def test_rules_digest_lands_in_stable_part(tmp_path: Path) -> None:
    """Stable parts are joined before volatile ones, so the digest must appear
    before the volatile <relevant-files> block."""
    project = init_project(tmp_path / "p", name="p")
    _seed_rule(project, kind="preference", body="answer in metric units")
    _seed_tree_path(project, "src/auth.py", "authentication module")
    sp = build_run_system_prompt(project, prompt="fix auth login bug")
    assert sp is not None
    assert "<relevant-files>" in sp  # volatile block present
    assert sp.index("answer in metric units") < sp.index("<relevant-files>")


def test_no_digest_when_no_rules(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    sp = build_run_system_prompt(project, prompt="anything")
    assert sp is not None
    assert "House rules" not in sp
