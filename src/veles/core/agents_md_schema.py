"""AGENTS.md schema validation — minimal section check.

PLAN.md §13 OQ#13 deferred this to "minimal validation: presence of
*Layout*, *Conventions*, *Workflows*". This module implements exactly
that — extract H2 headings from the markdown, compare against the
recommended set, return what's missing. No semantic analysis, no
formatting rules; the agent already tolerates free-form bodies, the
schema check is just a kindness so the user notices when their
auto-loaded context is gibberish.

The validator is **non-blocking** by contract: callers warn on
issues, never refuse to run. `veles schema edit` makes the warning
actionable by opening `$EDITOR` on `AGENTS.md` and re-validating.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

RECOMMENDED_SECTIONS: tuple[str, ...] = ("Layout", "Conventions", "Workflows")

_H2_RE = re.compile(r"^\s*##\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    present: list[str]  # H2 headings actually found, original casing
    missing: list[str]  # subset of RECOMMENDED_SECTIONS not present (case-insensitive)

    @property
    def ok(self) -> bool:
        return not self.missing


def extract_h2_sections(text: str) -> list[str]:
    """Return the list of H2 headings in document order.

    Only matches `## Heading`; ignores `#` (H1) and `### …` (H3+).
    Trailing whitespace is stripped.
    """
    return [m.group(1).strip() for m in _H2_RE.finditer(text or "")]


def validate(text: str) -> ValidationResult:
    """Return which `RECOMMENDED_SECTIONS` are present vs missing.

    Comparison is case-insensitive — `## layout` counts as Layout.
    Section ordering is irrelevant.
    """
    present = extract_h2_sections(text)
    present_lower = {h.lower() for h in present}
    missing = [s for s in RECOMMENDED_SECTIONS if s.lower() not in present_lower]
    return ValidationResult(present=present, missing=missing)


def default_template(name: str) -> str:
    """Return a fresh AGENTS.md that passes `validate()`.

    The template intentionally stays short — PLAN.md §5 caps AGENTS.md
    at ~300 lines, and `INDEX.md` carries the volume. Sections here
    are placeholders the user is expected to fill in; the agent reads
    the file as-is so empty sections still load without error.
    """
    return (
        f"# {name}\n\n"
        f"Add your project context here. Auto-loaded into the system prompt\n"
        f"when you run `veles run`, `veles ingest`, or `veles query` from\n"
        f"this directory (or any subdirectory).\n\n"
        f"## Layout\n\n"
        f"- `sources/` — immutable raw inputs.\n"
        f"- `wiki/` — agent-curated knowledge "
        f"(concepts, entities, sources, queries, sessions, insights).\n"
        f"- `INDEX.md` — auto-generated catalogue, refreshed on every wiki write.\n"
        f"- `LOG.md` — append-only journal of agent operations.\n\n"
        f"## Conventions\n\n"
        f"- Wiki pages use kebab-case slugs.\n"
        f"- Tool calls log to `LOG.md` via `wiki_append_log`.\n"
        f"- LLM-only writes go under `wiki/`; `sources/` is read-only.\n\n"
        f"## Workflows\n\n"
        f"- `veles ingest <url|file>` — read source, write a wiki page.\n"
        f"- `veles query <question>` — search the wiki and synthesise an answer.\n"
        f"- `veles lint` — audit for orphans, stale claims, duplicates.\n"
        f"- `veles curate` — compact recent sessions into `wiki/sessions/`.\n"
    )
