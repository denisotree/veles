"""Curated how-to notes: parse `knowledge/notes/*.md` into `Note` objects.

Each note is frontmatter (`title`, `topics`, `related`) + a markdown body.
`related` holds typed refs (`cmd:`, `flag:<cmd>:`, `skill:`, `tool:`) that the
freshness guard (tests/knowledge/test_knowledge_freshness.py) validates against
the live skeleton so a note can never lie about what Veles offers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from veles.core.skills import parse_frontmatter

# Notes ship inside the package, next to this module's parent:
# src/veles/knowledge/notes/*.md
_NOTES_ROOT = Path(__file__).resolve().parent.parent.parent / "knowledge" / "notes"


@dataclass(frozen=True, slots=True)
class Note:
    slug: str
    title: str
    body: str
    topics: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def parse_note(path: Path) -> Note:
    fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return Note(
        slug=path.stem,
        title=str(fm.get("title", path.stem)).strip(),
        body=body.strip(),
        topics=_as_str_list(fm.get("topics")),
        related=_as_str_list(fm.get("related")),
    )


def load_notes(root: Path | None = None) -> list[Note]:
    base = root or _NOTES_ROOT
    if not base.is_dir():
        return []
    return [parse_note(p) for p in sorted(base.glob("*.md"))]
