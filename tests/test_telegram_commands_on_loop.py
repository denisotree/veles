"""Every Telegram command runs on the daemon's event loop without tripping the
memory loop guard (`core/memory/aio.py::submit`, M264).

Telegram handlers are coroutines on the daemon's loop, so any synchronous
memory access in one fails with "memory.aio.submit() called from inside an
event loop" — the class of the daemon bug fixed in 0.40.0 (M281) and of the
REPL's `/insights` / `/rules`. Clean when written (2026-09-23); this keeps a new
command from reintroducing it. Driven through the real gateway and in-process
backend against a real project, the way the daemon runs them.
"""

from __future__ import annotations

import pytest

from veles.channels._telegram_commands import _HANDLERS, dispatch
from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.in_process_backend import InProcessRunBackend
from veles.daemon.server import build_state

_LOOP_GUARD = ("inside an event loop", "cannot be called from a running event loop")


@pytest.fixture()
def gateway(tmp_path):
    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)
    state = build_state(
        project=project,
        store=store,
        token_store=TokenStore.load(tmp_path / "t.json"),
        agent_factory=lambda *a, **k: None,
    )
    smap = SessionMap.load(tmp_path / "tg.json")
    smap.set("42", store.create_session())
    sent: list[str] = []

    async def fake_send(method, payload):
        sent.append(str(payload.get("text", "")))
        return {"message_id": 1, "chat": payload.get("chat_id")}

    gw = TelegramGateway(
        bot_token="X",
        daemon_client=InProcessRunBackend(state),
        session_map=smap,
        project_root=project.root,
    )
    gw._telegram_send = fake_send  # type: ignore[method-assign]
    yield gw, sent
    store.close()


@pytest.mark.parametrize("args", ["", "all"])
async def test_no_telegram_command_trips_the_loop_guard(gateway, args) -> None:
    gw, sent = gateway
    failures: dict[str, str] = {}
    for name in sorted(_HANDLERS):
        sent.clear()
        try:
            reply = await dispatch(gw, "42", name, args)
        except Exception as exc:
            reply = f"{type(exc).__name__}: {exc}"
        seen = " ".join([str(reply), *sent])
        if any(marker in seen for marker in _LOOP_GUARD):
            failures[name] = seen[:200]
    assert not failures, f"commands hit the memory loop guard: {failures}"
