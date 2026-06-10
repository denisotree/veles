"""Plan-as-durable-artifact (Tier ε late, closes M70 xfail).

A *plan* in this module is the «how to approach the work» artifact that
the agent and the user share for high-risk or multi-step tasks. Stored
as one markdown file per plan with YAML frontmatter; lives in
`<project>/.veles/plans/active/<id>.md` until it's marked done, then
moves to `<project>/.veles/plans/completed/<id>.md`.

This is the storage half of the «Planning mode» story (M71 gave us the
runtime-state half). The two are independent: you can have an active
plan without being in `AgentState.PLANNING`, and you can be in planning
mode without a plan artifact. They cooperate when both are present —
Planning blocks mutations while you draft, the artifact persists the
draft itself.

Why this matters for M70: the existing `xfail` eval
`test_compaction_preserves_active_plan` requires *some* canonical
representation of an active plan that the compactor can preserve across
turn boundaries. This module provides it; M71 hooks the artifact into
the system prompt; the compactor reattaches the artifact reference on
rehydration. After this milestone the eval flips to a real pass.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

PLANS_DIRNAME = "plans"
PLANS_ACTIVE_SUBDIR = "active"
PLANS_COMPLETED_SUBDIR = "completed"

PlanStatus = Literal["draft", "approved", "executing", "completed", "abandoned"]


@dataclass(slots=True)
class PlanArtifact:
    id: str
    objective: str
    scope: str = ""
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    tools_required: list[str] = field(default_factory=list)
    approval_points: list[str] = field(default_factory=list)
    validation: list[str] = field(default_factory=list)
    rollback: str = ""
    done_condition: str = ""
    status: PlanStatus = "draft"
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None
    evidence_ref: str | None = None


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def plans_dir(state_dir: Path) -> Path:
    return state_dir / PLANS_DIRNAME


def active_dir(state_dir: Path) -> Path:
    return plans_dir(state_dir) / PLANS_ACTIVE_SUBDIR


def completed_dir(state_dir: Path) -> Path:
    return plans_dir(state_dir) / PLANS_COMPLETED_SUBDIR


def plan_ref(plan_id: str) -> str:
    """Stable URI scheme for cross-referencing a plan from other artefacts
    (compaction summaries, events.jsonl, approval records)."""
    return f"artifact://veles/plans/{plan_id}"


def parse_plan_ref(ref: str) -> str | None:
    """Inverse of `plan_ref` — return plan_id, or None if `ref` doesn't match."""
    m = re.fullmatch(r"artifact://veles/plans/([A-Za-z0-9]+)", ref)
    return m.group(1) if m else None


# ---------- storage ----------


def create_plan(
    state_dir: Path,
    *,
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
) -> PlanArtifact:
    if not objective.strip():
        raise ValueError("plan objective cannot be empty")
    now = _now_iso()
    plan = PlanArtifact(
        id=uuid.uuid4().hex[:12],
        objective=objective.strip(),
        scope=scope,
        assumptions=list(assumptions or []),
        risks=list(risks or []),
        steps=list(steps or []),
        tools_required=list(tools_required or []),
        approval_points=list(approval_points or []),
        validation=list(validation or []),
        rollback=rollback,
        done_condition=done_condition,
        status="draft",
        created_at=now,
        updated_at=now,
    )
    _write(state_dir, plan, completed=False)
    return plan


def read_plan(state_dir: Path, plan_id: str) -> PlanArtifact | None:
    """Look up a plan by id in both `active/` and `completed/` directories."""
    for d in (active_dir(state_dir), completed_dir(state_dir)):
        p = d / f"{plan_id}.md"
        if p.exists():
            return _read_markdown(p)
    return None


def list_active(state_dir: Path) -> list[PlanArtifact]:
    d = active_dir(state_dir)
    if not d.exists():
        return []
    out: list[PlanArtifact] = []
    for f in sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix == ".md":
            plan = _read_markdown(f)
            if plan is not None:
                out.append(plan)
    return out


