"""`tui.screens._model_fetcher.fetch_models` — cache / live / curated
strategy per provider class."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from veles.tui.screens import _model_fetcher as mf


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Pin VELES_USER_HOME so caches land in pytest tmp, not the user's real one."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles_home"))


def _write_cache_file(provider: str, models: list[str], age_seconds: float = 0.0) -> Path:
    path = mf._cache_path(provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(UTC) - timedelta(seconds=age_seconds)
    path.write_text(
        json.dumps({"fetched_at": fetched_at.isoformat(timespec="seconds"), "models": models}),
        encoding="utf-8",
    )
    return path


def _make_provider_returning(models: list[str] | None, raises: Exception | None = None):
    """Return a fake `_make_provider` that yields an adapter whose
    `list_models()` returns `models` (or raises if `raises` is set)."""
    adapter = MagicMock()
    if raises is not None:
        adapter.list_models = MagicMock(side_effect=raises)
    elif models is not None:
        adapter.list_models = MagicMock(return_value=models)
    else:
        del adapter.list_models  # adapter doesn't expose list_models at all
    return MagicMock(return_value=adapter)


# ---------- cloud cacheable ----------


def test_cloud_fresh_cache_hits_without_calling_adapter() -> None:
    _write_cache_file("openrouter", ["cached-a", "cached-b"], age_seconds=60)
    fake_make = MagicMock(side_effect=AssertionError("must not be called"))
    with patch("veles.cli._make_provider", fake_make):
        result = mf.fetch_models("openrouter")
    assert result.source == "cache"
    assert result.models == ["cached-a", "cached-b"]
    fake_make.assert_not_called()


def test_cloud_stale_cache_triggers_live_and_overwrites() -> None:
    cache_file = _write_cache_file("openrouter", ["stale"], age_seconds=mf.CACHE_TTL_SECONDS + 10)
    fake_make = _make_provider_returning(["anthropic/claude-opus-4.7", "openai/gpt-4o"])
    with patch("veles.cli._make_provider", fake_make):
        result = mf.fetch_models("openrouter")
    assert result.source == "live"
    # live first, curated names deduped onto the tail
    assert result.models[0] == "anthropic/claude-opus-4.7"
    assert "openai/gpt-4o" in result.models
    rewritten = json.loads(cache_file.read_text(encoding="utf-8"))
    assert rewritten["models"] == result.models


def test_cloud_refresh_skips_fresh_cache() -> None:
    _write_cache_file("openrouter", ["cached"], age_seconds=60)
    fake_make = _make_provider_returning(["live"])
    with patch("veles.cli._make_provider", fake_make):
        result = mf.fetch_models("openrouter", refresh=True)
    assert result.source == "live"
    assert "live" in result.models


def test_cloud_live_failure_falls_back_to_curated_without_touching_cache() -> None:
    cache_file = mf._cache_path("openrouter")
    assert not cache_file.exists()
    fake_make = _make_provider_returning(None, raises=RuntimeError("boom"))
    with patch("veles.cli._make_provider", fake_make):
        result = mf.fetch_models("openrouter")
    assert result.source == "curated"
    assert result.models == mf.known_models("openrouter")
    assert not cache_file.exists()


def test_cloud_missing_api_key_falls_back_to_curated() -> None:
    fake_make = MagicMock(side_effect=RuntimeError("OPENAI_API_KEY env var is required"))
    with patch("veles.cli._make_provider", fake_make):
        result = mf.fetch_models("openai")
    assert result.source == "curated"
    assert result.models == mf.known_models("openai")


def test_cloud_merge_dedup() -> None:
    """Live `[A, B]` + curated `[B, C]` → `[A, B, C]` (no duplicates, live order kept)."""
    with patch.object(mf, "known_models", return_value=["B", "C"]):
        merged = mf._merge_with_curated(["A", "B"], "openrouter")
    assert merged == ["A", "B", "C"]


# ---------- local live-only ----------


def test_local_ignores_cache_file_and_does_not_write_one(tmp_path: Path) -> None:
    """Even with a stale cache file on disk, local providers must hit
    the network. After a successful fetch the cache file stays absent."""
    cache_file = _write_cache_file("ollama", ["from-cache"], age_seconds=60)
    fake_make = _make_provider_returning(["qwen2.5:7b"])
    with patch("veles.cli._make_provider", fake_make):
        result = mf.fetch_models("ollama")
    assert result.source == "live"
    assert result.models == ["qwen2.5:7b"]
    # File we manually wrote is still on disk, but its contents are NOT
    # what fetch_models returned, proving the function ignored it.
    on_disk = json.loads(cache_file.read_text(encoding="utf-8"))
    assert on_disk["models"] == ["from-cache"]


def test_local_does_not_merge_with_curated() -> None:
    """Live result for a local provider is the source of truth — curated
    entries (if any) must not appear alongside, since they'd advertise
    models the local server doesn't actually have."""
    fake_make = _make_provider_returning(["only-local"])
    with (
        patch("veles.cli._make_provider", fake_make),
        patch.object(mf, "known_models", return_value=["curated-ghost"]),
    ):
        result = mf.fetch_models("ollama")
    assert result.models == ["only-local"]


def test_local_live_failure_falls_back_to_curated() -> None:
    fake_make = _make_provider_returning(None, raises=ConnectionRefusedError("nope"))
    with patch("veles.cli._make_provider", fake_make):
        result = mf.fetch_models("llamacpp")
    assert result.source == "curated"
    # llamacpp has no curated entries; that's fine — empty list is the
    # honest answer when the server is dead.
    assert result.models == mf.known_models("llamacpp")


def test_local_no_cache_written_after_live_success() -> None:
    fake_make = _make_provider_returning(["a", "b"])
    with patch("veles.cli._make_provider", fake_make):
        mf.fetch_models("openai-compat")
    assert not mf._cache_path("openai-compat").exists()


# ---------- curated-only ----------


def test_curated_only_provider_skips_network() -> None:
    fake_make = MagicMock(side_effect=AssertionError("must not be called"))
    with patch("veles.cli._make_provider", fake_make):
        result = mf.fetch_models("anthropic")
    assert result.source == "curated"
    assert result.models == mf.known_models("anthropic")
    fake_make.assert_not_called()


def test_cli_delegates_return_empty_curated() -> None:
    for provider in ("claude-cli", "gemini-cli"):
        result = mf.fetch_models(provider)
        assert result.source == "curated"
        assert result.models == mf.known_models(provider)


# ---------- adapter missing list_models ----------


def test_adapter_without_list_models_falls_back_to_curated() -> None:
    """If a future adapter is registered as cacheable but doesn't expose
    `list_models()`, we degrade gracefully instead of crashing."""
    fake_make = _make_provider_returning(None)  # adapter without list_models
    with patch("veles.cli._make_provider", fake_make):
        result = mf.fetch_models("openrouter")
    assert result.source == "curated"
