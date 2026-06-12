"""`veles daemon token` CRUD + token-store bootstrap (M153 — moved from
`commands/daemon.py`).

The daemon authenticates clients via bearer tokens stored in
`~/.veles/daemon.tokens.json` (`veles.daemon.auth.TokenStore`). This
module owns the `token {add,list,remove}` verb handlers and the
startup-time `_initialise_token_store` (auto-creates a `default` token
on first run). All names remain re-exported from `commands/daemon.py`.
"""

from __future__ import annotations

import argparse
import sys
import time

from veles.daemon.auth import TokenStore, _default_tokens_path


def _initialise_token_store() -> TokenStore:
    """Load `~/.veles/daemon.tokens.json`; if empty, auto-create a
    `default` token and print it to stderr so the user has something
    to paste into client `Authorization: Bearer <…>` headers."""
    store = TokenStore.load()
    if not store.list():
        entry = store.add("default")
        print(
            "warning: no daemon tokens configured. Auto-created token "
            f"'default': {entry.token}\n"
            "         Pass it as `Authorization: Bearer <token>` from clients.",
            file=sys.stderr,
        )
    return store


def _cmd_daemon_token(args: argparse.Namespace) -> int:
    sub = args.daemon_token_command
    store = TokenStore.load()
    if sub == "add":
        return _cmd_daemon_token_add(args, store)
    if sub == "list":
        return _cmd_daemon_token_list(args, store)
    if sub == "remove":
        return _cmd_daemon_token_remove(args, store)
    print(f"error: unknown daemon token subcommand: {sub!r}", file=sys.stderr)
    return 2


def _cmd_daemon_token_add(args: argparse.Namespace, store: TokenStore) -> int:
    try:
        entry = store.add(args.name)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"created token {entry.name}: {entry.token}")
    print(f"stored in {_default_tokens_path()}")
    return 0


def _cmd_daemon_token_list(args: argparse.Namespace, store: TokenStore) -> int:
    entries = store.list()
    if not entries:
        print("no tokens configured.")
        return 0
    for entry in entries:
        masked = entry.token[:6] + "..." + entry.token[-4:]
        when = time.strftime("%Y-%m-%d", time.localtime(entry.created_at))
        print(f"  {entry.name}\t{masked}\t{when}")
    return 0


def _cmd_daemon_token_remove(args: argparse.Namespace, store: TokenStore) -> int:
    if not store.remove(args.name):
        print(f"error: no token named {args.name!r}.", file=sys.stderr)
        return 1
    print(f"removed token {args.name}.")
    return 0