def list_completed(state_dir: Path) -> list[PlanArtifact]:
    d = completed_dir(state_dir)
    if not d.exists():
        return []
    out: list[PlanArtifact] = []
    for f in sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix == ".md":
            plan = _read_markdown(f)
            if plan is not None:
                out.append(plan)
    return out


def update_status(
    state_dir: Path,
    plan_id: str,
    *,
    status: PlanStatus,
) -> PlanArtifact:
    plan = _require(state_dir, plan_id)
    if plan.status == status:
        return plan
    plan.status = status
    plan.updated_at = _now_iso()
    _write(state_dir, plan, completed=False)
    return plan


def mark_done(
    state_dir: Path,
    plan_id: str,
    *,
    evidence_ref: str | None = None,
) -> PlanArtifact:
    """Move plan from `active/` to `completed/`. evidence_ref is optional
    pointer to whatever proves the plan was satisfied."""
    plan = _require(state_dir, plan_id)
    plan.status = "completed"
    plan.completed_at = _now_iso()
    plan.updated_at = plan.completed_at
    plan.evidence_ref = evidence_ref
    # Remove from active first to avoid duplicate-id collisions on filesystem.
    active_path = active_dir(state_dir) / f"{plan_id}.md"
    if active_path.exists():
        active_path.unlink()
    _write(state_dir, plan, completed=True)
    return plan


def render_system_block(plan: PlanArtifact) -> str:
    """Render `<active-plan>...</active-plan>` for system-prompt injection.

    Kept compact — the model sees objective, done_condition, current step
    list (numbered), and approval points. Full scope / risks / rollback
    stay in the artifact body so the prompt doesn't bloat per turn.
    """
    lines = [
        f'<active-plan id="{plan.id}" status="{plan.status}" ref="{plan_ref(plan.id)}">',
        f"Objective: {plan.objective}",
    ]
    if plan.done_condition:
        lines.append(f"Done when: {plan.done_condition}")
    if plan.steps:
        lines.append("Steps:")
        for i, s in enumerate(plan.steps, 1):
            lines.append(f"  {i}. {s}")
    if plan.approval_points:
        lines.append("Approval points: " + ", ".join(plan.approval_points))
    lines.append("</active-plan>")
    return "\n".join(lines)


# ---------- markdown serialization ----------


