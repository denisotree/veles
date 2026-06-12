"""M124: daemon `_handle_create_run` routes long/research-keyword prompts
through manager-spawn when a `worker_agent_factory` is configured.

We don't spin up a real agent — `decompose_and_run` is patched to a
canned ManagerRunResult so the integration test focuses on the
*wiring* (gate decision, event emission, fallback semantics) rather
than the orchestration internals (covered by `test_orchestration_*`)."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from aiohttp import WSMsgType, web

from veles.core.memory import SessionStore
from veles.core.orchestration.workers import WorkerHandle
from veles.core.project import Project, init_project
from veles.daemon.auth import TokenStore
from veles.daemon.server import build_state, make_app


def _stub_agent_factory(store: SessionStore):
    """Direct-path factory used for the fall-through case. Returns a
    minimal Agent stub via _RUN_TOOLS-free Registry."""
    from veles.core.agent import Agent
    from veles.core.tools.registry import Registry

    class _NoopProvider:
        name = "noop"
        supports_tools = False
        supports_streaming = True

        def create_message(self, *a, **kw):
            from veles.core.provider import ProviderResponse, TokenUsage

            return ProviderResponse(
                text="direct",
                tool_calls=[],
                usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                finish_reason="stop",
            )

        def stream_message(self, *a, **kw):
            from veles.core.provider import (
                ProviderResponse,
                StreamEnd,
                TextDelta,
                TokenUsage,
            )

            yield TextDelta(text="direct")
            yield StreamEnd(
                response=ProviderResponse(
                    text="direct",
                    tool_calls=[],
                    usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    finish_reason="stop",
                )
            )

    def factory(session_id: str | None, *, prompt: str | None = None):
        sid = session_id or store.create_session()
        return Agent(
            provider=_NoopProvider(),
            registry=Registry(),
            model="stub",
            max_iterations=1,
            store=store,
            session_id=sid,
        )

    return factory


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="m124test")


@pytest.fixture()
def store(project: Project):
    return SessionStore(project.memory_db_path)


@pytest.fixture()
def token_store(tmp_path: Path) -> TokenStore:
    ts = TokenStore.load(tmp_path / "daemon.tokens.json")
    ts.add("default")
    return ts


@pytest.fixture()
def good_token(token_store: TokenStore) -> str:
    return token_store.list()[0].token


def _make_app_with_manager(
    project: Project,
    store: SessionStore,
    token_store: TokenStore,
    *,
    manager_result,
) -> web.Application:
    """Build a daemon app whose worker_agent_factory routes via a
    patched decompose_and_run returning `manager_result`."""
    agent_factory = _stub_agent_factory(store)
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=agent_factory,
    )

    def worker_factory(**kwargs):
        # Workers never actually run — decompose_and_run is patched.
        return MagicMock()

    state.worker_agent_factory = worker_factory
    app = make_app(state)
    app["_manager_result"] = manager_result  # surfaced for the test patch
    return app


async def _drain_events(ws, *, timeout: float = 5.0) -> list[dict[str, Any]]:
    events: list[dict] = []
    deadline = time.time() + timeout
    while True:
        remaining = max(0.0, deadline - time.time())
        try:
            msg = await asyncio.wait_for(ws.receive(), timeout=remaining)
        except TimeoutError:
            break
        if msg.type == WSMsgType.TEXT:
            events.append(json.loads(msg.data))
            if events[-1].get("type") in ("completed", "error"):
                break
        elif msg.type in (
            WSMsgType.CLOSED,
            WSMsgType.CLOSE,
            WSMsgType.CLOSING,
            WSMsgType.ERROR,
        ):
            break
    return events


# ---- gate: prompt below threshold goes direct ----


async def test_short_prompt_bypasses_manager(
    aiohttp_client,
    project: Project,
    store: SessionStore,
    token_store: TokenStore,
    good_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Short prompts without research-keyword skip manager-spawn and
    run through the legacy direct agent path."""
    monkeypatch.delenv("VELES_MANAGER_MODE", raising=False)
    called = {"manager": False}

    def fake_decompose(*a, **kw):
        called["manager"] = True
        raise AssertionError("manager path should not fire for short prompt")

    monkeypatch.setattr("veles.core.orchestration.decompose_and_run", fake_decompose)

    app = _make_app_with_manager(project, store, token_store, manager_result=None)
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs",
        json={"prompt": "hi"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 202
    run_id = (await resp.json())["run_id"]
    # Wait for the background run to finish via its event stream (no sleeps).
    headers = {"Authorization": f"Bearer {good_token}"}
    async with client.ws_connect(f"/v1/runs/{run_id}/events", headers=headers) as ws:
        events = await _drain_events(ws)
    assert events[-1]["type"] == "completed"
    assert called["manager"] is False


# ---- gate: research-keyword routes through manager ----


async def test_research_prompt_routes_through_manager_and_emits_plan(
    aiohttp_client,
    project: Project,
    store: SessionStore,
    token_store: TokenStore,
    good_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M122f opt-in: with `VELES_MANAGER_MODE=1` a prompt routes through
    manager-spawn; WS stream surfaces `manager_plan` event + final `completed`."""
    monkeypatch.setenv("VELES_MANAGER_MODE", "1")

    from veles.core.orchestration.manager import ManagerRunResult
    from veles.core.orchestration.workers import WorkerPlan, WorkerStep

    plan = WorkerPlan(objective="research the auth module")
    plan.add(WorkerStep(role="explorer", prompt="…", status="done"))
    plan.add(WorkerStep(role="writer", prompt="…", status="done"))
    explorer_handle = WorkerHandle(
        role="explorer", prompt="…", result="raw findings", session_id="sess-explorer"
    )
    writer_handle = WorkerHandle(
        role="writer",
        prompt="…",
        result="final synthesised answer",
        session_id="sess-writer",
    )
    manager_result = ManagerRunResult(
        final_text="final synthesised answer",
        handles=(explorer_handle, writer_handle),
        plan=plan,
        error=None,
    )

    monkeypatch.setattr(
        "veles.core.orchestration.decompose_and_run",
        lambda *a, **kw: manager_result,
    )

    app = _make_app_with_manager(project, store, token_store, manager_result=manager_result)
    client = await aiohttp_client(app)
    headers = {"Authorization": f"Bearer {good_token}"}
    resp = await client.post(
        "/v1/runs",
        json={"prompt": "research the auth module and document it"},
        headers=headers,
    )
    body = await resp.json()
    run_id = body["run_id"]

    async with client.ws_connect(f"/v1/runs/{run_id}/events", headers=headers) as ws:
        events = await _drain_events(ws)

    types = [e["type"] for e in events]
    assert "started" in types
    assert "manager_plan" in types
    assert types[-1] == "completed"
    plan_event = next(e for e in events if e["type"] == "manager_plan")
    assert plan_event["objective"] == "research the auth module"
    assert [s["role"] for s in plan_event["steps"]] == ["explorer", "writer"]
    completion = events[-1]
    assert completion["text"] == "final synthesised answer"
    assert completion["session_id"] == "sess-writer"


# ---- fallback: manager error surfaces as run error ----


async def test_manager_error_marks_run_failed(
    aiohttp_client,
    project: Project,
    store: SessionStore,
    token_store: TokenStore,
    good_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the manager path errors mid-run, the WS stream emits an
    `error` event and the run is marked failed — no partial text
    leaks to the user."""
    monkeypatch.setenv("VELES_MANAGER_MODE", "1")

    from veles.core.orchestration.manager import ManagerRunResult
    from veles.core.orchestration.workers import WorkerPlan

    plan = WorkerPlan(objective="research")
    failed_result = ManagerRunResult(
        final_text=None,
        handles=(),
        plan=plan,
        error="provider quota exhausted",
    )
    monkeypatch.setattr(
        "veles.core.orchestration.decompose_and_run",
        lambda *a, **kw: failed_result,
    )

    app = _make_app_with_manager(project, store, token_store, manager_result=failed_result)
    client = await aiohttp_client(app)
    headers = {"Authorization": f"Bearer {good_token}"}
    resp = await client.post(
        "/v1/runs",
        json={"prompt": "research the auth module thoroughly please"},
        headers=headers,
    )
    body = await resp.json()
    run_id = body["run_id"]

    async with client.ws_connect(f"/v1/runs/{run_id}/events", headers=headers) as ws:
        events = await _drain_events(ws)

    types = [e["type"] for e in events]
    assert types[-1] == "error"
    assert "quota" in events[-1]["error"]


# ---- gate: kill switch ----


async def test_kill_switch_disables_manager_even_for_long_prompt(
    aiohttp_client,
    project: Project,
    store: SessionStore,
    token_store: TokenStore,
    good_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`VELES_MANAGER_MODE=0` → manager path bypassed; long prompt
    runs through the direct agent factory."""
    monkeypatch.setenv("VELES_MANAGER_MODE", "0")

    def boom(*a, **kw):
        raise AssertionError("decompose_and_run should not be invoked")

    monkeypatch.setattr("veles.core.orchestration.decompose_and_run", boom)

    app = _make_app_with_manager(project, store, token_store, manager_result=None)
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs",
        json={"prompt": "research the auth module thoroughly please"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 202
    run_id = (await resp.json())["run_id"]
    headers = {"Authorization": f"Bearer {good_token}"}
    async with client.ws_connect(f"/v1/runs/{run_id}/events", headers=headers) as ws:
        events = await _drain_events(ws)
    # Direct path completed — the gate skipped manager dispatch
    # (the patched decompose_and_run would have errored the run).
    assert events[-1]["type"] == "completed"


# ---- gate: factory absent → skip manager silently ----


async def test_missing_worker_factory_bypasses_manager(
    aiohttp_client,
    project: Project,
    store: SessionStore,
    token_store: TokenStore,
    good_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `state.worker_agent_factory` is None (older callers,
    test fixtures), manager-spawn is skipped silently — direct path
    runs as before."""
    monkeypatch.delenv("VELES_MANAGER_MODE", raising=False)

    def boom(*a, **kw):
        raise AssertionError("decompose_and_run should not be invoked")

    monkeypatch.setattr("veles.core.orchestration.decompose_and_run", boom)

    # build_state defaults worker_agent_factory=None
    agent_factory = _stub_agent_factory(store)
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=agent_factory,
    )
    app = make_app(state)
    assert state.worker_agent_factory is None

    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs",
        json={"prompt": "research the whole thing thoroughly please"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 202
    run_id = (await resp.json())["run_id"]
    headers = {"Authorization": f"Bearer {good_token}"}
    async with client.ws_connect(f"/v1/runs/{run_id}/events", headers=headers) as ws:
        events = await _drain_events(ws)
    # Direct path completed — manager-spawn was skipped silently.
    assert events[-1]["type"] == "completed"
