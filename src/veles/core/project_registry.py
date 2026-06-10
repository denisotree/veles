"""Global multi-project registry — slug → absolute path + last-active timestamp.

TASK.md #2.4 + PLAN.md §5: Veles must hold several projects in a single
agent loop. Per-cwd discovery (M3) only finds the project containing
`cwd`; this registry adds a global directory of known projects so the
user can `veles project list`, `veles project switch <slug>`, or
`/project <slug> ...` mid-prompt to operate on any tracked project
without `cd`.

File layout: `~/.veles/projects/registry.json` (overridable via
`VELES_REGISTRY_PATH` env). Single JSON document; atomic writes via
tempfile + `os.replace`. No file lock — the registry is touched once
per command (auto-touch on `init` / `run`), so contention is rare and
losing a single `last_active_at` bump is acceptable.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from veles.core.project import Project
from veles.core.wiki import _normalize_slug

_DEFAULT_REGISTRY_REL = ".veles/projects/registry.json"
_REGISTRY_VERSION = 1


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    slug: str
    path: str
    name: str
    last_active_at: float


def default_registry_path() -> Path:
    """Resolve the registry path. `VELES_REGISTRY_PATH` overrides for tests."""
    override = os.environ.get("VELES_REGISTRY_PATH")
    if override:
        return Path(override)
    return Path.home() / _DEFAULT_REGISTRY_REL


class Registry:
    """In-memory view of the registry file, with atomic save-back.

    Construct via `Registry.load(path=None)` — missing/corrupt files
    yield an empty registry without raising; the caller decides whether
    to call `save()` to materialise the empty doc.
    """

    def __init__(self, path: Path, entries: dict[str, RegistryEntry]) -> None:
        self._path = path
        self._entries = entries

    @classmethod
    def load(cls, path: Path | None = None) -> Registry:
        path = path or default_registry_path()
        if not path.is_file():
            return cls(path, {})
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(path, {})
        raw = data.get("projects") if isinstance(data, dict) else None
        if not isinstance(raw, dict):
            return cls(path, {})
        entries: dict[str, RegistryEntry] = {}
        for slug, payload in raw.items():
            if not isinstance(payload, dict):
                continue
            try:
                entries[str(slug)] = RegistryEntry(
                    slug=str(slug),
                    path=str(payload["path"]),
                    name=str(payload.get("name") or slug),
                    last_active_at=float(payload.get("last_active_at") or 0.0),
                )
            except (KeyError, ValueError, TypeError):
                continue
        return cls(path, entries)

    def get(self, slug: str) -> RegistryEntry | None:
        return self._entries.get(slug)

    def list_entries(self) -> list[RegistryEntry]:
        """Return entries sorted by most-recent first."""
        return sorted(self._entries.values(), key=lambda e: e.last_active_at, reverse=True)

    def add(self, project: Project, *, slug: str | None = None) -> RegistryEntry:
        """Insert or update an entry from a `Project`. Returns the new entry."""
        resolved_slug = slug or _normalize_slug(project.name) or project.root.name
        entry = RegistryEntry(
            slug=resolved_slug,
            path=str(project.root.resolve()),
            name=project.name,
            last_active_at=time.time(),
        )
        self._entries[resolved_slug] = entry
        return entry

    def remove(self, slug: str) -> RegistryEntry:
        """Remove and return the entry. Raises KeyError if absent."""
        return self._entries.pop(slug)

    def touch(self, slug: str) -> RegistryEntry | None:
        """Bump `last_active_at` for `slug`. Returns the new entry or None."""
        existing = self._entries.get(slug)
        if existing is None:
            return None
        bumped = RegistryEntry(
            slug=existing.slug,
            path=existing.path,
            name=existing.name,
            last_active_at=time.time(),
        )
        self._entries[slug] = bumped
        return bumped

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _REGISTRY_VERSION,
            "projects": {slug: asdict(e) for slug, e in self._entries.items()},
        }
        fd, tmp = tempfile.mkstemp(prefix=".registry-", dir=self._path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            os.replace(tmp, self._path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    @property
    def path(self) -> Path:
        return self._path
