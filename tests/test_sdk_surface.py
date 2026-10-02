"""`veles.sdk` is the public surface registry modules build on.

The name lists are a snapshot: changing one is a deliberate act that goes into
the CHANGELOG. Every name must be the very object core uses (a re-export, not a
copy), so a module and core never disagree about a type.
"""

from __future__ import annotations

import importlib

import pytest

_SURFACE: dict[str, dict[str, str]] = {
    "veles.sdk": {
        "Project": "veles.core.project",
        "current_origin": "veles.core.context",
        "current_project": "veles.core.context",
        "first_heading": "veles.core.text",
        "load_optional_toml": "veles.core.io_utils",
        "load_project": "veles.core.project",
        "normalize_slug": "veles.core.slug",
        "now_timestamp_slug": "veles.core.slug",
        "shown": "veles.core.text",
        "title_and_summary": "veles.core.text",
        "utc_iso": "veles.core.timeutil",
    },
    "veles.sdk.contributions": {
        "BackgroundOp": "veles.core.contributions",
        "Contribution": "veles.core.contributions",
        "CuratorTarget": "veles.core.contributions",
        "DreamStep": "veles.core.contributions",
        "Engine": "veles.core.contributions",
        "PageInfo": "veles.core.contributions",
        "PageSource": "veles.core.contributions",
        "ToolSet": "veles.core.contributions",
        "active": "veles.core.contributions",
        "contributions": "veles.core.contributions",
        "engine_enabled": "veles.core.layout.engines",
    },
    "veles.sdk.tools": {
        "RiskClass": "veles.core.risk",
        "TOOLSETS": "veles.core.tools.toolsets",
        "current_toolset": "veles.core.agent_state",
        "fetch_url": "veles.core.tools.builtin.fetch_url",
        "guard_write": "veles.core.tools.builtin.fs_write_guard",
        "is_inside": "veles.core.path_guard",
        "read_file": "veles.core.tools.builtin.read_file",
        "resolve_safe": "veles.core.path_guard",
        "scan_for_injection": "veles.core.safety",
        "tool": "veles.core.tools.registry",
        "trust_frontmatter": "veles.core.untrusted",
    },
    "veles.sdk.memory": {
        "DreamResult": "veles.core.dreaming",
        "IngestingMemoryProvider": "veles.core.memory.provider",
        "MemoryProvider": "veles.core.memory.provider",
        "RecallHit": "veles.core.memory.router",
        "append_memory_log": "veles.core.memory.artefacts",
        "escape_query": "veles.core.fts",
        "write_proposal": "veles.core.memory.artefacts",
    },
    "veles.sdk.layout": {
        "LayoutManifest": "veles.core.layout.manifest",
        "find_layout": "veles.core.layout.discovery",
        "load_context_file": "veles.runtime.prompt",
        "load_subprojects": "veles.core.subproject",
        "resolve_subproject_path": "veles.core.subproject",
    },
    "veles.sdk.jobs": {
        "MAX_DELEGATE_DEPTH": "veles.core.orchestration.delegation",
        "current_delegate_depth": "veles.core.orchestration.delegation",
        "current_subagent_factory": "veles.core.orchestration.delegation",
        "enter_delegate": "veles.core.orchestration.delegation",
        "exit_delegate": "veles.core.orchestration.delegation",
        "spawn": "veles.core.orchestration.workers",
        "submit_oneshot_job": "veles.core.jobs_store",
    },
}


@pytest.mark.parametrize("module", sorted(_SURFACE))
def test_sdk_names_are_the_snapshot(module: str) -> None:
    assert sorted(importlib.import_module(module).__all__) == sorted(_SURFACE[module])


@pytest.mark.parametrize(
    ("module", "name", "origin"),
    [(m, n, o) for m, names in sorted(_SURFACE.items()) for n, o in sorted(names.items())],
)
def test_sdk_names_are_core_objects(module: str, name: str, origin: str) -> None:
    exported = getattr(importlib.import_module(module), name)
    assert exported is getattr(importlib.import_module(origin), name)
