"""M246: a raw httpx timeout mid-stream becomes a typed ProviderTimeout.

The SDK wraps httpx errors on the initial request, but a streamed response is
consumed by iterating the generator *after* `create()` returned, and the
per-chunk read timeout fires inside that loop where nothing wrapped it.
`httpx.ReadTimeout` is not a subclass of any SDK error, so it sailed through
`_chunks()`'s except clause, past `ProviderTimeout`, and killed the whole turn
with an untyped error and no retry — measured as a 2.7-hour research run lost to
a 120s timeout on a slow reasoning model, with nothing saying "timeout".
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from veles.core.provider import Message, ProviderTimeout, ProviderUnavailable


class _Namespace:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


def _provider(stream_exc: Exception):
    """An OpenRouter provider whose stream raises `stream_exc` mid-iteration."""
    from veles.adapters.openrouter import OpenRouterProvider

    def _raising_stream():
        raise stream_exc
        yield  # pragma: no cover - generator marker

    class _Chat:
        def create(self, **kwargs: Any) -> Any:
            if kwargs.get("stream"):
                return _raising_stream()
            raise AssertionError("expected a streaming call")

    client = _Namespace(
        chat=_Namespace(completions=_Chat()),
        base_url="https://openrouter.ai/api/v1",
    )
    provider = OpenRouterProvider.__new__(OpenRouterProvider)
    provider._client = client  # type: ignore[attr-defined]
    return provider


def _drain(provider) -> None:
    for _ in provider.stream_message(
        [Message(role="user", content="hi")], model="z-ai/glm-5.3-flash"
    ):
        pass


def test_read_timeout_midstream_becomes_provider_timeout() -> None:
    with pytest.raises(ProviderTimeout):
        _drain(_provider(httpx.ReadTimeout("The read operation timed out")))


def test_connect_timeout_midstream_becomes_provider_timeout() -> None:
    with pytest.raises(ProviderTimeout):
        _drain(_provider(httpx.ConnectTimeout("connect timed out")))


def test_non_timeout_transport_error_becomes_provider_unavailable() -> None:
    with pytest.raises(ProviderUnavailable):
        _drain(_provider(httpx.ConnectError("connection refused")))


def test_unrelated_exception_is_not_swallowed() -> None:
    """Only transport failures are translated; a bug must still surface."""
    with pytest.raises(ValueError):
        _drain(_provider(ValueError("some bug")))
