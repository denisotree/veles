"""Tests for core/plan_artifact.py — durable plan storage (closes M70 xfail)."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.plan_artifact import (
    PLANS_ACTIVE_SUBDIR,
    PLANS_COMPLETED_SUBDIR,
    PLANS_DIRNAME,
    PlanArtifact,
    active_dir,
    collect_active_refs,
    completed_dir,
    create_plan,
    list_active,
    list_completed,
    mark_done,
    parse_plan_ref,
    plan_ref,
    plans_dir,
    read_plan,
    render_system_block,
    update_status,
)

# ---------- path helpers + plan_ref scheme ----------


def test_plans_dir_layout(tmp_path: Path) -> None:
    assert plans_dir(tmp_path) == tmp_path / PLANS_DIRNAME
    assert active_dir(tmp_path).name == PLANS_ACTIVE_SUBDIR
    assert completed_dir(tmp_path).name == PLANS_COMPLETED_SUBDIR


def test_plan_ref_round_trip() -> None:
    ref = plan_ref("abc123")
    assert ref == "artifact://veles/plans/abc123"
    assert parse_plan_ref(ref) == "abc123"


def test_parse_plan_ref_rejects_garbage() -> None:
    assert parse_plan_ref("artifact://veles/sessions/x") is None
    assert parse_plan_ref("not a ref") is None
    assert parse_plan_ref("artifact://veles/plans/has-dash") is None


# ---------- create / read ----------


def test_create_writes_to_active_dir(tmp_path: Path) -> None:
    plan = create_plan(
        tmp_path,
        objective="Refactor permission engine.",
        steps=["read engine.py", "extract rule helper", "rerun tests"],
        approval_points=["before deleting trust.py"],
    )
    p = active_dir(tmp_path) / f"{plan.id}.md"
    assert p.exists()
    body = p.read_text()
    assert body.startswith("---\n")
    assert "Refactor permission engine." in body
    assert "rerun tests" in body


def test_create_rejects_empty_objective(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="objective"):
        create_plan(tmp_path, objective="   ")


def test_read_plan_finds_active(tmp_path: Path) -> None:
    plan = create_plan(tmp_path, objective="X")
    loaded = read_plan(tmp_path, plan.id)
    assert loaded is not None
    assert loaded.objective == "X"


def test_read_plan_finds_completed(tmp_path: Path) -> None:
    plan = create_plan(tmp_path, objective="X")
    mark_done(tmp_path, plan.id)
    loaded = read_plan(tmp_path, plan.id)
    assert loaded is not None
    assert loaded.status == "completed"


def test_read_missing_returns_none(tmp_path: Path) -> None:
    assert read_plan(tmp_path, "nope") is None


def test_full_round_trip_preserves_all_fields(tmp_path: Path) -> None:
    plan = create_plan(
        tmp_path,
        objective="Big migration.",
        scope="src/veles/core",
        assumptions=["v0.1.0 baseline tag exists", "pytest green now"],
        risks=["compactor history may not rehydrate", "trust store schema changed"],
        steps=["audit usages", "rename Foo to Bar", "fix tests"],
        tools_required=["read_file", "write_file"],
        approval_points=["before any write_file"],
        validation=["uv run pytest -q", "uv run mypy"],
        rollback="git reset --hard pre-migration",
        done_condition="all 1500 tests pass + mypy strict clean",
    )
    loaded = read_plan(tmp_path, plan.id)
    assert loaded is not None
    assert loaded.scope == "src/veles/core"
    assert loaded.assumptions == ["v0.1.0 baseline tag exists", "pytest green now"]
    assert loaded.risks[1] == "trust store schema changed"
    assert loaded.steps == ["audit usages", "rename Foo to Bar", "fix tests"]
    assert loaded.tools_required == ["read_file", "write_file"]
    assert loaded.approval_points == ["before any write_file"]
    assert loaded.validation == ["uv run pytest -q", "uv run mypy"]
    assert loaded.rollback == "git reset --hard pre-migration"
    assert loaded.done_condition == "all 1500 tests pass + mypy strict clean"


# ---------- list / status ----------


def test_list_active_excludes_completed(tmp_path: Path) -> None:
    a = create_plan(tmp_path, objective="active one")
    b = create_plan(tmp_path, objective="will be done")
    mark_done(tmp_path, b.id)
    active = list_active(tmp_path)
    assert [p.id for p in active] == [a.id]
    completed = list_completed(tmp_path)
    assert [p.id for p in completed] == [b.id]


def test_update_status_transitions(tmp_path: Path) -> None:
    plan = create_plan(tmp_path, objective="x")
    assert plan.status == "draft"
    p2 = update_status(tmp_path, plan.id, status="approved")
    assert p2.status == "approved"
    p3 = update_status(tmp_path, plan.id, status="executing")
    assert p3.status == "executing"
    reloaded = read_plan(tmp_path, plan.id)
    assert reloaded is not None
    assert reloaded.status == "executing"


def test_mark_done_moves_to_completed_dir(tmp_path: Path) -> None:
    plan = create_plan(tmp_path, objective="x")
    active_path = active_dir(tmp_path) / f"{plan.id}.md"
    assert active_path.exists()
    mark_done(tmp_path, plan.id, evidence_ref="artifact://veles/abc")
    assert not active_path.exists()
    completed_path = completed_dir(tmp_path) / f"{plan.id}.md"
    assert completed_path.exists()
    reloaded = read_plan(tmp_path, plan.id)
    assert reloaded is not None
    assert reloaded.status == "completed"
    assert reloaded.evidence_ref == "artifact://veles/abc"


def test_mark_done_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        mark_done(tmp_path, "no-such-plan")


# ---------- system-prompt block ----------


def test_render_block_minimal() -> None:
    plan = PlanArtifact(id="abc", objective="Do thing.")
    block = render_system_block(plan)
    assert block.startswith('<active-plan id="abc"')
    assert "Do thing." in block
    assert block.endswith("</active-plan>")


def test_render_block_with_steps_and_approval() -> None:
    plan = PlanArtifact(
        id="abc",
        objective="Migrate",
        done_condition="tests green",
        steps=["one", "two"],
        approval_points=["before push"],
    )
    block = render_system_block(plan)
    assert "Done when: tests green" in block
    assert "  1. one" in block
    assert "  2. two" in block
    assert "Approval points: before push" in block


def test_render_block_contains_plan_ref() -> None:
    plan = PlanArtifact(id="xyz", objective="o")
    block = render_system_block(plan)
    assert 'ref="artifact://veles/plans/xyz"' in block


# ---------- collect_active_refs (compactor-side helper) ----------


def test_collect_active_refs_returns_uris(tmp_path: Path) -> None:
    a = create_plan(tmp_path, objective="alpha")
    b = create_plan(tmp_path, objective="beta")
    mark_done(tmp_path, b.id)  # completed shouldn't appear in active refs.
    refs = collect_active_refs(tmp_path)
    assert refs == [plan_ref(a.id)] or refs == [plan_ref(a.id), plan_ref(b.id)]
    # Strict: completed plans are excluded.
    assert plan_ref(b.id) not in refs


def test_collect_active_refs_empty_when_no_plans(tmp_path: Path) -> None:
    assert collect_active_refs(tmp_path) == []
