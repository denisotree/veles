"""Tests for core/goal.py — long-horizon objectives with budgets."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.goal import (
    GOALS_DIRNAME,
    Goal,
    GoalBudget,
    append_checkpoint,
    budget_exhausted,
    cancel,
    complete,
    create_goal,
    goals_dir,
    list_goals,
    pause,
    read_goal,
    render_system_block,
    resume,
)

# ---------- create / read ----------


def test_create_goal_persists_to_disk(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="Build the digest pipeline.")
    assert (tmp_path / GOALS_DIRNAME / f"{g.id}.json").exists()
    loaded = read_goal(tmp_path, g.id)
    assert loaded is not None
    assert loaded.objective == "Build the digest pipeline."
    assert loaded.status == "active"


def test_create_goal_rejects_empty_objective(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="objective"):
        create_goal(tmp_path, objective="   ")


def test_create_goal_carries_all_optional_fields(tmp_path: Path) -> None:
    g = create_goal(
        tmp_path,
        objective="Refactor X.",
        scope="src/veles/core",
        done_condition="pytest green + mypy --strict clean",
        budget=GoalBudget(max_steps=10, max_cost_usd=1.0, max_wall_time_s=600),
        forbidden_actions=["git_push"],
        approval_required_for=["delete_file"],
    )
    loaded = read_goal(tmp_path, g.id)
    assert loaded is not None
    assert loaded.scope == "src/veles/core"
    assert loaded.budget.max_steps == 10
    assert loaded.forbidden_actions == ["git_push"]
    assert loaded.approval_required_for == ["delete_file"]


def test_read_missing_goal_returns_none(tmp_path: Path) -> None:
    assert read_goal(tmp_path, "nonexistent") is None


# ---------- list ----------


def test_list_goals_empty(tmp_path: Path) -> None:
    assert list_goals(tmp_path) == []


def test_list_goals_sorted_by_updated_at_desc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `_now_iso` has 1s granularity — freeze it instead of sleeping >1s.
    import veles.core.goal as goal_mod

    stamps = iter(["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"])
    monkeypatch.setattr(goal_mod, "_now_iso", lambda: next(stamps))
    create_goal(tmp_path, objective="first")
    create_goal(tmp_path, objective="second")
    goals = list_goals(tmp_path)
    assert [g.objective for g in goals] == ["second", "first"]


def test_list_goals_filter_by_status(tmp_path: Path) -> None:
    a = create_goal(tmp_path, objective="a")
    b = create_goal(tmp_path, objective="b")
    complete(tmp_path, a.id)
    cancel(tmp_path, b.id, reason="not needed")
    active = list_goals(tmp_path, status="active")
    completed = list_goals(tmp_path, status="completed")
    cancelled = list_goals(tmp_path, status="cancelled")
    assert active == []
    assert len(completed) == 1
    assert len(cancelled) == 1


# ---------- transitions ----------


def test_pause_then_resume(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x")
    pause(tmp_path, g.id)
    assert read_goal(tmp_path, g.id).status == "paused"  # type: ignore[union-attr]
    resume(tmp_path, g.id)
    assert read_goal(tmp_path, g.id).status == "active"  # type: ignore[union-attr]


def test_pause_active_only(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x")
    complete(tmp_path, g.id)
    with pytest.raises(ValueError, match="cannot transition"):
        pause(tmp_path, g.id)


def test_resume_only_when_paused(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x")
    with pytest.raises(ValueError, match="cannot transition"):
        resume(tmp_path, g.id)


def test_complete_appends_evidence_checkpoint(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x")
    complete(tmp_path, g.id, evidence="all 7 evals green")
    loaded = read_goal(tmp_path, g.id)
    assert loaded is not None
    assert loaded.status == "completed"
    assert loaded.completed_at is not None
    assert any("done: all 7 evals green" in p.description for p in loaded.progress)


def test_cannot_complete_completed(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x")
    complete(tmp_path, g.id)
    with pytest.raises(ValueError, match="completed"):
        complete(tmp_path, g.id)


def test_cancel_appends_reason(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x")
    cancel(tmp_path, g.id, reason="user changed mind")
    loaded = read_goal(tmp_path, g.id)
    assert loaded is not None
    assert loaded.status == "cancelled"
    assert any("user changed mind" in p.description for p in loaded.progress)


# ---------- checkpoints ----------


def test_checkpoint_advances_step_counter(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x")
    append_checkpoint(tmp_path, g.id, "step 1 done")
    append_checkpoint(tmp_path, g.id, "step 2 done")
    loaded = read_goal(tmp_path, g.id)
    assert loaded is not None
    assert loaded.steps_done == 2
    assert len(loaded.progress) == 2


def test_checkpoint_no_advance_for_info_only(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x")
    append_checkpoint(tmp_path, g.id, "just a note", advance_step=False)
    loaded = read_goal(tmp_path, g.id)
    assert loaded is not None
    assert loaded.steps_done == 0
    assert len(loaded.progress) == 1


def test_checkpoint_tracks_cost(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x")
    append_checkpoint(tmp_path, g.id, "call 1", cost_usd=0.10)
    append_checkpoint(tmp_path, g.id, "call 2", cost_usd=0.05)
    loaded = read_goal(tmp_path, g.id)
    assert loaded is not None
    assert abs(loaded.cost_spent_usd - 0.15) < 1e-9


def test_checkpoint_on_completed_goal_rejected(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x")
    complete(tmp_path, g.id)
    with pytest.raises(ValueError, match="status"):
        append_checkpoint(tmp_path, g.id, "too late")


# ---------- budgets ----------


def test_budget_exhausted_by_steps(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x", budget=GoalBudget(max_steps=2))
    append_checkpoint(tmp_path, g.id, "a")
    append_checkpoint(tmp_path, g.id, "b")
    loaded = read_goal(tmp_path, g.id)
    assert loaded is not None
    assert budget_exhausted(loaded) is not None
    assert "max_steps" in budget_exhausted(loaded)  # type: ignore[operator]


def test_budget_exhausted_by_cost(tmp_path: Path) -> None:
    g = create_goal(tmp_path, objective="x", budget=GoalBudget(max_cost_usd=0.01))
    append_checkpoint(tmp_path, g.id, "expensive", cost_usd=0.5)
    loaded = read_goal(tmp_path, g.id)
    assert loaded is not None
    assert "max_cost" in (budget_exhausted(loaded) or "")


def test_budget_not_exhausted_at_zero() -> None:
    g = Goal(id="x", objective="o", created_at="2099-01-01T00:00:00Z")
    assert budget_exhausted(g) is None


def test_seconds_since_iso_treats_input_as_utc(monkeypatch) -> None:
    """`_now_iso` writes UTC; `_seconds_since_iso` must interpret its
    input as UTC too. Previously it used `time.mktime`, which interprets
    `struct_tm` as local time — on any non-UTC host (e.g. Europe/Moscow)
    a goal created seconds ago would appear to be hours old and trip
    the wall-time budget on the first turn.

    This pins the fix: regardless of `TZ`, a goal created `_now_iso()`-
    fresh must have an elapsed value bounded by a few seconds.
    """
    import time

    from veles.core.goal import _now_iso, _seconds_since_iso

    monkeypatch.setenv("TZ", "Europe/Moscow")
    time.tzset()  # apply the env var change to time-conversion calls
    try:
        elapsed = _seconds_since_iso(_now_iso())
        assert elapsed < 5, f"elapsed={elapsed}s for a just-created goal"
    finally:
        # Restore default TZ so subsequent tests aren't affected.
        monkeypatch.delenv("TZ", raising=False)
        time.tzset()


# ---------- render_system_block ----------


def test_render_block_has_required_lines() -> None:
    g = Goal(
        id="abc",
        objective="Build digest.",
        done_condition="report.md exists",
        budget=GoalBudget(max_steps=5),
        steps_done=2,
        cost_spent_usd=0.1,
    )
    block = render_system_block(g)
    assert block.startswith('<goal id="abc"')
    assert "Build digest." in block
    assert "report.md exists" in block
    assert "2/5 steps" in block
    assert block.endswith("</goal>")


def test_render_block_includes_forbidden_when_set() -> None:
    g = Goal(id="x", objective="o", forbidden_actions=["git_push", "send_email"])
    block = render_system_block(g)
    assert "git_push, send_email" in block


# ---------- path helper ----------


def test_goals_dir_helper(tmp_path: Path) -> None:
    assert goals_dir(tmp_path) == tmp_path / GOALS_DIRNAME
