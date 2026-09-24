"""Install a directory from a git URL or a local path, rolling back on failure.

Shared by skill and module installation: both clone or copy a source into a
target directory, validate what arrived, and delete the target if anything
went wrong. What counts as valid differs, so it is the caller's `validate`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from veles.core.slug import normalize_slug

_GIT_URL_RE = re.compile(r"^(git@|git://|ssh://|https?://)")
_GIT_TIMEOUT_SEC = 300


def is_git_url(source: str) -> bool:
    return bool(_GIT_URL_RE.match(source)) or source.endswith(".git")


def derive_name(source: str, *, fallback: str) -> str:
    """The install name a source implies: the repo name for a git URL, else the
    directory name."""
    if is_git_url(source):
        last = source.rstrip("/").split("/")[-1].removesuffix(".git")
        return normalize_slug(last) or fallback
    return Path(source).resolve().name


def install_tree[T](
    source: str, target: Path, *, validate: Callable[[], T], error: type[Exception]
) -> T:
    """Clone or copy `source` into `target`, then return `validate()`.

    `target` must not exist yet (or be empty); on any failure — including one
    raised by `validate` — it is removed again. Problems are raised as `error`.
    """
    if target.exists() and any(target.iterdir()):
        raise error(f"target directory {target} already exists and is non-empty; remove it first")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if is_git_url(source):
            _git_clone(source, target, error)
        else:
            src_path = Path(source).resolve()
            if not src_path.is_dir():
                raise error(f"source {source!r} is neither a git URL nor a directory")
            shutil.copytree(src_path, target, symlinks=False)
        return validate()
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


def _git_clone(url: str, target: Path, error: type[Exception]) -> None:
    if shutil.which("git") is None:
        raise error("git executable not found in PATH")
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target)],
            check=True,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SEC,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.decode("utf-8", "replace").strip() if exc.stderr else "(no stderr)"
        raise error(f"git clone failed: {msg}") from exc
    except subprocess.TimeoutExpired as exc:
        raise error(f"git clone timed out after {_GIT_TIMEOUT_SEC}s") from exc


__all__ = ["derive_name", "install_tree", "is_git_url"]
