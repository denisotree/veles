"""M125: TUI `/rules` slash command — surfaces M119 `rules` table rows."""

from __future__ import annotations

import time

from veles.cli.repl.slash import build_default_registry
from veles.core.memory import SessionStore


def _reg():
    return build_default_registry()


def _seed_rule(project, *, kind: str, body: str, source: str, created_at: float) -> None:
    store = SessionStore(project.memory_db_path)
    store._conn.execute(
        "INSERT INTO rules(kind, body, source, created_at) VALUES (?, ?, ?, ?)",
        (kind, body, source, created_at),
    )
    store._conn.commit()
    store._conn.close()


# ---- empty + basic ----


def test_rules_empty_project(slash_ctx) -> None:
    res = _reg().dispatch("/rules", slash_ctx)
    assert res is not None and not res.is_error
    assert "no rules" in res.text.lower()


def test_rules_lists_recent_across_kinds(slash_ctx) -> None:
    now = time.time()
    _seed_rule(
        slash_ctx.project,
        kind="preference",
        body="User prefers terse responses",
        source="session-1",
        created_at=now - 10,
    )
    _seed_rule(
        slash_ctx.project,
        kind="dont",
        body="Never commit without running tests",
        source="session-2",
        created_at=now,
    )
    res = _reg().dispatch("/rules", slash_ctx)
    assert res is not None and not res.is_error
    text = res.text
    assert "terse" in text
    assert "Never commit" in text
    # Newest first
    assert text.index("Never commit") < text.index("terse")
    # Kind markers visible
    assert "[preference]" in text
    assert "[dont]" in text


# ---- filtering ----


def test_rules_filtered_by_kind(slash_ctx) -> None:
    now = time.time()
    _seed_rule(
        slash_ctx.project,
        kind="do",
        body="A do-rule",
        source="src",
        created_at=now - 5,
    )
    _seed_rule(
        slash_ctx.project,
        kind="preference",
        body="A preference-rule",
        source="src",
        created_at=now,
    )
    res = _reg().dispatch("/rules do", slash_ctx)
    assert res is not None
    assert "A do-rule" in res.text
    assert "preference-rule" not in res.text
    assert "kind=do" in res.text


def test_rules_unknown_kind_returns_friendly_empty(slash_ctx) -> None:
    res = _reg().dispatch("/rules bogus-kind", slash_ctx)
    assert res is not None and not res.is_error
    assert "no rules" in res.text.lower()
    assert "bogus-kind" in res.text


# ---- limit ----


def test_rules_default_limit_ten(slash_ctx) -> None:
    now = time.time()
    for i in range(15):
        _seed_rule(
            slash_ctx.project,
            kind="format",
            body=f"row {i}",
            source="src",
            created_at=now + i,
        )
    res = _reg().dispatch("/rules", slash_ctx)
    assert "latest 10" in res.text


def test_rules_all_with_custom_limit(slash_ctx) -> None:
    now = time.time()
    for i in range(15):
        _seed_rule(
            slash_ctx.project,
            kind="format",
            body=f"row {i}",
            source="src",
            created_at=now + i,
        )
    res = _reg().dispatch("/rules all 5", slash_ctx)
    assert "latest 5" in res.text


# ---- body truncation ----


def test_rules_truncates_long_bodies(slash_ctx) -> None:
    """Rule bodies over 120 chars are truncated for the inline list view."""
    long_body = "X" * 200
    _seed_rule(
        slash_ctx.project,
        kind="format",
        body=long_body,
        source="src",
        created_at=time.time(),
    )
    res = _reg().dispatch("/rules", slash_ctx)
    # ellipsis present, full body not
    assert "…" in res.text
    assert long_body not in res.text


# ---- registry exposure ----


def test_rules_in_help_listing(slash_ctx) -> None:
    res = _reg().dispatch("/help", slash_ctx)
    assert "/rules" in res.text


def test_rules_discoverable_by_completer() -> None:
    assert "/rules" in _reg().names()
