"""Install / remove plugins from git URLs or local directories.

Cloning, copying and rollback are `core/source_install.py`, shared with skill
installation; what is module-specific is the validation — `module.toml` must
parse and its entrypoint file must exist.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from veles.core.module_manifest import (
    ManifestError,
    entrypoint_file,
    parse_manifest,
)
from veles.core.modules import ModuleHandle, discover_modules_in
from veles.core.registry.hashing import git_dirs
from veles.core.source_install import derive_name, install_tree
from veles.core.text import shown


class ModuleInstallError(RuntimeError):
    pass


class ModuleNotFoundError(RuntimeError):
    pass


_MANIFEST_FILENAME = "module.toml"


def derive_module_name(source: str) -> str:
    return derive_name(source, fallback="installed-module")


def install_module_from_source(
    source: str, *, modules_dir: Path, name_override: str | None = None
) -> ModuleHandle:
    """Clone (git URL) or copy (local dir) → validate manifest → return handle.

    Cleans up the partially-installed directory on any failure.
    """
    target = modules_dir / (name_override or derive_module_name(source))

    def validate() -> ModuleHandle:
        manifest_path = target / _MANIFEST_FILENAME
        if not manifest_path.is_file():
            raise ModuleInstallError(
                f"installed source has no {_MANIFEST_FILENAME} at {shown(target)}"
            )
        try:
            manifest = parse_manifest(manifest_path.read_text(encoding="utf-8"))
            entry, _ = entrypoint_file(target, manifest.entrypoint)
        except ManifestError as exc:
            raise ModuleInstallError(f"manifest validation failed: {shown(exc)}") from exc
        if not entry.is_file():
            raise ModuleInstallError(f"entrypoint file {entry.name!r} not found in {shown(target)}")
        # The handle is always `target`: approving "the first dir with this name" would
        # approve whatever else in the scope declares it — e.g. a dir the agent planted.
        others = [
            shown(h.dir)
            for h in discover_modules_in(modules_dir)
            if h.name == manifest.name and h.dir != target
        ]
        if others:
            raise ModuleInstallError(
                f"another module in {shown(modules_dir)} already declares name "
                f"{manifest.name!r}: "
                f"{', '.join(others)} — review and remove it first"
            )
        # Nothing reads a module's `.git`, and the load gate refuses one (it is
        # outside the approval hash), so an installed module never carries it.
        for git in git_dirs(target):
            if git.is_dir():
                shutil.rmtree(git)
            else:
                git.unlink()
        return ModuleHandle(name=manifest.name, manifest=manifest, dir=target)

    return install_tree(source, target, validate=validate, error=ModuleInstallError)


def remove_module(name: str, *, modules_dir: Path) -> None:
    """Delete <modules_dir>/<name>/ recursively."""
    target = modules_dir / name
    if not target.is_dir():
        raise ModuleNotFoundError(f"no module named {name!r} at {shown(target)}")
    shutil.rmtree(target)
