"""M204 Phase 2: the daemon gets a sub-agent factory (it was REPL-only).

Audit prerequisite: `set_subagent_factory` was wired only in the REPL, so a
daemon/channel/job agent could not `delegate` or run `wiki_add` (its per-file
sub-agent loop needs a factory). Two pieces:

- `_make_scoped_subagent_factory(args, project=…, store=…, toolset=…)` — a
  `factory(*, system_prompt, tools)` whose registry is CAPPED at the named
  toolset (an ingest worker can never get `run_shell`/`fetch_url` — B1);
- `run_agent_in_background(..., subagent_factory=…)` installs it around the
  turn (the ContextVar reaches the worker thread via `to_thread`), and
  `turn_lock=` serializes turns on one session (the resume queue).
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from veles.core.context import reset_active_project, set_active_project
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.agent_factory import _make_scoped_subagent_factory
from veles.daemon.runner import new_run_handle, run_agent_in_background


def _patched_cli(monkeypatch, captured: dict):
    import veles.cli as cli_mod
    import veles.core.agent as agent_mod

    class _StubProvider:
        pass

    class _StubAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(cli_mod, "_make_provider", lambda name, model=None: _StubProvider())
    monkeypatch.setattr(
        cli_mod,
        "_load_skills",
        lambda p, t, *, provider, model, **_kw: captured.__setitem__("tools", tuple(t)) or object(),
    )
    monkeypatch.setattr(cli_mod, "build_run_system_prompt", lambda p, *, prompt="", **_kw: "STUB")
    monkeypatch.setattr(cli_mod, "build_compressor", lambda p, prov, **_kw: None)
    monkeypatch.setattr(agent_mod, "Agent", _StubAgent)


def _args() -> argparse.Namespace:
    return argparse.Namespace(model="test/model", provider="openrouter", _provider_explicit=True)


def test_scoped_factory_caps_tools_at_the_toolset(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path, name=None, force=False)
    token = set_active_project(project)
    try:
        store = SessionStore(project.memory_db_path)
        captured: dict = {}
        _patched_cli(monkeypatch, captured)
        factory = _make_scoped_subagent_factory(
            _args(), project=project, store=store, toolset="ingest"
        )
        # A worker asking for run_shell/fetch_url must NOT get them (B1) —
        # they are outside the [ingest] ceiling.
        factory(system_prompt="SP", tools=["wiki_write_page", "run_shell", "fetch_url"])
        tools = set(captured["tools"])
        assert "wiki_write_page" in tools
        assert "run_shell" not in tools and "fetch_url" not in tools
    finally:
        reset_active_project(token)


def test_scoped_factory_defaults_to_the_full_toolset(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path, name=None, force=False)
    token = set_active_project(project)
    try:
        store = SessionStore(project.memory_db_path)
        captured: dict = {}
        _patched_cli(monkeypatch, captured)
        factory = _make_scoped_subagent_factory(
            _args(), project=project, store=store, toolset="ingest"
        )
        factory(system_prompt="SP", tools=None)
        from veles.core.tools.toolsets import TOOLSETS

        assert set(captured["tools"]) == set(TOOLSETS["ingest"])
    finally:
        reset_active_project(token)


def test_run_agent_in_background_installs_subagent_factory() -> None:
    """The daemon turn's agent must see the factory via the ContextVar — that is
    what makes delegate/wiki_add work under the daemon at all."""
    seen: dict = {}

    class _Agent:
        def run(self, prompt, on_text_delta=None, event_listener=None):
            from veles.core.orchestration.delegation import current_subagent_factory

            seen["factory"] = current_subagent_factory()

            class _RR:
                text = "ok"
                iterations = 1
                stopped_reason = "completed"
                session_id = "s1"

            return _RR()

    def my_factory(*, system_prompt, tools):  # pragma: no cover - identity only
        raise AssertionError("not called in this test")

    async def go():
        handle = new_run_handle()
        await run_agent_in_background(
            handle, agent=_Agent(), prompt="p", subagent_factory=my_factory
        )
        assert handle.state == "completed"

    asyncio.run(go())
    assert seen["factory"] is my_factory


def test_turn_lock_serializes_turns_on_one_session() -> None:
    """Two runs sharing a turn_lock never overlap — the per-session queue that
    lets a background-op resume wait for a live user turn instead of racing it."""
    order: list[str] = []

    class _SlowAgent:
        def __init__(self, tag: str, delay: float) -> None:
            self.tag, self.delay = tag, delay

        def run(self, prompt, on_text_delta=None, event_listener=None):
            import time as _t

            order.append(f"{self.tag}:start")
            _t.sleep(self.delay)
            order.append(f"{self.tag}:end")

            class _RR:
                text = "ok"
                iterations = 1
                stopped_reason = "completed"
                session_id = "s1"

            return _RR()

    async def go():
        lock = asyncio.Lock()
        h1, h2 = new_run_handle(), new_run_handle()
        await asyncio.gather(
            run_agent_in_background(h1, agent=_SlowAgent("a", 0.15), prompt="p", turn_lock=lock),
            run_agent_in_background(h2, agent=_SlowAgent("b", 0.0), prompt="p", turn_lock=lock),
        )

    asyncio.run(go())
    assert order in (
        ["a:start", "a:end", "b:start", "b:end"],
        ["b:start", "b:end", "a:start", "a:end"],
    )  # strictly serialized, never interleaved
