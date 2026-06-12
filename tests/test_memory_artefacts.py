"""M160 — `.veles/memory/` artefact tree: paths, journal, proposals, views."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory.artefacts import (
    ProposalInfo,
    append_memory_log,
    ensure_memory_dirs,
    insights_dir,
    list_proposals,
    memory_log_path,
    proposals_dir,
    sessions_dir,
    write_insight_view,
    write_proposal,
    write_session_summary,
)
from veles.core.project import Project, init_project


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


# ---- paths ----


def test_paths_live_under_state_dir(project: Project) -> None:
    assert project.memory_dir == project.state_dir / "memory"
    assert project.jobs_dir == project.state_dir / "jobs"
    assert memory_log_path(project) == project.memory_dir / "LOG.md"
    assert insights_dir(project) == project.memory_dir / "insights"
    assert sessions_dir(project) == project.memory_dir / "sessions"
    assert proposals_dir(project) == project.memory_dir / "proposals"


def test_ensure_memory_dirs_creates_tree(project: Project) -> None:
    ensure_memory_dirs(project)
    assert insights_dir(project).is_dir()
    assert sessions_dir(project).is_dir()
    assert proposals_dir(project).is_dir()


def test_artefacts_never_touch_user_content(project: Project) -> None:
    """The whole memory tree stays under `.veles/` — never in `wiki/`."""
    ensure_memory_dirs(project)
    write_proposal(project, slug="p", title="P", content="body")
    write_session_summary(project, slug="s", title="S", content="body")
    write_insight_view(project, slug="i", title="I", body="body")
    append_memory_log(project, op="test", summary="x")
    wiki_proposals = project.root / "wiki" / "proposals"
    assert not wiki_proposals.exists() or not list(wiki_proposals.iterdir())


# ---- journal ----


def test_append_memory_log_creates_and_appends(project: Project) -> None:
    append_memory_log(project, op="curate-batch", summary="2 sessions")
    append_memory_log(project, op="autopilot-run_shell", summary="dispatched")
    log = memory_log_path(project).read_text(encoding="utf-8")
    assert "curate-batch" in log
    assert "autopilot-run_shell" in log
    assert log.index("curate-batch") < log.index("autopilot-run_shell")


# ---- pages ----


def test_write_proposal_normalises_slug_and_adds_h1(project: Project) -> None:
    path = write_proposal(project, slug="Hello World!", title="Hello", content="no heading body")
    assert path.name == "hello-world.md"
    body = path.read_text(encoding="utf-8")
    assert body.startswith("# Hello")


def test_write_proposal_idempotent_overwrite(project: Project) -> None:
    write_proposal(project, slug="x", title="X", content="# X\n\nv1")
    path = write_proposal(project, slug="x", title="X", content="# X\n\nv2")
    assert path.read_text(encoding="utf-8").endswith("v2")
    assert len(list(proposals_dir(project).iterdir())) == 1


def test_write_session_summary_and_insight_view_paths(project: Project) -> None:
    s = write_session_summary(project, slug="ses-1", title="S", content="# S\n\nbody")
    i = write_insight_view(project, slug="lesson", title="L", body="# L\n\nbody")
    assert s.parent == sessions_dir(project)
    assert i.parent == insights_dir(project)


# ---- listing ----


def test_list_proposals_round_trip(project: Project) -> None:
    write_proposal(
        project,
        slug="frontend",
        title="Subproject proposal: frontend",
        content="# Subproject proposal: frontend\n\n4 pages share thematic tokens.",
    )
    out = list_proposals(project)
    assert len(out) == 1
    info = out[0]
    assert isinstance(info, ProposalInfo)
    assert info.slug == "frontend"
    assert info.title == "Subproject proposal: frontend"
    assert "thematic tokens" in info.summary
    assert info.path.is_file()


def test_list_proposals_empty_when_dir_missing(project: Project) -> None:
    assert list_proposals(project) == []
