"""Parser for `veles browse {modules,skills}`."""

from __future__ import annotations

import argparse


def register(sub: argparse._SubParsersAction) -> None:
    browse = sub.add_parser(
        "browse",
        help="List and search curated module / skill registries.",
    )
    browse_sub = browse.add_subparsers(dest="browse_kind", required=True)
    for kind in ("modules", "skills"):
        sp = browse_sub.add_parser(kind, help=f"Browse the curated {kind} registry.")
        sp.add_argument("query", nargs="?", default="", help="Optional substring filter.")
        sp.add_argument(
            "--source",
            metavar="URL_OR_PATH",
            help="Override the registry source (defaults to canonical URL).",
        )
        sp.add_argument(
            "--json", action="store_true", help="Emit JSON instead of human text."
        )
