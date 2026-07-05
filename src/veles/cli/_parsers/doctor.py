"""Parser for `veles doctor`."""

from __future__ import annotations

import argparse


def register(sub: argparse._SubParsersAction) -> None:
    doctor = sub.add_parser(
        "doctor",
        help="Run health checks across user-global state and the active project.",
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON instead of human-readable text.",
    )
    doctor.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any warning fires (useful for CI gating).",
    )
    doctor.add_argument(
        "--fix",
        action="store_true",
        help="Attempt safe repairs (currently: rebuild a broken memory recall index).",
    )
