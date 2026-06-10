"""Install / remove plugins from git URLs or local directories.

Mirrors `core/skill_install.py` (M23): same git-clone / shutil.copytree
flow, same rollback-on-failure contract. The validator is different —
we parse `module.toml` and confirm the entrypoint file exists, instead
of running the skill discovery pipeline.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from veles.core.module_manifest import (
    ManifestError,
    parse_entrypoint,
    parse_manifest,
)
from veles.core.modules import ModuleHandle, discover_modules
from veles.core.project import Project
from veles.core.wiki import _normalize_slug


class ModuleInstallError(RuntimeError):
    pass


class ModuleNotFoundError(RuntimeError):
    pass


_GIT_URL_RE = re.compile(r"^(git@|git://|ssh://|https?://)")
_GIT_TIMEOUT_SEC = 300
_MANIFEST_FILENAME = "module.toml"


def _is_git_url(source: str) -> bool:
    return bool(_GIT_URL_RE.match(source)) or source.endswith(".git")


def _derive_name(source: str) -> str:
    if _is_git_url(source):
        last = source.rstrip("/").split("/")[-1]
        last = last.removesuffix(".git")
        return _normalize_slug(last) or "installed-module"
    return Path(source).resolve().name


def install_module_from_source(
    source: str, *, project: Project, name_override: str | None = None
) -> ModuleHandle:
    """Clone (git URL) or copy (local dir) → validate manifest → return handle.

    Cleans up the partially-installed directory on any failure.
    """
    name = name_override or _derive_name(source)
    target = project.modules_dir / name
    if target.exists() and any(target.iterdir()):
        raise ModuleInstallError(
            f"target directory {target} already exists and is non-empty; "
            "remove the existing module first"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if _is_git_url(source):
            _git_clone(source, target)
        else:
            src_path = Path(source).resolve()
            if not src_path.is_dir():
                raise ModuleInstallError(f"source {source!r} is neither a git URL nor a directory")
            shutil.copytree(src_path, target, symlinks=False)
        manifest_path = target / _MANIFEST_FILENAME
        if not manifest_path.is_file():
            raise ModuleInstallError(f"installed source has no {_MANIFEST_FILENAME} at {target}")
        try:
            manifest = parse_manifest(manifest_path.read_text(encoding="utf-8"))
        except ManifestError as exc:
            raise ModuleInstallError(f"manifest validation failed: {exc}") from exc
        file_part, _ = parse_entrypoint(manifest.entrypoint)
        if not (target / file_part).is_file():
            raise ModuleInstallError(f"entrypoint file {file_part!r} not found in {target}")
        match = next((h for h in discover_modules(project) if h.name == manifest.name), None)
        if match is None:
            raise ModuleInstallError(
                f"installed module at {target} did not pass discover_modules; "
                f"check that [module].name == {manifest.name!r}"
            )
        return match
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


def _git_clone(url: str, target: Path) -> None:
    if shutil.which("git") is None:
        raise ModuleInstallError("git executable not found in PATH")
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
        raise ModuleInstallError(f"git clone failed: {msg}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ModuleInstallError(f"git clone timed out after {_GIT_TIMEOUT_SEC}s") from exc


def remove_module(name: str, *, project: Project) -> None:
    """Delete <project>/.veles/modules/<name>/ recursively."""
    target = project.modules_dir / name
    if not target.is_dir():
        raise ModuleNotFoundError(f"no module named {name!r} at {target}")
    shutil.rmtree(target)
