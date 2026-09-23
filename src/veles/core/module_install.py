"""Install / remove plugins from git URLs or local directories.

Cloning, copying and rollback are `core/source_install.py`, shared with skill
installation; what is module-specific is the validation — `module.toml` must
parse and its entrypoint file must exist.
"""

from __future__ import annotations

import shutil

from veles.core.module_manifest import (
    ManifestError,
    parse_entrypoint,
    parse_manifest,
)
from veles.core.modules import ModuleHandle, discover_modules
from veles.core.project import Project
from veles.core.source_install import derive_name, install_tree


class ModuleInstallError(RuntimeError):
    pass


class ModuleNotFoundError(RuntimeError):
    pass


_MANIFEST_FILENAME = "module.toml"


def derive_module_name(source: str) -> str:
    return derive_name(source, fallback="installed-module")


def install_module_from_source(
    source: str, *, project: Project, name_override: str | None = None
) -> ModuleHandle:
    """Clone (git URL) or copy (local dir) → validate manifest → return handle.

    Cleans up the partially-installed directory on any failure.
    """
    target = project.modules_dir / (name_override or derive_module_name(source))

    def validate() -> ModuleHandle:
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

    return install_tree(source, target, validate=validate, error=ModuleInstallError)


def remove_module(name: str, *, project: Project) -> None:
    """Delete <project>/.veles/modules/<name>/ recursively."""
    target = project.modules_dir / name
    if not target.is_dir():
        raise ModuleNotFoundError(f"no module named {name!r} at {target}")
    shutil.rmtree(target)
