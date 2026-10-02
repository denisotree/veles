"""A fake content engine, loaded as a builtin module, reaches every release-A
point's consumer in core — and nothing of it shows up for a project whose layout
doesn't request the engine."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from veles.core import contributions as contrib
from veles.core.layout import clear_engine_cache
from veles.core.project import init_project

_FIXTURES = Path(__file__).parent / "fixtures" / "modules"


@pytest.fixture()
def engine(monkeypatch, tmp_path):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    monkeypatch.syspath_prepend(str(_FIXTURES))
    monkeypatch.setattr(contrib, "BUILTIN_MODULES", (*contrib.BUILTIN_MODULES, "fake_engine"))
    contrib.reset_builtin_contributions()
    clear_engine_cache()
    pack = tmp_path / "home" / ".veles" / "layouts" / "fakepack"
    pack.mkdir(parents=True)
    (pack / "layout.toml").write_text(
        '[layout]\nname = "fakepack"\n[layout.engines]\nfake = true\n', encoding="utf-8"
    )
    import fake_engine

    fake_engine.CALLS.clear()
    yield fake_engine
    contrib.reset_builtin_contributions()
    clear_engine_cache()
    sys.modules.pop("fake_engine", None)


def test_every_point_reaches_its_consumer(engine, tmp_path, monkeypatch) -> None:
    from veles.core.dreaming import dream_cycle
    from veles.core.memory import SessionStore
    from veles.core.memory.router import MemoryRouter
    from veles.core.self_doc import refresh_self_doc
    from veles.core.subproject_proposer import detect_clusters
    from veles.runtime.learning import curation_plan
    from veles.runtime.prompt import build_run_system_prompt

    project = init_project(tmp_path / "p", name="p", layout="fakepack")
    assert (project.root / "fake-engine").is_dir()  # scaffold

    store = SessionStore(project.memory_db_path)
    try:
        hits = MemoryRouter(project, store=store).recall("anything")
    finally:
        store.close()
    assert "fake-hit" in [h.title for h in hits]  # recall

    assert "<fake-engine-block>" in (build_run_system_prompt(project) or "")  # prompt

    dream_cycle(project, skip_insights=True, skip_dedup=True, skip_promote=True)
    assert "dream" in engine.CALLS  # dream_step

    assert "fake_do" in curation_plan(project, "s").persist_tools  # curator_target
    assert refresh_self_doc(project) == "fake/self-doc/overview.md"  # page_store
    clusters = detect_clusters(project, min_pages=2)  # subproject_source
    assert [c.pages for c in clusters] == [["f/1.md", "f/2.md"]]
    import argparse

    import veles.daemon.background_ops as bg

    monkeypatch.setattr(bg, "_scoped_factory_for", lambda *a, **k: lambda **kw: None)
    handlers = bg.make_contributed_kind_handlers(argparse.Namespace(), project=project, store=None)
    assert "fake" in handlers  # background_op
    assert contrib.load_tool_sets(project) == {
        t
        for c in contrib.contributions("tool")
        for t in c.obj.tools  # type: ignore[attr-defined]
        if c.obj.engine == "wiki"  # type: ignore[attr-defined]
    }  # tool: only the wiki set (engine off here) is gated
    assert "tool" in engine.CALLS


def test_nothing_of_the_engine_shows_for_a_project_without_it(engine, tmp_path) -> None:
    from veles.runtime.prompt import build_run_system_prompt

    project = init_project(tmp_path / "b", name="b", layout="bare")
    assert not (project.root / "fake-engine").exists()
    assert "<fake-engine-block>" not in (build_run_system_prompt(project) or "")
    assert "fake_do" in contrib.load_tool_sets(project)
