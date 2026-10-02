"""`background_op` contributions: daemon job kinds modules own (e.g. wiki ingest)."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

from veles.core.contributions import BackgroundOp
from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry


def test_daemon_builds_a_handler_per_contributed_op(tmp_path: Path, monkeypatch) -> None:
    import veles.daemon.background_ops as bg

    seen: dict[str, object] = {}

    def run(job, *, spawn_agent, project) -> str:
        seen["agent"] = spawn_agent("SYSTEM")
        seen["project"] = project
        return f"done {job.params['x']}"

    scratch, reg = ModuleRegistry(), ModuleRegistry()
    ModuleAPI(scratch, "m").contribute("background_op", "fake", BackgroundOp("fake", "run", run))
    reg.merge_from(scratch, "m")
    factories: list[str] = []

    def fake_factory(args, project, store, toolset, **_kw):
        factories.append(toolset)
        return lambda *, system_prompt, tools: f"agent<{system_prompt}>"

    monkeypatch.setattr(bg, "_scoped_factory_for", fake_factory)
    token = set_module_registry(reg)
    try:
        handlers = bg.make_contributed_kind_handlers(
            argparse.Namespace(), project="P", store="S", daemon_session=None
        )
    finally:
        reset_module_registry(token)
    assert "fake" in handlers
    assert handlers["fake"](SimpleNamespace(params={"x": 1})) == "done 1"
    assert seen == {"agent": "agent<SYSTEM>", "project": "P"}
    assert "run" in factories
