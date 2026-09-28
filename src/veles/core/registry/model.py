"""`registry.toml` and `extensions/<group>/<name>/extension.toml` — the registry data model.

A registry is a git repository. Each extension directory holds an `extension.toml`
(metadata + where the code comes from) and, for `source.type = "path"`, the payload
itself. Parsing is strict: a malformed entry is reported, never half-accepted.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

EXTENSION_FILE = "extension.toml"
REGISTRY_FILE = "registry.toml"
KINDS = ("module", "skill", "layout", "mcp")
SOURCE_TYPES = ("path", "git")

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def is_slug(value: str) -> bool:
    """`True` iff `value` is a safe extension/group name: lowercase, digits, `-`,
    starting with an alnum. Used both to validate `extension.toml`'s
    `[extension].name` and, in `template.py`, to reject a `name`/`group` before
    it is ever used to build a filesystem path or TOML string — a slug can
    never contain `..`, `/`, or a quote."""
    return bool(_SLUG_RE.match(value))


class ExtensionError(ValueError):
    """A registry or extension manifest is malformed."""


@dataclass(frozen=True, slots=True)
class Source:
    type: str
    url: str | None = None
    commit: str | None = None
    subdir: str = ""
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class Extension:
    name: str
    kind: str
    version: str
    description: str
    license: str
    requires_veles: str
    source: Source
    tags: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    upstream: str | None = None
    yanked: str | None = None
    mcp: dict[str, Any] | None = None
    group: str = ""
    dir: Path | None = None


@dataclass(frozen=True, slots=True)
class RegistryMeta:
    name: str
    description: str
    schema: int
    public: bool


def parse_extension(text: str, *, group: str = "", dir: Path | None = None) -> Extension:
    """Parse one `extension.toml`. Raises `ExtensionError` naming the bad field."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ExtensionError(f"invalid TOML: {exc}") from exc
    ext = data.get("extension")
    if not isinstance(ext, dict):
        raise ExtensionError("missing [extension] table")
    src = data.get("source")
    if not isinstance(src, dict):
        raise ExtensionError("missing [source] table")
    name = _required(ext, "name")
    if not is_slug(name):
        raise ExtensionError(f"[extension].name {name!r} must match [a-z0-9][a-z0-9-]*")
    kind = _required(ext, "kind")
    if kind not in KINDS:
        raise ExtensionError(f"[extension].kind {kind!r} must be one of {', '.join(KINDS)}")
    version = _required(ext, "version")
    if not _SEMVER_RE.match(version):
        raise ExtensionError(f"[extension].version {version!r} must be MAJOR.MINOR.PATCH")
    provides = _str_list(ext, "provides")
    requires = _str_list(ext, "requires")
    if kind != "module" and (provides or requires):
        raise ExtensionError("provides/requires are only allowed for kind = 'module'")
    mcp = data.get("mcp")
    if kind == "mcp":
        if not isinstance(mcp, dict) or not mcp:
            raise ExtensionError("kind = 'mcp' needs a non-empty [mcp] recipe table")
    elif mcp is not None:
        raise ExtensionError("[mcp] is only allowed for kind = 'mcp'")
    return Extension(
        name=name,
        kind=kind,
        version=version,
        description=_required(ext, "description"),
        license=_required(ext, "license"),
        requires_veles=_required(ext, "requires_veles"),
        source=_parse_source(src, kind),
        tags=_str_list(ext, "tags"),
        provides=provides,
        requires=requires,
        upstream=_optional(ext, "upstream"),
        yanked=_optional(ext, "yanked"),
        mcp=dict(mcp) if isinstance(mcp, dict) else None,
        group=group,
        dir=dir,
    )


def load_registry_meta(root: Path) -> RegistryMeta:
    path = root / REGISTRY_FILE
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ExtensionError(f"cannot read {path}: {exc}") from exc
    reg = data.get("registry")
    if not isinstance(reg, dict):
        raise ExtensionError(f"{path}: missing [registry] table")
    schema = reg.get("schema")
    if schema != 1:
        raise ExtensionError(f"{path}: unsupported schema {schema!r} (expected 1)")
    return RegistryMeta(
        name=_required(reg, "name", where="registry"),
        description=str(reg.get("description", "")),
        schema=1,
        public=reg.get("public") is True,
    )


def scan_registry(root: Path) -> tuple[list[Extension], list[tuple[Path, str]]]:
    """Every `extensions/<group>/<name>/extension.toml`, plus the ones that failed to parse."""
    entries: list[Extension] = []
    errors: list[tuple[Path, str]] = []
    base = root / "extensions"
    if not base.is_dir():
        return entries, errors
    for group_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for ext_dir in sorted(p for p in group_dir.iterdir() if p.is_dir()):
            manifest = ext_dir / EXTENSION_FILE
            if not manifest.is_file():
                continue
            try:
                text = manifest.read_text(encoding="utf-8")
                entries.append(parse_extension(text, group=group_dir.name, dir=ext_dir))
            except (OSError, UnicodeDecodeError, ExtensionError) as exc:
                errors.append((manifest, str(exc)))
    return entries, errors


def _parse_source(src: dict[str, Any], kind: str) -> Source:
    kind_of_source = src.get("type")
    if kind_of_source not in SOURCE_TYPES:
        raise ExtensionError(f"source.type {kind_of_source!r} must be one of path, git")
    if kind == "mcp" and kind_of_source != "path":
        raise ExtensionError("an mcp recipe carries no code: source.type must be 'path'")
    if kind_of_source == "path":
        stray = sorted(k for k in ("url", "commit", "subdir", "sha256") if k in src)
        if stray:
            raise ExtensionError(f"source.type 'path' does not take {', '.join(stray)}")
        return Source(type="path")
    url = _required(src, "url", where="source")
    if url.startswith("-"):
        raise ExtensionError("source.url must not start with '-'")
    commit = _required(src, "commit", where="source")
    if not _COMMIT_RE.match(commit):
        raise ExtensionError("source.commit must be a full 40-character commit SHA")
    sha256 = _required(src, "sha256", where="source")
    if not _SHA256_RE.match(sha256):
        raise ExtensionError("source.sha256 must be a 64-character hex digest")
    subdir = str(src.get("subdir", ""))
    if not _is_safe_subdir(subdir):
        raise ExtensionError("source.subdir must be a relative path inside the repository")
    return Source(
        type="git",
        url=url,
        commit=commit,
        subdir=subdir,
        sha256=sha256,
    )


def _is_safe_subdir(subdir: str) -> bool:
    if not subdir:
        return True
    if PurePosixPath(subdir).is_absolute() or "\\" in subdir or has_control_char(subdir):
        return False
    return ".." not in PurePosixPath(subdir).parts


def has_control_char(value: str) -> bool:
    """Shared with `config.py`: a URL/ref/subdir must not smuggle a control character."""
    return any(ord(c) < 32 or ord(c) == 127 for c in value)


def _required(table: dict[str, Any], key: str, *, where: str = "extension") -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise ExtensionError(f"[{where}].{key} is required and must be a non-empty string")
    return value


def _optional(table: dict[str, Any], key: str) -> str | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ExtensionError(f"[extension].{key} must be a non-empty string when present")
    return value


def _str_list(table: dict[str, Any], key: str) -> tuple[str, ...]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ExtensionError(f"[extension].{key} must be a list of non-empty strings")
    return tuple(value)
