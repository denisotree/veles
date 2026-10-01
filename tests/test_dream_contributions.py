"""`dream_step` contributions: module steps inside the dream cycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.contributions import DreamStep
from veles.core.dreaming import dream_cycle
from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry
from veles.core.project import init_project

_SKIP_CORE = dict(skip_insights=True, skip_dedup=True, skip_promote=True)


@pytest.fixture()
def project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return init_project(tmp_path / "p", name="p", layout="bare")


def _with(step: DreamStep):
    scratch, reg = ModuleRegistry(), ModuleRegistry()
    ModuleAPI(scratch, "m").contribute("dream_step", step.name, step)
    reg.merge_from(scratch, "m")
    return set_module_registry(reg)


def test_contributed_step_runs_and_its_failure_becomes_a_note(project) -> None:
    ran: list[bool] = []

    def run(proj, result, *, dry_run: bool) -> None:
        ran.append(dry_run)
        raise RuntimeError("step exploded")

    token = _with(DreamStep(name="fake", run=run, skip_flag="skip_lint"))
    try:
        result = dream_cycle(project, **_SKIP_CORE)
    finally:
        reset_module_registry(token)
    assert ran == [False]
    assert any("fake step failed" in n for n in result.notes)


def test_contributed_step_honours_its_skip_flag(project) -> None:
    ran: list[bool] = []
    step = DreamStep(
        name="fake", run=lambda p, r, *, dry_run: ran.append(dry_run), skip_flag="skip_lint"
    )
    token = _with(step)
    try:
        dream_cycle(project, skip_lint=True, **_SKIP_CORE)
    finally:
        reset_module_registry(token)
    assert ran == []


def test_wiki_lint_and_reindex_still_run_on_a_wiki_project(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    wiki_project = init_project(tmp_path / "w", name="w", layout="llm-wiki")
    result = dream_cycle(wiki_project, **_SKIP_CORE)
    assert not any("step failed" in n for n in result.notes)
    assert result.lint_findings >= 0 and result.reindexed_pages >= 0
