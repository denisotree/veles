"""Builtin list_files — recursive directory listing under the sandbox.

Lightweight `ls`-style read-only tool. Each line: `<type>\\t<size_bytes>\\t<rel_path>`,
where type is `d` (directory), `f` (regular file) or `l` (symlink). Lets the
agent enumerate project contents without falling back to `run_shell ls -la`.

`risk_class=READ_ONLY` → default policy `allow` (no prompt). Sandboxed via
`resolve_safe` so an agent can't `list_files("/etc")` past the active project.
"""

from __future__ import annotations

import logging
from pathlib import Path

from veles.core.path_guard import resolve_safe
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

logger = logging.getLogger(__name__)

_IGNORE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        "tmp",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)


@tool(
    risk_class=RiskClass.READ_ONLY,
    side_effects=[],
)
def list_files(
    path: str = ".",
    glob: str = "*",
    max_results: int = 500,
    show_hidden: bool = False,
) -> str:
    """List entries under `path` matching `glob` (default `*` = direct
    children). Use `**/*` for a recursive walk.

    Returns up to `max_results` lines `<type>\\t<size>\\t<rel_path>`,
    sorted by path. Hidden entries (leading `.`) are skipped unless
    `show_hidden=True`. The same opinionated ignore-list as
    `search_files` (`.git`, `node_modules`, `__pycache__`, `tmp`,
    `dist`, `build`, …) is always honoured — overriding it isn't
    supported in the MVP.
    """

    root = resolve_safe(path)
    if not root.exists():
        return f"<no such path: {path!r}>"
    if not root.is_dir():
        return _format_entry(root, root)

    try:
        candidates = sorted(root.glob(glob))
    except OSError as exc:
        return f"<glob {glob!r} failed: {exc}>"

    rows: list[str] = []
    for entry in candidates:
        if len(rows) >= max_results:
            rows.append(f"<... truncated at {max_results} entries>")
            break
        if not show_hidden and entry.name.startswith("."):
            continue
        try:
            rel_parts = entry.relative_to(root).parts
        except ValueError:
            rel_parts = entry.parts
        if any(part in _IGNORE_DIRS for part in rel_parts):
            continue
        rows.append(_format_entry(entry, root))

    if not rows:
        return "<empty>"
    return "\n".join(rows)


def _format_entry(entry: Path, root: Path) -> str:
    try:
        stat = entry.lstat()
    except OSError:
        return f"?\t?\t{entry}"
    if entry.is_symlink():
        type_char = "l"
    elif entry.is_dir():
        type_char = "d"
    elif entry.is_file():
        type_char = "f"
    else:
        type_char = "?"
    try:
        rel = str(entry.relative_to(root))
    except ValueError:
        rel = str(entry)
    return f"{type_char}\t{stat.st_size}\t{rel}"
