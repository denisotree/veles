"""ReminderRunner (M166) — async tick loop that delivers due task reminders.

A trivial sibling of `JobRunner`: where a job spawns an agent, a reminder just
pushes text. On each tick it asks `TasksStore.due_reminders(now)` for tasks
that are open, due, not yet delivered, and have a target, then sends each via
the **shared** M165 `DeliveryRouter` (the same instance the daemon registers
channel deliverers on — a fresh router would have no deliverers and silently
no-op) and marks it delivered. Delivery is idempotent via `reminded_at`; a
*failed* delivery is left unmarked so the next tick retries — important when
the channel gateway isn't up yet at fire time.

No semaphore, no parallelism, no agent spawn — a reminder is strictly "push
this text at time T". Only the start/stop/tick lifecycle is borrowed from
JobRunner.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

logger = logging.getLogger(__name__)


class ReminderRunner:
    def __init__(self, *, store, delivery_router, interval_seconds: float = 60.0) -> None:
        self._store = store
        self._delivery = delivery_router
        self._interval = interval_seconds
        self._loop_task: asyncio.Task | None = None
        self._running = False

    async def start(self, *, interval_seconds: float | None = None) -> None:
        """Spawn the tick loop. Idempotent — a second call is a no-op."""
        if self._loop_task is not None and not self._loop_task.done():
            return
        self._running = True
        self._loop_task = asyncio.create_task(
            self._run_loop(interval_seconds if interval_seconds is not None else self._interval)
        )

    async def stop(self) -> None:
        """Stop the loop and close the store this runner owns."""
        self._running = False
        if self._loop_task is not None:
            self._loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._loop_task
            self._loop_task = None
        with contextlib.suppress(Exception):
            self._store.close()

    async def _run_loop(self, interval: float) -> None:
        while self._running:
            try:
                await self.tick(time.time())
            except Exception:  # pragma: no cover - defensive
                logger.exception("reminder runner tick failed")
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

    async def tick(self, now: float) -> int:
        """Deliver every due reminder once. Returns the count delivered."""
        if self._delivery is None:
            return 0
        delivered = 0
        for task in self._store.due_reminders(now):
            if not task.deliver_to:
                continue
            text = f"⏰ {task.title}"
            if task.body:
                text += f"\n\n{task.body}"
            try:
                await self._delivery.deliver(task.deliver_to, text)
            except ValueError as exc:
                # Malformed target (fails the router grammar) — permanent; a
                # retry can never succeed, so disable the reminder instead of
                # failing every tick forever. Task tools validate targets at
                # write time (M208); this catches pre-validation rows.
                logger.error(
                    "reminder %s has an invalid delivery target %r; disabling it: %s",
                    task.id,
                    task.deliver_to,
                    exc,
                )
                self._store.mark_reminded(task.id, now=now)
                continue
            except Exception as exc:
                # Channel may not be up yet (no deliverer registered). Leave the
                # task unmarked so the next tick retries instead of dropping it.
                logger.warning("reminder %s delivery failed: %s", task.id, exc)
                continue
            self._store.mark_reminded(task.id, now=now)
            delivered += 1
        return delivered


__all__ = ["ReminderRunner"]
