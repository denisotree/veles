"""M280 a2: the daemon's agent factory builds what an agent mode asks for.

Mirrors the REPL factory (`cli/repl/runtime.py`): planning gets the read-only
planning toolset and `plan_mode`, a mode's `system_block` and a phase's
`extra_system` reach the prompt, `toolless` means an empty registry. Before,
the daemon always built the full writing agent, so `/mode planning` in a chat
could still write files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli import _PLANNING_TOOLS, _RUN_TOOLS
from veles.cli.commands.daemon import _build_agent_for_turn, _FactorySettings
from veles.core.memory import SessionStore
from veles.core.modes import get_mode
from veles.core.project import init_project

_SETTINGS = _FactorySettings(
    provider_name="openrouter",
    model="stub/model",
    max_iterations=3,
    max_tokens=4096,
    verbose=False,
    no_compress=True,
    compress_threshold=50_000,
    compressor_model="stub/small",
    max_summariser_input_tokens=None,
    hard_ceiling_tokens=None,
)


@pytest.fixture()
def build(tmp_path: Path, monkeypatch):
    """`_build_agent_for_turn` with the provider, skills and Agent stubbed;
    returns (build_fn, captured Agent kwargs, toolsets asked of _load_skills)."""
    import veles.cli as cli_mod
    import veles.core.agent as agent_mod

    project = init_project(tmp_path, name=None, force=False)
    store = SessionStore(project.memory_db_path)
    captured: dict[str, object] = {}
    toolsets: list[tuple[str, ...]] = []

    def fake_load_skills(project, tools, **_kw):
        toolsets.append(tuple(tools))
        return object()

    class _StubAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(cli_mod, "_make_provider", lambda *a, **k: object())
    monkeypatch.setattr(cli_mod, "_load_skills", fake_load_skills)
    monkeypatch.setattr(cli_mod, "build_run_system_prompt", lambda *a, **k: "BASE")
    monkeypatch.setattr(cli_mod, "build_compressor", lambda *a, **k: None)
    monkeypatch.setattr(agent_mod, "Agent", _StubAgent)

    def _build(**kw):
        sid = store.create_session()
        _build_agent_for_turn(
            _SETTINGS, project=project, store=store, session_id=sid, prompt="hi", **kw
        )
        return sid

    yield _build, captured, toolsets, store
    store.close()


def test_default_is_unchanged(build) -> None:
    _build, captured, toolsets, _ = build
    _build()
    assert toolsets == [tuple(_RUN_TOOLS)]
    assert captured["plan_mode"] is False
    assert captured["system_prompt"] == "BASE"


def test_planning_gets_the_read_only_toolset_and_plan_mode(build) -> None:
    _build, captured, toolsets, _ = build
    _build(mode="planning")
    assert toolsets == [tuple(_PLANNING_TOOLS)]
    assert "write_file" not in _PLANNING_TOOLS  # the point of the toolset
    assert captured["plan_mode"] is True
    block = get_mode("planning").system_block.strip()
    assert block and block in str(captured["system_prompt"])


def test_writing_keeps_the_full_toolset(build) -> None:
    _build, captured, toolsets, _ = build
    _build(mode="writing")
    assert toolsets == [tuple(_RUN_TOOLS)]
    assert captured["plan_mode"] is False


def test_toolless_hands_the_turn_an_empty_registry(build) -> None:
    from veles.core.tools.registry import Registry

    _build, captured, toolsets, _ = build
    _build(mode="goal", toolless=True)
    assert toolsets == []  # no toolset loaded at all
    registry = captured["registry"]
    assert isinstance(registry, Registry)
    assert registry.list_names() == []


def test_a_phase_prompt_is_appended_after_the_mode_block(build) -> None:
    _build, captured, _, _ = build
    _build(mode="goal", extra_system="PHASE: interview")
    prompt = str(captured["system_prompt"])
    assert prompt.startswith("BASE")
    assert prompt.endswith("PHASE: interview")
    assert get_mode("goal").system_block.strip() in prompt


def test_a_given_session_is_used_not_a_new_one(build) -> None:
    """A mode calls the factory several times per turn (AutoMode's scratch
    agent, GoalMode's phases); each must reuse the turn's session, not mint an
    empty one."""
    _build, captured, _, store = build
    before = len(store.list_sessions(limit=100))
    sid = _build(mode="planning")
    assert captured["session_id"] == sid
    assert len(store.list_sessions(limit=100)) == before + 1  # only _build's own
