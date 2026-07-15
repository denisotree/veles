"""DreamRunner (M76) — daemon-side idle-timer for `dream_cycle`.

Lives under `DaemonState.dream_runner`. The async loop wakes every
`check_interval_seconds` (default 120), and if:

  - no active runs in `state.runs`,
  - `now - state.last_activity_at > idle_threshold_seconds` (default 600),
  - `now - last_deep_dream_at > deep_interval_seconds` (default 6h),

then it kicks off `dream_cycle(include_consolidation=True)` in a worker.
Otherwise the loop sleeps.

A throttle on `CuratorState.last_deep_dream_at` (persisted by
`dream_cycle`) is the only race-free way to suppress repeat deep cycles
across daemon restarts. The runner takes no locks of its own —
`dream_cycle` already holds the `<project>/.veles/dream.lock`.

Why a separate runner module: keeps `dreaming.py` pure (no asyncio loop,
no daemon imports), so the CLI can call `dream_cycle` directly without
pulling in the runtime.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING

from veles.core.curator_state import load, save_atomic
from veles.core.dreaming import (
    _DEEP_DEFAULT_IDLE_SEC,
    _DEEP_DEFAULT_INTERVAL_SEC,
    DreamResult,
    dream_cycle,
    run_proactive_extraction,
)

if TYPE_CHECKING:
    from veles.core.project import Project

logger = logging.getLogger(__name__)

# M214: proactive extraction runs on its OWN cadence, far shorter than the 6h
# deep dream — a "remind me at 20:00" mentioned at 19:00 must be materialised
# well before 20:00. It does not wait for the long idle gate (a user chatting
# for an hour would otherwise never get near-term events surfaced).
_PROACTIVE_DEFAULT_INTERVAL_SEC = 15 * 60.0


class DreamRunner:
    def __init__(
        self,
        *,
        project: Project,
        state,
        provider_factory,
        check_interval_seconds: float = 120.0,
        idle_threshold_seconds: float = _DEEP_DEFAULT_IDLE_SEC,
        deep_interval_seconds: float = _DEEP_DEFAULT_INTERVAL_SEC,
        proactive_interval_seconds: float = _PROACTIVE_DEFAULT_INTERVAL_SEC,
        consolidation_model: str | None = None,
        insight_history_loader=None,
        runtime_session_loader=None,
        proactive_history_loader=None,
    ) -> None:
        self._project = project
        self._state = state
        self._provider_factory = provider_factory
        self._check_interval = check_interval_seconds
        self._idle_threshold = idle_threshold_seconds
        self._deep_interval = deep_interval_seconds
        self._proactive_interval = proactive_interval_seconds
        self._consolidation_model = consolidation_model
        self._insight_loader = insight_history_loader
        self._runtime_session_loader = runtime_session_loader
        # M214: recent-activity-window corpus loader for proactive extraction —
        # deliberately NOT the curation-cursor `insight_history_loader`, whose
        # sessions disappear once curated (would empty the corpus on an active
        # daemon). Decoupled: curation and proactivity have different retention.
        self._proactive_loader = proactive_history_loader
        self._loop_task: asyncio.Task | None = None
        self._running = False
        self._inflight: asyncio.Task | None = None
        self._last_result: DreamResult | None = None

    async def start(self) -> None:
        if self._loop_task is not None and not self._loop_task.done():
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._loop_task is not None:
            self._loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._loop_task
            self._loop_task = None
        if self._inflight is not None:
            with contextlib.suppress(Exception):
                await self._inflight

    def status(self) -> dict[str, object]:
        return {
            "enabled": self._running,
            "inflight": self._inflight is not None and not self._inflight.done(),
            "idle_threshold": self._idle_threshold,
            "deep_interval": self._deep_interval,
            "last_summary": self._last_result.summary() if self._last_result else None,
        }

    async def force_run(self, *, include_consolidation: bool = True) -> DreamResult:
        """Synchronous-ish trigger used by the daemon `/v1/dream/run` endpoint."""
        return await asyncio.to_thread(self._run_cycle, include_consolidation=include_consolidation)

    def _run_cycle(self, *, include_consolidation: bool) -> DreamResult:
        provider = None
        if include_consolidation and self._provider_factory is not None:
            try:
                provider = self._provider_factory()
            except Exception as exc:
                logger.warning("dream: provider factory failed: %s", exc)
        result = dream_cycle(
            self._project,
            include_consolidation=include_consolidation and provider is not None,
            provider=provider,
            consolidation_model=self._consolidation_model,
            insight_history_loader=self._insight_loader,
            runtime_session_loader=self._runtime_session_loader,
            proactive_history_loader=self._proactive_loader,
        )
        self._last_result = result
        return result

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._maybe_run()
            except Exception:  # pragma: no cover - defensive
                logger.exception("dream runner tick failed")
            try:
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break

    def _run_proactive(self, now: float) -> int:
        """M214: fast-cadence proactive extraction (definite dated events →
        reminders). Runs off the deep-dream throttle so near-term events are
        materialised promptly. Best-effort; persists its own throttle cursor."""
        if self._provider_factory is None or self._proactive_loader is None:
            return 0
        try:
            provider = self._provider_factory()
        except Exception as exc:
            logger.warning("proactive: provider factory failed: %s", exc)
            return 0
        if provider is None:
            return 0
        count = 0
        try:
            count = run_proactive_extraction(
                self._project,
                provider=provider,
                model=self._consolidation_model or "",
                history_loader=self._proactive_loader,
                now=now,
            )
        except Exception:
            logger.exception("proactive extraction failed")
        # Advance the throttle regardless of outcome so a persistent failure
        # doesn't hammer the provider every check interval.
        state_path = self._project.state_dir / "curator.state.json"
        from dataclasses import replace

        with contextlib.suppress(Exception):
            state = load(state_path)
            save_atomic(state_path, replace(state, last_proactive_at=now))
        return count

    async def _maybe_run(self) -> None:
        now = time.time()
        if self._inflight is not None and not self._inflight.done():
            return
        if self._state.has_running_run():
            return
        state = load(self._project.state_dir / "curator.state.json")
        # M214: proactive extraction first — its own short throttle, and it does
        # NOT wait for the long idle gate (near-term events surfaced during an
        # active session too). LLM-gated: only when a provider is available.
        if (
            self._provider_factory is not None
            and self._proactive_loader is not None
            and now - state.last_proactive_at >= self._proactive_interval
        ):
            self._inflight = asyncio.create_task(asyncio.to_thread(self._run_proactive, now))
            return
        if now - self._state.last_activity_at < self._idle_threshold:
            return
        if now - state.last_deep_dream_at < self._deep_interval:
            return
        # Spawn the cycle on a worker thread; dream_cycle is sync.
        self._inflight = asyncio.create_task(
            asyncio.to_thread(self._run_cycle, include_consolidation=True)
        )


__all__ = ["DreamRunner"]
