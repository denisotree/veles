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

M214 (proactive delivery): `'dream'`-source reminders carry no `deliver_to` —
their target ("the last active channel") is resolved by `target_resolver` at
delivery time. When it returns None (cold start: no channel has seen a message
yet) the notice is **left unmarked and retried next tick**, never dropped —
the load-bearing invariant that turns "randomly missing" into "reliable". Every
attempt (success, cold-start defer, channel-down, invalid target) is written to
the optional `delivery_log` so self-diagnosis reads facts, not guesses.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class ReminderRunner:
    def __init__(
        self,
        *,
        store,
        delivery_router,
        interval_seconds: float = 60.0,
        target_resolver: Callable[[], str | None] | None = None,
        delivery_log=None,
        on_delivered: Callable[[str, str], Any] | None = None,
    ) -> None:
        self._store = store
        self._delivery = delivery_router
        self._interval = interval_seconds
        # Resolves the target for a dream notice with no `deliver_to` (the last
        # active channel). None-returning = "not resolvable yet" → retry.
        self._target_resolver = target_resolver
        self._delivery_log = delivery_log
        # M214 (A4): async hook run after a successful push — the daemon uses it
        # to bind the notice to the chat's session (record it as an assistant
        # turn, creating a session if needed) so a reply continues coherently.
        # Best-effort: its failure never blocks delivery or mark-as-sent.
        self._on_delivered = on_delivered
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
        if self._delivery_log is not None:
            with contextlib.suppress(Exception):
                self._delivery_log.close()

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

    def _resolve_target(self, task) -> str | None:
        """The concrete `<platform>:<chat_id>` a task delivers to. User
        reminders carry it directly; a dream notice with no `deliver_to` gets
        the last active channel from the resolver (None until one exists)."""
        if task.deliver_to:
            return task.deliver_to
        if task.source == "dream" and self._target_resolver is not None:
            return self._target_resolver()
        return None

    def _log(self, task, *, target, ok, reason, now) -> None:
        if self._delivery_log is None:
            return
        with contextlib.suppress(Exception):
            self._delivery_log.record(
                target=target,
                dedup_key=task.dedup_key,
                ok=ok,
                reason=reason,
                now=now,
            )

    async def tick(self, now: float) -> int:
        """Deliver every due reminder once. Returns the count delivered."""
        if self._delivery is None:
            return 0
        delivered = 0
        for task in self._store.due_reminders(now):
            target = self._resolve_target(task)
            if not target:
                # Not resolvable yet (dream notice, cold start — no active
                # channel). Leave unmarked so a later tick retries once a chat
                # exists. NEVER drop or mark-done: the load-bearing invariant.
                logger.debug("reminder %s has no resolvable target yet; deferring", task.id)
                self._log(task, target=None, ok=False, reason="no_target_yet", now=now)
                continue
            text = f"⏰ {task.title}"
            if task.body:
                text += f"\n\n{task.body}"
            try:
                await self._delivery.deliver(target, text)
            except ValueError as exc:
                # Malformed target (fails the router grammar) — permanent; a
                # retry can never succeed, so disable the reminder instead of
                # failing every tick forever. Task tools validate targets at
                # write time (M208); this catches pre-validation rows.
                logger.error(
                    "reminder %s has an invalid delivery target %r; disabling it: %s",
                    task.id,
                    target,
                    exc,
                )
                self._log(task, target=target, ok=False, reason=f"invalid_target: {exc}", now=now)
                self._store.mark_reminded(task.id, now=now)
                continue
            except Exception as exc:
                # Channel may not be up yet (no deliverer registered). Leave the
                # task unmarked so the next tick retries instead of dropping it.
                logger.warning("reminder %s delivery failed: %s", task.id, exc)
                self._log(task, target=target, ok=False, reason=f"delivery_failed: {exc}", now=now)
                continue
            self._log(task, target=target, ok=True, reason=None, now=now)
            # A4: bind the notice to the chat's session (best-effort — a binding
            # failure must not un-deliver a sent reminder).
            if self._on_delivered is not None:
                try:
                    await self._on_delivered(target, text)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("reminder %s post-deliver bind failed: %s", task.id, exc)
            self._store.mark_reminded(task.id, now=now)
            delivered += 1
        return delivered


__all__ = ["ReminderRunner"]
