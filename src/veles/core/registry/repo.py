"""Local git clones of connected registries under `~/.veles/registries/<name>/`.

Everything network-facing is the system `git`, so private registries work with
whatever the user already has (SSH keys, `gh auth setup-git`). The cache lives
outside the agent sandbox; a clone that fails midway is removed so a half-cloned
directory is never read as a registry.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from veles.core.registry.config import RegistrySource, cache_dir
from veles.core.registry.model import Source

_GIT_TIMEOUT_S = 300


class RegistryRepoError(RuntimeError):
    pass


def ensure_cache(source: RegistrySource) -> Path:
    """Clone once, atomically: `path` only ever exists complete or not at all.

    Cloning into a sibling staging dir and renaming it into place on success
    means a kill/Ctrl+C mid-clone (or a crash) can never leave a half-cloned
    directory at `path` for the next run to mistake for a real cache."""
    path = cache_dir(source.name)
    if (path / ".git").is_dir():
        return path
    staging = path.with_name(f".{path.name}.cloning")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(path, ignore_errors=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    args = ["clone", "--quiet", "--filter=blob:none"]
    if source.ref:
        args += ["--branch", source.ref]
    try:
        _git(*args, "--", source.url, str(staging))
        staging.rename(path)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return path


def update(source: RegistrySource) -> str:
    """Fetch and move the clone to the remote tip; returns the new HEAD."""
    path = ensure_cache(source)
    _git("fetch", "--quiet", "--prune", "origin", cwd=path)
    target = f"origin/{source.ref}" if source.ref else "origin/HEAD"
    _git("reset", "--quiet", "--hard", target, cwd=path)
    return head_commit(path)


def head_commit(repo: Path) -> str:
    return _git("rev-parse", "HEAD", cwd=repo).strip()


def fetched_at(repo: Path) -> float:
    """mtime of the last fetch (or of the clone when never fetched)."""
    marker = repo / ".git" / "FETCH_HEAD"
    return (marker if marker.exists() else repo / ".git").stat().st_mtime


def diff_stat(repo: Path, old: str, new: str, relpath: str) -> str:
    return _git("diff", "--stat", old, new, "--", relpath, cwd=repo).strip()


def fetch_git_source(src: Source, dest: Path) -> None:
    """Clone `src.url`, check out the pinned commit and copy `src.subdir` to `dest`."""
    assert src.url is not None and src.commit is not None
    work = dest.parent / f".fetch-{dest.name}"
    shutil.rmtree(work, ignore_errors=True)
    try:
        _git("clone", "--quiet", "--filter=blob:none", "--no-checkout", "--", src.url, str(work))
        _git("checkout", "--quiet", src.commit, cwd=work)
        work_real = work.resolve()
        payload = (work / src.subdir).resolve() if src.subdir else work_real
        if not payload.is_relative_to(work_real):
            raise RegistryRepoError(f"subdir {src.subdir!r} escapes the repository")
        if not payload.is_dir():
            raise RegistryRepoError(f"subdir {src.subdir!r} not found at {src.commit}")
        shutil.copytree(payload, dest, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _git(*args: str, cwd: Path | None = None) -> str:
    if shutil.which("git") is None:
        raise RegistryRepoError("git executable not found in PATH")
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RegistryRepoError(f"git {args[0]} timed out after {_GIT_TIMEOUT_S}s") from exc
    if result.returncode != 0:
        raise RegistryRepoError(result.stderr.strip() or f"git {args[0]} failed")
    return result.stdout
