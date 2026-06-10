"""Built-in sanitization rules — applied to every text before any
user-defined rules from `<project>/.veles/sanitize.toml` or
`~/.veles/sanitize.toml`.

Ordering rationale:
1. project_root *before* home_dir — project paths usually live under
   `$HOME` and contain it, so the literal `home_dir.replace` would
   otherwise shorten the longer string first and break the project
   match.
2. Secret rules last — they target syntactic shapes (`sk-...`,
   `AKIA...`) that no path can collide with, so relative order vs paths
   is irrelevant. Keeping them grouped helps readers scan the policy.
"""

from __future__ import annotations

import getpass
from pathlib import Path

from veles.core.sanitize.rule import LiteralRule, RegexRule, Rule


def builtin_rules(project_name: str | None, project_root: Path | None) -> list[Rule]:
    """Build the canonical list. `project_name`/`project_root` may be
    None — in that case the `project_root` rule is skipped (no project
    means no project-shaped path to redact)."""
    rules: list[Rule] = []
    if project_name and project_root is not None:
        rules.append(
            LiteralRule(
                name="project_root",
                pattern=str(project_root.resolve()),
                replacement=f"<{project_name}>",
            )
        )
    rules.append(
        LiteralRule(
            name="home_dir",
            pattern=str(Path.home().resolve()),
            replacement="~",
        )
    )
    try:
        os_user = getpass.getuser()
    except Exception:
        os_user = ""
    # Skip the rule when the username is empty or trivially short — a
    # one-letter literal would carpet-bomb the text.
    if os_user and len(os_user) >= 3:
        rules.append(
            LiteralRule(
                name="os_user",
                pattern=os_user,
                replacement="<user>",
            )
        )
    secret_specs = [
        # Anthropic before OpenAI — `sk-ant-...` starts with `sk-`, and
        # the OpenAI rule would otherwise eat the prefix.
        ("secret_anthropic", r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b", "sk-ant-<redacted>"),
        ("secret_openai", r"\bsk-[A-Za-z0-9]{32,}\b", "sk-<redacted>"),
        ("secret_aws", r"\bAKIA[A-Z0-9]{16}\b", "AKIA<redacted>"),
        ("secret_bearer", r"Bearer\s+[A-Za-z0-9._\-]{20,}", "Bearer <token>"),
    ]
    for name, pattern, replacement in secret_specs:
        rule = RegexRule.build(name, pattern, replacement)
        if rule is not None:
            rules.append(rule)
    return rules
