"""M61 — promote candidate detection + proposal writing + auto-trigger."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from veles.core.project import Project, init_project
from veles.core.skill_promotion import (
    find_promote_candidates,
    proposal_path,
    proposal_slug,
    recent_promote_proposals,
    write_promote_proposals,
)


# User-home isolation is provided by the autouse `_hermetic_user_home`
# fixture in tests/conftest.py.


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


def _write_skill(
    project: Project,
    name: str,
    *,
    description: str = "describe",
    body: str = "body",
    use_count: int = 0,
    success_count: int = 0,
) -> None:
    skill_dir = project.skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    fm_lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        f"use_count: {use_count}",
        f"success_count: {success_count}",
        "---",
        body,
    ]
    (skill_dir / "SKILL.md").write_text("\n".join(fm_lines), encoding="utf-8")


# ---- find_promote_candidates ----


def test_empty_when_no_skills(project: Project) -> None:
    assert find_promote_candidates(project) == []


def test_skip_below_min_uses(project: Project) -> None:
    _write_skill(project, "rare", use_count=3, success_count=3)
    assert find_promote_candidates(project, min_uses=10) == []


def test_skip_below_min_success_rate(project: Project) -> None:
    _write_skill(project, "flaky", use_count=20, success_count=5)
    assert find_promote_candidates(project, min_success_rate=0.7) == []


def test_picks_qualifying_skill(project: Project) -> None:
    _write_skill(project, "winner", use_count=20, success_count=18)
    candidates = find_promote_candidates(project)
    assert len(candidates) == 1
    assert candidates[0].skill.name == "winner"
    assert candidates[0].success_rate > 0.85


def test_ranks_strongest_first(project: Project) -> None:
    _write_skill(project, "good", use_count=11, success_count=10)
    _write_skill(project, "great", use_count=100, success_count=99)
    candidates = find_promote_candidates(project)
    assert [c.skill.name for c in candidates] == ["great", "good"]


def test_skip_when_user_scope_exists(project: Project, tmp_path: Path) -> None:
    """A same-name skill at user scope means promotion would collide."""
    from veles.core.skills import user_skills_dir

    _write_skill(project, "shadow", use_count=20, success_count=18)
    user_skill = user_skills_dir() / "shadow"
    user_skill.mkdir(parents=True, exist_ok=True)
    (user_skill / "SKILL.md").write_text(
        "---\nname: shadow\ndescription: existing\n---\nuser body\n",
        encoding="utf-8",
    )
    assert find_promote_candidates(project) == []


def test_skip_user_scope_skills(project: Project, tmp_path: Path) -> None:
    """User-scope skills already are at user scope; nothing to promote."""
    from veles.core.skills import user_skills_dir

    user_skill = user_skills_dir() / "user-only"
    user_skill.mkdir(parents=True, exist_ok=True)
    (user_skill / "SKILL.md").write_text(
        "---\n"
        "name: user-only\n"
        "description: desc\n"
        "use_count: 50\n"
        "success_count: 45\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    assert find_promote_candidates(project) == []


# ---- write_promote_proposals ----


def test_write_creates_page_and_log(project: Project) -> None:
    _write_skill(project, "winner", use_count=20, success_count=18)
    candidates = find_promote_candidates(project)
    written = write_promote_proposals(project, candidates)
    assert len(written) == 1
    page = proposal_path(project, "winner")
    assert page.is_file()
    body = page.read_text(encoding="utf-8")
    assert "Promote skill: winner" in body
    assert "veles skill promote winner" in body
    log = (project.memory_dir / "LOG.md").read_text(encoding="utf-8")
    assert "skill-promote-proposal" in log
    assert "winner" in log


def test_proposal_slug_uses_promote_prefix() -> None:
    assert proposal_slug("auth") == "promote-auth"


def test_write_idempotent_rewrites(project: Project) -> None:
    """Re-running with updated telemetry should overwrite the page."""
    _write_skill(project, "winner", use_count=20, success_count=18)
    cands1 = find_promote_candidates(project)
    write_promote_proposals(project, cands1)
    body1 = proposal_path(project, "winner").read_text(encoding="utf-8")
    assert "20 invocations" in body1
    # Bump the telemetry.
    _write_skill(project, "winner", use_count=50, success_count=45)
    cands2 = find_promote_candidates(project)
    write_promote_proposals(project, cands2)
    body2 = proposal_path(project, "winner").read_text(encoding="utf-8")
    assert "50 invocations" in body2


# ---- recent_promote_proposals ----


def test_recent_filters_by_age(project: Project) -> None:
    _write_skill(project, "winner", use_count=20, success_count=18)
    write_promote_proposals(project, find_promote_candidates(project))
    fresh = recent_promote_proposals(project, max_age_days=7)
    assert len(fresh) == 1
    # Backdate the proposal page 30 days.
    page = proposal_path(project, "winner")
    old = time.time() - 30 * 86400
    import os

    os.utime(page, (old, old))
    assert recent_promote_proposals(project, max_age_days=7) == []


def test_recent_excludes_non_promote_proposals(project: Project) -> None:
    """Subproject proposals (M62) share the proposals dir but a different prefix."""
    from veles.core.memory.artefacts import write_proposal

    write_proposal(
        project,
        slug="frontend-cluster",
        title="Subproject proposal: frontend-cluster",
        content="something",
    )
    out = recent_promote_proposals(project)
    assert out == []
