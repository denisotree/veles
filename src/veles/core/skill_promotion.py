"""Auto-promote suggestion for project-level skills (M61).

VISION §5.5: a project-level skill that proves itself across many
invocations is a candidate for `~/.veles/skills/` so other projects of
the same user can reuse it. M40 shipped the explicit `veles skill
promote <name>` verb; M61 adds the *suggestion* layer — every once in
a while we surface "this skill has been useful, want to promote?"
without requiring the user to remember.

Decision rule:

- `use_count >= min_uses` (default 10).
- `success_rate >= min_success_rate` (default 0.7).
- `scope == "project"` (already-user-level skills are excluded).
- No same-name skill at user scope (collision = noisy suggestion).

Output channel (M160): `.veles/memory/proposals/promote-<slug>.md` —
system memory, same proposals dir as M62 subproject proposals. The
proposals system-prompt block surfaces fresh ones to the agent; the
agent then mentions them to the user in conversation.
`recent_promote_proposals(project)` lists fresh ones; staleness is
mtime-based same as M62.

Idempotency: `write_promote_proposals` overwrites the page when a
candidate is still active, so updated telemetry is reflected on every
trigger.
"""

from __future__ import annotations

import datetime as _dt
import time
from dataclasses import dataclass
from pathlib import Path

from veles.core.memory.artefacts import (
    ProposalInfo,
    append_memory_log,
    list_proposals,
    proposals_dir,
    write_proposal,
)
from veles.core.project import Project
from veles.core.skills import Skill, discover_skills, user_skills_dir

_DEFAULT_MIN_USES = 10
_DEFAULT_MIN_SUCCESS_RATE = 0.7
_PROPOSAL_SLUG_PREFIX = "promote-"
_DEFAULT_MAX_AGE_DAYS = 7


@dataclass(frozen=True, slots=True)
class PromoteCandidate:
    """A project-level skill that meets the auto-promote bar."""

    skill: Skill
    success_rate: float
    rationale: str


def find_promote_candidates(
    project: Project,
    *,
    min_uses: int = _DEFAULT_MIN_USES,
    min_success_rate: float = _DEFAULT_MIN_SUCCESS_RATE,
) -> list[PromoteCandidate]:
    """Return project-scope skills that pass the promotion threshold.

    Excludes skills whose name already exists at user-scope to avoid
    proposing collisions. Excludes already user-scope skills since
    they're nothing to promote.
    """
    all_skills = discover_skills(project)
    user_dir = user_skills_dir()
    user_scope_names = {p.name for p in user_dir.iterdir()} if user_dir.is_dir() else set()
    out: list[PromoteCandidate] = []
    for skill in all_skills:
        if skill.scope != "project":
            continue
        if skill.name in user_scope_names:
            continue
        if skill.use_count < min_uses:
            continue
        if skill.use_count == 0:
            continue
        success_rate = skill.success_count / skill.use_count
        if success_rate < min_success_rate:
            continue
        out.append(
            PromoteCandidate(
                skill=skill,
                success_rate=success_rate,
                rationale=(
                    f"{skill.use_count} invocations, "
                    f"{int(success_rate * 100)}% success — consider promoting to user scope."
                ),
            )
        )
    # Strongest candidates first: rank by use_count * success_rate.
    out.sort(key=lambda c: -(c.skill.use_count * c.success_rate))
    return out


def proposal_slug(skill_name: str) -> str:
    return f"{_PROPOSAL_SLUG_PREFIX}{skill_name}"


def proposal_path(project: Project, skill_name: str) -> Path:
    return proposals_dir(project) / f"{proposal_slug(skill_name)}.md"


def _render_proposal(candidate: PromoteCandidate) -> tuple[str, str]:
    skill = candidate.skill
    title = f"Promote skill: {skill.name}"
    when = _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"# {title}",
        "",
        f"**Generated:** {when}",
        f"**Skill:** `{skill.name}` (project scope)",
        f"**Use count:** {skill.use_count}",
        f"**Success rate:** {int(candidate.success_rate * 100)}%",
        "",
        candidate.rationale,
        "",
        "## Skill description",
        "",
        skill.description,
        "",
        "## Suggested action",
        "",
        f"Promote to user scope: `veles skill promote {skill.name}`",
        "",
        "After promotion the skill becomes available in every Veles project on "
        "this machine. Pass `--keep-telemetry` to preserve the existing counters.",
    ]
    return title, "\n".join(lines) + "\n"


def write_promote_proposals(project: Project, candidates: list[PromoteCandidate]) -> list[str]:
    """Persist each candidate as `.veles/memory/proposals/promote-<name>.md`.

    Returns the written paths relative to the project root. Each write
    is journalled to the system-ops log.
    """
    written: list[str] = []
    for candidate in candidates:
        title, body = _render_proposal(candidate)
        path = write_proposal(
            project,
            slug=proposal_slug(candidate.skill.name),
            title=title,
            content=body,
        )
        append_memory_log(
            project,
            op="skill-promote-proposal",
            summary=(
                f"suggested promotion of skill '{candidate.skill.name}' "
                f"({candidate.skill.use_count} uses, "
                f"{int(candidate.success_rate * 100)}% success)"
            ),
        )
        written.append(path.relative_to(project.root).as_posix())
    return written


def recent_promote_proposals(
    project: Project, *, max_age_days: int = _DEFAULT_MAX_AGE_DAYS
) -> list[ProposalInfo]:
    """List `promote-*.md` proposals younger than `max_age_days`.

    Used by the system-prompt surfacing block so the agent only
    mentions promotions the user might still be interested in.
    """
    cutoff = time.time() - max_age_days * 86_400
    out: list[ProposalInfo] = []
    for page in list_proposals(project):
        if not page.slug.startswith(_PROPOSAL_SLUG_PREFIX):
            continue
        try:
            mtime = page.path.stat().st_mtime
        except OSError:
            continue
        if mtime >= cutoff:
            out.append(page)
    return out
