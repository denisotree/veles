"""M166 — ReminderRunner: deliver due task reminders via the shared router.

Unit behavior (deliver / idempotent / retry-on-failure) plus the daemon
wiring invariant: the runner shares the SAME DeliveryRouter the channels
register deliverers on (a fresh router would silently no-op — the M165 bug).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.reminder_runner import ReminderRunner
from veles.core.tasks_store import TasksStore
from veles.daemon.agent_factory import _attach_background_runners
from veles.daemon.auth import TokenStore
from veles.daemon.state import DaemonState


class _RecordingRouter:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    async def deliver(self, target, text):
        self.sent.append((target, text))


# ---- unit ----


async def test_tick_delivers_and_is_idempotent():
    store = TasksStore(":memory:")
    store.add_task(title="standup", due_at=50, deliver_to="telegram:42", now=10)
    router = _RecordingRouter()
    runner = ReminderRunner(store=store, delivery_router=router)
    assert await runner.tick(now=100) == 1
    assert router.sent == [("telegram:42", "⏰ standup")]
    assert await runner.tick(now=100) == 0  # already delivered — never twice
    assert len(router.sent) == 1
    store.close()


async def test_tick_includes_body():
    store = TasksStore(":memory:")
    store.add_task(title="call", body="re: invoice", due_at=50, deliver_to="telegram:1", now=10)
    router = _RecordingRouter()
    runner = ReminderRunner(store=store, delivery_router=router)
    await runner.tick(100)
    assert "⏰ call" in router.sent[0][1]
    assert "re: invoice" in router.sent[0][1]
    store.close()


async def test_failed_delivery_retries_next_tick():
    store = TasksStore(":memory:")
    store.add_task(title="x", due_at=50, deliver_to="telegram:1", now=10)

    class _Flaky:
        def __init__(self):
            self.calls = 0

        async def deliver(self, target, text):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("channel down")

    router = _Flaky()
    runner = ReminderRunner(store=store, delivery_router=router)
    assert await runner.tick(100) == 0  # failed → left unmarked
    assert await runner.tick(100) == 1  # retried, succeeded
    store.close()


async def test_malformed_target_is_disabled_not_retried_forever():
    """M208: a grammar-invalid target (e.g. 'chat') can never deliver — the
    runner must disable the reminder instead of retrying every tick forever."""
    from veles.channels.delivery import DeliveryRouter

    store = TasksStore(":memory:")
    store.add_task(title="x", due_at=50, deliver_to="chat", now=10)
    runner = ReminderRunner(store=store, delivery_router=DeliveryRouter())
    assert await runner.tick(100) == 0
    assert store.due_reminders(200) == []  # excluded from future sweeps
    store.close()


async def test_no_router_is_noop():
    store = TasksStore(":memory:")
    store.add_task(title="x", due_at=50, deliver_to="telegram:1", now=10)
    runner = ReminderRunner(store=store, delivery_router=None)
    assert await runner.tick(100) == 0
    store.close()


async def test_loop_delivers_then_stop_closes_store():
    store = TasksStore(":memory:")
    store.add_task(title="ring", due_at=50, deliver_to="telegram:1", now=10)
    router = _RecordingRouter()
    runner = ReminderRunner(store=store, delivery_router=router, interval_seconds=0.01)
    await runner.start()
    for _ in range(100):
        if router.sent:
            break
        await asyncio.sleep(0.01)
    await runner.stop()
    assert router.sent and router.sent[0][0] == "telegram:1"


# ---- M214: proactive (dream-source) reminders ----


async def test_dream_reminder_resolves_target_at_delivery():
    store = TasksStore(":memory:")
    store.upsert_dream_event(dedup_key="ev1", title="BC GAME live", due_at=50, now=10)
    router = _RecordingRouter()
    runner = ReminderRunner(
        store=store,
        delivery_router=router,
        target_resolver=lambda: "telegram:99",
    )
    assert await runner.tick(now=100) == 1
    assert router.sent == [("telegram:99", "⏰ BC GAME live")]
    store.close()


async def test_dream_reminder_cold_start_defers_then_delivers():
    """No active channel yet → resolver returns None → notice is NOT dropped,
    NOT marked; a later tick (channel now up) delivers it."""
    store = TasksStore(":memory:")
    store.upsert_dream_event(dedup_key="ev1", title="x", due_at=50, now=10)
    router = _RecordingRouter()
    target: list[str | None] = [None]  # cold start
    runner = ReminderRunner(store=store, delivery_router=router, target_resolver=lambda: target[0])
    assert await runner.tick(now=100) == 0  # deferred, not dropped
    assert store.due_reminders(100)  # still pending
    target[0] = "telegram:7"  # a chat became active
    assert await runner.tick(now=100) == 1
    assert router.sent == [("telegram:7", "⏰ x")]
    store.close()


async def test_delivery_attempts_are_logged():
    from veles.core.proactive.delivery_log import DeliveryLog

    store = TasksStore(":memory:")
    store.upsert_dream_event(dedup_key="ev1", title="x", due_at=50, now=10)
    log = DeliveryLog(":memory:")
    target: list[str | None] = [None]
    runner = ReminderRunner(
        store=store,
        delivery_router=_RecordingRouter(),
        target_resolver=lambda: target[0],
        delivery_log=log,
    )
    await runner.tick(now=100)  # cold start → logged as no_target_yet
    target[0] = "telegram:7"
    await runner.tick(now=100)  # delivered → logged ok
    attempts = log.recent()
    assert [a.ok for a in attempts] == [True, False]
    assert attempts[1].reason == "no_target_yet"
    assert attempts[0].dedup_key == "ev1"
    store.close()
    log.close()


# ---- daemon wiring ----


def _make_state(tmp_path: Path) -> DaemonState:
    project = init_project(tmp_path, name=None, force=False)
    store = SessionStore(project.memory_db_path)
    return DaemonState(
        project=project,
        store=store,
        token_store=TokenStore.load(),
        agent_factory=lambda *a, **kw: None,
        started_at=0.0,
    )


def test_attach_wires_reminder_runner_sharing_router(tmp_path: Path):
    state = _make_state(tmp_path)
    jobs_store = _attach_background_runners(state, state.project, lambda s: None, "anthropic")
    try:
        assert state.reminder_runner is not None
        # MUST be the same instance channels register deliverers on (M165 lesson).
        assert state.reminder_runner._delivery is state.delivery_router
        # M214: the daemon hand-off itself — proactive plumbing must be wired,
        # not just constructable. Locks the seam that unit tests can't see.
        assert state.reminder_runner._target_resolver is not None
        assert state.reminder_runner._delivery_log is not None
        assert state.dream_runner is not None
        assert state.dream_runner._proactive_loader is not None
    finally:
        jobs_store.close()
        state.reminder_runner._store.close()
        state.store.close()


async def test_due_reminder_reaches_registered_deliverer(tmp_path: Path):
    state = _make_state(tmp_path)
    jobs_store = _attach_background_runners(state, state.project, lambda s: None, "anthropic")
    try:
        seen: list[tuple[str, str]] = []

        async def deliverer(chat_id, text, thread_id):
            seen.append((chat_id, text))

        state.delivery_router.register_deliverer("telegram", deliverer)

        ts = TasksStore(state.project.memory_db_path)
        ts.add_task(title="hi", due_at=50, deliver_to="telegram:42", now=10)
        ts.close()

        assert await state.reminder_runner.tick(now=100) == 1
        assert seen == [("42", "⏰ hi")]
    finally:
        jobs_store.close()
        await state.reminder_runner.stop()
        state.store.close()
