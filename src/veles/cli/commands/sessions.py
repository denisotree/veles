"""`veles sessions` — list / show / delete saved sessions."""

from __future__ import annotations

import argparse
import datetime as _dt
import sys

from veles.core.memory import SessionInfo, SessionStore
from veles.core.project import Project
from veles.core.provider import Message


def cmd_sessions(args: argparse.Namespace, project: Project) -> int:
    with SessionStore(project.memory_db_path) as store:
        if args.sessions_command == "list":
            return _list(store, args.limit)
        if args.sessions_command == "show":
            return _show(store, args.session_id)
        if args.sessions_command == "delete":
            return _delete(store, args.session_id)
        if args.sessions_command == "search":
            return _search(store, args)
    return 2


def _list(store: SessionStore, limit: int) -> int:
    items = store.list_sessions(limit=limit)
    if not items:
        print("(no sessions)")
        return 0
    print(f"{'id':<19}  {'last_activity':<19}  {'turns':>5}  title")
    for s in items:
        print(_fmt_session_row(s))
    return 0


def _show(store: SessionStore, session_id: str) -> int:
    info = store.get_session(session_id)
    if info is None:
        print(f"error: session {session_id} not found", file=sys.stderr)
        return 1
    msgs = store.load_messages(session_id)
    print(f"# session {session_id}  ({info.turn_count} turns)")
    if info.title:
        print(f"# title: {info.title}")
    print()
    for m in msgs:
        _print_message(m)
    return 0


def _delete(store: SessionStore, session_id: str) -> int:
    ok = store.delete_session(session_id)
    if not ok:
        print(f"error: session {session_id} not found", file=sys.stderr)
        return 1
    print(f"deleted {session_id}")
    return 0


def _search(store: SessionStore, args: argparse.Namespace) -> int:
    role_filter = _resolve_role_filter(getattr(args, "role", "both"))
    since = _resolve_since(getattr(args, "since", None))
    hits = store.search_turns(
        args.query,
        limit=args.limit,
        role_filter=role_filter,
        since=since,
    )
    if not hits:
        print("(no matches)")
        return 0
    print(f"{'session_id':<19}  {'seq':>4}  role       when              content")
    for h in hits:
        when = _dt.datetime.fromtimestamp(h.created_at).strftime("%Y-%m-%d %H:%M")
        snippet = (h.content or "").replace("\n", " ")[:80]
        print(f"{h.session_id}  {h.seq:>4}  {h.role:<9}  {when}  {snippet}")
    return 0


def _resolve_role_filter(spec: str) -> tuple[str, ...] | None:
    if spec == "all":
        return None
    if spec == "user":
        return ("user",)
    if spec == "assistant":
        return ("assistant",)
    return ("user", "assistant")


def _resolve_since(raw: str | None) -> float | None:
    if not raw:
        return None
    # Accept the same `+1d`-style duration parser as M63 autopilot for consistency.
    from veles.core.autopilot import parse_until

    try:
        # `parse_until` returns an absolute future timestamp; for `since` we
        # negate the offset: `--since 7d` means "last 7 days", not "in 7 days".
        # parse_until expects `+7d`; strip a leading `-` or normalise bare `7d`.
        normalised = raw.strip()
        if normalised.startswith("-"):
            normalised = "+" + normalised[1:]
        elif not normalised.startswith("+"):
            normalised = "+" + normalised
        future = parse_until(normalised)
        import time as _t

        delta = future - _t.time()
        return _t.time() - delta
    except ValueError:
        return None


def _fmt_session_row(info: SessionInfo) -> str:
    ts = _dt.datetime.fromtimestamp(info.last_activity_at).strftime("%Y-%m-%d %H:%M:%S")
    title = info.title or ""
    return f"{info.id}  {ts}  {info.turn_count:>5}  {title}"


def _print_message(m: Message) -> None:
    label = f"[{m.role}"
    if m.tool_call_id:
        label += f" call={m.tool_call_id}"
    label += "]"
    body = m.content if m.content is not None else ""
    print(f"{label}\n{body}")
    for tc in m.tool_calls:
        print(f"  -> tool_call {tc.name}({tc.arguments})  id={tc.id}")
    print()
