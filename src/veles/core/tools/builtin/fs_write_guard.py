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
from veles.core.text import shown


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
    - Inside the project's `.veles/` but outside the agent's own subdirs →
      refused: trust.json, config.toml, modules/ … are Veles' state, and
      writing them would let the agent grant itself tools or load code.
    - Inside the project root → M117d writable-zone check from the active
      layout pack; a write outside the declared zones is refused with the
      allowed-zones hint.
    - Through `.git/`, `.claude/`, `.envrc`, … (`writable.needs_confirmation`)
      → M39 hard-confirm: those files run on their own or steer an agent CLI.
    """
    if project is None:
        return None
    root = project.root.resolve()
    if not is_within(p, root):
        ok = confirm_critical(
            f"write file outside active project to {shown(str(p))}",
            "This writes to user-global storage; the agent could install "
            "executable code under ~/.veles/skills/ or ~/.veles/modules/ this way.",
        )
        if not ok:
            return f"<refused: write to {p} outside active project not confirmed>"
        return None
    from veles.core.layout.writable import (
        is_veles_managed,
        is_writable,
        needs_confirmation,
        writable_zones,
    )

    if is_veles_managed(project, p):
        return (
            f"<refused: {shown(display_path(p, project))} is managed by Veles; "
            "change it with veles commands, not file tools>"
        )
    if not is_writable(project, p):
        zones = writable_zones(project)
        zones_hint = ", ".join(zones) if zones else "(none)"
        return (
            f"<refused: {shown(display_path(p, project))} is outside the "
            f"active layout-pack's writable zones. Allowed: {zones_hint}>"
        )
    if needs_confirmation(project, p):
        shown_path = shown(display_path(p, project))
        ok = confirm_critical(
            f"write auto-executed or agent config file {shown_path}",
            "Files here run without an explicit command (git hooks, .envrc, editor "
            "tasks) or configure an agent CLI; trust grants and autopilot don't cover it.",
        )
        if not ok:
            return f"<refused: write to {shown_path} not confirmed>"
    return None


def tool_file_note(p: Path, project) -> str:
    """What to tell the model after it wrote a self-authored tool file (M325).

    Empty unless `p` is a loadable `.py` in a tools directory. The model that
    skipped `tool_authoring` wrote a CLI script there and reported "tool
    created"; even a correct `@tool` file loads only after a human approves its
    bytes, which the model cannot do. Both are said in the same turn, in the
    tool result the model reads."""
    from veles.core.tools.loader import tool_file_problem
    from veles.core.user_paths import user_home

    tools_dirs = [user_home() / "tools"]
    if project is not None:
        tools_dirs.append(project.state_dir / "tools")
    if (
        p.suffix != ".py"
        or p.name.startswith("_")
        or not any(p.parent == d.resolve() for d in tools_dirs)
    ):
        return ""
    lines = []
    problem = tool_file_problem(p.read_text(encoding="utf-8"))
    if problem is not None:
        lines.append(
            f"warning: {p.name} {problem}, so Veles will not load it as a tool. "
            'See veles_help("tool_authoring") or call the tool_authoring skill.'
        )
    lines.append(
        f"note: Veles loads it only after the user reviews it and runs "
        f"`veles tool approve {p.stem}` — you cannot approve it, so tell them."
    )
    return "\n" + "\n".join(lines)


__all__ = ["display_path", "guard_write", "is_within", "tool_file_note"]
