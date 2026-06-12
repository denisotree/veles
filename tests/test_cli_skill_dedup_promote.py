"""M61 — `veles skill {dedup, suggest-promote}` CLI + auto-trigger tests."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from veles.cli.commands import skills as skills_cmd
from veles.core.project import Project, init_project


# User-home isolation comes from the autouse `_hermetic_user_home`
# fixture in tests/conftest.py.
@pytest.fixture(autouse=True)
def _force_tfidf_fallback(monkeypatch):
    # Force TF-IDF fallback path so we don't hit any real API key.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


def _ns(**fields):
    return type("A", (), fields)()


def _write_skill(
    project: Project,
    name: str,
    *,
    description: str = "describe",
    body: str = "",
    use_count: int = 0,
    success_count: int = 0,
) -> None:
    skill_dir = project.skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    fm = [
        "---",
        f"name: {name}",
        f"description: {description}",
        f"use_count: {use_count}",
        f"success_count: {success_count}",
        "---",
        body or "body",
    ]
    (skill_dir / "SKILL.md").write_text("\n".join(fm), encoding="utf-8")


# ---- dedup CLI ----


def test_dedup_no_skills_reports_skip(project, capsys) -> None:
    args = _ns(
        skill_command="dedup",
        mode="tfidf",
        embedding_threshold=0.85,
        tfidf_threshold=0.5,
    )
    rc = skills_cmd.cmd_skill(args, project)
    assert rc == 0
    assert "at least 2" in capsys.readouterr().out


def test_dedup_reports_no_clusters_when_skills_distinct(project, capsys) -> None:
    _write_skill(project, "alpha", description="alpha", body="alpha alpha alpha")
    _write_skill(project, "bravo", description="bravo", body="bravo bravo bravo")
    args = _ns(
        skill_command="dedup",
        mode="tfidf",
        embedding_threshold=0.85,
        tfidf_threshold=0.99,
    )
    rc = skills_cmd.cmd_skill(args, project)
    assert rc == 0
    assert "no duplicate" in capsys.readouterr().out.lower()


def test_dedup_finds_clusters_with_tfidf(project, capsys) -> None:
    _write_skill(
        project,
        "auth-login",
        description="user login flow",
        body="login signup password reset email",
    )
    _write_skill(
        project,
        "auth-signup",
        description="user signup flow",
        body="login signup password reset email",
    )
    _write_skill(
        project,
        "build",
        description="ci/cd",
        body="docker compose deploy artifact",
    )
    args = _ns(
        skill_command="dedup",
        mode="tfidf",
        embedding_threshold=0.85,
        tfidf_threshold=0.3,
    )
    rc = skills_cmd.cmd_skill(args, project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "auth-login" in out
    assert "auth-signup" in out
    assert "tfidf" in out


# ---- suggest-promote CLI ----


def test_suggest_promote_no_candidates(project, capsys) -> None:
    _write_skill(project, "lonely", use_count=2, success_count=2)
    args = _ns(
        skill_command="suggest-promote",
        save=False,
        min_uses=10,
        min_success_rate=0.7,
    )
    rc = skills_cmd.cmd_skill(args, project)
    assert rc == 0
    assert "no project-scope" in capsys.readouterr().out


def test_suggest_promote_prints_candidates(project, capsys) -> None:
    _write_skill(project, "winner", use_count=20, success_count=18)
    args = _ns(
        skill_command="suggest-promote",
        save=False,
        min_uses=10,
        min_success_rate=0.7,
    )
    rc = skills_cmd.cmd_skill(args, project)
    out = capsys.readouterr().out
    assert rc == 0
    assert "winner" in out
    assert "use=" in out
    assert "(pass --save" in out


def test_suggest_promote_save_writes_proposals(project, capsys) -> None:
    _write_skill(project, "winner", use_count=20, success_count=18)
    args = _ns(
        skill_command="suggest-promote",
        save=True,
        min_uses=10,
        min_success_rate=0.7,
    )
    rc = skills_cmd.cmd_skill(args, project)
    out = capsys.readouterr().out
    assert rc == 0
    page = project.memory_dir / "proposals" / "promote-winner.md"
    assert page.is_file()
    assert "wrote 1 proposal" in out


# ---- auto-trigger ----


def test_auto_trigger_skipped_on_resume(project, monkeypatch) -> None:
    from veles.cli._curator import _maybe_suggest_promotions

    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    _write_skill(project, "winner", use_count=20, success_count=18)
    args = _ns(provider="openrouter", resume="ses-x", no_suggest_promote=False)
    _maybe_suggest_promotions(args, project)
    proposals = project.memory_dir / "proposals"
    if proposals.exists():
        assert not list(proposals.iterdir())


def test_auto_trigger_skipped_by_flag(project, monkeypatch) -> None:
    from veles.cli._curator import _maybe_suggest_promotions

    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    _write_skill(project, "winner", use_count=20, success_count=18)
    args = _ns(provider="openrouter", resume=None, no_suggest_promote=True)
    _maybe_suggest_promotions(args, project)
    proposals = project.memory_dir / "proposals"
    if proposals.exists():
        assert not list(proposals.iterdir())


def test_auto_trigger_writes_proposals_on_first_call(project, monkeypatch) -> None:
    from veles.cli._curator import _maybe_suggest_promotions

    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    _write_skill(project, "winner", use_count=20, success_count=18)
    args = _ns(provider="openrouter", resume=None, no_suggest_promote=False)
    _maybe_suggest_promotions(args, project)
    page = project.memory_dir / "proposals" / "promote-winner.md"
    assert page.is_file()
    state = project.state_dir / "promote_suggest.state.json"
    assert state.is_file()


def test_auto_trigger_idle_threshold_skips_second_call(project, monkeypatch) -> None:
    from veles.cli._curator import _maybe_suggest_promotions

    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    _write_skill(project, "winner", use_count=20, success_count=18)
    args = _ns(provider="openrouter", resume=None, no_suggest_promote=False)
    _maybe_suggest_promotions(args, project)
    page = project.memory_dir / "proposals" / "promote-winner.md"
    first = page.stat().st_mtime
    time.sleep(0.05)
    _maybe_suggest_promotions(args, project)
    second = page.stat().st_mtime
    assert first == second  # 7-day idle threshold blocked the rerun
