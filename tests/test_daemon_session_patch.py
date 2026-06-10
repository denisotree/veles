"""M127: PATCH /v1/sessions/{id} — mode-only.

Model and provider are fixed at daemon launch from config; PATCH now
rejects them and accepts only `mode` (auto/planning/writing/goal).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from aiohttp import web

from veles.core.memory import SessionStore
from veles.core.project import Project, init_project
from veles.daemon.auth import TokenStore
from veles.daemon.runner import AgentFactory
from veles.daemon.server import build_state, make_app
from veles.daemon.state import SessionOverrides


def _noop_agent_factory(store: SessionStore) -> AgentFactory:
    def factory(session_id: str | None, *, prompt: str | None = None):  # noqa: ARG001
        raise RuntimeError("not invoked in patch tests")

    return factory


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="patchtest")


@pytest.fixture()
def store(project: Project):
    return SessionStore(project.memory_db_path)


@pytest.fixture()
def token_store(tmp_path: Path) -> TokenStore:
    ts = TokenStore.load(tmp_path / "tokens.json")
    ts.add("default")
    return ts


@pytest.fixture()
def good_token(token_store: TokenStore) -> str:
    return token_store.list()[0].token


@pytest.fixture()
def app(
    project: Project, store: SessionStore, token_store: TokenStore
) -> web.Application:
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=_noop_agent_factory(store),
    )
    return make_app(state)


# ---- mode happy path ----


async def test_patch_session_sets_mode(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.patch(
        "/v1/sessions/sess-abc",
        json={"mode": "planning"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 200
    body = await resp.json()
    assert body["session_id"] == "sess-abc"
    assert body["overrides"]["mode"] == "planning"
    assert body["overrides"]["model"] is None
    assert body["overrides"]["provider"] is None


# ---- M127: model / provider are fixed at launch ----


async def test_patch_rejects_model(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.patch(
        "/v1/sessions/x",
        json={"model": "anthropic/claude-haiku-4.5"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 400
    body = await resp.json()
    assert "fixed at daemon launch" in body["error"]


async def test_patch_rejects_provider(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.patch(
        "/v1/sessions/x",
        json={"provider": "openai"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 400
    body = await resp.json()
    assert "fixed at daemon launch" in body["error"]


async def test_patch_rejects_model_even_with_mode(
    aiohttp_client, app, good_token: str
) -> None:
    """A model field poisons the whole request — no partial apply."""
    client = await aiohttp_client(app)
    resp = await client.patch(
        "/v1/sessions/x",
        json={"mode": "planning", "model": "gpt-4o"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 400


# ---- validation ----


async def test_patch_rejects_invalid_mode(
    aiohttp_client, app, good_token: str
) -> None:
    client = await aiohttp_client(app)
    resp = await client.patch(
        "/v1/sessions/x",
        json={"mode": "bogus"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 400
    body = await resp.json()
    assert "invalid mode" in body["error"]
    assert "auto" in body["valid_modes"]


async def test_patch_rejects_empty_body(
    aiohttp_client, app, good_token: str
) -> None:
    client = await aiohttp_client(app)
    resp = await client.patch(
        "/v1/sessions/x",
        json={},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 400
    body = await resp.json()
    assert "mode required" in body["error"]


async def test_patch_rejects_malformed_json(
    aiohttp_client, app, good_token: str
) -> None:
    client = await aiohttp_client(app)
    resp = await client.patch(
        "/v1/sessions/x",
        data=b"{ not json",
        headers={
            "Authorization": f"Bearer {good_token}",
            "Content-Type": "application/json",
        },
    )
    assert resp.status == 400


async def test_patch_requires_auth(aiohttp_client, app) -> None:
    client = await aiohttp_client(app)
    resp = await client.patch("/v1/sessions/x", json={"mode": "auto"})
    assert resp.status == 401


# ---- SessionOverrides dataclass (mode still carried) ----


def test_session_overrides_is_empty_when_unset() -> None:
    assert SessionOverrides().is_empty()


def test_session_overrides_to_dict() -> None:
    so = SessionOverrides(mode="auto")
    assert so.to_dict() == {"model": None, "mode": "auto", "provider": None}
