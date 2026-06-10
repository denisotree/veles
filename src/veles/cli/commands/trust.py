"""`veles trust` (M63) — non-interactive trust-store management.

Subcommands:

    veles trust list                        — show all grants from both scopes
    veles trust set <tool> [--scope]        — programmatically grant (default: project)
    veles trust revoke <tool> [--scope]     — remove a grant (default: both scopes)
    veles trust clear [--scope all|...]     — wipe all grants in a scope

M38 ships an *interactive* 4-option ladder; M63 adds the headless
counterpart so CI / scripts / `veles autopilot` warm-up can pre-grant
without entering the prompt. Always-confirm operations (M39) are
independent and not influenced by these grants.

Scope rules:

- `--scope project` requires an active Veles project; refuses with rc=2
  if none is resolved.
- `--scope user` mutates `~/.veles/trust.json` regardless of project.
- `--scope all` (clear only) wipes both files.
- For `revoke` the default is "both scopes" so the user can drop a
  grant without remembering where it lives.
"""

from __future__ import annotations

import argparse
import sys

from veles.core.project import Project
from veles.core.trust_store import TrustStore, user_trust_path


def cmd_trust(args: argparse.Namespace, project: Project | None = None) -> int:
    sub = args.trust_command
    if sub == "list":
        return _list(project)
    if sub == "set":
        return _set(args, project)
    if sub == "revoke":
        return _revoke(args, project)
    if sub == "clear":
        return _clear(args, project)
    print(f"error: unknown trust subcommand: {sub!r}", file=sys.stderr)
    return 2


def _list(project: Project | None) -> int:
    user = TrustStore.load(user_trust_path())
    user_tools = sorted(user.tools.items())
    if user_tools:
        print("user-scope grants (~/.veles/trust.json):")
        for name, when in user_tools:
            print(f"  {name:<20}  granted {when}")
    else:
        print("user-scope grants: (none)")
    if project is None:
        print("project-scope grants: (no active project)")
        return 0
    proj = TrustStore.load(project.trust_path)
    proj_tools = sorted(proj.tools.items())
    if proj_tools:
        print(f"project-scope grants ({project.trust_path}):")
        for name, when in proj_tools:
            print(f"  {name:<20}  granted {when}")
    else:
        print("project-scope grants: (none)")
    return 0


def _set(args: argparse.Namespace, project: Project | None) -> int:
    scope = args.scope
    if scope == "project":
        if project is None:
            print(
                "error: --scope project requires an active Veles project",
                file=sys.stderr,
            )
            return 2
        store = TrustStore.load(project.trust_path)
        store.grant(args.tool)
        print(f"granted {args.tool!r} for this project.")
        return 0
    store = TrustStore.load(user_trust_path())
    store.grant(args.tool)
    print(f"granted {args.tool!r} user-wide.")
    return 0


def _revoke(args: argparse.Namespace, project: Project | None) -> int:
    scope = args.scope
    removed_any = False
    if scope in ("user", "both"):
        user = TrustStore.load(user_trust_path())
        if user.revoke(args.tool):
            print(f"revoked {args.tool!r} from user scope.")
            removed_any = True
    if scope in ("project", "both"):
        if project is None and scope == "project":
            print(
                "error: --scope project requires an active Veles project",
                file=sys.stderr,
            )
            return 2
        if project is not None:
            proj = TrustStore.load(project.trust_path)
            if proj.revoke(args.tool):
                print(f"revoked {args.tool!r} from project scope.")
                removed_any = True
    if not removed_any:
        print(f"no grant for {args.tool!r} in {scope} scope.", file=sys.stderr)
        return 1
    return 0


def _clear(args: argparse.Namespace, project: Project | None) -> int:
    scope = args.scope
    cleared_any = False
    if scope in ("user", "all"):
        user = TrustStore.load(user_trust_path())
        if user.tools:
            for name in list(user.tools):
                user.revoke(name)
            print("cleared all user-scope grants.")
            cleared_any = True
    if scope in ("project", "all"):
        if project is None and scope == "project":
            print(
                "error: --scope project requires an active Veles project",
                file=sys.stderr,
            )
            return 2
        if project is not None:
            proj = TrustStore.load(project.trust_path)
            if proj.tools:
                for name in list(proj.tools):
                    proj.revoke(name)
                print("cleared all project-scope grants.")
                cleared_any = True
    if not cleared_any:
        print(f"no grants to clear in {scope} scope.", file=sys.stderr)
        return 1
    return 0
