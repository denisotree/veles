"""Strict TOML parser for `module.toml`.

The manifest is the only contract between Veles and a third-party plugin
directory: name + description for `veles module list`, entrypoint
(`<file>:<func>` spec) for `load_module`. We validate strictly and
fail-fast — silently accepting a malformed manifest would mean the
module is shown in `list` but never actually fires its hooks, which is
worse than a clear error at install / discovery time.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass


class ManifestError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    name: str
    description: str
    entrypoint: str
    version: str | None = None


def parse_manifest(text: str) -> ModuleManifest:
    """Parse module.toml content. Raises ManifestError on any problem."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"invalid TOML: {exc}") from exc
    section = data.get("module")
    if not isinstance(section, dict):
        raise ManifestError("missing [module] section")
    for key in ("name", "description", "entrypoint"):
        value = section.get(key)
        if not isinstance(value, str) or not value:
            raise ManifestError(f"[module].{key} is required and must be a non-empty string")
    version = section.get("version")
    if version is not None and not isinstance(version, str):
        raise ManifestError("[module].version must be a string if present")
    return ModuleManifest(
        name=section["name"],
        description=section["description"],
        entrypoint=section["entrypoint"],
        version=version,
    )


def parse_entrypoint(spec: str) -> tuple[str, str]:
    """Split `<file>:<func>` into (file_part, func_part). Raises ManifestError."""
    if ":" not in spec:
        raise ManifestError(f"entrypoint must be 'file:func', got {spec!r}")
    file_part, _, func_part = spec.partition(":")
    if not file_part or not func_part:
        raise ManifestError(f"entrypoint has empty file or func: {spec!r}")
    return file_part, func_part
