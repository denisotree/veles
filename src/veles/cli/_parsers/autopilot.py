"""Parser for `veles autopilot {enable,disable,status}`."""

from __future__ import annotations

import argparse


def register(sub: argparse._SubParsersAction) -> None:
    autopilot = sub.add_parser(
        "autopilot",
        help="Manage the trust-ladder bypass window.",
    )
    autopilot_sub = autopilot.add_subparsers(dest="autopilot_command", required=True)

    autopilot_enable = autopilot_sub.add_parser(
        "enable", help="Open an autopilot window; trust-ladder prompts auto-allow until then."
    )
    autopilot_enable.add_argument(
        "--until",
        required=True,
        metavar="DUR",
        help="Window end: `+30m` / `+2h` / `+1d` or ISO 8601 like `2026-05-12T18:00:00Z`.",
    )

    autopilot_sub.add_parser("disable", help="Close the autopilot window immediately.")
    autopilot_sub.add_parser("status", help="Report whether autopilot is active.")
