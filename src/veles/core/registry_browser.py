"""Curated module / skill registries (Tier δ, M54).

A registry is a JSON document at some URL (canonical: a raw `index.json`
in `github.com/<veles-org>/{modules,skills}`). It enumerates installable
items the agent — or the user via `veles browse` — can look at before
running `veles {module,skill} add ...`.

Why this module is thin:
  - the *install* code already lives in `core/skill_install.py` and
    `core/module_install.py`; this one only browses,
  - canonical URLs are still a placeholder (no public veles-org yet), so
    we make the source overridable per env var,
  - the registry can be a local file too — that's the contract tests use,
    and it lets users vendor an internal registry without internet access.

Schema (one entry):
    {
      "name": "scheduler",
      "description": "Cron-style scheduling for unattended runs.",
      "repo_url": "https://github.com/foo/veles-scheduler",
      "version": "0.1.0",
      "reviewed": true,
      "tags": ["scheduling", "background"]
    }

`reviewed: true` means a maintainer of the canonical registry vetted the
source. The CLI surfaces unreviewed entries with a red warning so users
notice supply-chain risk before they install.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# Placeholder canonical URLs — replace once the public veles-org is set up.
DEFAULT_MODULES_REGISTRY = (
    "https://raw.githubusercontent.com/veles-org/veles-modules/main/index.json"
)
DEFAULT_SKILLS_REGISTRY = "https://raw.githubusercontent.com/veles-org/veles-skills/main/index.json"

_MODULES_ENV = "VELES_MODULES_REGISTRY_URL"
_SKILLS_ENV = "VELES_SKILLS_REGISTRY_URL"
_FETCH_TIMEOUT_S = 10.0


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    name: str
    description: str
    repo_url: str
    version: str
    reviewed: bool = False
    tags: tuple[str, ...] = ()


class RegistryFetchError(RuntimeError):
    """Raised when the registry cannot be read (network, parse, file)."""


def registry_url(kind: str) -> str:
    """`kind` is "modules" or "skills". Env-var overrides take precedence."""
    if kind == "modules":
        return os.environ.get(_MODULES_ENV) or DEFAULT_MODULES_REGISTRY
    if kind == "skills":
        return os.environ.get(_SKILLS_ENV) or DEFAULT_SKILLS_REGISTRY
    raise ValueError(f"unknown registry kind {kind!r} (expected modules|skills)")


def load_registry(source: str) -> list[RegistryEntry]:
    """Load a registry from an HTTP URL or a local `file://` / bare path.

    Raises `RegistryFetchError` with a precise message on every failure
    path; the CLI catches it and prints a friendly fallback.
    """
    raw_bytes = _read_source(source)
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryFetchError(f"registry at {source} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(data, list):
        raise RegistryFetchError(
            f"registry at {source} must be a JSON array, got {type(data).__name__}"
        )
    out: list[RegistryEntry] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise RegistryFetchError(f"registry entry #{i} is not an object: {entry!r}")
        try:
            out.append(
                RegistryEntry(
                    name=str(entry["name"]),
                    description=str(entry.get("description", "")),
                    repo_url=str(entry["repo_url"]),
                    version=str(entry.get("version", "")),
                    reviewed=bool(entry.get("reviewed", False)),
                    tags=tuple(str(t) for t in entry.get("tags", [])),
                )
            )
        except KeyError as exc:
            raise RegistryFetchError(f"registry entry #{i} missing required field {exc}") from exc
    return out


def search(entries: list[RegistryEntry], query: str) -> list[RegistryEntry]:
    """Substring match on `name`, `description`, `tags`. Case-insensitive."""
    if not query.strip():
        return entries
    needle = query.lower().strip()
    out: list[RegistryEntry] = []
    for e in entries:
        haystack = " ".join((e.name, e.description, " ".join(e.tags))).lower()
        if needle in haystack:
            out.append(e)
    return out


def _read_source(source: str) -> bytes:
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in ("http", "https"):
        try:
            with urllib.request.urlopen(source, timeout=_FETCH_TIMEOUT_S) as r:
                return r.read()
        except urllib.error.URLError as exc:
            raise RegistryFetchError(f"failed to fetch {source}: {exc}") from exc
    # `file://` and bare paths both end up as filesystem reads.
    path = Path(parsed.path) if parsed.scheme == "file" else Path(source)
    if not path.exists():
        raise RegistryFetchError(f"registry file not found at {path}")
    return path.read_bytes()


__all__ = [
    "DEFAULT_MODULES_REGISTRY",
    "DEFAULT_SKILLS_REGISTRY",
    "RegistryEntry",
    "RegistryFetchError",
    "load_registry",
    "registry_url",
    "search",
]
