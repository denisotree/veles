"""M230 — a long free-text query must not silently retrieve nothing.

Recall is keyed on the raw prompt (`cli/_runtime.py`), and `_fts_escape_query`
quoted every token and joined them with FTS5's implicit AND. That demands one
stored row contain *every* token of the query, so a paragraph — or a pasted
alert payload, where timestamps, ids and metric values never recur — matched
nothing at all. No `<memory-context>` block was emitted and nothing was logged:
a total, silent retrieval failure for exactly the prompts that needed memory.

Short queries still use AND, so keyword lookups are unchanged.
"""

from __future__ import annotations

import pytest

from veles.core.memory import SessionStore, _fts_escape_query
from veles.core.provider import Message


@pytest.fixture()
def store() -> SessionStore:
    return SessionStore(":memory:")


def _seed(store: SessionStore, content: str) -> None:
    store.append_turn(store.create_session(), Message(role="user", content=content))


# ---- expression shape --------------------------------------------------------


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_query_still_yields_no_expression(query: str) -> None:
    assert _fts_escape_query(query) == ""


@pytest.mark.parametrize(
    "query",
    ["cosine", "cpu_saturation noisy", "alpha beta gamma", "one two three four"],
)
def test_short_query_keeps_strict_and(query: str) -> None:
    """Unchanged behaviour for keyword lookups — the precision case."""
    expected = " ".join(f'"{token}"' for token in query.split())
    assert _fts_escape_query(query) == expected


def test_long_query_switches_to_or() -> None:
    expr = _fts_escape_query("how does the curator decide what to keep in project memory")
    assert " OR " in expr
    assert '"curator"' in expr


def test_long_query_drops_stopwords_and_numeric_noise() -> None:
    expr = _fts_escape_query(
        "Alert cpu_saturation fired on instance pay-03 value 87.4 threshold 80 at 2026-08-17T10:00Z"
    )
    assert '"cpu_saturation"' in expr
    for noise in ('"the"', '"at"', '"on"', '"80"', '"87"', '"00Z"', '"17T10"'):
        assert noise not in expr


def test_or_fan_out_is_bounded() -> None:
    """A pasted wall of text must not become a 500-term MATCH."""
    expr = _fts_escape_query(" ".join(f"distinctword{i}" for i in range(200)))
    assert expr.count(" OR ") <= 7  # 8 terms → 7 separators


def test_quotes_in_a_long_query_cannot_break_the_parser(store: SessionStore) -> None:
    _seed(store, "the deployment pipeline rejects unsigned artifacts")
    # Must not raise — every term is quoted, inner quotes doubled.
    store.search_turns('why does the "deployment" pipeline reject my unsigned artifacts today')


# ---- end-to-end: the actual failure being fixed -------------------------------


def test_long_prompt_retrieves_a_related_turn(store: SessionStore) -> None:
    """The regression. Every token of the prompt is NOT in the stored row."""
    _seed(store, "rule cpu_saturation is noisy on weekends for the payments cluster")

    hits = store.search_turns(
        "Alert cpu_saturation fired on instance pay-03 value 87.4 threshold 80 at 2026-08-17"
    )

    assert hits, "a long prompt sharing a distinctive term must not retrieve nothing"
    assert "cpu_saturation" in hits[0].content


def test_long_prompt_still_ranks_the_better_match_first(store: SessionStore) -> None:
    """OR without ranking would be noise; bm25 has to keep the ordering useful."""
    _seed(store, "the nightly backup window is unrelated to alerting")
    _seed(store, "cpu_saturation on pay-03 threshold breach was a real incident")

    hits = store.search_turns(
        "Alert cpu_saturation fired on instance pay-03 threshold breach at 2026-08-17"
    )

    assert len(hits) >= 1
    assert "cpu_saturation" in hits[0].content


def test_long_query_matching_nothing_still_returns_empty(store: SessionStore) -> None:
    _seed(store, "the deployment pipeline rejects unsigned artifacts")
    assert store.search_turns("quaternion interpolation for skeletal animation blending") == []


def test_shared_function_words_do_not_manufacture_matches(store: SessionStore) -> None:
    """The failure mode OR introduces, if the stopword list is too thin.

    Empty and noisy are NOT equivalent outcomes: an absent `<memory-context>`
    block says nothing, while an injected one reads to the model as relevant.
    Every seeded turn here opens with an interrogative, so a topically unrelated
    question would match all of them on "how"/"what"/"when" alone.
    """
    for content in (
        "how do I rotate the API key for this project",
        "how does the curator decide what to keep",
        "what happens when the deploy pipeline rejects unsigned artifacts",
        "when should I use a subproject instead of a new project",
    ):
        _seed(store, content)

    unrelated = "how do I configure quaternion interpolation for skeletal animation blending"
    assert store.search_turns(unrelated) == []

    # ...while a query that shares real topic words still hits.
    assert store.search_turns("how does the curator decide which sessions to keep in memory")


def test_wiki_search_shares_the_same_escaper(store: SessionStore) -> None:
    """Wiki is one of the five recall streams — it must not stay on plain AND.

    Otherwise a long prompt retrieves turns and insights but zero wiki pages.
    """
    from veles.core.fts import escape_query
    from veles.modules.wiki.wiki import _fts_escape

    assert _fts_escape is escape_query
    assert _fts_escape_query is escape_query


def test_insight_search_gets_the_same_treatment(store: SessionStore) -> None:
    store._conn.execute(
        "INSERT INTO insights(title, body, category, created_at, confidence) VALUES (?,?,?,?,?)",
        ("cpu_saturation is noisy", "It fires on weekends for the payments cluster", "x", 1.0, 1.0),
    )
    hits = store.search_insights(
        "Alert cpu_saturation fired on instance pay-03 value 87.4 at 2026-08-17"
    )
    assert hits
