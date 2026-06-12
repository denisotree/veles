"""Tests for core/memory_providers/* — concrete Honcho + Mem0 adapters."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from veles.core.memory.providers.builder import build_extra_providers
from veles.core.memory.providers.honcho import HonchoMemoryProvider
from veles.core.memory.providers.mem0 import Mem0MemoryProvider
from veles.core.memory.providers.supermemory import SupermemoryProvider

# ---------- Honcho adapter ----------


def _install_fake_honcho(monkeypatch: pytest.MonkeyPatch, search_result: Any) -> MagicMock:
    """Drop a fake `honcho_ai` module into sys.modules and return the Honcho
    class mock so the test can assert on call args."""
    fake_client = MagicMock()
    fake_client.search.return_value = search_result
    honcho_cls = MagicMock(return_value=fake_client)
    fake_mod = SimpleNamespace(Honcho=honcho_cls)
    monkeypatch.setitem(sys.modules, "honcho_ai", fake_mod)
    return honcho_cls


def test_honcho_recall_returns_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_honcho(
        monkeypatch,
        [
            {
                "id": "m1",
                "title": "Last conversation",
                "content": "agent discussed X",
                "score": 0.9,
            },
            {"id": "m2", "text": "earlier note", "score": 0.5},
        ],
    )
    p = HonchoMemoryProvider(api_key="key", app_id="app", user_id="u")
    hits = p.recall("X", limit=5)
    assert len(hits) == 2
    assert hits[0].rel_path == "honcho:m1"
    assert "Last conversation" in hits[0].title
    assert hits[0].score == 0.9


def test_honcho_handles_response_with_items_field(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_honcho(
        monkeypatch,
        SimpleNamespace(items=[{"id": "m1", "text": "found"}]),
    )
    p = HonchoMemoryProvider(api_key="k", app_id="a", user_id="u")
    hits = p.recall("q", limit=5)
    assert len(hits) == 1


def test_honcho_no_sdk_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """If `honcho_ai` cannot be imported, recall returns empty list."""
    monkeypatch.setitem(sys.modules, "honcho_ai", None)
    p = HonchoMemoryProvider(api_key="k", app_id="a", user_id="u")
    assert p.recall("q", limit=5) == []


def test_honcho_network_error_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = MagicMock()
    fake_client.search.side_effect = RuntimeError("connection refused")
    monkeypatch.setitem(
        sys.modules, "honcho_ai", SimpleNamespace(Honcho=MagicMock(return_value=fake_client))
    )
    p = HonchoMemoryProvider(api_key="k", app_id="a", user_id="u")
    assert p.recall("q", limit=5) == []


def test_honcho_long_content_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_honcho(monkeypatch, [{"id": "m1", "content": "x" * 1000}])
    p = HonchoMemoryProvider(api_key="k", app_id="a", user_id="u")
    hits = p.recall("q", limit=1)
    assert len(hits[0].summary) <= 200
    assert hits[0].summary.endswith("…")


def test_honcho_base_url_passed_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    honcho_cls = _install_fake_honcho(monkeypatch, [])
    p = HonchoMemoryProvider(
        api_key="k", app_id="a", user_id="u", base_url="https://internal.honcho/"
    )
    p.recall("q", limit=1)
    call_kwargs = honcho_cls.call_args.kwargs
    assert call_kwargs.get("base_url") == "https://internal.honcho/"


# ---------- Mem0 adapter ----------


def _install_fake_mem0(monkeypatch: pytest.MonkeyPatch, search_result: Any) -> MagicMock:
    fake_client = MagicMock()
    fake_client.search.return_value = search_result
    mem_cls = MagicMock(return_value=fake_client)
    fake_mod = SimpleNamespace(MemoryClient=mem_cls)
    monkeypatch.setitem(sys.modules, "mem0", fake_mod)
    return fake_client


def test_mem0_recall_returns_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_mem0(
        monkeypatch,
        {"results": [{"id": "x1", "memory": "prefers concise responses", "score": 0.7}]},
    )
    p = Mem0MemoryProvider(api_key="k", user_id="denisotree")
    hits = p.recall("preferences", limit=3)
    assert len(hits) == 1
    assert hits[0].rel_path == "mem0:x1"
    assert "concise" in hits[0].summary


def test_mem0_handles_bare_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_mem0(monkeypatch, [{"id": "y1", "memory": "stuff"}])
    p = Mem0MemoryProvider(api_key="k", user_id="u")
    assert len(p.recall("q", limit=1)) == 1


def test_mem0_no_sdk_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "mem0", None)
    p = Mem0MemoryProvider(api_key="k", user_id="u")
    assert p.recall("q", limit=5) == []


def test_mem0_propagates_agent_id(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _install_fake_mem0(monkeypatch, [])
    p = Mem0MemoryProvider(api_key="k", user_id="u", agent_id="veles")
    p.recall("q", limit=2)
    kwargs = client.search.call_args.kwargs
    assert kwargs.get("agent_id") == "veles"


# ---------- builder factory ----------


def test_builder_no_config_returns_empty(tmp_path: Path) -> None:
    assert build_extra_providers(tmp_path / "nope.toml") == []


def test_builder_picks_up_honcho_and_mem0(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        """
[memory.external.honcho]
api_key = "h-key"
app_id = "demo"
user_id = "denisotree"

