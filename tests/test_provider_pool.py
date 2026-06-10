"""Tests for FailoverProvider — Tier δ M56."""

from __future__ import annotations

import pytest

from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.provider_pool import FailoverProvider, is_transient


# ---------- transient classification ----------


def test_is_transient_by_exception_name() -> None:
    class RateLimitError(Exception):
        pass

    class APITimeoutError(Exception):
        pass

    assert is_transient(RateLimitError("slow down")) is True
    assert is_transient(APITimeoutError("timeout")) is True


def test_is_transient_by_status_code() -> None:
    class ServerError(Exception):
        def __init__(self) -> None:
            super().__init__("boom")
            self.status_code = 503

    class ClientError(Exception):
        def __init__(self) -> None:
            super().__init__("nope")
            self.status_code = 400

    assert is_transient(ServerError()) is True
    assert is_transient(ClientError()) is False


def test_is_transient_unknown_returns_false() -> None:
    assert is_transient(ValueError("bad input")) is False
    assert is_transient(KeyError("missing")) is False


# ---------- pool stubs ----------


class _OkProvider:
    name = "ok"
    supports_tools = True
    supports_streaming = False

    def __init__(self, response: ProviderResponse | None = None) -> None:
        self._response = response or ProviderResponse(
            text="ok", tool_calls=[], usage=TokenUsage(total_tokens=1)
        )
        self.call_count = 0

    def create_message(self, *args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        self.call_count += 1
        return self._response

    def stream_message(self, *args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        yield self._response  # not realistic, just unused in tests


class _RateLimit(Exception):
    pass


_RateLimit.__name__ = "RateLimitError"  # match the heuristic


class _TransientFailProvider:
    name = "transient"
    supports_tools = True
    supports_streaming = False

    def __init__(self) -> None:
        self.call_count = 0

    def create_message(self, *args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        self.call_count += 1
        raise _RateLimit("429")

    def stream_message(self, *args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        raise _RateLimit("429")


class _HardFailProvider:
    name = "hard"
    supports_tools = True
    supports_streaming = False

    def create_message(self, *args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        raise ValueError("permanent")

    def stream_message(self, *args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        raise ValueError("permanent")


# ---------- FailoverProvider ----------


def test_empty_providers_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        FailoverProvider([])


def test_single_provider_passthrough() -> None:
    p = _OkProvider()
    pool = FailoverProvider([p])  # type: ignore[list-item]
    resp = pool.create_message([], model="m")
    assert resp.text == "ok"
    assert p.call_count == 1


def test_pool_rotates_on_transient_failure() -> None:
    """Primary throws RateLimitError → pool tries secondary → success."""
    bad = _TransientFailProvider()
    good = _OkProvider()
    pool = FailoverProvider([bad, good])  # type: ignore[list-item]
    resp = pool.create_message([], model="m")
    assert resp.text == "ok"
    assert bad.call_count == 1
    assert good.call_count == 1
    assert pool.current_index == 1


def test_pool_does_not_rotate_on_permanent_failure() -> None:
    """ValueError isn't transient — propagate immediately, don't rotate."""
    hard = _HardFailProvider()
    ok = _OkProvider()
    pool = FailoverProvider([hard, ok])  # type: ignore[list-item]
    with pytest.raises(ValueError):
        pool.create_message([], model="m")
    assert ok.call_count == 0


def test_pool_exhausts_and_reraises_last_transient() -> None:
    """All providers throw transient errors → reraise the last seen."""
    a = _TransientFailProvider()
    b = _TransientFailProvider()
    pool = FailoverProvider([a, b])  # type: ignore[list-item]
    with pytest.raises(_RateLimit):
        pool.create_message([], model="m")
    assert a.call_count == 1
    assert b.call_count == 1


def test_max_attempts_bounded_by_provider_count() -> None:
    """max_attempts gets clamped down to len(providers) — we don't burn
    extra calls re-asking the same one twice in a small pool."""
    bad = _TransientFailProvider()
    pool = FailoverProvider([bad], max_attempts=10)  # type: ignore[list-item]
    with pytest.raises(_RateLimit):
        pool.create_message([], model="m")
    assert bad.call_count == 1


def test_pool_name_is_stable_across_rotation() -> None:
    """trace.provider expects one bucket per logical pool — name stays put."""
    a = _OkProvider()
    b = _OkProvider()
    pool = FailoverProvider([a, b])  # type: ignore[list-item]
    name_before = pool.name
    pool.create_message([], model="m")
    assert pool.name == name_before


def test_supports_flags_inherit_from_first() -> None:
    class _NoTools:
        name = "x"
        supports_tools = False
        supports_streaming = True

        def create_message(self, *a, **kw):  # noqa: ANN002, ANN003
            del a, kw
            return ProviderResponse(text="", tool_calls=[], usage=TokenUsage())

        def stream_message(self, *a, **kw):  # noqa: ANN002, ANN003
            del a, kw
            yield None  # unused

    pool = FailoverProvider([_NoTools()])  # type: ignore[list-item]
    assert pool.supports_tools is False
    assert pool.supports_streaming is True
