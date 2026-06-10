"""`veles curate` — batch curator entry point (M21 + M28)."""

from __future__ import annotations

import argparse
import datetime as _dt
import sys

from veles.core.project import Project


def cmd_curate(args: argparse.Namespace, project: Project) -> int:
    from veles.cli import (
        _PROVIDER_API_KEY_ENVS,
        _ensure_api_key,
        _run_curator_pass,
    )

    if args.provider in _PROVIDER_API_KEY_ENVS and not _ensure_api_key(args.provider):
        return 2
    result = _run_curator_pass(args, project, max_sessions=args.limit, mode_label="batch")
    if not result.had_candidates:
        iso = _dt.datetime.fromtimestamp(result.starting_cursor, tz=_dt.UTC).isoformat()
        print(f"<no new sessions since {iso}>", file=sys.stderr)
        return 0
    print(f"<curated {result.successes} session(s)>", file=sys.stderr)
    return 0
