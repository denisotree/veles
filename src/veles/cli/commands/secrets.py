"""`veles secret {set,get,list,delete}` — keychain-backed secret CLI.

M271: a provider API key (`OPENROUTER_API_KEY`, …) is routed to the entry the
runtime actually reads, `veles:<provider>:<scope>` (M92) — the same place the
setup wizard writes. Before this, the command wrote `veles:OPENROUTER_API_KEY`,
which M149 had deliberately stopped reading as a legacy form: `set` reported
success for a key no provider would ever see, and `list` reported a working
wizard-stored key as "(unset)". Every other secret keeps its flat
`veles:<NAME>` entry. The routing table is `PROVIDER_API_KEY_ENVS`, via
`secrets.provider_for_env_name`.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from veles.core.secrets import (
    KeyringUnavailable,
    delete_provider_key,
    delete_secret,
    get_provider_key,
    get_secret,
    list_known_names,
    list_providers_with_keys,
    provider_for_env_name,
    set_provider_key,
    set_secret,
    stored_scopes,
)


def _scope_label(project: str | None) -> str:
    return f"project {project!r}" if project else "default"


def _reject_project_for_plain_secret(args: argparse.Namespace) -> bool:
    """`--project` scopes provider keys only; say so instead of ignoring it."""
    if getattr(args, "project", None):
        print(
            f"error: --project applies to provider API keys only; {args.name} is not one.",
            file=sys.stderr,
        )
        return True
    return False


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
    provider = provider_for_env_name(args.name)
    if provider is None and _reject_project_for_plain_secret(args):
        return 2
    value = args.value
    if value is None:
        # Read from a pipe when stdin isn't a TTY, otherwise prompt
        # without echo. Never let the value land in shell history.
        if sys.stdin.isatty():
            value = getpass.getpass(f"value for {args.name}: ")
        else:
            value = sys.stdin.read().rstrip("\n")
    try:
        if provider is not None:
            set_provider_key(provider, value, project=args.project)
        else:
            set_secret(args.name, value)
    except KeyringUnavailable as exc:
        print(
            f"error: keychain backend unavailable: {exc}\n"
            f"       Falling back: set the env var {args.name} in your shell.",
            file=sys.stderr,
        )
        return 2
    except ValueError as exc:  # set_provider_key refuses an empty key
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if provider is not None:
        print(f"stored {provider} API key ({_scope_label(args.project)})", file=sys.stderr)
    else:
        print(f"stored secret veles:{args.name}", file=sys.stderr)
    return 0


def _get(args: argparse.Namespace) -> int:
    provider = provider_for_env_name(args.name)
    if provider is None and _reject_project_for_plain_secret(args):
        return 2
    if provider is not None:
        value = get_provider_key(
            provider, project=args.project, env_fallback=not args.no_env_fallback
        )
    else:
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


def _sources(name: str) -> str:
    """Where `name` is set, in the order the runtime reads it: keychain, then env.

    A provider key is looked for where the runtime looks (`veles:<provider>:<scope>`),
    and every scope that holds one is named — `keychain (default, myproj)`."""
    provider = provider_for_env_name(name)
    found: list[str] = []
    if provider is not None:
        scopes = stored_scopes(provider)
        if scopes:
            found.append(f"keychain ({', '.join(scopes)})")
    elif get_secret(name, env_fallback=False) is not None:
        found.append("keychain")
    if os.environ.get(name):
        found.append("env")
    return "; ".join(found) or "(unset)"


def _list(args: argparse.Namespace) -> int:
    del args
    rows = [(name, _sources(name)) for name in list_known_names()]
    # Channel credentials (a Telegram bot token, …) share the scoped layout —
    # `channel_wizard` stores them with `set_provider_key(<platform>, …)` — but
    # are not model providers, so they have no env name in the table above.
    from veles.core.provider_factory import PROVIDER_API_KEY_ENVS

    channels = sorted(
        (platform, stored_scopes(platform))
        for platform in list_providers_with_keys()
        if platform not in PROVIDER_API_KEY_ENVS
    )
    width = max(len(r[0]) for r in rows)
    for name, source in rows:
        print(f"  {name:<{width}}  {source}")
    shown = [(p, s) for p, s in channels if s]
    if shown:
        print("channel credentials:")
        for platform, scopes in shown:
            print(f"  {platform:<{width}}  keychain ({', '.join(scopes)})")
    return 0


def _delete(args: argparse.Namespace) -> int:
    provider = provider_for_env_name(args.name)
    if provider is not None:
        scope = _scope_label(args.project)
        if delete_provider_key(provider, project=args.project):
            print(f"deleted {provider} API key ({scope})", file=sys.stderr)
            return 0
        print(f"no {provider} API key stored ({scope})", file=sys.stderr)
        return 1
    if _reject_project_for_plain_secret(args):
        return 2
    if delete_secret(args.name):
        print(f"deleted secret veles:{args.name}", file=sys.stderr)
        return 0
    print(f"no keychain entry for veles:{args.name}", file=sys.stderr)
    return 1
