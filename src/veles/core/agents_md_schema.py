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

# Telltale phrase every scaffold-generated AGENTS.md (default + the builtin
# pack templates) carries. Its presence means the file is the unmodified
# scaffold default — used by `apply_scaffold` and `doctor` to tell a stale
# copied-from-another-project default from real user content.
DEFAULT_TEMPLATE_MARKER = "Add your project context here"

_H2_RE = re.compile(r"^\s*##\s+(.+?)\s*$", re.MULTILINE)


def is_default_template(text: str) -> bool:
    """True when `text` is still the unmodified scaffold default AGENTS.md."""
    return DEFAULT_TEMPLATE_MARKER in text


def title_of(text: str) -> str | None:
    """The first `# ` H1 title in `text`, or None."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


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

    M162: this is the *layout-agnostic fallback* — a layout pack that
    wants a richer, structure-specific AGENTS.md ships its own template
    via `[layout.scaffold].agents_md_template` (the builtin llm-wiki
    pack does). The template intentionally stays short — PLAN.md §5
    caps AGENTS.md at ~300 lines. Sections are placeholders the user is
    expected to fill in; the agent reads the file as-is so empty
    sections still load without error.
    """
    return (
        f"# {name}\n\n"
        f"Add your project context here. Auto-loaded into the system prompt\n"
        f"when you run `veles run` or bare `veles` from this directory (or any\n"
        f"subdirectory).\n\n"
        f"## Layout\n\n"
        f"Describe how this project organises its files — which directories\n"
        f"exist, what lives where, and where the agent may write.\n\n"
        f"## Conventions\n\n"
        f"Naming, formatting, and workflow rules the agent should follow in\n"
        f"this project.\n\n"
        f"## Workflows\n\n"
        f"The recurring tasks this project is used for, and how to run them.\n"
    )
