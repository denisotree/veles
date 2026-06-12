"""M62 — `veles subproject suggest` CLI + curator auto-trigger + run-flag tests."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from veles.cli.commands import subprojects as subprojects_cmd
from veles.core.project import init_project
from veles.core.subproject_proposer import (
    Cluster,
    recent_proposals,
    write_proposals,
)
from veles.core.wiki import Wiki


@pytest.fixture()
def project_with_cluster(tmp_path: Path):
    project = init_project(tmp_path / "demo", name="demo")
    wiki = Wiki(project.wiki_root)
    for slug, title in [
        ("frontend-auth", "Frontend authentication"),
        ("frontend-routes", "Frontend routes"),
        ("frontend-state", "Frontend state management"),
        ("frontend-build", "Frontend build pipeline"),
    ]:
        wiki.write_page(category="concepts", slug=slug, title=title, content="body")
    return project


def _ns(**fields):
    return type("A", (), fields)()


# ---- CLI ----


def test_suggest_prints_clusters_without_save(project_with_cluster, capsys) -> None:
    args = _ns(
        subproject_command="suggest",
        save=False,
        min_pages=3,
        min_similarity=0.2,
    )
    rc = subprojects_cmd.cmd_subproject(args, project_with_cluster)
    assert rc == 0
    out = capsys.readouterr().out
    assert "frontend" in out
    assert "pages=" in out
    # No file should be written
    proposals_dir = project_with_cluster.memory_dir / "proposals"
    if proposals_dir.exists():
        assert list(proposals_dir.iterdir()) == []


def test_suggest_with_save_persists_proposals(project_with_cluster, capsys) -> None:
    args = _ns(
        subproject_command="suggest",
        save=True,
        min_pages=3,
        min_similarity=0.2,
    )
    rc = subprojects_cmd.cmd_subproject(args, project_with_cluster)
    assert rc == 0
    out = capsys.readouterr().out
    assert "wrote" in out
    pages = list((project_with_cluster.memory_dir / "proposals").iterdir())
    assert pages, "expected at least one proposal markdown file"
    # The system-ops journal should mention the proposal op
    log = (project_with_cluster.memory_dir / "LOG.md").read_text(encoding="utf-8")
    assert "subproject-proposal" in log


def test_suggest_reports_no_clusters(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path / "empty", name="empty")
    args = _ns(
        subproject_command="suggest",
        save=False,
        min_pages=3,
        min_similarity=0.2,
    )
    rc = subprojects_cmd.cmd_subproject(args, project)
    assert rc == 0
    assert "no thematic clusters" in capsys.readouterr().out


# ---- curator auto-trigger ----


def test_proposer_skipped_when_resume_set(project_with_cluster, monkeypatch) -> None:
    from veles.cli._curator import _maybe_run_subproject_proposer

    args = _ns(provider="openrouter", resume="ses-X", no_proposer=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    _maybe_run_subproject_proposer(args, project_with_cluster)
    proposals_dir = project_with_cluster.memory_dir / "proposals"
    if proposals_dir.exists():
        assert list(proposals_dir.iterdir()) == []


def test_proposer_skipped_by_flag(project_with_cluster, monkeypatch) -> None:
    from veles.cli._curator import _maybe_run_subproject_proposer

    args = _ns(provider="openrouter", resume=None, no_proposer=True)
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    _maybe_run_subproject_proposer(args, project_with_cluster)
    proposals_dir = project_with_cluster.memory_dir / "proposals"
    if proposals_dir.exists():
        assert list(proposals_dir.iterdir()) == []


def test_proposer_skipped_when_no_api_key(project_with_cluster, monkeypatch) -> None:
    from veles.cli._curator import _maybe_run_subproject_proposer

    args = _ns(provider="openrouter", resume=None, no_proposer=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    _maybe_run_subproject_proposer(args, project_with_cluster)
    proposals_dir = project_with_cluster.memory_dir / "proposals"
    if proposals_dir.exists():
        assert list(proposals_dir.iterdir()) == []


def test_proposer_runs_first_time_and_writes_state(project_with_cluster, monkeypatch) -> None:
    from veles.cli._curator import _maybe_run_subproject_proposer

    args = _ns(provider="openrouter", resume=None, no_proposer=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    _maybe_run_subproject_proposer(args, project_with_cluster)
    pages = list((project_with_cluster.memory_dir / "proposals").iterdir())
    assert pages, "expected proposals to be written"
    state = project_with_cluster.state_dir / "proposer.state.json"
    assert state.is_file()


def test_proposer_idle_threshold_skips_second_call(project_with_cluster, monkeypatch) -> None:
    from veles.cli._curator import _maybe_run_subproject_proposer

    args = _ns(provider="openrouter", resume=None, no_proposer=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    _maybe_run_subproject_proposer(args, project_with_cluster)
    # Get mtime of first proposal page
    pages = list((project_with_cluster.memory_dir / "proposals").iterdir())
    first_mtime = pages[0].stat().st_mtime

    # Sleep a moment so a re-run would change mtime if it ran
    time.sleep(0.05)
    _maybe_run_subproject_proposer(args, project_with_cluster)
    second_mtime = pages[0].stat().st_mtime
    assert second_mtime == first_mtime, "second call should be no-op (idle threshold)"


def test_proposer_logs_skip_on_detector_failure(project_with_cluster, monkeypatch, capsys) -> None:
    from veles.cli._curator import _maybe_run_subproject_proposer

    args = _ns(provider="openrouter", resume=None, no_proposer=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")

    def _boom(*_a, **_kw):
        raise RuntimeError("detector exploded")

    import veles.core.subproject_proposer as sp

    monkeypatch.setattr(sp, "detect_clusters", _boom)
    _maybe_run_subproject_proposer(args, project_with_cluster)
    log = (project_with_cluster.memory_dir / "LOG.md").read_text(encoding="utf-8")
    assert "proposer-skip" in log


# ---- system-prompt surfacing ----


def test_proposals_block_present_in_system_prompt(project_with_cluster) -> None:
    from veles.cli._runtime import _build_run_system_prompt

    cluster = Cluster(
        slug="frontend-stack",
        pages=["wiki/concepts/frontend-auth.md"],
        score=0.5,
        rationale="ok",
    )
    write_proposals(project_with_cluster, [cluster])

    args = _ns(
        no_agents_md=False,
        no_index=False,
        prompt="anything",
    )
    prompt = _build_run_system_prompt(args, project_with_cluster)
    assert prompt is not None
    assert "<subproject-proposals>" in prompt
    assert "frontend-stack" in prompt


def test_proposals_block_absent_when_none(project_with_cluster) -> None:
    from veles.cli._runtime import _build_run_system_prompt

    args = _ns(
        no_agents_md=False,
        no_index=False,
        prompt="anything",
    )
    prompt = _build_run_system_prompt(args, project_with_cluster)
    # No proposals were written
    assert prompt is None or "<subproject-proposals>" not in prompt


def test_proposals_block_skipped_when_stale(project_with_cluster) -> None:
    from veles.cli._runtime import _build_run_system_prompt

    cluster = Cluster(slug="stale", pages=["wiki/concepts/a.md"], score=0.5, rationale="ok")
    write_proposals(project_with_cluster, [cluster])
    # Backdate the page 30 days
    page = project_with_cluster.memory_dir / "proposals" / "stale.md"
    old = time.time() - 30 * 86400
    import os

    os.utime(page, (old, old))

    args = _ns(no_agents_md=False, no_index=False, prompt="x")
    prompt = _build_run_system_prompt(args, project_with_cluster)
    assert prompt is None or "<subproject-proposals>" not in prompt


def test_recent_proposals_used_by_runtime(project_with_cluster) -> None:
    # Sanity: the helper that the runtime calls (`recent_proposals`) sees the
    # same .veles/memory/proposals/ pages as the rest of the M62 surface.
    cluster = Cluster(slug="frontend", pages=["wiki/concepts/a.md"], score=0.5, rationale="r")
    write_proposals(project_with_cluster, [cluster])
    pages = recent_proposals(project_with_cluster)
    assert any(p.slug == "frontend" for p in pages)
