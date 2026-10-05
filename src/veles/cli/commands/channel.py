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
from veles.core.channel_setup import resolve_secrets
from veles.core.chat_sessions import SessionMap, channel_session_path
from veles.core.defaults import DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT
from veles.core.platforms import get_platform, list_platforms


def cmd_channel(args: argparse.Namespace) -> int:
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


def _cmd_channel_add(args: argparse.Namespace) -> int:
    """`veles channel add` — wizard to attach a channel to a daemon session."""
    from veles.cli._project import require_project
    from veles.cli.channel_wizard import add_channel

    project = require_project(args)
    if project is None:
        return 2
    return add_channel(
        project,
        session=getattr(args, "session", None),
        channel=getattr(args, "channel", None),
    )


def _cmd_channel_remove(args: argparse.Namespace) -> int:
    """`veles channel remove <channel>` — drop a channel's config block."""
    from veles.cli._project import require_project
    from veles.cli.channel_wizard import remove_channel

    project = require_project(args)
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
        spec = get_platform(channel)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    daemon_url = (
        args.daemon_url
        or os.environ.get("VELES_DAEMON_URL")
        or f"http://{DEFAULT_DAEMON_HOST}:{DEFAULT_DAEMON_PORT}"
    )
    # M271: keychain first (`veles secret set VELES_DAEMON_TOKEN`), env second —
    # before this only the env was read, so a token stored with `veles secret`
    # was never used.
    from veles.core.secrets import get_secret

    daemon_token = args.daemon_token or get_secret("VELES_DAEMON_TOKEN")
    if not daemon_token:
        print(
            "error: --daemon-token or VELES_DAEMON_TOKEN is required\n"
            "       create one via `veles daemon token add <name>`, then store it with\n"
            "       `veles secret set VELES_DAEMON_TOKEN` or export it",
            file=sys.stderr,
        )
        return 2

    # M226: a standalone gateway (talking to a remote daemon over HTTP) still
    # describes incoming images locally, using this project's vision route.
    # `channel` is dispatched before the CLI's own `set_active_project`, so
    # resolve it here — the keychain lookup behind the vision call is
    # project-scoped and needs the ContextVar set.
    from veles.cli._project import _resolve_active_project
    from veles.core.context import set_active_project
    from veles.core.vision import install_vision_adapter

    project = _resolve_active_project(args)
    if project is None:
        print(
            "warning: no Veles project found from this directory — images "
            "sent to this channel won't be described. Run the gateway from "
            "inside a project.",
            file=sys.stderr,
        )
    else:
        set_active_project(project)
        install_vision_adapter(project)

    config = _channel_config(project, channel)
    secrets, missing = resolve_secrets(spec, channel, config, project=project, use_env=True)
    first_secret = next((f for f in spec.cred_fields if f.secret), None)
    if args.bot_token and first_secret is not None:
        secrets[first_secret.key] = args.bot_token
        missing = [k for k in missing if k != first_secret.key]
    if missing:
        hints = ["--bot-token" if first_secret and k == first_secret.key else k for k in missing]
        envs = [f.env for f in spec.cred_fields if f.key in missing and f.env]
        print(
            f"error: {channel} needs {', '.join(missing)} — pass {', '.join(hints)}"
            + (f", set {', '.join(envs)}" if envs else "")
            + f", or store it with `veles channel add {channel}`",
            file=sys.stderr,
        )
        return 2

    return asyncio.run(
        _run_gateway(spec, channel, secrets, config, daemon_url, daemon_token, project)
    )


def _channel_config(project, channel: str) -> dict:
    """The channel's `[channels.<name>]` block, or {} outside a project."""
    if project is None:
        return {}
    from veles.core.project_config import get_section, load_project_config

    return dict(get_section(load_project_config(project), "channels", channel))


async def _run_gateway(
    spec, channel: str, secrets, config, daemon_url: str, daemon_token: str, project
) -> int:
    from veles.core.platforms import ChannelContext

    session_map = SessionMap.load(channel_session_path(channel))
    async with DaemonClient(daemon_url, daemon_token) as client:
        try:
            health = await client.health()
        except DaemonClientError as exc:
            print(f"error: daemon health-check failed: {exc}", file=sys.stderr)
            return 1
        print(
            f"channel: {channel} → daemon {daemon_url} (project: {health.get('project', '?')})",
            file=sys.stderr,
        )
        gateway = spec.build(
            ChannelContext(
                name=channel,
                config=config,
                secrets=secrets,
                backend=client,
                session_map=session_map,
                project=project,
            )
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
