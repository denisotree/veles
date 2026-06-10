"""Layout-pack discovery.

Three search roots, in priority order:
  1. Project-level:  `<project_root>/.veles/layouts/<name>/layout.toml`
  2. User-level:     `~/.veles/layouts/<name>/layout.toml`
  3. Builtin:        `src/veles/layouts/<name>/layout.toml` (shipped with Veles)

A pack at a higher priority shadows lower-priority packs of the same
name — this mirrors the existing skill/tool override pattern from §5.4
/ §5.5. Builtin packs are always discoverable as a fallback so `veles
init` has a working default.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from veles.core.layout.manifest import (
    LayoutManifest,
    LayoutManifestError,
    read_manifest,
)
from veles.core.project import Project
from veles.core.user_paths import user_home

LAYOUT_DEFAULT = "llm-wiki"
"""Builtin layout pack name. `veles init` defaults to this; it produces
the Karpathy LLM Wiki layout described in VISION §5.2."""


@dataclass(frozen=True, slots=True)
class LayoutDirectory:
    """One discovered pack: its parsed manifest plus the root directory
    (where its `skills/<name>/SKILL.md` files live)."""

    manifest: LayoutManifest
    root: Path
    scope: str  # "project" | "user" | "builtin"


def builtin_layouts_root() -> Path:
    """The directory in the installed package that holds builtin layout
    packs. Resolved relative to this module so it works from a wheel
    install or an editable `pip install -e .` checkout."""
    # core/layout/discovery.py → core/layout → core → veles → layouts/
    return Path(__file__).resolve().parent.parent.parent / "layouts"


def discover_layouts(project: Project | None = None) -> list[LayoutDirectory]:
    """Return every available layout-pack in priority order.

    When two packs share a name, the higher-priority one wins (project
    > user > builtin); the shadowed ones are dropped from the result so
    callers see one entry per pack name.
    """
    seen: dict[str, LayoutDirectory] = {}
    for entry in _iter_layouts(project):
        # First sighting wins because `_iter_layouts` yields in
        # priority order (project → user → builtin).
        if entry.manifest.name in seen:
            continue
        seen[entry.manifest.name] = entry
    return list(seen.values())


def find_layout(name: str, project: Project | None = None) -> LayoutDirectory | None:
    """Find one pack by name, respecting the override hierarchy."""
    for entry in _iter_layouts(project):
        if entry.manifest.name == name:
            return entry
    return None


# ---------- iteration helpers ----------


def _iter_layouts(project: Project | None) -> list[LayoutDirectory]:
    """Walk every search root in priority order, yielding discovered
    packs. Malformed manifests are dropped silently — callers that care
    can re-discover with `read_manifest` to surface the original error."""
    out: list[LayoutDirectory] = []
    for scope, root in _search_roots(project):
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            try:
                manifest = read_manifest(child)
            except (FileNotFoundError, LayoutManifestError):
                continue
            out.append(LayoutDirectory(manifest=manifest, root=child, scope=scope))
    return out


def _search_roots(project: Project | None) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    if project is not None:
        roots.append(("project", project.root / ".veles" / "layouts"))
    # `user_home()` already returns `<override>/.veles` — don't double it.
    roots.append(("user", user_home() / "layouts"))
    roots.append(("builtin", builtin_layouts_root()))
    return roots


__all__ = [
    "LAYOUT_DEFAULT",
    "LayoutDirectory",
    "builtin_layouts_root",
    "discover_layouts",
    "find_layout",
]
