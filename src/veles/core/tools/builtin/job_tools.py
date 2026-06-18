"""Recurring scheduled-job tools (M167b).

Lets the bot schedule recurring autonomous actions from chat — a monitoring
check, a daily digest. Distinct from `task_add`, which is a ONE-SHOT personal
reminder: use `job_add` for anything recurring ("каждый день", "по будням",
"every 2h"); use `task_add` for a single "remind me at 18:00".

`job_add` is SENSITIVE: creating a recurring run that executes a prompt with
full tools (shell, DB, external delivery) unattended is high-privilege, so it
goes through the trust ladder — the user confirms in the channel before the
job is scheduled.
"""

from __future__ import annotations

import datetime as _dt

from veles.core.context import current_origin, current_project
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool


def _store(project):
    from veles.core.jobs_store import JobsStore

    return JobsStore(project.memory_db_path)


def _fmt_local(ts: float, project) -> str:
    from veles.core.job_schedule import resolve_schedule_tz

    return _dt.datetime.fromtimestamp(ts, resolve_schedule_tz(project)).strftime(
        "%Y-%m-%d %H:%M %Z"
    )


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, sensitive=True, side_effects=["filesystem"])
def job_add(name: str, prompt: str, schedule: str, deliver_to: str = "") -> str:
    """Schedule a RECURRING job: run `prompt` on `schedule` and deliver the result.

    Use this for anything recurring — a daily digest, a periodic monitoring
    check. For a single one-shot reminder use `task_add` instead.

    `schedule` is a human form (NOT cron — translate the user's words into it):
      `daily@09:00` · `weekdays@18:00` · `weekend@10:00` · `weekly:mon,fri@09:00`
      · `every:2h` · `30m` · `once:2026-07-01 18:00`
    Times are in the project's timezone. `deliver_to` (`telegram:<chat>`)
    defaults to the chat this request came from — leave it empty for that.

    This schedules an autonomous run with full tools; the user is asked to
    confirm before it is created. Returns the new job id.
    """
    project = current_project()
    if project is None:
        return "<error: no active project>"
    if not name.strip() or not prompt.strip():
        return "<error: name and prompt are both required>"

    from veles.core.job_schedule import parse_schedule, resolve_schedule_tz

    try:
        parse_schedule(schedule)  # validate early with a friendly message
    except ValueError as exc:
        return f"<error: {exc}>"

    target = deliver_to.strip() or current_origin()
    store = _store(project)
    try:
        rec = store.add_job(
            name=name.strip(),
            prompt=prompt.strip(),
            schedule_expr=schedule.strip(),
            deliver_to=target,
            tz=resolve_schedule_tz(project),
        )
    except ValueError as exc:
        return f"<error: {exc}>"
    finally:
        store.close()

    tail = f" → {target}" if target else " (no delivery target — result only saved to file)"
    return (
        f"scheduled job {rec.id}: {rec.name} [{rec.schedule.display()}], "
        f"next {_fmt_local(rec.next_run_at, project)}{tail}"
    )


@tool(risk_class=RiskClass.READ_ONLY, side_effects=[])
def job_list() -> str:
    """List the scheduled jobs (id, name, schedule, next run)."""
    project = current_project()
    if project is None:
        return "<error: no active project>"
    store = _store(project)
    try:
        jobs = store.list_jobs(include_disabled=True)
    finally:
        store.close()
    if not jobs:
        return "(no scheduled jobs)"
    lines = ["# Scheduled jobs"]
    for j in jobs:
        state = "" if (j.enabled and j.state == "scheduled") else f" ({j.state})"
        lines.append(
            f"- `{j.id}` {j.name} — {j.schedule.display()} — "
            f"next {_fmt_local(j.next_run_at, project)}{state}"
        )
    return "\n".join(lines)


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["filesystem"])
def job_remove(job_id: str) -> str:
    """Remove (unschedule) a job by its id (from `job_list`)."""
    project = current_project()
    if project is None:
        return "<error: no active project>"
    store = _store(project)
    try:
        ok = store.delete_job(job_id.strip())
    finally:
        store.close()
    return f"removed job {job_id}" if ok else f"<error: no job {job_id!r}>"
