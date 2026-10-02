"""Final-review fixes for release A: names collide with builtins too; the
identity consumers key on must match the contributed name; failures in
directly-called points are contained; recall stream order is 1.2.1's."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.contributions import BackgroundOp, CuratorTarget, Engine, PageSource
from veles.core.module_manifest import parse_manifest
from veles.core.modules import (
    ModuleAPI,
    ModuleHandle,
    ModuleLoadError,
    ModuleRegistry,
    load_module,
    reset_module_registry,
    set_module_registry,
)
from veles.core.project import init_project


def _module(root: Path, body: str) -> ModuleHandle:
    d = root / "mine"
    d.mkdir(parents=True)
    (d / "module.toml").write_text(
        '[module]\nname = "mine"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (d / "m.py").write_text(body, encoding="utf-8")
    return ModuleHandle("mine", parse_manifest((d / "module.toml").read_text()), d)


def test_a_user_module_cannot_take_a_builtin_name(tmp_path) -> None:
    body = (  # `tool:agentops` belongs to the builtin agentops module
        "from veles.core.contributions import ToolSet\n"
        "def register(api):\n"
        "    api.contribute('tool', 'agentops', ToolSet(load=lambda: None, tools=()))\n"
    )
    with pytest.raises(ModuleLoadError, match="already registered"):
        load_module(_module(tmp_path, body), ModuleRegistry())


def test_core_recall_stream_names_are_reserved(tmp_path) -> None:
    body = (
        "def register(api):\n    api.contribute('recall', 'insights', lambda p, q, *, limit: [])\n"
    )
    with pytest.raises(ModuleLoadError, match="reserved"):
        load_module(_module(tmp_path, body), ModuleRegistry())


def test_background_op_name_must_be_its_kind() -> None:
    with pytest.raises(ValueError, match="kind"):
        ModuleAPI(ModuleRegistry(), "m").contribute(
            "background_op", "other", BackgroundOp("ingest", "run", lambda *a, **k: "")
        )


def _with(point: str, name: str, obj: object):
    scratch, reg = ModuleRegistry(), ModuleRegistry()
    ModuleAPI(scratch, "m").contribute(point, name, obj)
    reg.merge_from(scratch, "m")
    return set_module_registry(reg)


@pytest.fixture()
def project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return init_project(tmp_path / "p", name="p", layout="bare")


def _boom(*_a, **_k):
    raise RuntimeError("module exploded")


def test_a_raising_page_source_does_not_break_self_doc_or_clusters(project) -> None:
    from veles.core.self_doc import generate_self_doc
    from veles.core.subproject_proposer import detect_clusters

    token = _with("subproject_source", "boom", PageSource(pages=_boom))
    try:
        assert detect_clusters(project) == []
        assert generate_self_doc(project).wiki_page_count == 0
    finally:
        reset_module_registry(token)


def test_a_raising_curator_target_falls_back_to_memory(project, monkeypatch) -> None:
    from veles.core import contributions as contrib
    from veles.runtime.learning import curation_plan

    # Treat only the broken target as active (its engine isn't real).
    monkeypatch.setattr(
        contrib,
        "active",
        lambda p, point: [c for c in contrib.contributions(point) if c.name == "boom"],
    )
    target = CuratorTarget(engine="x", prepare=_boom, instructions=_boom, persist_tools=("x",))
    token = _with("curator_target", "boom", target)
    try:
        plan = curation_plan(project, "s")
    finally:
        reset_module_registry(token)
    assert plan.persist_tools == frozenset({"memory_save_insight"})


def test_contributed_recall_ranks_before_external_providers_on_a_tie(project, monkeypatch) -> None:
    """1.2.1's stream order: insights, turns, about, wiki (now: contributions), extra."""
    from veles.core.memory import SessionStore
    from veles.core.memory.router import MemoryRouter, RecallHit

    monkeypatch.setattr(
        MemoryRouter,
        "_collect_extra",
        lambda self, q, *, limit: [RecallHit(rel_path="x:1", title="extra-hit", summary="s")],
    )
    token = _with(
        "recall",
        "mod",
        lambda p, q, *, limit: [RecallHit(rel_path="m:1", title="module-hit", summary="s")],
    )
    store = SessionStore(project.memory_db_path)
    try:
        hits = MemoryRouter(project, store=store).recall("q", limit=1)
    finally:
        store.close()
        reset_module_registry(token)
    assert [h.title for h in hits] == ["module-hit"]


def test_engine_import_is_used() -> None:
    assert Engine("x").name == "x"
