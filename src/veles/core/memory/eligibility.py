"""The single predicate deciding whether an insight may reach recall (M258).

Before M258 the answer was spelled as raw SQL in six places:

    id NOT IN (SELECT from_insight_id FROM insight_refs)

which conflated two different statements — "A links to B" and "A was
superseded by B" were the same row. `insight_refs` is documented as a
generic relation table, so the moment a second relation kind is stored
there (`extends`, `derives`, "see also"), every linked insight would
silently vanish from recall. That is a correctness bug waiting on a
feature, not a style problem.

M258 moves supersession onto its own column (`insights.superseded_by`)
and funnels every query through `eligible_sql()`, so the next filter
(visibility, expiry, review state) is added in one place instead of six.

M260 is that next filter, and it subsumes the first: `hidden_at` records
*that* a row left recall and `hidden_reason` records *why*, while
`superseded_by` keeps the pointer to whatever replaced it. Dedup writes
all three, so eligibility asks the visibility column alone. Nothing
deletes from `insights` — hiding is the only way a fact leaves recall,
which is what keeps the removal reversible (clear the columns) and
explainable (`/insights` prints the reason).

The predicate is deliberately a SQL fragment rather than a Python filter:
all six call sites are SQL, and pulling ineligible rows into Python just
to drop them would make recall pay for what the database can exclude.
"""

from __future__ import annotations

__all__ = ["eligible_sql"]


def eligible_sql(alias: str = "") -> str:
    """Return the SQL predicate for "this insight may be recalled".

    `alias` is the table alias used by the calling query (`"i"` for
    `FROM insights i`); empty means the columns are unqualified.
    """
    prefix = f"{alias}." if alias else ""
    return f"{prefix}hidden_at IS NULL"
