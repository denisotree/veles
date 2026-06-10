"""Pluggable text sanitization for boundaries that emit or persist
agent-visible content.

Why a module instead of a one-off helper: the same redaction policy
needs to apply to the system prompt, conversation history (read +
write), tool outputs, and HTTP responses — five different boundaries
sharing one set of rules. Inlining the policy at each site led to the
Mind Palace regression (Round 1 fixed the system prompt but missed
`SessionStore`, `write_file`, `SandboxViolation`, and daemon endpoints).

Rule sources, in precedence order (later wins on overlap):
1. Built-in rules — project root, $HOME, OS user, common secret
   shapes. See `builtin.py` for the exact list.
2. `~/.veles/sanitize.toml` — user-global custom rules.
3. `<project>/.veles/sanitize.toml` — project-local overrides.

Public entry point: `sanitize(text, project=None)`.
"""

from __future__ import annotations

from veles.core.context import current_project
from veles.core.project import Project
from veles.core.sanitize.loader import clear_cache, load_rules
from veles.core.sanitize.rule import LiteralRule, RegexRule, Rule, RuleSet


def sanitize(text: str, project: Project | None = None) -> str:
    """Apply the active rule set to `text`.

    `project` defaults to `current_project()`. A `None` project is
    fine — context-free rules still run (secrets, OS user, $HOME),
    only the `project_root` rule is skipped."""
    if not text:
        return text
    effective = project if project is not None else current_project()
    rules = load_rules(effective)
    return rules.apply(text)


__all__ = [
    "LiteralRule",
    "RegexRule",
    "Rule",
    "RuleSet",
    "clear_cache",
    "load_rules",
    "sanitize",
]
