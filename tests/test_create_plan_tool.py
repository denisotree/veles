"""`create_plan` builtin tool — thin wrapper around `plan_artifact.create_plan`.

The tool exists so PlanningMode can offer the model a typed schema for
delivering a plan artifact. These tests pin the tool's contract:

  - persists a markdown file under `<project>/.veles/plans/active/`
  - returns `{plan_id, path, status}` for the model to quote
  - surfaces a structured error when no project is active (rather than
    raising; tools return; agents observe)
  - registered with `RiskClass.DRAFT_ONLY` so the Permission Engine's
    planning-mode rule does NOT block it
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.plan_artifact import active_dir
from veles.core.project import init_project
from veles.core.risk import RiskClass
from veles.core.tools.builtin.plan_tool import create_plan
from veles.core.tools.registry import registry


@pytest.fixture
def project(tmp_path):
    """Fresh project rooted under pytest's tmp dir. Mirrors
    `tests/tui/conftest.py:tmp_project` minus the SessionStore — this
    suite only needs the project paths."""
    return init_project(tmp_path / "proj", name="proj")


def test_create_plan_writes_artifact_to_active_dir(project) -> None:
    token = set_active_project(project)
    try:
        result = create_plan(
            objective="refactor X for clarity",
            steps=["read code", "draft", "write"],
            done_condition="tests green, code reviewed",
        )
    finally:
        reset_active_project(token)

    assert "plan_id" in result
    plan_id = result["plan_id"]
    artifact_path = Path(result["path"])
    assert artifact_path.exists()
    assert artifact_path.parent == active_dir(project.state_dir)
    assert artifact_path.name == f"{plan_id}.md"
    assert result["status"] == "draft"


def test_create_plan_returns_error_without_active_project() -> None:
    """No ambient project ContextVar → return an `error` field rather
    than raising. The model gets to read the error and adapt."""
    result = create_plan(objective="anything")
    assert "error" in result
    assert "no active project" in result["error"].lower()


def test_create_plan_persists_all_structured_fields(project) -> None:
    token = set_active_project(project)
    try:
        result = create_plan(
            objective="ship the feature",
            scope="TUI only",
            assumptions=["test env is set up"],
            risks=["flaky Textual binding"],
            steps=["a", "b", "c"],
            tools_required=["write_file", "run_shell"],
            approval_points=["before merge"],
            validation=["pytest green"],
            rollback="revert commit",
            done_condition="merged to main",
        )
    finally:
        reset_active_project(token)

    body = Path(result["path"]).read_text(encoding="utf-8")
    assert "ship the feature" in body
    assert "TUI only" in body
    assert "flaky Textual binding" in body
    assert "merged to main" in body


def test_create_plan_is_registered_as_draft_only() -> None:
    """The DRAFT_ONLY risk class is what keeps `create_plan` usable in
    planning mode — `_planning_mode_rule` only blocks mutation classes
    and DRAFT_ONLY is not in that set."""
    entry = registry.get("create_plan")
    assert entry.risk_class is RiskClass.DRAFT_ONLY


def test_create_plan_in_planning_toolset() -> None:
    """The planning toolset must surface `create_plan` so the model
    sees its schema and knows it can deliver a plan from this mode."""
    from veles.cli._runtime import _PLANNING_TOOLS

    assert "create_plan" in _PLANNING_TOOLS
