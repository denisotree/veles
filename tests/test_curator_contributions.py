"""`curator_target` and `subproject_source` contributions, and the post-turn
project-tree rescan (M118b)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from veles.core.contributions import CuratorTarget, PageSource
from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry
from veles.core.project import init_project


@pytest.fixture()
def home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path


def _with(point: str, name: str, obj: object):
    scratch, reg = ModuleRegistry(), ModuleRegistry()
    ModuleAPI(scratch, "m").contribute(point, name, obj)
    reg.merge_from(scratch, "m")
    return set_module_registry(reg)


def test_bare_project_curates_into_memory_only(home) -> None:
    from veles.runtime.learning import curation_plan

    project = init_project(home / "b", name="b", layout="bare")
    plan = curation_plan(project, "sess-1")
    assert "wiki_write_page" not in plan.persist_steps
    assert plan.persist_tools == frozenset({"memory_save_insight"})


def test_contributed_target_without_its_engine_is_ignored(home) -> None:
    from veles.runtime.learning import curation_plan

    project = init_project(home / "b", name="b", layout="bare")
    target = CuratorTarget(
        engine="fake",
        prepare=lambda p: None,
        instructions=lambda p, sid: ("intro", "- Call fake_save().\n", "log"),
        persist_tools=("fake_save",),
    )
    token = _with("curator_target", "fake", target)
    try:
        plan = curation_plan(project, "s")
    finally:
        reset_module_registry(token)
    assert "fake_save" not in plan.persist_steps


@dataclass
class _Page:
    rel_path: str
    title: str
    summary: str
    category: str


def test_subproject_proposer_reads_contributed_pages(home) -> None:
    from veles.core.subproject_proposer import detect_clusters

    project = init_project(home / "b", name="b", layout="bare")
    pages = [_Page(f"x/{i}.md", f"kafka consumer lag {i}", "s", "concepts") for i in range(5)]
    token = _with("subproject_source", "fake", PageSource(pages=lambda p: pages, engine=None))
    try:
        clusters = detect_clusters(project)
    finally:
        reset_module_registry(token)
    assert clusters and "kafka" in clusters[0].slug


def test_tree_rescan_runs_once_per_interval(home, monkeypatch) -> None:
    import veles.runtime.learning as learning

    project = init_project(home / "t", name="t", layout="bare")
    scans: list[int] = []
    monkeypatch.setattr(learning, "scan_project_tree", lambda p: scans.append(1))
    learning.maybe_rescan_tree(project)
    learning.maybe_rescan_tree(project)
    assert scans == [1]
