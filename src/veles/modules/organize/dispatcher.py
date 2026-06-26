"""Resolve the active layout's `organize` operation → its skill body.

`veles organize` is layout-driven by construction: each layout pack may
declare `[[layout.operations]] name = "organize"` pointing at a skill whose
SKILL.md body is the reorg recipe (cluster into `wiki/concepts|entities|...`
for llm-wiki, sort notes for the notes pack, …). A pack that declares no
`organize` operation (e.g. `bare`) has no reorg behaviour — the command
exits cleanly. This consumes the dormant `[[layout.operations]]` schema
(`core/layout/manifest.py`) that the runtime never wired up before M175.
"""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.layout.discovery import find_layout
from veles.core.project import Project
from veles.core.skills import parse_frontmatter


@dataclass(frozen=True, slots=True)
class ResolvedOperation:
    """A layout operation resolved to a runnable recipe."""

    skill: str
    body: str


def resolve_operation(project: Project, op_name: str) -> ResolvedOperation | None:
    """Return the (skill, body) for `op_name` on the project's active layout.

    Returns ``None`` when the layout pack is missing, declares no operation
    of that name, or its skill file is absent/empty — every "no-op by
    absence" case the caller reports as a clean exit rather than an error.
    """
    pack = find_layout(project.layout_name, project)
    if pack is None:
        return None
    op = pack.manifest.operation(op_name)
    if op is None:
        return None
    skill_path = pack.root / "skills" / op.skill / "SKILL.md"
    if not skill_path.is_file():
        return None
    _, body = parse_frontmatter(skill_path.read_text(encoding="utf-8"))
    body = body.strip()
    if not body:
        return None
    return ResolvedOperation(skill=op.skill, body=body)