def _write(state_dir: Path, plan: PlanArtifact, *, completed: bool) -> None:
    target_dir = completed_dir(state_dir) if completed else active_dir(state_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{plan.id}.md"
    path.write_text(_to_markdown(plan), encoding="utf-8")


def _require(state_dir: Path, plan_id: str) -> PlanArtifact:
    plan = read_plan(state_dir, plan_id)
    if plan is None:
        raise KeyError(f"no plan with id {plan_id!r} at {state_dir}")
    return plan


_FRONTMATTER_KEYS = ("id", "status", "created_at", "updated_at", "completed_at", "evidence_ref")


def _append_text_section(out: list[str], header: str, text: str) -> None:
    if not text:
        return
    out.extend(("## " + header, text, ""))


def _append_bullet_section(out: list[str], header: str, items: list[str]) -> None:
    if not items:
        return
    out.append("## " + header)
    out.extend(f"- {item}" for item in items)
    out.append("")


def _to_markdown(plan: PlanArtifact) -> str:
    """YAML-frontmatter + human-readable body. Body fields mirror the
    dataclass so a round-trip through `_read_markdown` is loss-free."""
    d = asdict(plan)
    frontmatter = ["---"]
    frontmatter.extend(f"{key}: {d[key]!s}" for key in _FRONTMATTER_KEYS if d.get(key) is not None)
    frontmatter.append("---")

    body: list[str] = ["", f"# {plan.objective}", ""]
    _append_text_section(body, "Scope", plan.scope)
    _append_text_section(body, "Done condition", plan.done_condition)
    body.append("## Steps")
    if plan.steps:
        body.extend(f"{i}. {step}" for i, step in enumerate(plan.steps, 1))
    else:
        body.append("(no steps yet)")
    body.append("")
    _append_bullet_section(body, "Assumptions", plan.assumptions)
    _append_bullet_section(body, "Risks", plan.risks)
    _append_bullet_section(body, "Tools required", plan.tools_required)
    _append_bullet_section(body, "Approval points", plan.approval_points)
    _append_bullet_section(body, "Validation", plan.validation)
    _append_text_section(body, "Rollback", plan.rollback)
    return "\n".join(frontmatter + body)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _read_markdown(path: Path) -> PlanArtifact | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _FRONTMATTER_RE.match(text)
    if m is None:
        return None
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    body = text[m.end():]
    obj_match = re.match(r"\s*#\s+(.+?)\s*$", body, re.MULTILINE)
    objective = obj_match.group(1).strip() if obj_match else "(no objective)"
    sections = _split_sections(body)
    return PlanArtifact(
        id=fm.get("id", path.stem),
        objective=objective,
        scope=_section_text(sections, "Scope"),
        assumptions=_section_list(sections, "Assumptions"),
        risks=_section_list(sections, "Risks"),
        steps=_section_numbered(sections, "Steps"),
        tools_required=_section_list(sections, "Tools required"),
        approval_points=_section_list(sections, "Approval points"),
        validation=_section_list(sections, "Validation"),
        rollback=_section_text(sections, "Rollback"),
        done_condition=_section_text(sections, "Done condition"),
        status=_coerce_status(fm.get("status")),
        created_at=fm.get("created_at", ""),
        updated_at=fm.get("updated_at", ""),
        completed_at=fm.get("completed_at") or None,
        evidence_ref=fm.get("evidence_ref") or None,
    )


def _coerce_status(raw: str | None) -> PlanStatus:
    valid: set[str] = {"draft", "approved", "executing", "completed", "abandoned"}
    if raw in valid:
        return raw  # type: ignore[return-value]
    return "draft"


def _split_sections(body: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    last_key: str | None = None
    buf: list[str] = []
    for line in body.splitlines():
        m = _SECTION_RE.match(line)
        if m is not None:
            if last_key is not None:
                parts[last_key] = "\n".join(buf).strip()
            last_key = m.group(1).strip()
            buf = []
        elif last_key is not None:
            buf.append(line)
    if last_key is not None:
        parts[last_key] = "\n".join(buf).strip()
    return parts


def _section_text(sections: dict[str, str], name: str) -> str:
    return sections.get(name, "").strip()


def _section_list(sections: dict[str, str], name: str) -> list[str]:
    block = sections.get(name, "")
    out: list[str] = []
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("- "):
            out.append(s[2:].strip())
    return out


def _section_numbered(sections: dict[str, str], name: str) -> list[str]:
    block = sections.get(name, "")
    out: list[str] = []
    for line in block.splitlines():
        s = line.strip()
        m = re.match(r"\d+\.\s+(.+)$", s)
        if m is not None:
            out.append(m.group(1).strip())
    return out


# ---------- compaction integration ----------


def collect_active_refs(state_dir: Path) -> list[str]:
    """List `artifact://veles/plans/<id>` URIs for every active plan.

    The compactor calls this to embed plan refs in the handoff summary —
    those refs survive rehydration verbatim, which closes the M70 xfail
    `test_compaction_preserves_active_plan`.
    """
    return [plan_ref(p.id) for p in list_active(state_dir)]


__all__ = [
    "PLANS_ACTIVE_SUBDIR",
    "PLANS_COMPLETED_SUBDIR",
    "PLANS_DIRNAME",
    "PlanArtifact",
    "PlanStatus",
    "active_dir",
    "collect_active_refs",
    "completed_dir",
    "create_plan",
    "list_active",
    "list_completed",
    "mark_done",
    "parse_plan_ref",
    "plan_ref",
    "plans_dir",
    "read_plan",
    "render_system_block",
    "update_status",
]
