"""`veles secret {set,get,list,delete}` — keychain-backed secret CLI."""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from veles.core.secrets import (
    KeyringUnavailable,
    delete_secret,
    get_secret,
    list_known_names,
    set_secret,
)


def cmd_secret(args: argparse.Namespace) -> int:
    verb = args.secret_command
    if verb == "set":
        return _set(args)
    if verb == "get":
        return _get(args)
    if verb == "list":
        return _list(args)
    if verb == "delete":
        return _delete(args)
    print(f"unknown secret verb: {verb!r}", file=sys.stderr)
    return 2


def _set(args: argparse.Namespace) -> int:
    value = args.value
    if value is None:
        # Read from a pipe when stdin isn't a TTY, otherwise prompt
        # without echo. Never let the value land in shell history.
        if sys.stdin.isatty():
            value = getpass.getpass(f"value for {args.name}: ")
        else:
            value = sys.stdin.read().rstrip("\n")
    try:
        set_secret(args.name, value)
    except KeyringUnavailable as exc:
        print(
            f"error: keychain backend unavailable: {exc}\n"
            f"       Falling back: set the env var {args.name} in your shell.",
            file=sys.stderr,
        )
        return 2
    print(f"stored secret veles:{args.name}", file=sys.stderr)
    return 0


def _get(args: argparse.Namespace) -> int:
    value = get_secret(args.name, env_fallback=not args.no_env_fallback)
    if value is None:
        print(f"(unset) {args.name}", file=sys.stderr)
        return 1
    # No echo to stdout for safety — print only the value when explicitly
    # asked via `--reveal`. Default is just a confirmation.
    if args.reveal:
        print(value)
    else:
        print(f"{args.name} is set (use --reveal to print the value)", file=sys.stderr)
    return 0


def _list(args: argparse.Namespace) -> int:
    del args
    rows = []
    for name in list_known_names():
        in_keyring = get_secret(name, env_fallback=False)
        in_env = os.environ.get(name)
        if in_keyring is not None:
            source = "keychain"
        elif in_env is not None:
            source = "env"
        else:
            source = "(unset)"
        rows.append((name, source))
    width = max(len(r[0]) for r in rows)
    for name, source in rows:
        print(f"  {name:<{width}}  {source}")
    return 0


def _delete(args: argparse.Namespace) -> int:
    if delete_secret(args.name):
        print(f"deleted secret veles:{args.name}", file=sys.stderr)
        return 0
    print(f"no keychain entry for veles:{args.name}", file=sys.stderr)
    return 1
