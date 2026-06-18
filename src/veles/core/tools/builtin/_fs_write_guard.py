"""Shared filesystem write-guard for builtin tools that mutate files
(`write_file`, `edit_file`).

Extracted in M168 so the two tools share ONE copy of the security gating
and can't drift: the M39 outside-active-project hard-confirm and the M117d
layout-pack writable-zone enforcement. Path-display (no `$HOME`/layout leak
to agent logs) lives here too.

`resolve_safe` (the M37 sandbox boundary) stays at each call site — it runs
before this guard, which assumes `p` is already an in-sandbox absolute path.
"""

from __future__ import annotations

from pathlib import Path

from veles.core.critical_ops import confirm_critical


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def display_path(p: Path, project) -> str:
    """Shortest meaningful path that doesn't leak the user's filesystem
    layout. Inside the active project: a relative path
    (`wiki/notes/topic.md`). Outside / no project: `sanitize` collapses
    `$HOME` to `~` and any project root to `<project>`."""
    from veles.core.sanitize import sanitize

    if project is not None:
        try:
            return str(p.relative_to(project.root.resolve()))
        except ValueError:
            pass
    return sanitize(str(p), project=project)


def guard_write(p: Path, project) -> str | None:
    """Gate a write to `p`. Returns an error string if refused, else None.

    - No active project → no gate (resolve_safe already bounded the path).
    - Outside the active project root → M39 hard-confirm (the agent could
      install executable code under `~/.veles/skills|modules/`); refusal
      returns a `<refused …>` string.
    - Inside the project root → M117d writable-zone check from the active
      layout pack; a write outside the declared zones is refused with the
      allowed-zones hint.
    """
    if project is None:
        return None
    root = project.root.resolve()
    if not is_within(p, root):
        ok = confirm_critical(
            f"write file outside active project to {p}",
            "This writes to user-global storage; the agent could install "
            "executable code under ~/.veles/skills/ or ~/.veles/modules/ this way.",
        )
        if not ok:
            return f"<refused: write to {p} outside active project not confirmed>"
        return None
    from veles.core.layout.writable import is_writable, writable_zones

    if not is_writable(project, p):
        zones = writable_zones(project)
        zones_hint = ", ".join(zones) if zones else "(none)"
        return (
            f"<refused: {display_path(p, project)} is outside the "
            f"active layout-pack's writable zones. Allowed: {zones_hint}>"
        )
    return None


__all__ = ["display_path", "guard_write", "is_within"]
