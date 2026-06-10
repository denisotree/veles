from __future__ import annotations

import logging
from pathlib import Path

from veles.core.context import current_project
from veles.core.critical_ops import confirm_critical
from veles.core.path_guard import resolve_safe
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

logger = logging.getLogger(__name__)


@tool(
    risk_class=RiskClass.WRITE_LOCAL_PROJECT,
    sensitive=True,
    side_effects=["filesystem"],
)
def write_file(path: str, content: str) -> str:
    """Write `content` to `path`, creating parent directories as needed.

    Overwrites existing files. Returns a one-line confirmation with bytes written.
    Path is sandbox-checked (M37) — must resolve under active project or `~/.veles/`.
    Writes resolved outside the active project root require an M39 hard
    confirmation (literal `yes`); the agent could install executable code into
    `~/.veles/skills/` or `~/.veles/modules/` otherwise.
    """
    p = resolve_safe(path)
    project = current_project()
    if project is not None and not _is_within(p, project.root.resolve()):
        ok = confirm_critical(
            f"write file outside active project to {p}",
            "This writes to user-global storage; the agent could install "
            "executable code under ~/.veles/skills/ or ~/.veles/modules/ this way.",
        )
        if not ok:
            return f"<refused: write to {p} outside active project not confirmed>"
    # M117d: enforce the active layout-pack's declared writable_zones
    # for writes that land inside the project root. Outside the project
    # the M39 hard-confirm above already gated; outside-active-project
    # writes don't have a layout-pack zone notion.
    if project is not None and _is_within(p, project.root.resolve()):
        from veles.core.layout.writable import is_writable, writable_zones

        if not is_writable(project, p):
            zones = writable_zones(project)
            zones_hint = ", ".join(zones) if zones else "(none)"
            return (
                f"<refused: {_display_path(p, project)} is outside the "
                f"active layout-pack's writable zones. "
                f"Allowed: {zones_hint}>"
            )
    p.parent.mkdir(parents=True, exist_ok=True)
    n = p.write_text(content, encoding="utf-8")
    display = _display_path(p, project)
    logger.info("file.write rel=%s bytes=%d", display, n)
    return f"wrote {n} bytes to {display}"


def _display_path(p: Path, project) -> str:
    """Pick the shortest meaningful path representation that doesn't
    leak the user's filesystem layout. Inside the active project: a
    relative path (`wiki/notes/topic.md`). Outside or no project:
    `sanitize` collapses `$HOME` to `~` and any project root to
    `<project>`."""
    from veles.core.sanitize import sanitize

    if project is not None:
        try:
            return str(p.relative_to(project.root.resolve()))
        except ValueError:
            pass
    return sanitize(str(p), project=project)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
