"""Recursive file-content search built into Veles (M124-perm-unify).

Replaces the `run_shell` + `find | xargs grep` workaround that pre-M124
agents reached for. Reasons to have it native:

- `run_shell` is `PROCESS_EXECUTION` → trust ladder gate on every call,
  even when the agent is just looking for a string.
- `find` / `xargs` output is shell-formatted and shells back through
  hundreds of tokens of tool dialogue per search.
- A typed tool gives the agent a stable shape (file:line:line_content)
  that's cheap to parse and equally cheap to truncate.

Backend selection:
1. Prefer `rg` (ripgrep) when it's in `PATH` — orders of magnitude
   faster on large trees, recursive by default, knows how to skip
   binary files. We pass conservative flags (`--no-heading
   --line-number --no-messages`) so the output is the same simple
   `path:line:content` shape regardless of `rg`'s version.
2. Fallback: pure-Python `pathlib.rglob` + `re.search` line-by-line.
   No new dependency, identical contract.

Sandbox is enforced via `resolve_safe`; the search root must live
under the active project (or the path_guard whitelist). Ignore-dirs
are hardcoded to a small, opinionated set; per-project ignore patterns
are out of scope for the MVP.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

from veles.core.path_guard import resolve_safe
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

logger = logging.getLogger(__name__)

_MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MiB
_MAX_LINE_LEN = 400  # truncate long lines so the agent's tail isn't trashed
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
    risk_class=RiskClass.SEARCH_ONLY,
    side_effects=[],
)
def search_files(
    pattern: str,
    path: str = ".",
    glob: str = "**/*",
    max_results: int = 200,
    case_insensitive: bool = False,
) -> str:
    """Recursively search files under `path` for lines matching `pattern`.

    `pattern` is a Python regular expression. `path` is the search root,
    sandboxed under the active project. `glob` filters which paths are
    scanned (e.g. `**/*.py`). `max_results` caps total matches across
    all files (default 200). `case_insensitive=True` adds the `re.I`
    flag (rg uses `-i`).

    Each match line is `relpath:line_no:content` (content trimmed at
    400 chars). Files larger than 2 MiB or under a hardcoded ignore
    list (`.git`, `node_modules`, `.venv`, `__pycache__`, `tmp`,
    `dist`, `build`, …) are skipped. The first 200 matches are
    returned; a tail note signals when more were found but skipped.
    """

    root = resolve_safe(path)
    if not root.exists():
        return f"<no such path: {path!r}>"
    try:
        compiled = re.compile(pattern, re.IGNORECASE if case_insensitive else 0)
    except re.error as exc:
        return f"<invalid regex {pattern!r}: {exc}>"

    rg = shutil.which("rg")
    if rg is not None:
        return _search_with_ripgrep(
            rg,
            pattern,
            root,
            glob=glob,
            max_results=max_results,
            case_insensitive=case_insensitive,
        )
    return _search_with_python(
        compiled,
        root,
        glob=glob,
        max_results=max_results,
    )


def _search_with_ripgrep(
    rg: str,
    pattern: str,
    root: Path,
    *,
    glob: str,
    max_results: int,
    case_insensitive: bool,
) -> str:
    cmd = [
        rg,
        "--no-heading",
        "--line-number",
        "--no-messages",
        "--max-count",
        str(max_results),
    ]
    if case_insensitive:
        cmd.append("-i")
    for ignored in _IGNORE_DIRS:
        cmd.extend(["--glob", f"!{ignored}"])
    if glob and glob != "**/*":
        cmd.extend(["--glob", glob])
    cmd.extend(["--regexp", pattern, str(root)])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("search_files: rg failed (%s), falling back to python", exc)
        compiled = re.compile(pattern, re.IGNORECASE if case_insensitive else 0)
        return _search_with_python(compiled, root, glob=glob, max_results=max_results)

    lines = [_relativise(ln, root) for ln in proc.stdout.splitlines() if ln]
    if not lines:
        return "<no matches>"
    capped = lines[:max_results]
    tail = f"\n<... truncated at {max_results} matches>" if len(lines) > max_results else ""
    return "\n".join(capped) + tail


def _search_with_python(
    compiled: re.Pattern[str],
    root: Path,
    *,
    glob: str,
    max_results: int,
) -> str:
    results: list[str] = []
    truncated = False
    if root.is_file():
        candidates: list[Path] = [root]
    else:
        candidates = list(root.glob(glob))
    for file_path in candidates:
        if len(results) >= max_results:
            truncated = True
            break
        if not file_path.is_file():
            continue
        try:
            rel_parts = file_path.relative_to(root).parts
        except ValueError:
            rel_parts = file_path.parts
        if any(part in _IGNORE_DIRS for part in rel_parts):
            continue
        try:
            if file_path.stat().st_size > _MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        try:
            with file_path.open(encoding="utf-8", errors="replace") as fh:
                for line_no, line in enumerate(fh, start=1):
                    if compiled.search(line):
                        results.append(_format_hit(file_path, line_no, line, root))
                        if len(results) >= max_results:
                            truncated = True
                            break
        except OSError:
            continue
    if not results:
        return "<no matches>"
    tail = f"\n<... truncated at {max_results} matches>" if truncated else ""
    return "\n".join(results) + tail


def _format_hit(file_path: Path, line_no: int, line: str, root: Path) -> str:
    try:
        rel = str(file_path.relative_to(root))
    except ValueError:
        rel = str(file_path)
    content = line.rstrip("\n")
    if len(content) > _MAX_LINE_LEN:
        content = content[:_MAX_LINE_LEN] + "…"
    return f"{rel}:{line_no}:{content}"


def _relativise(rg_line: str, root: Path) -> str:
    """`rg` returns absolute paths when invoked with an absolute root —
    fold them back to project-relative so the agent's view stays clean."""
    parts = rg_line.split(":", 2)
    if len(parts) < 3:
        return rg_line
    abs_path, line_no, content = parts
    try:
        rel = str(Path(abs_path).relative_to(root))
    except ValueError:
        rel = abs_path
    if len(content) > _MAX_LINE_LEN:
        content = content[:_MAX_LINE_LEN] + "…"
    return f"{rel}:{line_no}:{content}"
