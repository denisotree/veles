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

from veles.core.curator_state import load
from veles.core.dreaming import (
    _DEEP_DEFAULT_IDLE_SEC,
    _DEEP_DEFAULT_INTERVAL_SEC,
    DreamResult,
    dream_cycle,
)

if TYPE_CHECKING:
    from veles.core.project import Project
    from veles.core.provider import Provider

logger = logging.getLogger(__name__)


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
        consolidation_model: str | None = None,
        insight_history_loader=None,
        runtime_session_loader=None,
    ) -> None:
        self._project = project
        self._state = state
        self._provider_factory = provider_factory
        self._check_interval = check_interval_seconds
        self._idle_threshold = idle_threshold_seconds
        self._deep_interval = deep_interval_seconds
        self._consolidation_model = consolidation_model
        self._insight_loader = insight_history_loader
        self._runtime_session_loader = runtime_session_loader
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
        return await asyncio.to_thread(
            self._run_cycle, include_consolidation=include_consolidation
        )

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

    async def _maybe_run(self) -> None:
        now = time.time()
        if self._inflight is not None and not self._inflight.done():
            return
        if self._state.has_running_run():
            return
        if now - self._state.last_activity_at < self._idle_threshold:
            return
        state = load(self._project.state_dir / "curator.state.json")
        if now - state.last_deep_dream_at < self._deep_interval:
            return
        # Spawn the cycle on a worker thread; dream_cycle is sync.
        self._inflight = asyncio.create_task(
            asyncio.to_thread(self._run_cycle, include_consolidation=True)
        )


__all__ = ["DreamRunner"]
