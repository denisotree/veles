"""`create_plan` — agent-facing tool that writes a plan artifact.

PlanningMode points the agent at this tool as the explicit way to
deliver a finalised plan. Under the hood it just wraps
`plan_artifact.create_plan(...)`, but registering it as a `@tool` gives
the model a typed schema (objective / scope / steps / etc.) instead of
making it parse a markdown template.

The risk class is `DRAFT_ONLY`: a plan file lives under
`<project>/.veles/plans/active/` and never executes by itself. The
Permission Engine's planning-mode rule (`_planning_mode_rule`,
`permission/engine.py:89`) only blocks *mutation* classes; DRAFT_ONLY
is intentionally outside that set so the tool can run while
`plan_mode=True`.
"""

from __future__ import annotations

from typing import Any

from veles.core.risk import RiskClass
from veles.core.tools.registry import tool


@tool(risk_class=RiskClass.DRAFT_ONLY)
def create_plan(
    objective: str,
    scope: str = "",
    assumptions: list[str] | None = None,
    risks: list[str] | None = None,
    steps: list[str] | None = None,
    tools_required: list[str] | None = None,
    approval_points: list[str] | None = None,
    validation: list[str] | None = None,
    rollback: str = "",
    done_condition: str = "",
) -> dict[str, Any]:
    """Persist a structured plan artifact to the active project.

    Call this in planning mode as the final step of a planning turn,
    once you have enough context. Returns `{plan_id, path, status}` so
    the agent can quote the id in its closing message.

    Required: `objective` — one short paragraph stating what the plan
    will accomplish. Everything else is optional but the more structure
    you provide, the more useful the artifact is for later execution.
    """
    from veles.core.context import current_project
    from veles.core.plan_artifact import active_dir, create_plan as _create_plan

    project = current_project()
    if project is None:
        return {
            "error": "no active project; create_plan requires a project context",
        }
    plan = _create_plan(
        project.state_dir,
        objective=objective,
        scope=scope,
        assumptions=assumptions,
        risks=risks,
        steps=steps,
        tools_required=tools_required,
        approval_points=approval_points,
        validation=validation,
        rollback=rollback,
        done_condition=done_condition,
    )
    return {
        "plan_id": plan.id,
        "path": str(active_dir(project.state_dir) / f"{plan.id}.md"),
        "status": plan.status,
    }
