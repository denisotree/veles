"""M165 — scheduled-job delivery is actually wired in the daemon.

The delivery plumbing (`DeliveryRouter`, `JobRunner._delivery`, the
`deliver_to` column) all existed but the daemon constructed
`JobRunner(delivery_router=None)` and never registered a platform
deliverer, so a job's `deliver_to` was silently dropped. These tests
pin the three seams that close the loop:

1. `TelegramGateway.deliver(...)` renders + sends to a chat.
2. `_attach_background_runners` builds a router and hands it to JobRunner.
3. `_start_channel_runners` registers each gateway's `deliver` on the
   router, so `deliver_to = "telegram:<chat>"` reaches the gateway.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from veles.channels.delivery import DeliveryRouter
from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.secrets import delete_provider_key, set_provider_key
from veles.daemon.agent_factory import _attach_background_runners
from veles.daemon.auth import TokenStore
from veles.daemon.server import _start_channel_runners
from veles.daemon.state import DaemonState


def _make_state(tmp_path: Path) -> DaemonState:
    project = init_project(tmp_path, name=None, force=False)
    store = SessionStore(project.memory_db_path)
    tokens = TokenStore.load()

    def factory(session_id):  # pragma: no cover - never called (no due jobs)
        raise AssertionError("agent factory must not run in these tests")

    return DaemonState(
        project=project,
        store=store,
        token_store=tokens,
        agent_factory=factory,
        started_at=0.0,
    )


# ---- 1. TelegramGateway.deliver ----


async def test_gateway_deliver_renders_and_sends(tmp_path: Path) -> None:
    sends: list[tuple[str, dict[str, Any]]] = []

    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        return {"message_id": 1, "chat": payload.get("chat_id")}

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=object(),
        session_map=SessionMap.load(tmp_path / "tg-sessions.json"),
    )
    gateway._telegram_send = stub_send

    await gateway.deliver("42", "**bold** reminder", None)

    assert len(sends) == 1
    method, payload = sends[0]
    assert method == "sendMessage"
    assert payload["chat_id"] == 42  # string target coerced to int
    assert "<b>bold</b>" in payload["text"]  # markdown rendered to telegram HTML


async def test_gateway_deliver_accepts_thread_id(tmp_path: Path) -> None:
    """thread_id is accepted (PlatformDeliverer signature) even though
    direct chats don't use forum topics — must not raise."""
    sends: list[tuple[str, dict[str, Any]]] = []

    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        return {"message_id": 1}

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=object(),
        session_map=SessionMap.load(tmp_path / "tg-sessions.json"),
    )
    gateway._telegram_send = stub_send

    await gateway.deliver("7", "hi", "topic-9")
    assert sends and sends[0][1]["chat_id"] == 7


# ---- 2. _attach_background_runners wires a router ----


def test_attach_wires_delivery_router_into_job_runner(tmp_path: Path) -> None:
    state = _make_state(tmp_path)

    def factory(session_id):  # pragma: no cover
        raise AssertionError

    jobs_store = _attach_background_runners(state, state.project, factory, "anthropic")
    try:
        assert state.delivery_router is not None
        # The router the daemon stored is the one the JobRunner will use.
        assert state.job_runner is not None
        assert state.job_runner._delivery is state.delivery_router
    finally:
        jobs_store.close()
        state.store.close()


# ---- 3. _start_channel_runners registers the gateway deliverer ----


async def test_start_channel_runners_registers_telegram_deliverer(
    tmp_path: Path, monkeypatch
) -> None:
    state = _make_state(tmp_path)
    state.delivery_router = DeliveryRouter()
    set_provider_key("telegram", "tok-test", project=state.project.name)
    (state.project.state_dir / "config.toml").write_text(
        '[channels.telegram]\nenabled = true\nwhitelist = ["12345"]\n',
        encoding="utf-8",
    )

    async def fake_start(self):
        pass

    from veles.channels import telegram as tg_mod

    monkeypatch.setattr(tg_mod.TelegramGateway, "start", fake_start)

    try:
        _start_channel_runners(state)
        assert len(state.channel_runners) == 1
        gateway = state.channel_runners[0]

        # Capture the gateway's outbound network call.
        sends: list[tuple[str, dict[str, Any]]] = []

        async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
            sends.append((method, payload))
            return {"message_id": 1}

        gateway._telegram_send = stub_send

        # Deliver via the router — exercises register_deliverer → gateway.deliver.
        info = await state.delivery_router.deliver("telegram:12345", "**alert**")
        assert info["delivered"] is True
        assert sends and sends[0][0] == "sendMessage"
        assert sends[0][1]["chat_id"] == 12345
        assert "<b>alert</b>" in sends[0][1]["text"]

        for task in list(state.channel_tasks):
            await asyncio.wait_for(task, timeout=2.0)
    finally:
        delete_provider_key("telegram", project=state.project.name)
        state.store.close()
