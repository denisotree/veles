"""M139: the "house rules" digest.

Curator and the insight-extractor save behavioural rules via
`memory_save_rule(kind="preference|do|dont|format")`, but until M139 nothing
read them back — they reached only the `/rules` inspector. This module renders
the highest-ranked rules into a small markdown block that `cli/_runtime.py`
injects into the **stable** (cacheable) part of the run system prompt, next to
AGENTS.md. Stable, not the per-turn `<memory-context>`, because rules are
query-independent and change rarely: keeping them turn-stable preserves prompt
caching.

The block is hard-capped (top-N + char budget) to honour the "AGENTS.md stays
small" design constraint — when it can't fit, the lowest-ranked rules are
dropped first, so the most-decayed/most-applied rules always survive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from veles.core.i18n import t

if TYPE_CHECKING:
    from veles.core.memory import RuleRow, SessionStore

_DEFAULT_LIMIT = 12
_DEFAULT_CHAR_BUDGET = 1500

# Render order and the i18n label key per `rules` CHECK kind.
_GROUP_ORDER = ("preference", "dont", "do", "format")


def _render(rows: list[RuleRow]) -> str:
    lines = [f"## {t('rules_digest.header')}"]
    for kind in _GROUP_ORDER:
        group = [r for r in rows if r.kind == kind]
        if not group:
            continue
        lines.append(t(f"rules_digest.group_{kind}"))
        lines.extend(f"- {r.body}" for r in group)
    return "\n".join(lines)


def build_rules_digest(
    store: SessionStore,
    *,
    limit: int = _DEFAULT_LIMIT,
    char_budget: int = _DEFAULT_CHAR_BUDGET,
) -> str | None:
    """Return the house-rules block, or `None` when there are no rules.

    Rows arrive rank-ordered from `SessionStore.top_rules`; if the rendered
    block overflows `char_budget`, the lowest-ranked rule is dropped and the
    block re-rendered until it fits (highest-ranked rules always kept)."""
    rows = store.top_rules(limit=limit)
    while rows:
        block = _render(rows)
        if len(block) <= char_budget:
            return block
        rows = rows[:-1]
    return None


__all__ = ["build_rules_digest"]
