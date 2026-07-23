"""M224: the OpenRouter adapter forwards the running turn's memory session id as
OpenRouter's `session_id` sticky-routing key, so a conversation's requests pin
one provider and the prompt cache actually hits. No hardcoded provider pin —
OpenRouter still picks the provider, sticky routing just keeps it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from veles.core.context import reset_current_session_id, set_current_session_id
from veles.core.openai_wire import OpenAICompatibleProvider
from veles.core.provider import Message


@pytest.fixture(autouse=True)
def _clear_session():
    tok = set_current_session_id(None)
    yield
    reset_current_session_id(tok)


def _openrouter():
    from veles.adapters.openrouter import OpenRouterProvider

    return OpenRouterProvider(api_key="sk-test")  # offline: no network at construction


def test_request_options_empty_without_session() -> None:
    assert _openrouter()._request_options("anthropic/claude-sonnet-4.6") == {}


def test_request_options_forwards_session_id() -> None:
    tok = set_current_session_id("sess-abc123")
    try:
        opts = _openrouter()._request_options("anthropic/claude-sonnet-4.6")
    finally:
        reset_current_session_id(tok)
    assert opts == {"extra_body": {"session_id": "sess-abc123"}}


def test_request_options_truncates_to_256() -> None:
    long = "x" * 300
    tok = set_current_session_id(long)
    try:
        opts = _openrouter()._request_options("anthropic/claude-sonnet-4.6")
    finally:
        reset_current_session_id(tok)
    assert len(opts["extra_body"]["session_id"]) == 256


def test_base_provider_adds_no_request_options() -> None:
    """Non-OpenRouter adapters (openai-direct, local) never forward session_id —
    it's an OpenRouter-only routing field."""
    base = OpenAICompatibleProvider(client=SimpleNamespace())
    assert base._request_options("gpt-4o") == {}


def test_create_message_sends_session_id_in_extra_body() -> None:
    captured: dict = {}

    class _FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="ok", tool_calls=[]),
                        finish_reason="stop",
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            )

    provider = _openrouter()
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions()))
    tok = set_current_session_id("sess-xyz")
    try:
        provider.create_message([Message(role="user", content="hi")], model="anthropic/claude")
    finally:
        reset_current_session_id(tok)
    assert captured["extra_body"] == {"session_id": "sess-xyz"}


def test_agent_run_exposes_session_id_to_provider(tmp_path) -> None:
    """End-to-end wiring: during a persisted run, the provider sees the memory
    session id via the ContextVar (so OpenRouter can pin routing from turn one)."""
    from veles.core.agent import Agent
    from veles.core.context import current_session_id
    from veles.core.memory import SessionStore
    from veles.core.provider import ProviderResponse, TokenUsage
    from veles.core.tools.registry import Registry

    seen: list[str | None] = []

    class _RecordingProvider:
        name = "rec"
        supports_tools = True
        supports_streaming = False

        def create_message(self, messages, tools=None, *, model, max_tokens=4096):
            seen.append(current_session_id())
            return ProviderResponse(
                text="done", tool_calls=[], usage=TokenUsage(), finish_reason="stop"
            )

    store = SessionStore(tmp_path / "m.db")
    try:
        agent = Agent(provider=_RecordingProvider(), registry=Registry(), model="m", store=store)
        result = agent.run("hello")
    finally:
        store.close()
    assert seen and seen[0] is not None
    assert seen[0] == result.session_id
    # ContextVar is reset after the run — no leak.
    assert current_session_id() is None
