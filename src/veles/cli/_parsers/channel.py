"""Parser for `veles channel {list,run,list-sessions,reset-session}`."""

from __future__ import annotations

import argparse


def register(sub: argparse._SubParsersAction) -> None:
    channel = sub.add_parser(
        "channel",
        help="Run an external chat gateway against a Veles daemon.",
    )
    channel_sub = channel.add_subparsers(dest="channel_command", required=True)

    channel_sub.add_parser(
        "list",
        help="List registered channel platforms and persisted session counts.",
    )

    channel_run = channel_sub.add_parser("run", help="Start a channel gateway in the foreground.")
    channel_run.add_argument(
        "--channel",
        default="telegram",
        help="Which channel to run (default: telegram).",
    )
    channel_run.add_argument(
        "--bot-token",
        default=None,
        help="Channel-specific bot token (env: TELEGRAM_BOT_TOKEN).",
    )
    channel_run.add_argument(
        "--daemon-url",
        default=None,
        help="Veles daemon base URL (env: VELES_DAEMON_URL, default http://127.0.0.1:8765).",
    )
    channel_run.add_argument(
        "--daemon-token",
        default=None,
        help="Bearer token for the daemon (env: VELES_DAEMON_TOKEN).",
    )

    channel_list = channel_sub.add_parser(
        "list-sessions", help="List chat_id → session_id mappings for a channel."
    )
    channel_list.add_argument(
        "--channel",
        default="telegram",
        help="Which channel's session map to read.",
    )

    channel_reset = channel_sub.add_parser(
        "reset-session", help="Forget a chat_id mapping so the next message starts fresh."
    )
    channel_reset.add_argument(
        "--channel",
        default="telegram",
        help="Which channel's session map to mutate.",
    )
    channel_reset.add_argument("chat_id", help="External chat id (Telegram chat_id, etc.).")

    # M137: add/remove a channel binding via a wizard (creds → keychain).
    channel_add = channel_sub.add_parser(
        "add", help="Attach a channel to a daemon session (wizard; creds go to the keychain)."
    )
    channel_add.add_argument("--channel", default=None, help="Channel type (asked if omitted).")
    channel_add.add_argument(
        "--session", default=None, help="Named daemon session (default daemon if omitted)."
    )

    channel_remove = channel_sub.add_parser(
        "remove", help="Remove a channel binding from a daemon session's config."
    )
    channel_remove.add_argument("channel", help="Channel type to remove (e.g. telegram).")
    channel_remove.add_argument(
        "--session", default=None, help="Named daemon session (default daemon if omitted)."
    )
