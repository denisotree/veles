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
    # Return actionable `<error: …>` markers instead of raising raw
    # IsADirectoryError / FileNotFoundError (which surface as noisy `tool.error`
    # lines and give the agent nothing to act on). A real vault migration had
    # the agent call read_file on directories and guessed paths — the hints let
    # it recover (list the dir, re-check the path) instead of stalling.
    if p.is_dir():
        return (
            f"<error: {path!r} is a directory, not a file — call list_files on it "
            "to see its contents, then read_file each file individually>"
        )
    if not p.exists():
        return (
            f"<error: no such file: {path!r} — do not guess paths; use list_files / "
            "search_files to find the real path first>"
        )
    with p.open(encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    selected = lines[offset : offset + limit]
    project = current_project()
    try:
        rel = str(p.relative_to(project.root.resolve())) if project is not None else str(p)
    except ValueError:
        rel = str(p)
    logger.info("file.read rel=%s lines=%d offset=%d", rel, len(selected), offset)
    return "".join(f"{i + offset + 1:>6}\t{line}" for i, line in enumerate(selected))
