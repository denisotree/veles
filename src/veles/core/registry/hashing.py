"""`tree_sha256` — one content hash for an extension's files.

Used by install (git sources), the module load gate, `verify` and `validate`, so all
four agree on what "the same code" means. Interpreter byte-code and OS litter are
excluded — Python writes `__pycache__/` next to a module on first import, and that
must not look like tampering. Symlinks are rejected: a link to `~/.ssh` inside a
payload would otherwise be copied or hashed as if it were extension code.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_SKIP_DIRS = frozenset({".git", "__pycache__"})
_SKIP_NAMES = frozenset({".DS_Store"})
_ROOT_SKIP = frozenset({"extension.toml"})


def tree_sha256(root: Path) -> str:
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    entries: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_symlink():
            raise ValueError(f"symlinks are not allowed in an extension: {rel.as_posix()}")
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if path.is_dir() or path.suffix == ".pyc" or path.name in _SKIP_NAMES:
            continue
        if len(rel.parts) == 1 and rel.name in _ROOT_SKIP:
            continue
        entries.append((rel.as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
    digest = hashlib.sha256()
    for rel_path, file_digest in sorted(entries):
        digest.update(f"{rel_path}\0{file_digest}\n".encode())
    return digest.hexdigest()
