"""Shared fixtures for `tests/tui/` — fake provider, agent factory, and
an `App.run_test()`-driven pilot harness.

We never touch the real provider SDKs in tui tests. The stub responds
deterministically to whatever the agent feeds it: one tool call (when
asked) then a final text reply. That's enough to cover the streaming
path (`on_text_delta`) and the event-listener path (`event_listener`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from veles.core.agent import Agent
from veles.core.provider import ProviderResponse, StreamEnd, TextDelta, TokenUsage, ToolCall
from veles.core.tools.registry import Registry


@dataclass
class StubProvider:
    """A provider that returns a queued list of `ProviderResponse`s.

    Streams: each response's `text` is chopped into 1-char `TextDelta`
    events followed by `StreamEnd(response)`. Sufficient for asserting
    that `ChatDelta` messages reach the ChatLog.
    """

    name: str = "stub"
    supports_tools: bool = True
    supports_streaming: bool = True
    responses: list[ProviderResponse] = field(default_factory=list)
    _idx: int = 0

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        del messages, tools, model, max_tokens
        resp = self.responses[self._idx]
        self._idx += 1
        return resp

    def stream_message(self, messages, tools=None, *, model, max_tokens=4096):
        del messages, tools, model, max_tokens
        resp = self.responses[self._idx]
        self._idx += 1
        for ch in resp.text or "":
            yield TextDelta(text=ch)
        yield StreamEnd(response=resp)


def _text_response(text: str) -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        finish_reason="stop",
    )


def _tool_response(name: str, args: dict, call_id: str = "c1") -> ProviderResponse:
    return ProviderResponse(
        text=None,
        tool_calls=[ToolCall(id=call_id, name=name, arguments=args)],
        usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        finish_reason="tool_use",
    )


@pytest.fixture
def stub_provider_factory():
    """Returns a callable building a fresh `StubProvider` per test with
    the given response list. Using a factory (rather than a fixture
    parameter) keeps the call site readable: each test states its
    scripted exchange inline."""

    def make(*responses: ProviderResponse) -> StubProvider:
        return StubProvider(responses=list(responses))

    return make


@pytest.fixture(autouse=True)
def _writing_default_mode(monkeypatch):
    """Force `state.mode == "auto"` → WritingMode in TUI integration
    tests that don't explicitly exercise the AutoMode classifier.

    AutoMode makes one extra `provider.create_message` call per turn
    (to decide direct-vs-plan). Tests written before Phase 4 queue
    exactly one provider response per turn — that single response gets
    eaten by the classifier and the actual `agent.run` blows up with
    `IndexError`.

    Tests that specifically validate AutoMode (`tests/test_modes_auto.py`)
    construct `AutoMode()` directly and don't go through the TUI
    fixtures, so they're unaffected.

    **Escape hatch for new TUI tests that want real AutoMode** — re-set
    the entry inside the test body after the fixture has run, and queue
    one extra provider response for the classifier:

        async def test_my_auto_routing(tmp_project, agent_factory_for, ...):
            from veles.core.modes import MODES
            from veles.core.modes.auto import AutoMode

            MODES["auto"] = AutoMode()  # opts back into real classifier
            # ... then call agent_factory_for with N+1 responses (one for
            # the classifier verdict, N for the actual turns)
    """
    from veles.core.modes import MODES
    from veles.core.modes.writing import WritingMode

    monkeypatch.setitem(MODES, "auto", WritingMode())


@pytest.fixture(autouse=True)
def _no_live_model_fetch(monkeypatch):
    """TUI tests construct `ModelPickerScreen` directly; without this
    fixture, opening the picker for a cloud provider would try the live
    API (or fail noisily on the missing key) depending on the dev's env.
    Force every test to see the curated list unless it opts back in."""
    from veles.tui.screens import _model_fetcher

    def _curated(provider: str, *, refresh: bool = False) -> _model_fetcher.ModelList:
        del refresh
        return _model_fetcher.ModelList(
            models=_model_fetcher.known_models(provider), source="curated"
        )

    monkeypatch.setattr(_model_fetcher, "fetch_models", _curated)


@pytest.fixture
def text_response():
    return _text_response


@pytest.fixture
def tool_response():
    return _tool_response


@pytest.fixture
def tmp_project(tmp_path):
    """Initialize an isolated Veles project rooted under pytest's tmp
    directory (already redirected to `./tmp/pytest/` by pyproject), plus
    a paired `SessionStore`. Slash-command tests get a real wiki + memory
    DB without touching `~/.veles/`."""
    from veles.core.memory import SessionStore
    from veles.core.project import init_project

    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)
    return project, store


@pytest.fixture
def slash_ctx(tmp_project):
    """Builds a `SlashContext` over a fresh project. Tests that only
    poke pure handlers (no UI) consume this directly."""
    from veles.tui.slash.registry import SlashContext
    from veles.tui.state import AppState

    project, store = tmp_project
    state = AppState(session_id=None, provider_name="stub", model="m")
    return SlashContext(state=state, project=project, store=store)


@pytest.fixture
def agent_factory_for(stub_provider_factory):
    """Build an `agent_factory` callable suitable for `TuiApp(agent_factory=…)`.

    Usage:
        factory = agent_factory_for(text_response("hi"))
        app = TuiApp(state=…, agent_factory=factory)
    """

    def build(*responses: ProviderResponse):
        provider = stub_provider_factory(*responses)
        registry = Registry()

        def factory(_state, **_kwargs):
            # `**_kwargs` absorbs mode-overrides (Phase 3+ PlanningMode and
            # friends pass `mode_override="planning"` etc.). Tests that
            # care about the kwargs use a richer factory in their own
            # module; this default just builds a stub Agent.
            return Agent(provider, registry, model="m")

        return factory

    return build
