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
def write_file(path: str, content: str) -> str:
    """Write `content` to `path`, creating parent directories as needed.

    Overwrites existing files. Returns a one-line confirmation with bytes written.
    Path is sandbox-checked (M37) — must resolve under active project or `~/.veles/`.
    Writes resolved outside the active project root require an M39 hard
    confirmation (literal `yes`); the agent could install executable code into
    `~/.veles/skills/` or `~/.veles/modules/` otherwise. Writes inside the
    project obey the active layout-pack's declared writable zones (M117d).
    """
    p = resolve_safe(path)
    project = current_project()
    refusal = guard_write(p, project)
    if refusal is not None:
        return refusal
    p.parent.mkdir(parents=True, exist_ok=True)
    n = p.write_text(content, encoding="utf-8")
    display = display_path(p, project)
    logger.info("file.write rel=%s bytes=%d", display, n)
    return f"wrote {n} bytes to {display}"
