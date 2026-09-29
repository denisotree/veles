"""`tree_sha256` — one content hash for an extension's files.

Used by install (git sources), the module load gate, `verify` and `validate`, so all
four agree on what "the same code" means. Interpreter byte-code and OS litter are
excluded — Python writes `__pycache__/` next to a module on first import, and that
must not look like tampering. Symlinks are rejected: a link to `~/.ssh` inside a
payload would otherwise be copied or hashed as if it were extension code.
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable
from pathlib import Path

_SKIP_NAMES = frozenset({".DS_Store"})
_ROOT_SKIP = frozenset({"extension.toml"})


def is_bytecode(name: str) -> bool:
    """A `__pycache__` dir or `*.pyc` name, in any letter case: on a case-insensitive
    filesystem (macOS APFS) the import system opens `__PYCACHE__/X.PYC` as the
    cache file for `x.py`."""
    folded = name.casefold()
    return folded == "__pycache__" or folded.endswith(".pyc")


def hash_skips(name: str) -> bool:
    """True for a path component `tree_sha256` never looks inside (`.git`, bytecode).
    Content there is unreviewed. What is enforced: an entrypoint may not sit under
    one (`entrypoint_file`), bytecode is stripped before a module loads, and a module
    containing any `.git` is refused (`git_dirs`)."""
    return _is_git(name) or is_bytecode(name)


def _is_git(name: str) -> bool:
    return name.casefold() == ".git"


def git_dirs(root: Path) -> list[Path]:
    """The outermost `.git` entries (any case) under `root`. `.git` is outside the
    hash, and anything in it — a `.py`, or a zip of any name for zipimport — could be
    swapped after approval and reached via `sys.path`, so modules never carry one."""
    return sorted(
        p
        for p in root.rglob("*")
        if _is_git(p.name) and not any(_is_git(x) for x in p.relative_to(root).parts[:-1])
    )


def copy_ignore(*extra: str) -> Callable[[str, list[str]], set[str]]:
    """`shutil.copytree` ignore: drop every hash-skipped name, plus `extra` names."""
    return lambda _dir, names: {n for n in names if hash_skips(n) or n in extra}


def bytecode_paths(root: Path) -> list[Path]:
    """Every `__pycache__/` dir and stray `*.pyc` under `root` — the files the hash
    ignores, so the ones that must never be trusted as reviewed code."""
    return sorted(p for p in root.rglob("*") if is_bytecode(p.name))


def strip_bytecode(root: Path) -> None:
    """Delete all bytecode under `root`. Bytecode sits outside `tree_sha256`, so a
    planted `.pyc` would run instead of the reviewed `.py`; after this, only the
    bytecode Python itself compiles from the hashed source can run."""
    for path in bytecode_paths(root):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


def tree_sha256(root: Path) -> str:
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    entries: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_symlink():
            raise ValueError(f"symlinks are not allowed in an extension: {rel.as_posix()}")
        if any(hash_skips(part) for part in rel.parts):
            continue
        if path.is_dir() or path.name in _SKIP_NAMES:
            continue
        if len(rel.parts) == 1 and rel.name in _ROOT_SKIP:
            continue
        entries.append((rel.as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
    digest = hashlib.sha256()
    for rel_path, file_digest in sorted(entries):
        digest.update(f"{rel_path}\0{file_digest}\n".encode())
    return digest.hexdigest()
