"""Builtin stat_file — cheap fingerprint of a sandboxed path.

Returns a JSON document with `path`, `type`, `size_bytes`, `mtime_iso`,
and `sha256_short` (SHA-256 of the first 1 MiB of the file, hex-encoded
and truncated to 16 chars). Lets the agent ask "what's this file?"
without slurping the contents through `read_file`.

`risk_class=READ_ONLY` ⇒ default allow. Sandboxed via `resolve_safe`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from veles.core.path_guard import resolve_safe
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

_HASH_LIMIT_BYTES = 1 * 1024 * 1024  # 1 MiB
_HASH_HEX_KEEP = 16


@tool(
    risk_class=RiskClass.READ_ONLY,
    side_effects=[],
)
def stat_file(path: str) -> str:
    """Return file metadata as JSON: `{path, type, size_bytes,
    mtime_iso, sha256_short}`.

    `type` is one of `"file"`, `"directory"`, `"symlink"`, `"other"`,
    `"missing"`. `sha256_short` is the leading 16 hex chars of the
    SHA-256 of the first 1 MiB of the file (omitted for non-files).
    """

    resolved = resolve_safe(path)
    if not resolved.exists():
        return json.dumps({"path": str(path), "type": "missing"})
    try:
        stat = resolved.lstat()
    except OSError as exc:
        return json.dumps({"path": str(path), "type": "missing", "error": str(exc)})

    kind = _classify(resolved)
    payload: dict[str, object] = {
        "path": str(path),
        "type": kind,
        "size_bytes": stat.st_size,
        "mtime_iso": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
    }
    if kind == "file":
        payload["sha256_short"] = _hash_prefix(resolved)
    return json.dumps(payload)


def _classify(p: Path) -> str:
    if p.is_symlink():
        return "symlink"
    if p.is_file():
        return "file"
    if p.is_dir():
        return "directory"
    return "other"


def _hash_prefix(p: Path) -> str:
    h = hashlib.sha256()
    try:
        with p.open("rb") as fh:
            h.update(fh.read(_HASH_LIMIT_BYTES))
    except OSError:
        return ""
    return h.hexdigest()[:_HASH_HEX_KEEP]
