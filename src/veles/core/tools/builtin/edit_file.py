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
def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Replace an exact substring in an EXISTING file (surgical edit).

    Unlike `write_file` (whole-file overwrite), `edit_file` changes only the
    matched text — use it to correct a line in a dbt model, a script, or a
    monitoring query without regenerating the whole file.

    `old_string` must appear EXACTLY ONCE unless `replace_all=true` — a
    non-unique match is refused so the agent can't silently edit the wrong
    occurrence (add surrounding context to disambiguate). The file must
    already exist (use `write_file` to create one). `old_string` and
    `new_string` must differ and `old_string` must be non-empty.

    Path is sandbox-checked (M37) and the write obeys the same M39
    outside-project confirm + M117d writable-zone rules as `write_file`.
    Returns a one-line confirmation with the replacement count.
    """
    if old_string == "":
        return "<refused: old_string is empty; use write_file to create or overwrite a file>"
    if old_string == new_string:
        return "<refused: old_string and new_string are identical (no-op)>"
    p = resolve_safe(path)
    project = current_project()
    if not p.is_file():
        return (
            f"<error: {display_path(p, project)} does not exist; "
            "use write_file to create it>"
        )
    refusal = guard_write(p, project)
    if refusal is not None:
        return refusal
    original = p.read_text(encoding="utf-8")
    count = original.count(old_string)
    display = display_path(p, project)
    if count == 0:
        return f"<error: old_string not found in {display}>"
    if count > 1 and not replace_all:
        return (
            f"<error: old_string appears {count} times in {display}; "
            "add surrounding context to make it unique, or pass replace_all=true>"
        )
    updated = original.replace(old_string, new_string) if replace_all else original.replace(
        old_string, new_string, 1
    )
    n = count if replace_all else 1
    p.write_text(updated, encoding="utf-8")
    logger.info("file.edit rel=%s replacements=%d", display, n)
    return f"edited {display} ({n} replacement{'s' if n != 1 else ''})"
