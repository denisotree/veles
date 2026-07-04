"""TUI /insights slash command — surfaces M119 insights table rows."""

from __future__ import annotations

import time

from veles.cli.repl.slash import build_default_registry
from veles.core.memory import SessionStore


def _reg():
    return build_default_registry()


def _seed_insight(project, *, title: str, body: str, category: str, created_at: float) -> None:
    store = SessionStore(project.memory_db_path)
    store._conn.execute(
        "INSERT INTO insights(title, body, category, created_at) VALUES (?, ?, ?, ?)",
        (title, body, category, created_at),
    )
    store._conn.close()


# ---- empty + basic ----


def test_insights_empty_project(slash_ctx) -> None:
    res = _reg().dispatch("/insights", slash_ctx)
    assert res is not None and not res.is_error
    assert "no insights" in res.text.lower()


def test_insights_lists_recent_across_categories(slash_ctx) -> None:
    now = time.time()
    _seed_insight(
        slash_ctx.project,
        title="Embedding backend not configured",
        body="install ollama or set OPENROUTER_API_KEY",
        category="setup-hint",
        created_at=now - 10,
    )
    _seed_insight(
        slash_ctx.project,
        title="Skill suggestion: wiki_search → wiki_read_page",
        body="3 reps detected",
        category="skill-suggestion",
        created_at=now,
    )
    res = _reg().dispatch("/insights", slash_ctx)
    assert res is not None and not res.is_error
    # Both titles present, newest first
    text = res.text
    assert "Skill suggestion" in text
    assert "Embedding backend" in text
    assert text.index("Skill suggestion") < text.index("Embedding backend")
    # Category markers visible
    assert "[setup-hint]" in text
    assert "[skill-suggestion]" in text


# ---- filtering ----


def test_insights_filtered_by_category(slash_ctx) -> None:
    now = time.time()
    _seed_insight(
        slash_ctx.project,
        title="A",
        body="x",
        category="setup-hint",
        created_at=now - 5,
    )
    _seed_insight(
        slash_ctx.project,
        title="B",
        body="y",
        category="skill-suggestion",
        created_at=now,
    )
    res = _reg().dispatch("/insights setup-hint", slash_ctx)
    assert res is not None
    assert "A" in res.text
    assert "B" not in res.text
    assert "category=setup-hint" in res.text


def test_insights_unknown_category_returns_friendly_empty(slash_ctx) -> None:
    res = _reg().dispatch("/insights nonexistent-category", slash_ctx)
    assert res is not None and not res.is_error
    assert "no insights" in res.text.lower()
    assert "nonexistent-category" in res.text


# ---- limit ----


def test_insights_default_limit_ten(slash_ctx) -> None:
    now = time.time()
    for i in range(15):
        _seed_insight(
            slash_ctx.project,
            title=f"row {i}",
            body="x",
            category="format",
            created_at=now + i,
        )
    res = _reg().dispatch("/insights", slash_ctx)
    # Header lists "latest 10"
    assert "latest 10" in res.text


def test_insights_all_with_custom_limit(slash_ctx) -> None:
    now = time.time()
    for i in range(15):
        _seed_insight(
            slash_ctx.project,
            title=f"row {i}",
            body="x",
            category="format",
            created_at=now + i,
        )
    res = _reg().dispatch("/insights all 5", slash_ctx)
    assert "latest 5" in res.text


def test_insights_category_with_custom_limit(slash_ctx) -> None:
    now = time.time()
    for i in range(8):
        _seed_insight(
            slash_ctx.project,
            title=f"hint {i}",
            body="x",
            category="setup-hint",
            created_at=now + i,
        )
    res = _reg().dispatch("/insights setup-hint 3", slash_ctx)
    assert "latest 3" in res.text
    # Only the 3 newest hint rows surfaced
    titles_shown = [f"hint {i}" for i in range(8) if f"hint {i}" in res.text]
    assert len(titles_shown) == 3
    # And those are the 3 highest indices (most recent)
    assert "hint 7" in res.text
    assert "hint 0" not in res.text


# ---- registry exposure ----


def test_insights_in_help_listing(slash_ctx) -> None:
    res = _reg().dispatch("/help", slash_ctx)
    assert "/insights" in res.text


def test_insights_discoverable_by_completer() -> None:
    assert "/insights" in _reg().names()
