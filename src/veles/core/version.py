"""Version helpers (Tier δ, M53).

Single source of truth for the package version. `pyproject.toml` carries
the canonical string; this module exposes it programmatically and
provides SemVer-shaped parsing / bumping for the release script.

We deliberately don't auto-bump on every commit — Veles ships in
human-paced releases. The script below is meant for `release.sh` to
call once, validate locally, and only then tag + publish.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import metadata

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?$"
)


@dataclass(frozen=True, slots=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: str | None = None

    def __str__(self) -> str:
        core = f"{self.major}.{self.minor}.{self.patch}"
        return f"{core}-{self.prerelease}" if self.prerelease else core

    def bump(self, level: str) -> SemVer:
        """`level` is "major" | "minor" | "patch". Pre-release tag is dropped."""
        if level == "major":
            return SemVer(self.major + 1, 0, 0)
        if level == "minor":
            return SemVer(self.major, self.minor + 1, 0)
        if level == "patch":
            return SemVer(self.major, self.minor, self.patch + 1)
        raise ValueError(f"bump level must be major|minor|patch, got {level!r}")


def parse(s: str) -> SemVer:
    """Strict SemVer parse. Build metadata (`+...`) intentionally rejected
    — PyPI's `version` field can't carry build metadata, and tolerating it
    here would let it leak into release tags by accident."""
    m = _SEMVER_RE.match(s)
    if not m:
        raise ValueError(f"not a strict SemVer: {s!r}")
    return SemVer(
        major=int(m.group("major")),
        minor=int(m.group("minor")),
        patch=int(m.group("patch")),
        prerelease=m.group("prerelease"),
    )


def current_version() -> str:
    """The version actually installed for the running interpreter.

    Falls back to a hard-coded literal when the package isn't installed
    (e.g. running from a source tree without `pip install -e .`); the
    literal is hand-kept in sync with pyproject.toml at release time.
    """
    try:
        return metadata.version("veles")
    except metadata.PackageNotFoundError:
        return "0.1.0"


__all__ = ["SemVer", "current_version", "parse"]
