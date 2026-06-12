"""Multi-daemon registry (M97).

Tracks every running `veles daemon` instance across projects so the
user can `veles daemon list` / `veles daemon <id> start|stop|restart|
delete` (M97) and the TUI picker (M98) can enumerate them.

Stored at `~/.veles/daemons.json` (override via `VELES_USER_HOME`).
Atomic write via tempfile + rename. The registry is best-effort: a
stale entry (process died, info file gone) is detected via
`is_alive()` and surfaces as `status == "stale"` in `list()`. The
user can `daemon <id> delete` to clear it.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from veles.core.user_paths import user_home

_REGISTRY_FILENAME = "daemons.json"


def registry_path() -> Path:
    return user_home() / _REGISTRY_FILENAME


@dataclass(slots=True)
class DaemonEntry:
    slug: str
    project_path: str
    project_name: str
    pid: int
    host: str
    port: int
    started_at: float
    info_file: str = ""
    token_file: str = ""

    @classmethod
    def from_dict(cls, slug: str, data: dict) -> DaemonEntry:
        return cls(
            slug=slug,
            project_path=str(data.get("project_path", "")),
            project_name=str(data.get("project_name", slug)),
            pid=int(data.get("pid", 0)),
            host=str(data.get("host", "127.0.0.1")),
            port=int(data.get("port", 0)),
            started_at=float(data.get("started_at", 0.0)),
            info_file=str(data.get("info_file", "")),
            token_file=str(data.get("token_file", "")),
        )


@dataclass(slots=True)
class DaemonRegistry:
    entries: dict[str, DaemonEntry] = field(default_factory=dict)

    @classmethod
    def load(cls) -> DaemonRegistry:
        path = registry_path()
        if not path.is_file():
            return cls()
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        daemons = data.get("daemons") or {}
        entries: dict[str, DaemonEntry] = {}
        if isinstance(daemons, dict):
            for slug, raw in daemons.items():
                if not isinstance(raw, dict):
                    continue
                entries[str(slug)] = DaemonEntry.from_dict(str(slug), raw)
        return cls(entries=entries)

    def save(self) -> None:
        path = registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"daemons": {slug: asdict(entry) for slug, entry in self.entries.items()}}
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def list(self) -> list[DaemonEntry]:
        return [self.entries[s] for s in sorted(self.entries.keys())]

    def get(self, slug_or_name: str) -> DaemonEntry | None:
        if slug_or_name in self.entries:
            return self.entries[slug_or_name]
        # Allow lookup by project name as well.
        for entry in self.entries.values():
            if entry.project_name == slug_or_name:
                return entry
        return None

    def upsert(self, entry: DaemonEntry) -> None:
        self.entries[entry.slug] = entry

    def remove(self, slug: str) -> bool:
        return self.entries.pop(slug, None) is not None


# ---------------- helpers ----------------


def is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def status_for(entry: DaemonEntry) -> str:
    """Return one of: 'running', 'stopped' (registry entry kept but the process
    is gone — entries persist after stop until an explicit delete, so a dead pid
    means stopped), 'unknown' (pid zero / no info)."""
    if entry.pid <= 0:
        return "unknown"
    return "running" if is_alive(entry.pid) else "stopped"


def uptime_seconds(entry: DaemonEntry, *, now: float | None = None) -> float:
    if entry.started_at <= 0:
        return 0.0
    return max(0.0, (now if now is not None else time.time()) - entry.started_at)


__all__ = [
    "DaemonEntry",
    "DaemonRegistry",
    "is_alive",
    "registry_path",
    "status_for",
    "uptime_seconds",
]
