"""Filesystem move / delete / mkdir primitives for the interactive agent.

Relocated from the organize module (M175) so these are ALWAYS registered — a
name in the `[run]` toolset only resolves if the tool is registered, and
`move_file` used to register only when the organize dispatcher imported its
module. The interactive surface therefore had no first-class move/rename/delete,
so the agent fell back to confirm-gated `run_shell("mv/rm")` and in practice
never moved files. All three obey the same sandbox (`resolve_safe`, M37) and
writable-zone (`guard_write`, M117d) rules as `write_file`/`edit_file`, so they
cannot touch read-only zones (e.g. `sources/`) or escape the project root.
"""

from __future__ import annotations

import logging

from veles.core.context import current_project
from veles.core.path_guard import resolve_safe
from veles.core.risk import RiskClass
from veles.core.tools.builtin._fs_write_guard import display_path, guard_write
from veles.core.tools.registry import tool

logger = logging.getLogger(__name__)


@tool(
    risk_class=RiskClass.WRITE_LOCAL_PROJECT,
    sensitive=True,
    side_effects=["filesystem"],
)
def move_file(src: str, dst: str) -> str:
    """Move or rename a file within the project's writable zones.

    Both paths are sandbox-checked and obey the same writable-zone rules as
    `write_file`/`edit_file` — the move is refused if either endpoint escapes a
    writable zone, so the agent cannot relocate files out of (or into) read-only
    areas. Parent directories of `dst` are created as needed (nested paths like
    `wiki/projects/work/foo.md` work). Use this — NOT `run_shell mv` — to
    physically move/rename files while reorganizing a project.

    For wiki *pages* specifically, prefer `wiki_rename_page` when available: it
    also rewrites inbound `[[wikilinks]]` and the INDEX. Returns a one-line
    confirmation, or a `<refused: ...>` / `<error: ...>` marker.
    """
    s = resolve_safe(src)
    d = resolve_safe(dst)
    project = current_project()
    if not s.is_file():
        return f"<error: {display_path(s, project)} does not exist or is not a file>"
    if d.exists():
        return f"<error: destination {display_path(d, project)} already exists; pick a free path>"
    # Guard both endpoints: src is removed (a write), dst is created (a write).
    for endpoint in (s, d):
        refusal = guard_write(endpoint, project)
        if refusal is not None:
            return refusal
    d.parent.mkdir(parents=True, exist_ok=True)
    s.rename(d)
    src_disp, dst_disp = display_path(s, project), display_path(d, project)
    logger.info("file.move src=%s dst=%s", src_disp, dst_disp)
    return f"moved {src_disp} -> {dst_disp}"


@tool(
    risk_class=RiskClass.DESTRUCTIVE,
    sensitive=True,
    side_effects=["filesystem"],
)
def delete_file(path: str) -> str:
    """Delete a single file within the project's writable zones.

    Refuses directories, non-existent paths, and read-only zones. Irreversible —
    prefer `move_file` to relocate rather than delete-then-recreate. Returns a
    one-line confirmation, or a `<refused: ...>` / `<error: ...>` marker.
    """
    p = resolve_safe(path)
    project = current_project()
    if not p.exists():
        return f"<error: {display_path(p, project)} does not exist>"
    if p.is_dir():
        return f"<error: {display_path(p, project)} is a directory; delete_file removes files only>"
    refusal = guard_write(p, project)
    if refusal is not None:
        return refusal
    p.unlink()
    disp = display_path(p, project)
    logger.info("file.delete path=%s", disp)
    return f"deleted {disp}"


@tool(
    risk_class=RiskClass.WRITE_LOCAL_PROJECT,
    sensitive=True,
    side_effects=["filesystem"],
)
def make_dir(path: str) -> str:
    """Create a directory (and any missing parents) within the project's
    writable zones. Idempotent — succeeds if it already exists. Use this to lay
    out a new wiki category / structure before writing pages into it. Returns a
    one-line confirmation, or a `<refused: ...>` / `<error: ...>` marker.
    """
    p = resolve_safe(path)
    project = current_project()
    if p.is_file():
        return f"<error: {display_path(p, project)} exists and is a file>"
    refusal = guard_write(p, project)
    if refusal is not None:
        return refusal
    p.mkdir(parents=True, exist_ok=True)
    disp = display_path(p, project)
    logger.info("file.mkdir path=%s", disp)
    return f"created directory {disp}"
