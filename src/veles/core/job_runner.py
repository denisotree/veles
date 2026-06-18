"""JobRunner (M75) — async tick loop driving JobsStore + AgentFactory.

A single instance lives inside the daemon (`DaemonState.job_runner`). On each
`tick(now)`:

1. fetch due jobs from `JobsStore.due_jobs(now)`,
2. for each due job, spawn `_run_one(job)` under a semaphore so an unbounded
   queue can't pile up parallel agent runs,
3. each `_run_one` constructs a fresh `Agent` via `AgentFactory(None)`
   (isolated session), optionally prefixes the prompt with the previous
   job's output (`context_from`), writes the markdown output under
   `<project>/.veles/jobs/<job_id>/<ts>.md`, marks the run finished,
   and computes the next `next_run_at` from the schedule (or marks the job
   `done` if a `once`-style schedule fired or `repeat_times` is exhausted).

Concurrency: bounded by `max_parallel` (default 2). A long-running job
doesn't block the tick — the next tick still sees other due jobs. We use
`asyncio.to_thread` for the synchronous `Agent.run` so the event loop stays
responsive (this mirrors `daemon.runner.run_agent_in_background`).

Delivery is optional: if `deliver_to` is set, a `DeliveryRouter` (passed in)
sends the output to the configured target. Failures during delivery don't
mark the run as failed — they're recorded in `last_error` separately so a
broken Telegram bot doesn't permanently break a working schedule.

CLI parity: `JobRunner.tick_once()` is a synchronous one-shot used by
`veles job tick` for testing / running without a daemon.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from veles.core.job_schedule import compute_next_run
from veles.core.jobs_store import JobRecord, JobsStore

logger = logging.getLogger(__name__)


# Signature compatible with daemon.runner.AgentFactory: factory(session_id)
# returns an Agent-shaped object whose `.run(prompt)` returns a RunResult.
AgentFactory = Callable[[str | None], Any]


@dataclass(slots=True)
class JobRunSummary:
    job_id: str
    run_id: str
    status: str  # 'ok' | 'error'
    iterations: int | None
    output_path: str | None
    error: str | None


class JobRunner:
    def __init__(
        self,
        *,
        store: JobsStore,
        agent_factory: AgentFactory,
        output_root: Path,
        max_parallel: int = 2,
        delivery_router=None,
        tz=None,
    ) -> None:
        self._store = store
        self._agent_factory = agent_factory
        self._output_root = Path(output_root)
        self._sem = asyncio.Semaphore(max_parallel)
        self._delivery = delivery_router
        # M167: timezone for calendar schedules (daily@09:00 …); None → host-local.
        self._tz = tz
        self._loop_task: asyncio.Task | None = None
        self._running = False
        self._inflight: set[asyncio.Task] = set()

    # ---- public lifecycle ----

    async def start(self, *, interval_seconds: float = 60.0) -> None:
        """Spawn the tick loop. Idempotent — second call is a no-op."""
        if self._loop_task is not None and not self._loop_task.done():
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop(interval_seconds))

    async def stop(self) -> None:
        """Stop the tick loop and wait for in-flight jobs."""
        self._running = False
        if self._loop_task is not None:
            self._loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._loop_task
            self._loop_task = None
        if self._inflight:
            await asyncio.gather(*self._inflight, return_exceptions=True)

    def status(self) -> dict[str, object]:
        return {
            "enabled": self._running,
            "inflight": len(self._inflight),
            "max_parallel": self._sem._value + len(self._inflight),  # crude best-effort
        }

    # ---- tick ----

    async def _run_loop(self, interval_seconds: float) -> None:
        while self._running:
            try:
                await self.tick(time.time())
            except Exception:  # pragma: no cover - defensive
                logger.exception("job runner tick failed")
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break

    async def tick(self, now: float) -> list[asyncio.Task]:
        """Spawn `_run_one` tasks for each due job. Returns the new tasks."""
        due = self._store.due_jobs(now)
        new_tasks: list[asyncio.Task] = []
        for job in due:
            task = asyncio.create_task(self._run_one(job, now=now))
            self._inflight.add(task)
            task.add_done_callback(self._inflight.discard)
            new_tasks.append(task)
        return new_tasks

    def tick_once(self, now: float | None = None) -> list[JobRunSummary]:
        """Synchronous wrapper for `tick` + drain — used by CLI `job tick`."""
        return asyncio.run(self._tick_once(now if now is not None else time.time()))

    async def _tick_once(self, now: float) -> list[JobRunSummary]:
        due = self._store.due_jobs(now)
        results = await asyncio.gather(
            *[self._run_one(job, now=now) for job in due], return_exceptions=False
        )
        return list(results)

    # ---- run one job ----

    async def _run_one(self, job: JobRecord, *, now: float) -> JobRunSummary:
        async with self._sem:
            return await self._execute(job, now=now)

    async def _execute(self, job: JobRecord, *, now: float) -> JobRunSummary:
        rid = self._store.mark_run_started(job_id=job.id, started_at=now)
        started = now
        prompt = job.prompt
        if job.context_from:
            prev = self._store.get_job(job.context_from)
            if prev is not None and prev.last_output_path:
                ctx_text = _read_text(Path(prev.last_output_path))
                if ctx_text:
                    prompt = (
                        f"<context_from job={prev.id} name={prev.name!r}>\n"
                        f"{ctx_text}\n"
                        f"</context_from>\n\n{prompt}"
                    )
        agent = self._agent_factory(None)
        try:
            result = await asyncio.to_thread(agent.run, prompt)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            self._store.mark_run_finished(run_id=rid, status="error", error=err, finished_at=now)
            self._advance_schedule(job, status="error", last_error=err, now=now)
            return JobRunSummary(
                job_id=job.id,
                run_id=rid,
                status="error",
                iterations=None,
                output_path=None,
                error=err,
            )
        output_path = self._write_output(job, result, started)
        delivery_err: str | None = None
        if job.deliver_to and self._delivery is not None:
            try:
                await self._delivery.deliver(job.deliver_to, result.text or "")
            except Exception as exc:  # pragma: no cover - delivery is best-effort
                delivery_err = f"delivery failed: {type(exc).__name__}: {exc}"
                logger.warning("job %s delivery failed: %s", job.id, exc)
        self._store.mark_run_finished(
            run_id=rid,
            status="ok",
            iterations=getattr(result, "iterations", None),
            output_path=str(output_path),
            error=delivery_err,
            finished_at=now,
        )
        self._advance_schedule(
            job,
            status="ok",
            last_output_path=str(output_path),
            last_error=delivery_err,
            now=now,
        )
        return JobRunSummary(
            job_id=job.id,
            run_id=rid,
            status="ok",
            iterations=getattr(result, "iterations", None),
            output_path=str(output_path),
            error=delivery_err,
        )

    def _advance_schedule(
        self,
        job: JobRecord,
        *,
        status: str,
        now: float,
        last_output_path: str | None = None,
        last_error: str | None = None,
    ) -> None:
        completed = job.repeat_completed + 1
        next_at = compute_next_run(job.schedule, now=now, tz=self._tz)
        done = next_at is None or (job.repeat_times is not None and completed >= job.repeat_times)
        updates: dict[str, object] = {
            "last_run_at": now,
            "last_status": status,
            "repeat_completed": completed,
        }
        if last_output_path is not None:
            updates["last_output_path"] = last_output_path
        if last_error is not None:
            updates["last_error"] = last_error
        if done:
            updates["state"] = "done"
            updates["enabled"] = False
            updates["next_run_at"] = job.next_run_at  # leave as-is; ignored when disabled
        else:
            updates["next_run_at"] = next_at
        self._store.update_job(job.id, **updates)

    def _write_output(
        self,
        job: JobRecord,
        result: Any,
        started_at: float,
    ) -> Path:
        when = dt.datetime.fromtimestamp(started_at, tz=dt.UTC).strftime("%Y%m%dT%H%M%SZ")
        target_dir = self._output_root / job.id
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{when}.md"
        text = getattr(result, "text", "") or ""
        iterations = getattr(result, "iterations", None)
        body = (
            f"# {job.name}\n\n"
            f"- job_id: `{job.id}`\n"
            f"- started_at: {when}\n"
            f"- iterations: {iterations}\n"
            f"- schedule: {job.schedule.display()}\n\n"
            f"## prompt\n\n```\n{job.prompt}\n```\n\n"
            f"## response\n\n{text}\n"
        )
        path.write_text(body, encoding="utf-8")
        return path


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


__all__ = ["AgentFactory", "JobRunSummary", "JobRunner"]
