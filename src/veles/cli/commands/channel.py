"""`veles channel` (M52) — run a channel gateway against a running daemon.

Subcommands:

    veles channel run --channel telegram
        [--bot-token TOK | env TELEGRAM_BOT_TOKEN]
        [--daemon-url URL | env VELES_DAEMON_URL | http://127.0.0.1:8765]
        [--daemon-token TOK | env VELES_DAEMON_TOKEN]
    veles channel list-sessions --channel telegram
    veles channel reset-session --channel telegram <chat_id>

The runner is a foreground process: Ctrl-C terminates it cleanly. For
production, run it under `systemd` / `tmux` / a process supervisor —
the same way you'd run `veles daemon start`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

from veles.channels.daemon_client import DaemonClient, DaemonClientError
from veles.channels.platform_registry import (
    ensure_builtins_registered,
    get_platform,
    list_platforms,
)
from veles.channels.session_map import SessionMap, channel_session_path


def cmd_channel(args: argparse.Namespace) -> int:
    ensure_builtins_registered()
    sub = args.channel_command
    if sub == "run":
        return _cmd_channel_run(args)
    if sub == "list-sessions":
        return _cmd_channel_list_sessions(args)
    if sub == "reset-session":
        return _cmd_channel_reset_session(args)
    if sub == "list":
        return _cmd_channel_list(args)
    if sub == "add":
        return _cmd_channel_add(args)
    if sub == "remove":
        return _cmd_channel_remove(args)
    print(f"error: unknown channel subcommand: {sub!r}", file=sys.stderr)
    return 2


def _resolve_project_or_error():
    from veles.cli import _resolve_active_project

    project = _resolve_active_project(argparse.Namespace())
    if project is None:
        print(
            "error: no Veles project found here. Run `veles init` first.",
            file=sys.stderr,
        )
    return project


def _cmd_channel_add(args: argparse.Namespace) -> int:
    """`veles channel add` — wizard to attach a channel to a daemon session."""
    from veles.cli.channel_wizard import add_channel

    project = _resolve_project_or_error()
    if project is None:
        return 2
    return add_channel(
        project,
        session=getattr(args, "session", None),
        channel=getattr(args, "channel", None),
    )


def _cmd_channel_remove(args: argparse.Namespace) -> int:
    """`veles channel remove <channel>` — drop a channel's config block."""
    from veles.cli.channel_wizard import remove_channel

    project = _resolve_project_or_error()
    if project is None:
        return 2
    return remove_channel(project, args.channel, session=getattr(args, "session", None))


def _cmd_channel_list(_args: argparse.Namespace) -> int:
    """`veles channel list` — show registered platforms + their session counts."""
    platforms = list_platforms()
    if not platforms:
        print("no channel platforms registered.")
        return 0
    for name in platforms:
        path = channel_session_path(name)
        count = 0
        if path.is_file():
            count = len(SessionMap.load(path).list())
        print(f"  {name}\tsessions: {count}\tmap: {path}")
    return 0


# ---- run ----


def _cmd_channel_run(args: argparse.Namespace) -> int:
    channel = args.channel
    try:
        entry = get_platform(channel)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Telegram is the only built-in M52 channel; honour its bot-token contract
    # explicitly. Other platforms (registered via plugins) handle their own
    # flag parsing inside their factories.
    if channel == "telegram":
        bot_token = args.bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            print(
                "error: --bot-token or TELEGRAM_BOT_TOKEN env var is required",
                file=sys.stderr,
            )
            return 2
    else:
        bot_token = args.bot_token or os.environ.get("TELEGRAM_BOT_TOKEN") or ""

    daemon_url = args.daemon_url or os.environ.get("VELES_DAEMON_URL") or "http://127.0.0.1:8765"
    daemon_token = args.daemon_token or os.environ.get("VELES_DAEMON_TOKEN")
    if not daemon_token:
        print(
            "error: --daemon-token or VELES_DAEMON_TOKEN env var is required\n"
            "       create one via `veles daemon token add <name>`",
            file=sys.stderr,
        )
        return 2

    return asyncio.run(_run_gateway(entry.factory, channel, bot_token, daemon_url, daemon_token))


async def _run_gateway(
    factory, channel: str, bot_token: str, daemon_url: str, daemon_token: str
) -> int:
    session_map = SessionMap.load(channel_session_path(channel))
    async with DaemonClient(daemon_url, daemon_token) as client:
        try:
            health = await client.health()
        except DaemonClientError as exc:
            print(f"error: daemon health-check failed: {exc}", file=sys.stderr)
            return 1
        project = health.get("project", "?")
        print(
            f"channel: {channel} → daemon {daemon_url} (project: {project})",
            file=sys.stderr,
        )
        gateway = factory(
            bot_token=bot_token,
            daemon_client=client,
            session_map=session_map,
        )
        try:
            await gateway.start()
        except KeyboardInterrupt:
            await gateway.stop()
    return 0


# ---- list-sessions / reset-session ----


def _cmd_channel_list_sessions(args: argparse.Namespace) -> int:
    channel = args.channel
    session_map = SessionMap.load(channel_session_path(channel))
    entries = session_map.list()
    if not entries:
        print(f"no sessions tracked for channel {channel!r}.")
        return 0
    for chat_id, sid, last in entries:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(last))
        print(f"  {chat_id}\t{sid}\t{when}")
    return 0


def _cmd_channel_reset_session(args: argparse.Namespace) -> int:
    channel = args.channel
    session_map = SessionMap.load(channel_session_path(channel))
    if not session_map.reset(args.chat_id):
        print(f"error: no session for chat_id {args.chat_id!r}", file=sys.stderr)
        return 1
    print(f"forgot session for chat_id {args.chat_id}.")
    return 0
