"""Personal task / reminder tools (M166).

Let the agent manage the user's personal tasks on their behalf: add a todo
(optionally with a reminder time), list open tasks, mark done, snooze. Rows
live in the project `memory.db` via `TasksStore`; the daemon's
`ReminderRunner` delivers due reminders to the task's `deliver_to` channel.

`deliver_to` defaults to the originating chat (`current_origin()`) so a
"remind me at 18:00" in Telegram reminds *that* chat without the model
needing to know the chat id. Reminders only fire under a running daemon — a
task added in a one-shot `veles run` is recorded but nothing sweeps it.
"""

from __future__ import annotations

import datetime as _dt
import time

from veles.core.context import current_origin, current_project
from veles.core.risk import RiskClass
from veles.core.tasks_store import TasksStore
from veles.core.tools.registry import tool

# Models routinely miscompute "tomorrow" (wrong year/month) — a due time this
# far in the past is a calendar error, not a deliberately-immediate reminder.
_PAST_GRACE_SECONDS = 120.0


def _fmt(ts: float | None) -> str:
    if ts is None:
        return "—"
    return _dt.datetime.fromtimestamp(ts, tz=_dt.UTC).strftime("%Y-%m-%d %H:%M UTC")


def _parse_when(raw: str) -> float:
    """Parse a due/snooze time. Accepts `+2h` / `+1d` relative durations, ISO
    timestamps, or epoch seconds. Raises ValueError on anything else."""
    from veles.core.autopilot import parse_until

    return parse_until(raw)


def _past_error(raw: str, due_ts: float) -> str | None:
    """Error text if `due_ts` is in the past, echoing the current time so the
    model can recompute; None if the time is fine."""
    now = time.time()
    if due_ts < now - _PAST_GRACE_SECONDS:
        return (
            f"<error: {raw!r} resolves to {_fmt(due_ts)}, which is in the past — "
            f"the current time is {_fmt(now)}; recompute the intended date>"
        )
    return None


def _resolve_target(spec: str) -> tuple[str | None, str | None]:
    """Resolve an explicit `deliver_to` into a stored target.

    Returns `(target, error)`. `origin` is resolved to the concrete originating
    chat at write time (the sweep loop has no request context to resolve it
    later). Anything failing the router grammar is rejected loudly so the
    model corrects itself now, not silently at delivery time."""
    from veles.channels.delivery import DeliveryTarget

    try:
        parsed = DeliveryTarget.parse(spec)
    except ValueError:
        return None, (
            f"<error: deliver_to {spec!r} is not a valid delivery target; use "
            "'<platform>:<chat_id>' (e.g. 'telegram:42'), 'origin', or 'local' — "
            "or leave it empty to deliver to the chat this request came from>"
        )
    if parsed.kind == "origin":
        return current_origin(), None
    return spec, None


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["filesystem"])
def task_add(title: str, due_at: str = "", body: str = "", deliver_to: str = "") -> str:
    """Add a personal task, optionally with a reminder.

    `due_at` (optional) is when to remind — a relative duration (`+2h`, `+1d`,
    `+30m`), an ISO timestamp (`2026-06-18T18:00:00Z`), or empty for a todo
    with no reminder. `deliver_to` (optional) is where the reminder is sent
    (`telegram:<chat_id>`); leave it empty to default to the chat this request
    came from. `body` is optional extra context.

    The reminder fires once when `due_at` passes, only while a daemon is
    running. Returns the new task id.
    """
    project = current_project()
    if project is None:
        return "<error: no active project>"
    if not title.strip():
        return "<error: task title must be non-empty>"

    due_ts: float | None = None
    if due_at.strip():
        try:
            due_ts = _parse_when(due_at.strip())
        except ValueError:
            return f"<error: due_at {due_at!r} not understood; use +2h / +1d / ISO timestamp>"
        if err := _past_error(due_at.strip(), due_ts):
            return err

    if deliver_to.strip():
        target, err = _resolve_target(deliver_to.strip())
        if err:
            return err
    else:
        target = current_origin()
    store = TasksStore(project.memory_db_path)
    try:
        rec = store.add_task(
            title=title.strip(),
            body=body.strip() or None,
            due_at=due_ts,
            deliver_to=target,
        )
    finally:
        store.close()

    if due_ts and target:
        tail = f"; reminder {_fmt(due_ts)} → {target}"
    elif due_ts:
        tail = f"; due {_fmt(due_ts)} (no delivery target — won't push)"
    else:
        tail = " (no reminder)"
    return f"added task {rec.id}: {rec.title}{tail}"


@tool(risk_class=RiskClass.READ_ONLY, side_effects=[])
def task_list(state: str = "open") -> str:
    """List the user's tasks. `state` is 'open' (default), 'done', or 'all'.

    Returns a markdown list with id, title, and reminder time."""
    project = current_project()
    if project is None:
        return "<error: no active project>"
    wanted = None if state == "all" else state
    store = TasksStore(project.memory_db_path)
    try:
        tasks = store.list_tasks(state=wanted)
    finally:
        store.close()
    if not tasks:
        return f"(no {state} tasks)"
    lines = [f"# Tasks ({state})"]
    for t in tasks:
        due = f" — {_fmt(t.due_at)}" if t.due_at else ""
        mark = "x" if t.state == "done" else " "
        lines.append(f"- [{mark}] `{t.id}` {t.title}{due}")
    return "\n".join(lines)


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["filesystem"])
def task_done(task_id: str) -> str:
    """Mark a task done by its id (from `task_list`)."""
    project = current_project()
    if project is None:
        return "<error: no active project>"
    store = TasksStore(project.memory_db_path)
    try:
        ok = store.mark_done(task_id.strip())
    finally:
        store.close()
    return f"task {task_id} marked done" if ok else f"<error: no task {task_id!r}>"


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["filesystem"])
def task_snooze(task_id: str, until: str) -> str:
    """Reschedule a task's reminder to `until` (a `+2h`/`+1d` duration or ISO
    timestamp). Re-arms the reminder even if it already fired."""
    project = current_project()
    if project is None:
        return "<error: no active project>"
    try:
        due_ts = _parse_when(until.strip())
    except ValueError:
        return f"<error: until {until!r} not understood; use +2h / +1d / ISO timestamp>"
    if err := _past_error(until.strip(), due_ts):
        return err
    store = TasksStore(project.memory_db_path)
    try:
        ok = store.snooze(task_id.strip(), due_at=due_ts)
    finally:
        store.close()
    return f"task {task_id} snoozed to {_fmt(due_ts)}" if ok else f"<error: no task {task_id!r}>"
