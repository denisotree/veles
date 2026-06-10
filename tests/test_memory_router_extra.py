"""Tests for the M55 extra-provider plug-in surface on MemoryRouter."""

from __future__ import annotations

from pathlib import Path

from veles.core.memory.router import MemoryRouter, RecallHit, _interleave_many
from veles.core.project import Project


class _StaticProvider:
    """Minimal MemoryProvider implementation for tests."""

    name = "static"

    def __init__(self, hits: list[RecallHit]) -> None:
        self._hits = hits
        self.last_query: str | None = None

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        self.last_query = query
        return self._hits[:limit]


class _ExplodingProvider:
    name = "boom"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        del query, limit
        raise RuntimeError("upstream is down")


def _project(tmp_path: Path) -> Project:
    state = tmp_path / ".veles"
    state.mkdir(parents=True, exist_ok=True)
    (tmp_path / "wiki").mkdir(exist_ok=True)
    return Project(root=tmp_path, name="t", created_at=0.0)


# ---------- _interleave_many ----------


def test_interleave_many_round_robins() -> None:
    a = [RecallHit("a1", "A1", ""), RecallHit("a2", "A2", "")]
    b = [RecallHit("b1", "B1", "")]
    c = [RecallHit("c1", "C1", ""), RecallHit("c2", "C2", "")]
    out = _interleave_many([a, b, c], limit=10)
    # Cycle 1: a1, b1, c1; cycle 2: a2, c2.
    assert [h.title for h in out] == ["A1", "B1", "C1", "A2", "C2"]


def test_interleave_many_respects_limit() -> None:
    a = [RecallHit(f"a{i}", f"A{i}", "") for i in range(5)]
    out = _interleave_many([a], limit=2)
    assert len(out) == 2


def test_interleave_many_empty_streams_safe() -> None:
    assert _interleave_many([[], []], limit=5) == []


# ---------- MemoryRouter extra_providers ----------


def test_router_calls_extra_providers(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    ext = _StaticProvider([RecallHit("ext:1", "from honcho", "summary")])
    router = MemoryRouter(proj, extra_providers=[ext])
    hits = router.recall("hello world", limit=5)
    assert any(h.title == "from honcho" for h in hits)
    assert ext.last_query == "hello world"


def test_router_swallows_provider_exceptions(tmp_path: Path) -> None:
    """A broken extra provider must not kill the recall — wiki+turns still
    return whatever they have, plus surviving providers."""
    proj = _project(tmp_path)
    good = _StaticProvider([RecallHit("ok:1", "good hit", "")])
    bad = _ExplodingProvider()
    router = MemoryRouter(proj, extra_providers=[bad, good])
    hits = router.recall("ping", limit=5)
    # The good provider's hit is present; the exception was swallowed.
    assert any(h.title == "good hit" for h in hits)


def test_router_with_no_extra_providers_is_unchanged(tmp_path: Path) -> None:
    """Back-compat: existing callers that don't pass extra_providers see
    the same behaviour as before M55."""
    proj = _project(tmp_path)
    router = MemoryRouter(proj)
    assert router.recall("anything", limit=3) == []


def test_router_empty_query_short_circuits(tmp_path: Path) -> None:
    """Empty query doesn't fire any provider — recall is wasted work."""
    proj = _project(tmp_path)
    ext = _StaticProvider([RecallHit("ext:1", "x", "")])
    router = MemoryRouter(proj, extra_providers=[ext])
    assert router.recall("   ", limit=5) == []
    assert ext.last_query is None
