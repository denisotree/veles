"""Regression: `AgentBridge._run_turn` re-installs the active-project and
module-registry ContextVars on its worker thread.

The CLI entry point sets both on the *main* thread, but Textual runs each
turn on a `ThreadPoolExecutor` worker (`run_worker(thread=True)`), which —
unlike the daemon's `asyncio.to_thread` — does NOT propagate ContextVars.
Before the fix the agent loop saw `current_project() == None`, so every
`wiki_*` / `memory_save` call hard-raised "no active Veles project" (the
symptom observed in a live `mind-palace` TUI session: six `wiki_search`
calls all returned that RuntimeError).

We don't spin up a real Textual App or worker thread here. Instead we
zero out the ambient context (faithfully mimicking a freshly-spawned
worker thread) and drive `_run_turn` directly, asserting it establishes
both vars from what the bridge captured at construction — and tears them
down again afterwards.
"""

from __future__ import annotations

import pytest

from veles.core.context import (
    current_project,
    reset_active_project,
    set_active_project,
)
from veles.core.modules import (
    ModuleRegistry,
    current_module_registry,
    reset_module_registry,
    set_module_registry,
)
from veles.core.session_state import AppState
from veles.tui.bridge import AgentBridge


class _FakeApp:
    """`_run_turn` only touches the app via `call_from_thread` on the
    error/event side channels. The happy path here never posts, so a
    stub that records (and would surface) any call is enough."""

    def call_from_thread(self, callable_, *args, **kwargs):  # pragma: no cover
        raise AssertionError(f"unexpected call_from_thread: {callable_}")


class _RecordingMode:
    """Stands in for a real Mode. Captures the ContextVars visible at the
    moment the agent turn would run."""

    name = "recording"

    def __init__(self) -> None:
        self.seen_project: object = "UNSET"
        self.seen_registry: object = "UNSET"

    def run_turn(self, prompt: str, ctx) -> None:
        self.seen_project = current_project()
        self.seen_registry = current_module_registry()


@pytest.fixture
def _zeroed_context():
    """Force the ambient active-project / module-registry vars to None,
    mimicking the fresh context of a Textual worker thread. Restored
    after the test."""
    proj_token = set_active_project(None)
    mod_token = set_module_registry(None)
    try:
        yield
    finally:
        reset_module_registry(mod_token)
        reset_active_project(proj_token)


def test_run_turn_installs_project_and_registry(monkeypatch, tmp_project, _zeroed_context) -> None:
    project, _store = tmp_project
    registry = ModuleRegistry()
    mode = _RecordingMode()
    monkeypatch.setattr("veles.core.modes.get_mode", lambda _name: mode)

    state = AppState(session_id=None, provider_name="stub", model="m")
    bridge = AgentBridge(
        app=_FakeApp(),  # type: ignore[arg-type]
        state=state,
        factory=lambda s: None,  # type: ignore[arg-type, return-value]
        project=project,
        module_registry=registry,
    )

    # Sanity: the worker context starts blank, exactly as Textual leaves it.
    assert current_project() is None
    assert current_module_registry() is None

    bridge._run_turn("hi")

    # The turn saw the bridge's captured project + registry, not None.
    assert mode.seen_project is project
    assert mode.seen_registry is registry

    # And the vars are reset once the turn unwinds (no leak across turns).
    assert current_project() is None
    assert current_module_registry() is None
