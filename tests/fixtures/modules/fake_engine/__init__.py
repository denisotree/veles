"""A content engine that contributes one object to every release-A point — the
end-to-end check that core reaches each contribution through the point alone."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CALLS: list[str] = []


@dataclass
class _Page:
    rel_path: str
    title: str
    summary: str
    category: str


def register(api) -> None:
    from veles.core.contributions import (
        BackgroundOp,
        CuratorTarget,
        DreamStep,
        Engine,
        PageSource,
        ToolSet,
    )
    from veles.core.layout.engines import engine_enabled
    from veles.core.memory.router import RecallHit

    def on(project) -> bool:
        return engine_enabled(project, "fake")

    api.contribute("engine", "fake", Engine("fake"))
    api.contribute(
        "tool",
        "fake",
        ToolSet(load=lambda: CALLS.append("tool"), tools=("fake_do",), engine="fake"),
    )
    api.contribute(
        "recall",
        "fake",
        lambda project, query, *, limit: (
            [RecallHit(rel_path="fake:1", title="fake-hit", summary=query)] if on(project) else []
        ),
    )
    api.contribute(
        "prompt",
        "fake",
        lambda project, *, include_index: ["<fake-engine-block>"] if on(project) else [],
    )
    api.contribute(
        "dream_step",
        "fake",
        DreamStep("fake", lambda p, r, *, dry_run: CALLS.append("dream"), "skip_lint"),
    )
    api.contribute(
        "curator_target",
        "fake",
        CuratorTarget(
            engine="fake",
            prepare=lambda p: CALLS.append("curator-prepare"),
            instructions=lambda p, sid: ("intro", "- Call fake_do().\n", "log"),
            persist_tools=("fake_do",),
        ),
    )
    api.contribute(
        "subproject_source",
        "fake",
        PageSource(
            pages=lambda p: [
                _Page("f/1.md", "kafka consumer lag", "s", "concepts"),
                _Page("f/2.md", "kafka consumer lag runbook", "s", "concepts"),
            ],
            engine="fake",
        ),
    )
    api.contribute(
        "self_doc",
        "fake",
        lambda project, content: "fake/self-doc.md" if on(project) else None,
    )
    api.contribute(
        "scaffold",
        "fake",
        lambda root, manifest: (
            (Path(root) / "fake-engine").mkdir(exist_ok=True)
            if manifest.engine_enabled("fake")
            else None
        ),
    )
    api.contribute(
        "background_op",
        "fake",
        BackgroundOp(kind="fake", toolset="run", run=lambda job, *, spawn_agent, project: "ok"),
    )
