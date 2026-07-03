"""Parser for `veles daemon {start,stop,status,token}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_common_run_flags


def register(sub: argparse._SubParsersAction) -> None:
    daemon = sub.add_parser(
        "daemon",
        help="Run/control the Veles HTTP+WS daemon.",
    )
    daemon_sub = daemon.add_subparsers(dest="daemon_command", required=False)

    daemon_start = daemon_sub.add_parser(
        "start",
        help="Start the daemon (detaches by default; --foreground keeps it attached).",
    )
    # None sentinel (not the literal default) so the runtime can apply the
    # cascade explicit CLI flag > `[daemon(.name)] host/port` in config > the
    # hardcoded 127.0.0.1:8765. See `daemon.py::_resolve_daemon_bind` (M173).
    daemon_start.add_argument("--host", default=None, help="Bind host (default: 127.0.0.1).")
    daemon_start.add_argument("--port", type=int, default=None, help="Bind port (default: 8765).")
    daemon_start.add_argument(
        "--foreground",
        action="store_true",
        help=(
            "Run the daemon attached to the current terminal (no detach). "
            "Use for `systemctl Type=simple`, Docker, or interactive debugging. "
            "Ctrl+C terminates the daemon."
        ),
    )
    add_common_run_flags(daemon_start)
    # Cascade: explicit CLI flag > `[engine]` in <project>/.veles/config.toml
    # > DEFAULT_MODEL/DEFAULT_PROVIDER. None sentinel lets the runtime tell
    # "not given" apart from a string that happens to equal the hardcoded
    # default. See `cli/commands/daemon.py::_factory_settings_from_args`.
    daemon_start.set_defaults(model=None, provider=None)
    # Named daemon session (several per project, each with its own
    # settings/pid/log). Must already exist — declare it with
    # `veles daemon session create <name>`. Absent → legacy single daemon.
    daemon_start.add_argument(
        "--name",
        default=None,
        help="Named daemon session to start (declare it with `daemon session create`).",
    )

    daemon_stop = daemon_sub.add_parser(
        "stop", help="Signal a running daemon to terminate (SIGTERM via pid file)."
    )
    daemon_stop.add_argument("--name", default=None, help="Named daemon session to stop.")
    daemon_status = daemon_sub.add_parser("status", help="Report whether the daemon is running.")
    daemon_status.add_argument("--name", default=None, help="Named daemon session to inspect.")

    # M97: multi-daemon control.
    daemon_sub.add_parser("list", help="List daemons registered across projects.")

    daemon_restart = daemon_sub.add_parser(
        "restart", help="Stop the named daemon and respawn it on the same host/port."
    )
    daemon_restart.add_argument(
        "target", nargs="?", help="Daemon id (slug) or project name (registry path)."
    )
    daemon_restart.add_argument(
        "--name", default=None, help="Named daemon session to restart (this project)."
    )

    daemon_delete = daemon_sub.add_parser(
        "delete", help="Stop the named daemon and remove its registry entry."
    )
    daemon_delete.add_argument("target", help="Daemon id (slug) or project name.")
    daemon_delete.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt (use for scripts/CI).",
    )

    # M135: named daemon sessions (several per project, each with its own
    # settings). Additive — the legacy unnamed daemon above is unchanged.
    daemon_session = daemon_sub.add_parser(
        "session", help="Manage named daemon sessions for this project."
    )
    ds_sub = daemon_session.add_subparsers(dest="daemon_session_command", required=True)

    ds_create = ds_sub.add_parser(
        "create", help="Declare a named daemon session ([daemon.<name>] + registry)."
    )
    ds_create.add_argument("name", help="Session name (e.g. 'api', 'research').")
    ds_create.add_argument("--host", default="127.0.0.1", help="Bind host.")
    ds_create.add_argument(
        "--port", type=int, default=None, help="Bind port (distinct per session)."
    )
    ds_create.add_argument("--model", default=None, help="Pin a model for this session.")
    ds_create.add_argument("--provider", default=None, help="Pin a provider for this session.")
    ds_create.add_argument("--mode", default=None, help="Default agent mode.")

    ds_list = ds_sub.add_parser("list", help="List this project's named daemon sessions.")
    ds_list.add_argument("--all", action="store_true", help="Include soft-deleted sessions.")

    ds_delete = ds_sub.add_parser(
        "delete", help="Soft-delete a named daemon session (kept in DB for history)."
    )
    ds_delete.add_argument("name", help="Session name to delete.")

    daemon_token = daemon_sub.add_parser("token", help="Manage daemon bearer tokens.")
    daemon_token_sub = daemon_token.add_subparsers(dest="daemon_token_command", required=True)

    daemon_token_add = daemon_token_sub.add_parser("add", help="Mint a new token.")
    daemon_token_add.add_argument("name", help="Logical name (e.g. 'tui-client').")

    daemon_token_sub.add_parser("list", help="List existing tokens (masked).")

    daemon_token_remove = daemon_token_sub.add_parser("remove", help="Delete a token by name.")
    daemon_token_remove.add_argument("name", help="Token name to remove.")
