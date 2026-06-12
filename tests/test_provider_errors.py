"""M132b: local-provider error surfacing.

A down local server (closed port) or an upstream 5xx used to reach the
user as a raw `APIConnectionError` / `InternalServerError` from the OpenAI
SDK — or, worse, as a silent hang while the SDK retried. The shared wire
layer now translates these into typed veles errors (`ProviderUnavailable`
/ `ProviderError`) carrying an actionable hint, and local adapters fail
fast (`max_retries=0`). The ollama adapter's hints name the real fixes
(`ollama serve`, broken-install reinstall) for the exact 500 users hit.
"""

from __future__ import annotations

import httpx
import pytest
from openai import APIConnectionError, InternalServerError

from veles.adapters.local.ollama import OllamaProvider
from veles.core.provider import (
    Message,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
)


def _conn_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "http://test/chat"))


def _status_500() -> InternalServerError:
    req = httpx.Request("POST", "http://test/chat")
    resp = httpx.Response(
        500,
        request=req,
        text='{"error":"error starting llama-server: llama-server binary not found"}',
    )
    return InternalServerError(
        "Error code: 500 - llama-server binary not found", response=resp, body=None
    )


class _Chat:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def create(self, **kwargs):
        raise self._exc


class _StreamChat:
    """Raises mid-stream: the initial create() returns an iterator that
    blows up on first iteration."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def create(self, **kwargs):
        exc = self._exc

        def _gen():
            raise exc
            yield  # pragma: no cover

        return _gen()


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _ollama_raising(exc: Exception, *, stream: bool = False) -> OllamaProvider:
    chat = (_StreamChat if stream else _Chat)(exc)
    client = _NS(base_url="http://localhost:11434/v1", chat=_NS(completions=chat))
    return OllamaProvider(client=client)


# ---- connection refused → ProviderUnavailable ----


def test_create_connection_error_becomes_unavailable():
    provider = _ollama_raising(_conn_error())
    with pytest.raises(ProviderUnavailable) as ei:
        provider.create_message([Message(role="user", content="hi")], model="qwen3")
    msg = str(ei.value)
    assert "cannot reach ollama" in msg
    assert "http://localhost:11434/v1" in msg
    assert "ollama serve" in msg


def test_stream_connection_error_becomes_unavailable():
    provider = _ollama_raising(_conn_error(), stream=True)
    with pytest.raises(ProviderUnavailable):
        list(provider.stream_message([Message(role="user", content="hi")], model="qwen3"))


# ---- 5xx → ProviderError with the llama-server / reinstall hint ----


def test_create_status_error_becomes_provider_error_with_hint():
    provider = _ollama_raising(_status_500())
    with pytest.raises(ProviderError) as ei:
        provider.create_message([Message(role="user", content="hi")], model="qwen3")
    msg = str(ei.value)
    assert "HTTP 500" in msg
    assert "llama-server" in msg  # upstream body preserved
    assert "reinstall" in msg.lower()  # actionable hint


def test_status_error_is_not_unavailable_or_timeout():
    """A 5xx must not be mislabelled as unreachable/timeout."""
    provider = _ollama_raising(_status_500())
    with pytest.raises(ProviderError) as ei:
        provider.create_message([Message(role="user", content="hi")], model="qwen3")
    assert not isinstance(ei.value, (ProviderUnavailable, ProviderTimeout))


# ---- local adapter fails fast (no retry storm on a closed port) ----


def test_local_provider_disables_sdk_retries():
    """`max_retries=0` so a closed port errors immediately instead of
    looping through the SDK's retry/backoff (the 'silent hang')."""
    provider = OllamaProvider(base_url="http://127.0.0.1:9/v1")
    assert provider._client.max_retries == 0
