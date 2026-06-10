from __future__ import annotations

import logging

from veles.core.context import current_project
from veles.core.path_guard import resolve_safe
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

logger = logging.getLogger(__name__)


@tool(risk_class=RiskClass.READ_ONLY, side_effects=[])
def read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
    """Read a UTF-8 text file and return numbered lines.

    `offset` is the 0-based starting line; `limit` caps how many lines come back.
    Output format mimics `cat -n`: 6-wide right-aligned line number, tab, content.
    Path is sandbox-checked (M37) — must resolve under active project or `~/.veles/`.
    """
    p = resolve_safe(path)
    with p.open(encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    selected = lines[offset : offset + limit]
    project = current_project()
    try:
        rel = (
            str(p.relative_to(project.root.resolve()))
            if project is not None
            else str(p)
        )
    except ValueError:
        rel = str(p)
    logger.info(
        "file.read rel=%s lines=%d offset=%d", rel, len(selected), offset
    )
    return "".join(f"{i + offset + 1:>6}\t{line}" for i, line in enumerate(selected))
