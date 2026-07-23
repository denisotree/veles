"""M220: the provider self-heals when the wire rejects `cache_control` on the
tool tail. A 400 that mentions `cache_control` must not break the turn — the
provider drops the tool-tail breakpoint process-wide and retries once. Any
other 400 propagates unchanged (single attempt, toggle left on).
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError

from veles.core.cache_hints import _reset_tool_tail, tool_tail_enabled
from veles.core.openai_wire import OpenAICompatibleProvider
from veles.core.provider import Message, ProviderError


@pytest.fixture(autouse=True)
def _reset_toggle():
    _reset_tool_tail(True)
    yield
    _reset_tool_tail(True)


def _status_400(message: str) -> APIStatusError:
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx.Response(400, request=req)
    return APIStatusError(message, response=resp, body=None)


def _ok_completion():
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="hi", tool_calls=[]),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


class _FlakyThenOK:
    """First `create` 400s on cache_control; the second succeeds."""

    def __init__(self, exc: Exception, ok) -> None:
        self.calls = 0
        self._exc = exc
        self._ok = ok

    def create(self, **_kw):
        self.calls += 1
        if self.calls == 1:
            raise self._exc
        return self._ok


class _AlwaysRaise:
    def __init__(self, exc: Exception) -> None:
        self.calls = 0
        self._exc = exc

    def create(self, **_kw):
        self.calls += 1
        raise self._exc


def _provider(completions) -> OpenAICompatibleProvider:
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return OpenAICompatibleProvider(client=client)


def test_self_heals_on_cache_control_400() -> None:
    flaky = _FlakyThenOK(
        _status_400("invalid cache_control block on tool message"), _ok_completion()
    )
    provider = _provider(flaky)
    resp = provider.create_message([Message(role="user", content="hi")], model="anthropic/claude")
    assert resp.text == "hi"
    assert flaky.calls == 2  # retried exactly once
    assert tool_tail_enabled() is False  # disabled for the rest of the process


def test_unrelated_400_does_not_retry_or_disable() -> None:
    flaky = _AlwaysRaise(_status_400("context length exceeded"))
    provider = _provider(flaky)
    with pytest.raises(ProviderError):
        provider.create_message([Message(role="user", content="hi")], model="anthropic/claude")
    assert flaky.calls == 1  # no retry for an unrelated error
    assert tool_tail_enabled() is True  # toggle untouched


def test_no_retry_once_already_disabled() -> None:
    """If tool-tail is already off, a cache_control 400 is not our tool-tail
    hint — don't swallow it with a retry."""
    _reset_tool_tail(False)
    flaky = _AlwaysRaise(_status_400("invalid cache_control block"))
    provider = _provider(flaky)
    with pytest.raises(ProviderError):
        provider.create_message([Message(role="user", content="hi")], model="anthropic/claude")
    assert flaky.calls == 1
