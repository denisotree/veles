"""M118c: relevant_semantic — embedding-aware ranking with token
fallback when no adapter is registered.

We don't need a real embedding model — a stub adapter returns
deterministic vectors keyed on substring presence, which is enough
to verify the call path + ordering + fallback semantics."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from veles.core.project_tree import (
    Scanner,
    ensure_table,
    relevant,
    relevant_semantic,
)
from veles.modules import (
    register_embedding_adapter,
    reset_embedding_adapter,
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    reset_embedding_adapter()
    yield
    reset_embedding_adapter()


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    ensure_table(c)
    return c


def _make_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir()
    (root / "src" / "auth.py").write_text("print(1)\n")
    (root / "src" / "billing.py").write_text("print(2)\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_auth.py").write_text("def test_x(): pass\n")
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("# Guide\n")
    return root


class _KeywordEmbedding:
    """Stub: vector is a one-hot encoding over a fixed keyword set.
    Cosine similarity between query and entry signatures is high
    when they share keywords — gives us a deterministic ranking we
    can assert against without spinning up Ollama."""

    name = "stub-kw"
    dim = 5

    _VOCAB = ("auth", "billing", "test", "doc", "src")

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        out = []
        for text in texts:
            low = text.lower()
            vec = [1.0 if kw in low else 0.0 for kw in self._VOCAB]
            # Avoid all-zero vectors (cosine undefined)
            if not any(vec):
                vec[0] = 0.1
            out.append(vec)
        return out


# ---- fallback when no adapter ----


def test_no_adapter_falls_back_to_token_ranking(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """With no embedding adapter registered, `relevant_semantic`
    returns whatever `relevant` (token-based) returns."""
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    semantic_hits = relevant_semantic(conn, "auth", limit=5)
    token_hits = relevant(conn, "auth", limit=5)
    # Same ordering when fallback path is hit
    assert [h.rel_path for h in semantic_hits] == [h.rel_path for h in token_hits]


def test_empty_query_returns_empty_with_adapter(conn: sqlite3.Connection, tmp_path: Path) -> None:
    register_embedding_adapter(_KeywordEmbedding())
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    assert relevant_semantic(conn, "", limit=5) == []


def test_empty_tree_returns_empty(conn: sqlite3.Connection) -> None:
    """No project_tree rows → empty list regardless of adapter."""
    register_embedding_adapter(_KeywordEmbedding())
    assert relevant_semantic(conn, "anything", limit=5) == []


# ---- happy path with stub adapter ----


def test_semantic_ranks_relevant_files_first(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Query containing 'auth' ranks auth-related entries above
    billing/docs entries via the stub's keyword-overlap cosine."""
    register_embedding_adapter(_KeywordEmbedding())
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()

    hits = relevant_semantic(conn, "auth login", limit=10)
    rel_paths = [h.rel_path for h in hits]
    # auth-named files should appear before non-auth ones
    auth_positions = [i for i, p in enumerate(rel_paths) if "auth" in p]
    other_positions = [i for i, p in enumerate(rel_paths) if "auth" not in p]
    assert auth_positions, "expected at least one auth hit"
    # Best auth hit ranks above worst non-auth hit
    if auth_positions and other_positions:
        assert min(auth_positions) < max(other_positions)


def test_semantic_respects_limit(conn: sqlite3.Connection, tmp_path: Path) -> None:
    register_embedding_adapter(_KeywordEmbedding())
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    hits = relevant_semantic(conn, "src", limit=2)
    assert len(hits) == 2


def test_semantic_invokes_adapter_with_query_and_signatures(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    """The adapter receives two embed calls: one with the user query,
    one with the per-entry signatures."""
    adapter = _KeywordEmbedding()
    register_embedding_adapter(adapter)
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    relevant_semantic(conn, "test files", limit=3)

    assert len(adapter.calls) == 2
    # First call is the query
    assert adapter.calls[0] == ["test files"]
    # Second is the entries — non-empty list of signatures
    assert len(adapter.calls[1]) > 0
    # Signatures embed path text
    assert any("auth.py" in sig for sig in adapter.calls[1])


# ---- error handling ----


def test_adapter_failure_falls_back_to_token(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """If the adapter raises EmbeddingError mid-query, we fall back
    to token ranking transparently — never break the user's turn."""
    from veles.modules import EmbeddingError

    class _Flaky:
        name = "flaky"
        dim = 4

        def embed(self, texts: list[str]) -> list[list[float]]:
            raise EmbeddingError("simulated network failure")

    register_embedding_adapter(_Flaky())
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()

    # Should not raise — returns whatever the token-based path gives
    hits = relevant_semantic(conn, "auth", limit=5)
    assert isinstance(hits, list)


# ---- M216: per-entry embedding cache ----


def _sig_batches(adapter: _KeywordEmbedding) -> list[list[str]]:
    """The embed calls that carried entry signatures (not the bare query).
    An entry signature contains a '/'-free path token like 'auth.py'."""
    return [batch for batch in adapter.calls if any(".py" in t or ".md" in t for t in batch)]


def test_semantic_caches_entry_embeddings(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Second query on an unchanged tree re-embeds zero entry signatures —
    only the (uncacheable) user query is embedded again. This is the M216
    hot-path fix: relevant_semantic used to embed the whole tree every turn."""
    adapter = _KeywordEmbedding()
    register_embedding_adapter(adapter)
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()

    relevant_semantic(conn, "auth", limit=10)
    batches_after_first = len(_sig_batches(adapter))
    assert batches_after_first == 1  # cold cache: all signatures embedded once

    relevant_semantic(conn, "billing", limit=10)
    # No new signature batch — every entry served from cache.
    assert len(_sig_batches(adapter)) == batches_after_first


def test_semantic_embeds_only_new_entries_after_change(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    """Adding a file re-embeds only its signature, not the whole tree."""
    adapter = _KeywordEmbedding()
    register_embedding_adapter(adapter)
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    relevant_semantic(conn, "auth", limit=10)

    (root / "src" / "payments.py").write_text("print(3)\n")
    Scanner(root, conn).scan()
    adapter.calls.clear()
    relevant_semantic(conn, "auth", limit=10)

    sig_batches = _sig_batches(adapter)
    assert len(sig_batches) == 1
    embedded = sig_batches[0]
    assert any("payments.py" in s for s in embedded)  # the new file
    assert not any("billing.py" in s for s in embedded)  # unchanged → cached


def test_returns_typed_entries(conn: sqlite3.Connection, tmp_path: Path) -> None:
    from veles.core.project_tree import TreeEntry

    register_embedding_adapter(_KeywordEmbedding())
    root = _make_project(tmp_path / "proj")
    Scanner(root, conn).scan()
    hits = relevant_semantic(conn, "src auth", limit=3)
    for h in hits:
        assert isinstance(h, TreeEntry)
        assert h.kind in {"file", "dir"}
