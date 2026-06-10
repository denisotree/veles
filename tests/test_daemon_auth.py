"""M51 daemon — TokenStore CRUD + bearer auth middleware tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from aiohttp import web

from veles.daemon.auth import TokenStore, bearer_auth_middleware


@pytest.fixture()
def tmp_store(tmp_path: Path) -> TokenStore:
    return TokenStore.load(tmp_path / "daemon.tokens.json")


def test_token_store_starts_empty(tmp_store: TokenStore) -> None:
    assert tmp_store.list() == []


def test_token_store_add_persists_and_returns_vd_prefix(
    tmp_path: Path, tmp_store: TokenStore
) -> None:
    entry = tmp_store.add("default")
    assert entry.token.startswith("vd_")
    assert len(entry.token) == 3 + 32  # 'vd_' + 16 bytes hex
    assert tmp_store.path.is_file()

    reloaded = TokenStore.load(tmp_store.path)
    assert [e.name for e in reloaded.list()] == ["default"]
    assert reloaded.verify(entry.token) == "default"


def test_token_store_rejects_duplicate_name(tmp_store: TokenStore) -> None:
    tmp_store.add("default")
    with pytest.raises(ValueError, match="already exists"):
        tmp_store.add("default")


def test_token_store_remove(tmp_store: TokenStore) -> None:
    tmp_store.add("a")
    tmp_store.add("b")
    assert tmp_store.remove("a") is True
    assert [e.name for e in tmp_store.list()] == ["b"]
    assert tmp_store.remove("missing") is False


def test_token_store_verify_unknown_returns_none(tmp_store: TokenStore) -> None:
    tmp_store.add("default")
    assert tmp_store.verify("vd_deadbeef" + "0" * 24) is None
    assert tmp_store.verify("not-a-token") is None


def test_token_store_load_permissive_on_corrupt_json(tmp_path: Path) -> None:
    target = tmp_path / "daemon.tokens.json"
    target.write_text("not json", encoding="utf-8")
    store = TokenStore.load(target)
    assert store.list() == []


def test_token_store_file_mode_is_0600(tmp_store: TokenStore) -> None:
    tmp_store.add("default")
    mode = tmp_store.path.stat().st_mode & 0o777
    assert mode == 0o600


# ---- middleware ----


async def _build_app(store: TokenStore) -> web.Application:
    app = web.Application(middlewares=[bearer_auth_middleware])
    app["token_store"] = store

    async def health(_request):
        return web.json_response({"status": "ok"})

    async def protected(_request):
        return web.json_response({"data": "secret"})

    app.router.add_get("/v1/health", health)
    app.router.add_get("/v1/protected", protected)
    return app


@pytest.mark.asyncio
async def test_middleware_lets_health_through_without_token(
    aiohttp_client, tmp_store: TokenStore
) -> None:
    app = await _build_app(tmp_store)
    client = await aiohttp_client(app)
    resp = await client.get("/v1/health")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_middleware_rejects_protected_without_token(
    aiohttp_client, tmp_store: TokenStore
) -> None:
    app = await _build_app(tmp_store)
    client = await aiohttp_client(app)
    resp = await client.get("/v1/protected")
    assert resp.status == 401
    body = await resp.json()
    assert "missing bearer token" in body["error"]


@pytest.mark.asyncio
async def test_middleware_rejects_invalid_token(aiohttp_client, tmp_store: TokenStore) -> None:
    tmp_store.add("default")
    app = await _build_app(tmp_store)
    client = await aiohttp_client(app)
    resp = await client.get(
        "/v1/protected",
        headers={"Authorization": "Bearer vd_notreallyatoken00000000000000"},
    )
    assert resp.status == 401
    body = await resp.json()
    assert body["error"] == "invalid token"


@pytest.mark.asyncio
async def test_middleware_accepts_valid_token(aiohttp_client, tmp_store: TokenStore) -> None:
    entry = tmp_store.add("default")
    app = await _build_app(tmp_store)
    client = await aiohttp_client(app)
    resp = await client.get(
        "/v1/protected",
        headers={"Authorization": f"Bearer {entry.token}"},
    )
    assert resp.status == 200
    body = await resp.json()
    assert body["data"] == "secret"


@pytest.mark.asyncio
async def test_middleware_rejects_non_bearer_scheme(aiohttp_client, tmp_store: TokenStore) -> None:
    entry = tmp_store.add("default")
    app = await _build_app(tmp_store)
    client = await aiohttp_client(app)
    resp = await client.get(
        "/v1/protected",
        headers={"Authorization": f"Basic {entry.token}"},
    )
    assert resp.status == 401


@pytest.mark.asyncio
async def test_middleware_reloads_store_on_each_request(
    aiohttp_client, tmp_store: TokenStore
) -> None:
    app = await _build_app(tmp_store)
    client = await aiohttp_client(app)
    # Initially no tokens at all — protected is 401.
    resp = await client.get("/v1/protected", headers={"Authorization": "Bearer vd_x"})
    assert resp.status == 401
    # Add a token on disk from a sibling process (simulated): write directly.
    sibling = TokenStore.load(tmp_store.path)
    entry = sibling.add("late")
    # No daemon restart — request with the new token should succeed.
    resp = await client.get("/v1/protected", headers={"Authorization": f"Bearer {entry.token}"})
    assert resp.status == 200
