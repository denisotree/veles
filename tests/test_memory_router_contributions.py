"""Recall streams contributed by modules (`api.contribute("recall", …)`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.memory.router import MemoryRouter, RecallHit
from veles.core.modules import (
    ModuleAPI,
    ModuleRegistry,
    reset_module_registry,
    set_module_registry,
)
from veles.core.project import init_project


@pytest.fixture()
def project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return init_project(tmp_path / "p", name="p", layout="bare")


def _with(contribs: dict[str, object]):
    scratch, reg = ModuleRegistry(), ModuleRegistry()
    for name, fn in contribs.items():
        ModuleAPI(scratch, "m").contribute("recall", name, fn)
    reg.merge_from(scratch, "m")
    return set_module_registry(reg)


def test_contributed_recall_hits_reach_the_result(project) -> None:
    def fake(proj, query: str, *, limit: int) -> list[RecallHit]:
        assert proj is project and limit > 0
        return [RecallHit(rel_path="fake:1", title="from-module", summary=query)]

    token = _with({"fake": fake})
    store = SessionStore(project.memory_db_path)
    try:
        hits = MemoryRouter(project, store=store).recall("kafka lag")
    finally:
        store.close()
        reset_module_registry(token)
    assert "from-module" in [h.title for h in hits]


def test_a_raising_recall_contribution_does_not_break_recall(project) -> None:
    def boom(proj, query: str, *, limit: int) -> list[RecallHit]:
        raise RuntimeError("module exploded")

    def fine(proj, query: str, *, limit: int) -> list[RecallHit]:
        return [RecallHit(rel_path="ok:1", title="still-here", summary="x")]

    token = _with({"boom": boom, "fine": fine})
    store = SessionStore(project.memory_db_path)
    try:
        hits = MemoryRouter(project, store=store).recall("anything")
    finally:
        store.close()
        reset_module_registry(token)
    assert [h.title for h in hits] == ["still-here"]
