"""Autopilot window state (M63) — temporary trust-ladder bypass with audit.

VISION §8.4: `veles autopilot --until <ts>` puts the agent into a
time-bounded mode where M38 trust-ladder prompts auto-allow without
the user typing anything. **Always-confirm operations (M39 — delete /
network beyond LLM / install / cross-project write) are NOT bypassed**
— autopilot is for skipping the 4-option ladder, not for skipping
hard-confirm. Every dispatch that uses the autopilot bypass is
logged to the project's `LOG.md` with `op="autopilot-<tool>"` so the
user can audit what the agent did unattended.

State file: `~/.veles/autopilot.json`:

    {"enabled_until": 1747000000.0}

`enabled_until` is a UNIX timestamp. The file is *the* source of truth:
absent file = autopilot off. `is_active()` reads the file on every
call (cheap, file is small) so the daemon / TUI / CLI all see the
same window without cross-process IPC.

Expiry is read-only: `is_active()` returns False once `time.time() >
enabled_until` but doesn't delete the file. `veles autopilot disable`
or a fresh `veles autopilot enable` overwrites it explicitly. Leaving
the stale file behind is intentional — `status` can still print "last
window: ended at <ts>" so the user has continuity.
"""

from __future__ import annotations

import datetime as _dt
import re
import time
from dataclasses import dataclass
from pathlib import Path

_AUTOPILOT_FILENAME = "autopilot.json"

_DURATION_RE = re.compile(r"^\+(\d+)\s*([smhd])$", re.IGNORECASE)
_ISO_FORMATS = ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


@dataclass(frozen=True, slots=True)
class AutopilotState:
    """Resolved view of the autopilot window.

    `active` is the only field tests / production code should branch
    on. `enabled_until` is exposed for `status` output so the user can
    see when the window ends. `seconds_remaining` is negative or zero
    when the window has expired.
    """

    active: bool
    enabled_until: float
    seconds_remaining: float


def autopilot_path() -> Path:
    from veles.core.user_paths import user_home

    return user_home() / _AUTOPILOT_FILENAME


def load_state() -> AutopilotState:
    from veles.core.io_utils import load_optional_json

    empty = AutopilotState(active=False, enabled_until=0.0, seconds_remaining=0.0)
    data = load_optional_json(autopilot_path())
    if not isinstance(data, dict):
        return empty
    raw = data.get("enabled_until")
    if not isinstance(raw, int | float):
        return empty
    enabled_until = float(raw)
    remaining = enabled_until - time.time()
    return AutopilotState(
        active=remaining > 0,
        enabled_until=enabled_until,
        seconds_remaining=remaining,
    )


def is_active() -> bool:
    """Cheap branch-only check used by `core/trust.py::evaluate_trust`."""
    return load_state().active


def activate(enabled_until: float) -> None:
    """Persist a new autopilot window, overwriting any previous state."""
    from veles.core.io_utils import atomic_write_json

    atomic_write_json(autopilot_path(), {"enabled_until": float(enabled_until)})


def deactivate() -> bool:
    """Remove the autopilot state file. Returns True if a file existed."""
    path = autopilot_path()
    if not path.is_file():
        return False
    path.unlink(missing_ok=True)
    return True


def parse_until(raw: str) -> float:
    """Parse a `--until` argument into an absolute UNIX timestamp.

    Accepts:
        - `+<N><unit>` relative durations: `+30s`, `+15m`, `+2h`, `+1d`.
        - ISO 8601 absolute timestamps: `2026-05-12T18:00:00Z`,
          `2026-05-12T18:00:00`, `2026-05-12 18:00:00`, `2026-05-12`.
        - Pure float / int seconds-since-epoch (rare; useful for tests).

    Raises `ValueError` on anything else.
    """
    if not raw:
        raise ValueError("autopilot duration is empty")
    stripped = raw.strip()
    m = _DURATION_RE.match(stripped)
    if m is not None:
        n = int(m.group(1))
        unit = m.group(2).lower()
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86_400}
        return time.time() + n * multipliers[unit]
    try:
        as_number = float(stripped)
    except ValueError:
        pass
    else:
        if as_number > 0:
            return as_number
    for fmt in _ISO_FORMATS:
        try:
            dt = _dt.datetime.strptime(stripped, fmt)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.UTC)
        return dt.timestamp()
    raise ValueError(
        f"autopilot duration {raw!r} not understood; use +30m / +2h / +1d / ISO timestamp"
    )


def format_remaining(seconds: float) -> str:
    """Human-friendly remaining-time string for `veles autopilot status`."""
    if seconds <= 0:
        return "expired"
    seconds = int(seconds)
    days, rem = divmod(seconds, 86_400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)
