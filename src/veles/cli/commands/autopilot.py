"""`veles autopilot` (M63) — manage the trust-ladder bypass window.

Subcommands:

    veles autopilot enable --until <duration|iso>
    veles autopilot disable
    veles autopilot status

`enable --until` accepts `+30s`, `+15m`, `+2h`, `+1d` relative
durations, ISO timestamps (`2026-05-12T18:00:00Z`), or raw UNIX
seconds. The state file lives at `~/.veles/autopilot.json`; while the
window is open, `evaluate_trust` short-circuits to allow without
prompting and every dispatch is logged to the active project's
LOG.md as `op="autopilot-<tool>"` for retrospective audit.

Always-confirm operations (M39) — file deletion, network beyond the
chosen LLM, install module/skill, writes outside the active project —
**are not bypassed** by autopilot. They keep their hard-confirm prompt.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
import time

from veles.core.autopilot import (
    activate,
    deactivate,
    format_remaining,
    load_state,
    parse_until,
)


def cmd_autopilot(args: argparse.Namespace) -> int:
    sub = args.autopilot_command
    if sub == "enable":
        return _enable(args)
    if sub == "disable":
        return _disable(args)
    if sub == "status":
        return _status(args)
    print(f"error: unknown autopilot subcommand: {sub!r}", file=sys.stderr)
    return 2


def _enable(args: argparse.Namespace) -> int:
    try:
        enabled_until = parse_until(args.until)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if enabled_until <= time.time():
        print("error: --until must resolve to a future point in time", file=sys.stderr)
        return 2
    activate(enabled_until)
    iso = _dt.datetime.fromtimestamp(enabled_until, tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    remaining = format_remaining(enabled_until - time.time())
    print(f"autopilot enabled until {iso} (in {remaining}).", file=sys.stderr)
    print(
        "trust-ladder prompts are auto-allowed until then; M39 always-confirm "
        "operations remain blocked. Every dispatch is logged to LOG.md.",
        file=sys.stderr,
    )
    return 0


def _disable(args: argparse.Namespace) -> int:
    removed = deactivate()
    if removed:
        print("autopilot disabled.", file=sys.stderr)
        return 0
    print("autopilot was not active.", file=sys.stderr)
    return 0


def _status(args: argparse.Namespace) -> int:
    state = load_state()
    if not state.active:
        if state.enabled_until > 0:
            iso = _dt.datetime.fromtimestamp(state.enabled_until, tz=_dt.UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            print(f"autopilot inactive (last window ended {iso}).")
        else:
            print("autopilot inactive.")
        return 1
    iso = _dt.datetime.fromtimestamp(state.enabled_until, tz=_dt.UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    print(f"autopilot active until {iso} ({format_remaining(state.seconds_remaining)} left).")
    return 0
