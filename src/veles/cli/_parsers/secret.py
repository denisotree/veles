"""Parser for `veles secret {set,get,list,delete}`."""

from __future__ import annotations

import argparse


def register(sub: argparse._SubParsersAction) -> None:
    secret = sub.add_parser(
        "secret",
        help="Manage OS-keychain-backed secrets.",
    )
    secret_sub = secret.add_subparsers(dest="secret_command", required=True)

    s_set = secret_sub.add_parser("set", help="Store a secret in the OS keychain.")
    s_set.add_argument("name", help="Secret name (e.g. OPENROUTER_API_KEY).")
    s_set.add_argument(
        "value",
        nargs="?",
        default=None,
        help="Value (omit for interactive prompt or piped stdin).",
    )

    s_get = secret_sub.add_parser("get", help="Look up a secret (env-fallback by default).")
    s_get.add_argument("name", help="Secret name (e.g. OPENROUTER_API_KEY).")
    s_get.add_argument("--reveal", action="store_true", help="Print the value to stdout.")
    s_get.add_argument(
        "--no-env-fallback",
        action="store_true",
        help="Don't fall back to environment variables when not in keychain.",
    )

    secret_sub.add_parser("list", help="Show which canonical secrets are configured.")

    s_del = secret_sub.add_parser("delete", help="Remove a secret from the keychain.")
    s_del.add_argument("name", help="Secret name to remove.")
