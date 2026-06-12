"""M132: errors/timeouts are recorded as typed events, and provider
timeouts are surfaced as the typed `ProviderTimeout`.

A failed turn used to vanish into a scrolled-away TUI chat line. Now the
agent emits an `ErrorEvent` (persisted to events.jsonl + fired to the live
listener feeding the inspector) before the exception propagates, and the
shared OpenAI wire layer translates the SDK's `APITimeoutError` into
`ProviderTimeout` so a stall is labelled distinctly instead of guessing
from a backend-specific class name.
"""

from __future__ import annotations

import httpx
import pytest
from openai import APITimeoutError

from veles.adapters.openai_direct import OpenAIProvider
from veles.core.agent import Agent
from veles.core.cancel import CancelToken, reset_cancel_token, set_cancel_token
from veles.core.provider import Message, ProviderTimeout
from veles.core.tools.registry import Registry

# ---- agent emits ErrorEvent on a failed turn ----


class _RaisingProvider:
    name = "stub"
    supports_tools = True
    supports_streaming = False

    def create_message(self, *a, **k):
        raise RuntimeError("boom")

    def stream_message(self, *a, **k):
        raise NotImplementedError


def test_failed_turn_emits_error_event_and_reraises():
    seen = []
    agent = Agent(_RaisingProvider(), Registry(), model="m")
    with pytest.raises(RuntimeError, match="boom"):
        agent.run("hi", event_listener=seen.append)
    errors = [e for e in seen if getattr(e, "type", None) == "error"]
    assert len(errors) == 1
    assert errors[0].error_type == "RuntimeError"
    assert "boom" in errors[0].message
    assert errors[0].where == "agent.run"


def test_cancelled_turn_does_not_emit_error_event():
    """A user-initiated stop is a clean outcome, not an error (M131/M132)."""

    class _Hang:
        name = "stub"
        supports_tools = True
        supports_streaming = False

        def create_message(self, *a, **k):
            raise AssertionError("must short-circuit before the provider call")

        def stream_message(self, *a, **k):
            raise NotImplementedError

    seen = []
    token = CancelToken()
    token.cancel()
    ctx = set_cancel_token(token)
    try:
        result = Agent(_Hang(), Registry(), model="m").run("hi", event_listener=seen.append)
    finally:
        reset_cancel_token(ctx)
    assert result.stopped_reason == "cancelled"
    assert [e for e in seen if getattr(e, "type", None) == "error"] == []


# ---- provider timeout → ProviderTimeout ----


def _timeout_error() -> APITimeoutError:
    return APITimeoutError(request=httpx.Request("POST", "http://test/chat"))


class _TimeoutChat:
    def create(self, **kwargs):
        raise _timeout_error()


class _TimeoutStreamChat:
    def create(self, **kwargs):
        def _gen():
            raise _timeout_error()
            yield  # pragma: no cover - generator marker

        return _gen()


class _Namespace:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _provider_with_chat(chat) -> OpenAIProvider:
    client = _Namespace(chat=_Namespace(completions=chat))
    return OpenAIProvider(client=client)


def test_create_message_translates_timeout():
    provider = _provider_with_chat(_TimeoutChat())
    with pytest.raises(ProviderTimeout):
        provider.create_message([Message(role="user", content="hi")], model="gpt-4o-mini")


def test_stream_message_translates_timeout_on_call():
    provider = _provider_with_chat(_TimeoutChat())
    with pytest.raises(ProviderTimeout):
        list(provider.stream_message([Message(role="user", content="hi")], model="gpt-4o-mini"))


def test_stream_message_translates_timeout_mid_stream():
    provider = _provider_with_chat(_TimeoutStreamChat())
    with pytest.raises(ProviderTimeout):
        list(provider.stream_message([Message(role="user", content="hi")], model="gpt-4o-mini"))
