"""M117c-final: enforce layout-pack writable_zones at write time.

Design rule (VISION §4): writable zones are declarative. The concrete
zones depend on the layout the user picked and are declared in
AGENTS.md. In the default LLM Wiki layout the LLM writes only to
`wiki/` and `<cwd>/.veles/`; `sources/` is read-only.

`is_writable(project, path)` is the runtime check the builtin
`write_file` tool (and any agent-generated write tool) consults
before persisting bytes. The read sandbox (`path_guard.py`) stays
unchanged — read remains full-project — but writes are restricted
to whatever the active layout-pack declares.

Always-writable zones, regardless of pack:
- `<cwd>/.veles/`  — project memory, agent's own scratch space.

Layout-pack-declared writable zones come from the active pack's
manifest (`find_layout(project.layout_name)`) via the
`writable_path_strings()` helper that already filters out readonly
zones.

When no pack is active (custom layout that didn't ship a layout.toml,
or the project's `layout_name` points at a missing pack), fall back
to permissive mode — allow everything inside the project root. This
preserves the pre-M117 contract: a project without a layout-pack
can still write anywhere in its tree.
"""

from __future__ import annotations

import logging
from pathlib import Path

from veles.core.project import Project

logger = logging.getLogger(__name__)


# These always count as writable, no matter what the layout-pack
# declares. `.veles/` is the agent's own state directory and
# shouldn't depend on layout-pack declarations.
_ALWAYS_WRITABLE_REL: tuple[str, ...] = (".veles/",)


def is_writable(project: Project, path: str | Path) -> bool:
    """True iff the agent may write to `path` under `project`'s active
    layout-pack. Always-writable zones (`.veles/`) override the
    pack's declaration; pack-declared zones extend the write surface
    beyond that minimum.

    `path` is normalised relative to `project.root`. Absolute paths
    outside the project root are rejected (those should never reach
    here — `path_guard` catches them first).
    """
    abs_path = (project.root / path).resolve()
    try:
        rel = abs_path.relative_to(project.root.resolve())
    except ValueError:
        # Outside the project root — `path_guard` is the gate for
        # that. We say no here too for defence in depth.
        return False
    rel_str = str(rel)
    # Normalise to forward slashes for the prefix check; Path's
    # `as_posix` does that without affecting filesystem behaviour.
    rel_posix = rel.as_posix() + ("/" if abs_path.is_dir() else "")

    for prefix in _ALWAYS_WRITABLE_REL:
        if rel_posix.startswith(prefix) or rel_str.startswith(prefix.rstrip("/")):
            return True

    zones = _effective_writable_zones(project)
    if not zones:
        # Permissive fallback when no pack declares zones.
        return True
    for zone in zones:
        # Zone may be `wiki/` or `wiki` — match both forms.
        zone_norm = zone.rstrip("/")
        if rel_posix.startswith(zone_norm + "/") or rel_str == zone_norm:
            return True
    return False


def writable_zones(project: Project) -> tuple[str, ...]:
    """Return the effective writable zones for `project` — the layout
    pack's declared zones plus the always-writable defaults. Used by
    diagnostic surfaces (`veles doctor`, `/status` slash) so the
    user can see what the agent can touch."""
    pack_zones = _effective_writable_zones(project)
    return _ALWAYS_WRITABLE_REL + tuple(z if z.endswith("/") else z + "/" for z in pack_zones)


def _effective_writable_zones(project: Project) -> list[str]:
    """Pull writable zones from the active layout-pack. Empty list
    when no pack resolves or the pack declares no zones."""
    try:
        from veles.core.layout.discovery import find_layout

        pack = find_layout(project.layout_name, project=project)
    except Exception as exc:
        logger.debug("layout lookup failed: %s", exc)
        return []
    if pack is None:
        return []
    return list(pack.manifest.writable_path_strings())


__all__ = ["is_writable", "writable_zones"]