[memory.external.mem0]
api_key = "m-key"
user_id = "denisotree"
"""
    )
    providers = build_extra_providers(cfg)
    names = sorted(getattr(p, "name", "?") for p in providers)
    assert names == ["honcho", "mem0"]


# ---------- Supermemory adapter ----------


def _install_fake_supermemory(
    monkeypatch: pytest.MonkeyPatch,
    search_result: Any,
    *,
    accept_kw: str = "q",
) -> MagicMock:
    """Plant a fake `supermemory.Supermemory` whose .search accepts only
    the `accept_kw` keyword (`q` or `query`). Helps test the fallback."""
    fake_client = MagicMock()

    def _search(**kw: Any) -> Any:
        if accept_kw not in kw:
            raise TypeError(f"unexpected keyword in {sorted(kw)}")
        return search_result

    fake_client.search.side_effect = _search
    sm_cls = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "supermemory", SimpleNamespace(Supermemory=sm_cls))
    return fake_client


def test_supermemory_recall_returns_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_supermemory(
        monkeypatch,
        {"results": [{"id": "s1", "content": "long-term fact", "score": 0.95}]},
    )
    p = SupermemoryProvider(api_key="k")
    hits = p.recall("fact", limit=3)
    assert len(hits) == 1
    assert hits[0].rel_path == "supermemory:s1"
    assert "long-term fact" in hits[0].summary


def test_supermemory_falls_back_from_q_to_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the SDK rejects `q=`, retry with `query=`."""
    _install_fake_supermemory(
        monkeypatch,
        [{"id": "s1", "memory": "ok"}],
        accept_kw="query",
    )
    p = SupermemoryProvider(api_key="k")
    hits = p.recall("test", limit=1)
    assert len(hits) == 1


def test_supermemory_no_sdk_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "supermemory", None)
    p = SupermemoryProvider(api_key="k")
    assert p.recall("q", limit=5) == []


def test_supermemory_handles_documents_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_supermemory(
        monkeypatch, {"documents": [{"id": "d1", "title": "doc", "content": "x"}]}
    )
    p = SupermemoryProvider(api_key="k")
    assert len(p.recall("q", limit=1)) == 1


def test_supermemory_user_id_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _install_fake_supermemory(monkeypatch, {"results": []})
    p = SupermemoryProvider(api_key="k", user_id="denisotree")
    p.recall("q", limit=1)
    kwargs = client.search.call_args.kwargs
    assert kwargs.get("user_id") == "denisotree"


def test_builder_picks_up_all_three(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        """
[memory.external.honcho]
api_key = "h"
app_id = "a"
user_id = "u"

[memory.external.mem0]
api_key = "m"
user_id = "u"

[memory.external.supermemory]
api_key = "s"
user_id = "u"
"""
    )
    providers = build_extra_providers(cfg)
    names = sorted(getattr(p, "name", "?") for p in providers)
    assert names == ["honcho", "mem0", "supermemory"]


def test_builder_skips_supermemory_without_api_key(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        """
[memory.external.supermemory]
user_id = "u"
"""
    )
    assert build_extra_providers(cfg) == []


def test_builder_skips_partial_section(tmp_path: Path) -> None:
    """An incomplete provider config (missing required key) is silently dropped."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        """
[memory.external.honcho]
api_key = "h-key"
# app_id missing on purpose
user_id = "denisotree"

[memory.external.mem0]
api_key = "m-key"
user_id = "denisotree"
"""
    )
    providers = build_extra_providers(cfg)
    assert [getattr(p, "name", "?") for p in providers] == ["mem0"]


def test_builder_malformed_toml_returns_empty(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text("not = toml = at all")
    assert build_extra_providers(cfg) == []
