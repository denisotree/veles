"""`tree_sha256` — one content hash for an extension's files.

Used by install (git sources), the module load gate, `verify` and `validate`, so all
four agree on what "the same code" means. Only bytecode and `.git` are excluded
(see `hash_skips`) — Python writes `__pycache__/` next to a module on first import,
and that must not look like tampering. Everything else, OS litter included, is
hashed: any unhashed file could be put on `sys.path` and swapped after approval.
Symlinks are rejected: a link to `~/.ssh` inside a
payload would otherwise be copied or hashed as if it were extension code.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections.abc import Callable
from pathlib import Path


def is_bytecode(name: str) -> bool:
    """A `__pycache__` dir or `*.pyc` name, in any letter case: on a case-insensitive
    filesystem (macOS APFS) the import system opens `__PYCACHE__/X.PYC` as the
    cache file for `x.py`."""
    folded = name.casefold()
    return folded == "__pycache__" or folded.endswith(".pyc")


def hash_skips(name: str) -> bool:
    """True for a path component `tree_sha256` never looks inside (`.git`, bytecode).

    Invariant: a path is skipped by the hash only if the gate strips it (bytecode,
    `strip_bytecode`) or refuses the module (`.git`, `git_dirs`). Add a skip here
    only together with gate handling for it. An entrypoint may not sit under a
    skipped component either (`entrypoint_file`)."""
    return _is_git(name) or is_bytecode(name)


def _is_git(name: str) -> bool:
    return name.casefold() == ".git"


def walk_tree(root: Path) -> list[Path]:
    """Every entry under `root`, sorted, not descending into hash-skipped dirs (those
    are stripped or refused whole). Strict, unlike `Path.rglob`, which silently skips
    a dir it cannot list although Python can still import from it: a dir that cannot
    be listed, a symlink, or anything but a regular file or dir raises `ValueError`."""
    out: list[Path] = []
    pending = [root]
    while pending:
        current = pending.pop()
        rel = current.relative_to(root).as_posix()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError as exc:
            raise ValueError(f"cannot list {rel!r} in an extension: {exc.strerror}") from exc
        for entry in entries:
            path = Path(entry.path)
            name = path.relative_to(root).as_posix()
            if entry.is_symlink():
                raise ValueError(f"symlinks are not allowed in an extension: {name}")
            if entry.is_dir(follow_symlinks=False):
                if not hash_skips(entry.name):
                    pending.append(path)
            elif not entry.is_file(follow_symlinks=False):
                raise ValueError(f"not a regular file or directory in an extension: {name}")
            out.append(path)
    return sorted(out)


def git_dirs(root: Path) -> list[Path]:
    """The `.git` entries (any case) under `root`. `.git` is outside the hash, and
    anything in it — a `.py`, or a zip of any name for zipimport — could be swapped
    after approval and reached via `sys.path`, so modules never carry one."""
    return [p for p in walk_tree(root) if _is_git(p.name)]


def copy_ignore(*extra: str) -> Callable[[str, list[str]], set[str]]:
    """`shutil.copytree` ignore: drop every hash-skipped name, plus `extra` names."""
    return lambda _dir, names: {n for n in names if hash_skips(n) or n in extra}


def bytecode_paths(root: Path) -> list[Path]:
    """Every `__pycache__/` dir and stray `*.pyc` under `root` — the files the hash
    ignores, so the ones that must never be trusted as reviewed code."""
    return [p for p in walk_tree(root) if is_bytecode(p.name)]


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
    for path in walk_tree(root):
        if hash_skips(path.name) or path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        entries.append((rel, hashlib.sha256(path.read_bytes()).hexdigest()))
    digest = hashlib.sha256()
    for rel_path, file_digest in sorted(entries):
        digest.update(f"{rel_path}\0{file_digest}\n".encode())
    return digest.hexdigest()
