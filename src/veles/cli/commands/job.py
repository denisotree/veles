"""`veles job ...` (M75) — manage scheduled agent jobs.

Subcommands operate on the active project's `.veles/memory.db` (jobs +
job_runs tables, see `core/jobs_store.py`). `tick` runs the runner once
synchronously — useful for testing and one-off invocations without a
daemon.

The daemon (`veles daemon start`) hosts a long-running `JobRunner` that
calls `tick()` every minute and dispatches due jobs. `veles job tick` and
the daemon are CRUD-symmetric over the SQLite store.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

from veles.core.jobs_store import JobsStore


def cmd_job(args: argparse.Namespace, project) -> int:
    sub = args.job_command
    store = JobsStore(project.memory_db_path)
    try:
        if sub == "add":
            return _cmd_add(args, store)
        if sub == "list":
            return _cmd_list(args, store)
        if sub == "show":
            return _cmd_show(args, store)
        if sub == "pause":
            return _cmd_set_enabled(args, store, enabled=False)
        if sub == "resume":
            return _cmd_set_enabled(args, store, enabled=True)
        if sub == "trigger":
            return _cmd_trigger(args, store)
        if sub == "remove":
            return _cmd_remove(args, store)
        if sub == "history":
            return _cmd_history(args, store)
        if sub == "tick":
            return _cmd_tick(args, store, project)
        print(f"error: unknown job subcommand: {sub!r}", file=sys.stderr)
        return 2
    finally:
        store.close()


def _cmd_add(args: argparse.Namespace, store: JobsStore) -> int:
    try:
        rec = store.add_job(
            name=args.name,
            prompt=args.prompt,
            schedule_expr=args.schedule,
            repeat_times=args.repeat,
            context_from=args.context_from,
            deliver_to=args.deliver_to,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"created job {rec.id}  next_run_at={time.strftime('%Y-%m-%d %H:%M', time.localtime(rec.next_run_at))}")
    return 0


def _cmd_list(args: argparse.Namespace, store: JobsStore) -> int:
    records = store.list_jobs(include_disabled=True)
    if not records:
        print("no jobs configured.")
        return 0
    if getattr(args, "json", False):
        print(json.dumps([_job_to_json(r) for r in records], indent=2, default=str))
        return 0
    for r in records:
        nxt = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.next_run_at))
        status = "✓" if r.enabled and r.state == "scheduled" else r.state
        last = r.last_status or "-"
        print(f"  {r.id}  {status:<10}  next={nxt}  last={last}  {r.name}")
    return 0


def _cmd_show(args: argparse.Namespace, store: JobsStore) -> int:
    rec = store.get_job(args.id)
    if rec is None:
        print(f"error: no job {args.id!r}", file=sys.stderr)
        return 1
    print(json.dumps(_job_to_json(rec), indent=2, default=str))
    return 0


def _cmd_set_enabled(
    args: argparse.Namespace, store: JobsStore, *, enabled: bool
) -> int:
    ok = store.update_job(args.id, enabled=enabled, state="scheduled" if enabled else "paused")
    if not ok:
        print(f"error: no job {args.id!r}", file=sys.stderr)
        return 1
    print(f"{'resumed' if enabled else 'paused'} {args.id}")
    return 0


def _cmd_trigger(args: argparse.Namespace, store: JobsStore) -> int:
    if not store.trigger_job(args.id):
        print(f"error: no job {args.id!r}", file=sys.stderr)
        return 1
    print(f"triggered {args.id} — next_run_at = now")
    return 0


def _cmd_remove(args: argparse.Namespace, store: JobsStore) -> int:
    if not store.delete_job(args.id):
        print(f"error: no job {args.id!r}", file=sys.stderr)
        return 1
    print(f"removed {args.id}")
    return 0


def _cmd_history(args: argparse.Namespace, store: JobsStore) -> int:
    runs = store.list_runs(args.id, limit=args.limit)
    if not runs:
        print("no runs recorded.")
        return 0
    for r in runs:
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r.started_at))
        dur = ""
        if r.finished_at is not None:
            dur = f"  ({r.finished_at - r.started_at:.1f}s)"
        out = r.output_path or ""
        err = f"  err={r.error}" if r.error else ""
        print(f"  {when}  {r.status:<7}{dur}  {out}{err}")
    return 0


def _cmd_tick(args: argparse.Namespace, store: JobsStore, project) -> int:
    """Synchronous one-shot tick — for testing / cron-less environments."""
    from veles.cli import _make_provider, _RUN_TOOLS, DEFAULT_MODEL, _load_skills
    from veles.core.agent import Agent
    from veles.core.job_runner import JobRunner
    from veles.core.memory import SessionStore

    session_store = SessionStore(project.memory_db_path)
    provider_name = getattr(args, "provider", "openrouter")
    model = getattr(args, "model", DEFAULT_MODEL)
    max_iterations = int(getattr(args, "max_iterations", 30))
    max_tokens = int(getattr(args, "max_tokens", 4096))

    def factory(session_id: str | None):
        provider = _make_provider(provider_name)
        registry = _load_skills(project, _RUN_TOOLS, provider=provider, model=model)
        sid = session_id or session_store.create_session()
        return Agent(
            provider=provider,
            registry=registry,
            model=model,
            max_iterations=max_iterations,
            max_tokens=max_tokens,
            store=session_store,
            session_id=sid,
        )

    runner = JobRunner(
        store=store,
        agent_factory=factory,
        output_root=project.jobs_dir,
    )
    try:
        summaries = asyncio.run(runner._tick_once(time.time()))
    finally:
        session_store.close()
    if not summaries:
        print("no due jobs.")
        return 0
    for s in summaries:
        print(f"  {s.job_id}  {s.status}  {s.output_path or s.error or ''}")
    return 0


def _job_to_json(rec) -> dict[str, object]:
    return {
        "id": rec.id,
        "name": rec.name,
        "prompt": rec.prompt,
        "schedule": {
            "kind": rec.schedule.kind,
            "expr": rec.schedule.expr,
            "display": rec.schedule.display(),
        },
        "repeat_times": rec.repeat_times,
        "repeat_completed": rec.repeat_completed,
        "context_from": rec.context_from,
        "deliver_to": rec.deliver_to,
        "enabled": rec.enabled,
        "state": rec.state,
        "created_at": rec.created_at,
        "next_run_at": rec.next_run_at,
        "last_run_at": rec.last_run_at,
        "last_status": rec.last_status,
        "last_error": rec.last_error,
        "last_output_path": rec.last_output_path,
    }
