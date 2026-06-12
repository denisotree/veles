"""Unit tests for fetch_url sandbox — no real network/DNS calls."""

from __future__ import annotations

import socket
from typing import ClassVar

import pytest

from veles.core.tools.builtin.fetch_url import _is_safe_url, fetch_url


def _stub_resolve(addr: str):
    """Build a fake getaddrinfo replacement that returns `addr` for any host."""

    def fake(host, port, *_, **__):
        family = socket.AF_INET6 if ":" in addr else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 0, "", (addr, 0))]

    return fake


def test_blocks_loopback_ipv4(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _stub_resolve("127.0.0.1"))
    ok, reason = _is_safe_url("http://anything/")
    assert ok is False
    assert "127.0.0.0/8" in reason or "127.0.0.1" in reason


def test_blocks_metadata_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _stub_resolve("169.254.169.254"))
    ok, reason = _is_safe_url("http://metadata.example/")
    assert ok is False
    assert "169.254" in reason


def test_blocks_private_10_net(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _stub_resolve("10.0.0.42"))
    ok, _reason = _is_safe_url("http://internal.example/")
    assert ok is False


def test_blocks_localhost_resolves_to_loopback(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _stub_resolve("127.0.0.1"))
    ok, _reason = _is_safe_url("http://localhost/")
    assert ok is False


def test_blocks_unsupported_scheme() -> None:
    ok, reason = _is_safe_url("file:///etc/passwd")
    assert ok is False
    assert "scheme" in reason


def test_blocks_missing_hostname() -> None:
    ok, reason = _is_safe_url("http:///")
    assert ok is False
    assert "hostname" in reason


def test_allows_public_url(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _stub_resolve("93.184.216.34"))
    ok, reason = _is_safe_url("https://example.com/")
    assert ok is True
    assert reason == ""


def test_env_override_allows_private(monkeypatch) -> None:
    monkeypatch.setenv("VELES_FETCH_ALLOW_PRIVATE", "1")
    monkeypatch.setattr(socket, "getaddrinfo", _stub_resolve("127.0.0.1"))
    ok, _reason = _is_safe_url("http://localhost/")
    assert ok is True


def test_dns_failure_returns_blocked(monkeypatch) -> None:
    def fake(*_args, **_kwargs):
        raise socket.gaierror("Name resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", fake)
    ok, reason = _is_safe_url("http://does-not-exist.invalid/")
    assert ok is False
    assert "DNS" in reason


def test_fetch_url_returns_block_error_for_private(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _stub_resolve("169.254.169.254"))
    out = fetch_url("http://metadata.example/path")
    assert out.startswith("<error: blocked:")


def test_fetch_url_does_call_httpx_for_public(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _stub_resolve("93.184.216.34"))
    captured = {}

    class _Resp:
        text = "OK body"
        status_code = 200
        headers: ClassVar[dict] = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        return _Resp()

    import httpx

    monkeypatch.setattr(httpx, "get", fake_get)
    out = fetch_url("https://example.com/")
    assert "OK body" in out
    assert "<http 200>" in out
    assert captured["url"] == "https://example.com/"
    assert captured["headers"]["User-Agent"].startswith("Veles/")


@pytest.mark.parametrize("addr", ["192.168.1.1", "172.16.0.1"])
def test_blocks_other_private_nets(monkeypatch, addr) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _stub_resolve(addr))
    ok, _reason = _is_safe_url(f"http://{addr.replace('.', '-')}.example/")
    assert ok is False
