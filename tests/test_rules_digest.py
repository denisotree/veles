"""M139: extracted behavioural rules surface back into the agent via a small,
capped, turn-stable "house rules" digest injected into the stable (cacheable)
part of the run system prompt.

Two units under test:
  - `SessionStore.top_rules(limit)` — ranked read of the `rules` table.
  - `build_rules_digest(store, ...)` — markdown block, grouped by kind, capped.
"""

from __future__ import annotations

import time
from pathlib import Path

from veles.core.memory import SessionStore


def _insert_rule(
    store: SessionStore,
    *,
    kind: str,
    body: str,
    decay_score: float = 1.0,
    created_at: float | None = None,
    last_applied_at: float | None = None,
) -> None:
    store._conn.execute(
        "INSERT INTO rules(kind, body, source, created_at, last_applied_at, decay_score)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (kind, body, "extracted", created_at if created_at is not None else time.time(),
         last_applied_at, decay_score),
    )
    store._conn.commit()


# ---- SessionStore.top_rules ----


def test_top_rules_orders_by_decay_then_recency(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        _insert_rule(store, kind="do", body="low decay", decay_score=0.2, created_at=100.0)
        _insert_rule(store, kind="preference", body="high decay", decay_score=0.9, created_at=50.0)
        _insert_rule(store, kind="dont", body="mid decay", decay_score=0.5, created_at=200.0)
        rows = store.top_rules(limit=10)
    finally:
        store.close()
    bodies = [r.body for r in rows]
    assert bodies == ["high decay", "mid decay", "low decay"]


def test_top_rules_honours_limit(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        for i in range(5):
            _insert_rule(store, kind="do", body=f"rule {i}", decay_score=1.0, created_at=float(i))
        rows = store.top_rules(limit=2)
    finally:
        store.close()
    assert len(rows) == 2


def test_top_rules_empty_when_no_rules(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        assert store.top_rules(limit=10) == []
    finally:
        store.close()


# ---- build_rules_digest ----


def test_rules_digest_none_when_empty(tmp_path: Path) -> None:
    from veles.core.memory.rules_digest import build_rules_digest

    store = SessionStore(tmp_path / "m.db")
    try:
        assert build_rules_digest(store) is None
    finally:
        store.close()


def test_rules_digest_groups_by_kind(tmp_path: Path) -> None:
    from veles.core.memory.rules_digest import build_rules_digest

    store = SessionStore(tmp_path / "m.db")
    try:
        _insert_rule(store, kind="do", body="run tests before commit", decay_score=1.0)
        _insert_rule(store, kind="preference", body="answer in metric units", decay_score=1.0)
        _insert_rule(store, kind="dont", body="never touch generated files", decay_score=1.0)
        digest = build_rules_digest(store)
    finally:
        store.close()
    assert digest is not None
    # all three bodies present
    assert "answer in metric units" in digest
    assert "run tests before commit" in digest
    assert "never touch generated files" in digest
    # preferences come before do-rules (grouping order)
    assert digest.index("answer in metric units") < digest.index("run tests before commit")


def test_rules_digest_respects_char_budget(tmp_path: Path) -> None:
    from veles.core.memory.rules_digest import build_rules_digest

    store = SessionStore(tmp_path / "m.db")
    try:
        # high-decay rule must survive; low-decay long ones get dropped under budget
        _insert_rule(store, kind="preference", body="KEEP ME", decay_score=1.0)
        for i in range(40):
            _insert_rule(store, kind="do", body=f"dropme padding rule number {i} " * 5, decay_score=0.1)
        digest = build_rules_digest(store, limit=50, char_budget=400)
    finally:
        store.close()
    assert digest is not None
    assert len(digest) <= 400
    assert "KEEP ME" in digest  # highest-ranked always kept
