"""Reorg primitives for the `organize` module (M175).

`move_file` is the path-guarded move/rename used by the apply phase of
`veles organize`. It lives in the organize *module* (not `core/`) so the
"organize is a module, not core" invariant holds (VISION §5.2): the tool
registers via the `@tool` decorator only once `veles.modules.organize.tools`
is imported, which the organize dispatcher does just before building the
agent — exactly the lazy-registration pattern the wiki engine uses.
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

    Both paths are sandbox-checked (M37) and obey the same writable-zone
    rules as `write_file`/`edit_file` (M117d) — the move is refused if
    either endpoint escapes a writable zone, so the agent cannot relocate
    files out of (or into) read-only areas. Parent directories of `dst` are
    created as needed. Use this for reorganizing a project's layout
    (clustering pages into directories, renaming to a consistent slug).

    Returns a one-line confirmation, or a `<refused: ...>` / `<error: ...>`
    marker the agent can react to.
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
