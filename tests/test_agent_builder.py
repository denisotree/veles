"""M152: `build_command_agent` — the shared CLI agent-construction spine.

Covers the three contracts the factory must honour:

(a) the constructed Agent is wired with the toolset registry / system
    prompt / compressor the helpers produced;
(b) a failing `_ensure_api_key` short-circuits to None (the helper
    prints the error; the factory just propagates the refusal);
(c) the monkeypatch contract — patching `veles.cli._<helper>` IS picked
    up by the factory at call time (lazy package-attr resolution, same
    as the extracted command bodies).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.conftest import StubProvider
from veles.cli._agent_builder import build_command_agent
from veles.core.agent import Agent
from veles.core.project import init_project


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return init_project(tmp_path / "proj", name="proj")


def _args(**overrides):
    base = dict(
        provider="openrouter",
        model="test/model",
        max_iterations=7,
        verbose=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_returns_wired_agent(project, monkeypatch: pytest.MonkeyPatch) -> None:
    """(a) toolset / system prompt / compressor pass through to the Agent."""
    stub_provider = StubProvider()
    sentinel_registry = object()
    sentinel_compressor = object()
    load_calls: list[dict] = []

    monkeypatch.setattr("veles.cli._ensure_api_key", lambda *a, **kw: True)
    monkeypatch.setattr("veles.cli._make_provider", lambda name, model=None: stub_provider)
    monkeypatch.setattr("veles.cli._build_compressor", lambda args, proj, prov: sentinel_compressor)

    def fake_load_skills(proj, tools, *, provider, model):
        load_calls.append({"tools": tools, "provider": provider, "model": model})
        return sentinel_registry

    monkeypatch.setattr("veles.cli._load_skills", fake_load_skills)

    agent = build_command_agent(
        _args(),
        project,
        tools=("read_file", "write_file"),
        system_prompt="SYS",
        with_compressor=True,
        plan_mode=True,
    )

    assert isinstance(agent, Agent)
    assert agent._provider is stub_provider
    assert agent._registry is sentinel_registry
    assert agent._system_prompt == "SYS"
    assert agent._compressor is sentinel_compressor
    assert agent._plan_mode is True
    assert agent._max_iterations == 7
    assert agent._model == "test/model"
    assert load_calls == [
        {
            "tools": ("read_file", "write_file"),
            "provider": stub_provider,
            "model": "test/model",
        }
    ]


def test_missing_api_key_returns_none(
    project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """(b) `_ensure_api_key` False → None; helper's error reaches stderr;
    no provider / skills / Agent construction happens after the refusal."""
    import sys

    def fake_ensure(provider, **kw):
        print(f"error: no API key for --provider {provider}", file=sys.stderr)
        return False

    def boom(*a, **kw):  # nothing past the key check may run
        raise AssertionError("must not be called when the API key is missing")

    monkeypatch.setattr("veles.cli._ensure_api_key", fake_ensure)
    monkeypatch.setattr("veles.cli._make_provider", boom)
    monkeypatch.setattr("veles.cli._load_skills", boom)

    agent = build_command_agent(_args(provider="openrouter"), project, tools=("read_file",))

    assert agent is None
    assert "no API key" in capsys.readouterr().err


def test_check_api_key_false_skips_gate(project, monkeypatch: pytest.MonkeyPatch) -> None:
    """Commands that gated the key earlier pass check_api_key=False and the
    factory must not consult `_ensure_api_key` again (call-count parity)."""
    monkeypatch.setattr(
        "veles.cli._ensure_api_key",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("factory must not re-check the key")),
    )
    monkeypatch.setattr("veles.cli._make_provider", lambda name, model=None: StubProvider())
    monkeypatch.setattr("veles.cli._load_skills", lambda *a, **kw: object())

    agent = build_command_agent(_args(), project, tools=("read_file",), check_api_key=False)
    assert isinstance(agent, Agent)


def test_monkeypatch_contract_is_lazy(project, monkeypatch: pytest.MonkeyPatch) -> None:
    """(c) `build_command_agent` was imported directly from `_agent_builder`
    at module-import time — yet a later patch of `veles.cli._make_provider`
    must still be picked up (the factory resolves helpers at call time)."""
    seen: list[str] = []

    def recording_make_provider(name, model=None):
        seen.append(name)
        return StubProvider()

    monkeypatch.setattr("veles.cli._ensure_api_key", lambda *a, **kw: True)
    monkeypatch.setattr("veles.cli._make_provider", recording_make_provider)
    monkeypatch.setattr("veles.cli._load_skills", lambda *a, **kw: object())

    agent = build_command_agent(_args(provider="openrouter"), project, tools=())
    assert isinstance(agent, Agent)
    assert seen == ["openrouter"]


def test_tool_aware_provider_and_callable_system_prompt(
    project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ingest shape: `_make_tool_aware_provider` builds the provider and the
    system-prompt callable receives that exact provider instance."""
    stub_provider = StubProvider()
    bridge_calls: list[dict] = []
    prompt_saw: list[object] = []

    def fake_bridge(name, proj, *, skill_model=None):
        bridge_calls.append({"name": name, "skill_model": skill_model})
        return stub_provider

    monkeypatch.setattr("veles.cli._ensure_api_key", lambda *a, **kw: True)
    monkeypatch.setattr("veles.cli._make_tool_aware_provider", fake_bridge)
    monkeypatch.setattr(
        "veles.cli._make_provider",
        lambda name: (_ for _ in ()).throw(
            AssertionError("tool_aware=True must not use _make_provider")
        ),
    )
    monkeypatch.setattr("veles.cli._load_skills", lambda *a, **kw: object())

    def make_prompt(provider):
        prompt_saw.append(provider)
        return "QUALIFIED"

    agent = build_command_agent(
        _args(),
        project,
        tools=("read_file",),
        system_prompt=make_prompt,
        tool_aware=True,
    )

    assert isinstance(agent, Agent)
    assert agent._provider is stub_provider
    assert agent._system_prompt == "QUALIFIED"
    assert prompt_saw == [stub_provider]
    assert bridge_calls == [{"name": "openrouter", "skill_model": "test/model"}]
    # no compressor requested → none built
    assert agent._compressor is None
