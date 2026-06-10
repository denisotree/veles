"""`veles browse {modules,skills} [<query>]` — surface curated registry (M54)."""

from __future__ import annotations

import argparse
import sys

from veles.core.registry_browser import (
    RegistryFetchError,
    load_registry,
    registry_url,
    search,
)


def cmd_browse(args: argparse.Namespace) -> int:
    kind = args.browse_kind  # "modules" | "skills"
    source = getattr(args, "source", None) or registry_url(kind)
    try:
        entries = load_registry(source)
    except RegistryFetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    results = search(entries, getattr(args, "query", "") or "")
    if not results:
        print(f"(no {kind} match {args.query!r})", file=sys.stderr)
        return 0
    if getattr(args, "json", False):
        import json
        from dataclasses import asdict

        print(json.dumps([asdict(e) for e in results], ensure_ascii=False, indent=2))
        return 0
    for e in results:
        flag = "REVIEWED" if e.reviewed else "UNREVIEWED"
        head = f"{e.name}  ({e.version})  [{flag}]"
        print(head)
        if e.description:
            print(f"  {e.description}")
        print(f"  {e.repo_url}")
        if e.tags:
            print(f"  tags: {', '.join(e.tags)}")
        if not e.reviewed:
            print(
                "  warning: this entry is not in the curated registry — "
                "review the repo before installing.",
                file=sys.stderr,
            )
        print()
    return 0
