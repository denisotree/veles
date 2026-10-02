"""`~/.veles/extensions.json` — what was installed where, from which registry, with which hash.

The file lives outside the agent write sandbox, which is the whole security property:
a record doubles as the user's approval of that exact code (the M199 pattern for
self-authored tools, extended to extensions). Keyed by absolute install path.
"""

from __future__ import annotations

import dataclasses
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from veles.core.file_lock import file_lock
from veles.core.io_utils import atomic_write_json, load_optional_json
from veles.core.user_paths import user_home


@dataclass(frozen=True, slots=True)
class InstallRecord:
    name: str
    kind: str
    path: str
    tree_sha256: str
    project: str | None = None
    registry: str | None = None
    group: str = ""
    version: str = ""
    commit: str = ""
    installed_at: str = ""


def _store_path() -> Path:
    return user_home() / "extensions.json"


def load_records() -> list[InstallRecord]:
    empty: list[Any] = []
    raw = load_optional_json(_store_path(), default=empty)
    if not isinstance(raw, list):
        return []
    names = {f.name for f in dataclasses.fields(InstallRecord)}
    out: list[InstallRecord] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(InstallRecord(**{k: v for k, v in item.items() if k in names}))
        except TypeError:
            continue
    return out


def put_record(rec: InstallRecord) -> None:
    with _locked():
        records = [r for r in load_records() if r.path != rec.path]
        records.append(rec)
        _save(records)


def drop_record(path: str) -> bool:
    with _locked():
        records = load_records()
        kept = [r for r in records if r.path != path]
        if len(kept) == len(records):
            return False
        _save(kept)
        return True


def _locked() -> AbstractContextManager[None]:
    """One writer at a time: two installs, or an install and `module approve`, can race."""
    path = _store_path()
    return file_lock(path.parent / (path.name + ".lock"))


def record_for_path(path: str) -> InstallRecord | None:
    return next((r for r in load_records() if r.path == path), None)


def _save(records: list[InstallRecord]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, [asdict(r) for r in records])
