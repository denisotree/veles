"""M191 — the default REPL must inject per-turn project-memory recall.

The inline REPL's Agent factory used to build the system prompt with an empty
recall query (`_build_run_system_prompt(args, project)` reads `args.prompt`,
which the REPL parser never sets), so `<memory-context>` was never injected —
"never forgets" was false in the flagship UX. These tests pin the turn-prompt
assembly seam: given a recall query that matches stored memory, the assembled
prompt carries it; an empty query carries none (the old, broken behaviour).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from veles.cli.commands.repl import _repl_turn_system_prompt
from veles.core.memory import SessionStore
from veles.core.modes import get_mode
from veles.core.project import init_project


def _seed_insight(db_path: Path, *, title: str, body: str) -> None:
    store = SessionStore(db_path)
    try:
        store._conn.execute(
            "INSERT INTO insights(title, body, category, created_at) VALUES (?, ?, ?, ?)",
            (title, body, "curated-session", time.time()),
        )
        store._conn.commit()
    finally:
        store.close()


def _args() -> argparse.Namespace:
    return argparse.Namespace(no_agents_md=False, no_index=False)


def test_repl_turn_prompt_injects_recall_when_query_matches_insight(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _seed_insight(
        project.memory_db_path,
        title="deploy flow",
        body="run terraform apply after the database migration completes",
    )

    # Keyword query whose tokens are present in the insight body. Recall is
    # FTS5 keyword-AND today (M192 adds embeddings for paraphrase matching);
    # this test pins the M191 wiring — a matching turn query reaches recall.
    prompt = _repl_turn_system_prompt(
        _args(),
        project,
        mode=get_mode("writing"),
        query="terraform migration",
        extra_system=None,
    )

    assert prompt is not None
    assert "terraform" in prompt
    assert "deploy flow" in prompt


def test_repl_turn_prompt_has_no_recall_for_empty_query(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _seed_insight(
        project.memory_db_path,
        title="deploy flow",
        body="run terraform apply after the database migration completes",
    )

    prompt = _repl_turn_system_prompt(
        _args(),
        project,
        mode=get_mode("writing"),
        query="",
        extra_system=None,
    )

    assert prompt is not None
    assert "terraform" not in prompt


def test_repl_post_turn_hooks_fire_insight_and_curator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M191: after a REPL turn the same learning-loop hooks `veles run` fires —
    insight extraction + post-turn curation (dream rides inside) — run, so the
    flagship REPL actually builds project memory (it ran none before M191)."""
    import veles.cli as cli
    from veles.cli.commands.repl import _run_repl_post_turn_hooks
    from veles.core.agent import RunResult

    calls: list[tuple] = []
    monkeypatch.setattr(
        cli, "_maybe_run_insight_extractor", lambda a, p, h, s: calls.append(("insight", h, s))
    )
    monkeypatch.setattr(
        cli, "_maybe_run_post_turn_curator", lambda a, p: calls.append(("curator",))
    )

    project = init_project(tmp_path, name="t")
    result = RunResult(text="ok", iterations=1, session_id="s1")
    _run_repl_post_turn_hooks(argparse.Namespace(), project, result)

    assert ("insight", result.history, "s1") in calls
    assert ("curator",) in calls


def test_repl_post_turn_hooks_skip_when_turn_produced_no_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cancelled/errored turn yields no RunResult — memory processing must be
    skipped, not fed a None result."""
    import veles.cli as cli
    from veles.cli.commands.repl import _run_repl_post_turn_hooks

    calls: list[tuple] = []
    monkeypatch.setattr(
        cli, "_maybe_run_insight_extractor", lambda a, p, h, s: calls.append(("insight",))
    )
    monkeypatch.setattr(
        cli, "_maybe_run_post_turn_curator", lambda a, p: calls.append(("curator",))
    )

    project = init_project(tmp_path, name="t")
    _run_repl_post_turn_hooks(argparse.Namespace(), project, None)

    assert calls == []


def test_repl_post_turn_hooks_skip_cancelled_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user-cancelled turn (Ctrl+C) has no meaningful content — memory upkeep
    must skip it, not distil a half-finished interruption into an insight."""
    import veles.cli as cli
    from veles.cli.commands.repl import _run_repl_post_turn_hooks

    calls: list[tuple] = []
    monkeypatch.setattr(
        cli, "_maybe_run_insight_extractor", lambda a, p, h, s: calls.append(("insight",))
    )
    monkeypatch.setattr(
        cli, "_maybe_run_post_turn_curator", lambda a, p: calls.append(("curator",))
    )

    cancelled = SimpleNamespace(stopped_reason="cancelled", history=[], session_id="s1")

    project = init_project(tmp_path, name="t")
    _run_repl_post_turn_hooks(argparse.Namespace(), project, cancelled)

    assert calls == []
