"""M127: model/provider are fixed at daemon launch from config.

Replaces the M126b per-session model-override persistence suite. These
tests lock the post-M127 behaviour:
  * `build_state` never rehydrates per-session model overrides — it
    starts empty and `/v1/health` `active_model` == the config model,
    even when an old DB still carries a stale `session_model_overrides`
    row (the exact mind-palace dashboard bug).
  * the SessionStore no longer exposes model-override persistence.
  * `set_overrides` no longer writes anything to the store.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.project import Project, init_project
from veles.daemon.auth import TokenStore
from veles.daemon.runner import AgentFactory
from veles.daemon.server import build_state, make_app
from veles.daemon.state import DaemonState


def _noop_factory() -> AgentFactory:
    def factory(session_id: str | None, *, prompt: str | None = None):
        raise RuntimeError("not invoked here")

    return factory


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="m127")


@pytest.fixture()
def token_store(tmp_path: Path) -> TokenStore:
    ts = TokenStore.load(tmp_path / "tokens.json")
    ts.add("default")
    return ts


def test_build_state_starts_with_empty_overrides(project: Project, token_store: TokenStore) -> None:
    store = SessionStore(project.memory_db_path)
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=_noop_factory(),
        default_model="qwen3:4b-instruct",
    )
    assert state.session_overrides == {}
    assert state.last_override_session_id is None


def test_store_has_no_model_override_api(project: Project) -> None:
    """The persistence surface was removed entirely."""
    store = SessionStore(project.memory_db_path)
    for gone in (
        "get_model_override",
        "upsert_model_override",
        "load_all_model_overrides",
        "latest_override_session_id",
    ):
        assert not hasattr(store, gone), f"{gone} should be removed in M127"


def test_set_overrides_does_not_touch_store(project: Project, token_store: TokenStore) -> None:
    store = SessionStore(project.memory_db_path)
    state = DaemonState(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=_noop_factory(),
    )
    # mode is carried in-memory; nothing is persisted.
    state.set_overrides("sess-1", mode="planning")
    assert state.get_overrides("sess-1").mode == "planning"  # type: ignore[union-attr]
    assert state.last_override_session_id is None


def test_build_state_ignores_legacy_override_table(
    project: Project, token_store: TokenStore
) -> None:
    """Mirror the mind-palace incident: an old DB still has a
    `session_model_overrides` row from a pre-M127 Telegram /model swap.
    M127 must NOT resurrect it — `session_overrides` stays empty."""
    store = SessionStore(project.memory_db_path)
    # Recreate the pre-M127 table + a stale row by hand (the schema no
    # longer creates it).
    store._conn.execute(  # type: ignore[attr-defined]
        "CREATE TABLE IF NOT EXISTS session_model_overrides ("
        "session_id TEXT PRIMARY KEY, model TEXT NOT NULL, updated_at REAL NOT NULL)"
    )
    store._conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO session_model_overrides VALUES (?,?,?)",
        ("stale-sess", "anthropic/claude-haiku-4.5", 1.0),
    )
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=_noop_factory(),
        default_model="qwen3:4b-instruct",
    )
    assert state.session_overrides == {}
    assert state.last_override_session_id is None


async def test_health_active_model_is_config_not_stale_override(
    project: Project, token_store: TokenStore, aiohttp_client
) -> None:
    """The headline fix: `/v1/health` reports the configured model as
    `active_model`, never a stale per-session override."""
    store = SessionStore(project.memory_db_path)
    store._conn.execute(  # type: ignore[attr-defined]
        "CREATE TABLE IF NOT EXISTS session_model_overrides ("
        "session_id TEXT PRIMARY KEY, model TEXT NOT NULL, updated_at REAL NOT NULL)"
    )
    store._conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO session_model_overrides VALUES (?,?,?)",
        ("stale-sess", "anthropic/claude-haiku-4.5", 1.0),
    )
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=_noop_factory(),
        provider="ollama",
        default_model="qwen3:4b-instruct",
    )
    client = await aiohttp_client(make_app(state))
    resp = await client.get("/v1/health")
    body = await resp.json()
    assert body["model"] == "qwen3:4b-instruct"
    assert body["active_model"] == "qwen3:4b-instruct"
