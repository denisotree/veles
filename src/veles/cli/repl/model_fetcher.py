"""Resolve the model list for a given provider for the `/model` picker
and the `veles models` CLI verb.

Three strategies, picked per provider:

- **Cloud cacheable** (`openrouter`, `openai`, `gemini`) — fetch via
  the adapter's `list_models()`, cache the result on disk at
  `~/.veles/cache/models/<provider>.json` with a 24h TTL. Open the
  picker fast on cache hits; force a refresh via `refresh=True`
  (mapped from `/model refresh` or `veles models … --refresh`). Cloud
  results are merged with the curated fallback so familiar names stay
  visible even if the live API trims them.
- **Local live-only** (`ollama`, `llamacpp`, `openai-compat`) — fetch
  every time, **never cache**. A model installed locally (e.g. via
  `ollama pull`) must show up in the picker without a refresh dance,
  and the localhost round-trip is cheap enough that a cache only adds
  staleness. Live results are returned as-is (no merge with curated),
  because for local providers "what the server reports" is the ground
  truth.
- **Curated-only** (`anthropic`, `claude-cli`, `gemini-cli`) — no
  network call. Anthropic's SDK does expose a listing endpoint, but
  the curated table is kept by an explicit project decision; cli
  delegates have no listing surface at all.

All failure modes (missing API key, network error, unexpected adapter
shape) collapse to the curated list with a clear source label so the
caller can tell the user why they're seeing the fallback.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from veles.cli.repl.model_catalog import known_models

_logger = logging.getLogger(__name__)

Source = Literal["live", "cache", "curated"]

CLOUD_CACHEABLE: frozenset[str] = frozenset({"openrouter", "openai", "gemini"})
LOCAL_LIVE_ONLY: frozenset[str] = frozenset({"ollama", "llamacpp", "openai-compat"})

CACHE_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class ModelList:
    models: list[str]
    source: Source

    def __iter__(self):
        return iter((self.models, self.source))


def _veles_home() -> Path:
    """M158: unified on `user_home()` — the cache moved from the ad-hoc
    `VELES_HOME` env var (the only consumer of that name) to the standard
    `VELES_USER_HOME` override every other user-scope path honours."""
    from veles.core.user_paths import user_home

    return user_home()


def _cache_path(provider: str) -> Path:
    return _veles_home() / "cache" / "models" / f"{provider}.json"


def _read_cache(provider: str) -> list[str] | None:
    path = _cache_path(provider)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        age = (datetime.now(UTC) - fetched_at).total_seconds()
        if age >= CACHE_TTL_SECONDS:
            return None
        models = payload.get("models")
        if not isinstance(models, list) or not all(isinstance(m, str) for m in models):
            return None
        return models
    except Exception as exc:  # corrupt cache — treat as a miss
        _logger.debug("model cache %s unreadable: %s", path, exc)
        return None


def _write_cache(provider: str, models: list[str]) -> None:
    path = _cache_path(provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "models": models,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _merge_with_curated(live: list[str], provider: str) -> list[str]:
    """Cloud merge: live first, curated names appended if not already present."""
    seen = set(live)
    merged = list(live)
    for m in known_models(provider):
        if m not in seen:
            merged.append(m)
            seen.add(m)
    return merged


def _try_live(provider: str) -> list[str] | None:
    """Build adapter and call `list_models()`. Returns `None` on any
    failure (missing key, no method, network/auth error)."""
    try:
        from veles.cli import _make_provider
    except Exception as exc:  # pragma: no cover — import path is stable
        _logger.debug("model fetcher: cannot import _make_provider: %s", exc)
        return None
    try:
        adapter = _make_provider(provider)
    except Exception as exc:
        _logger.debug("model fetcher: cannot build %s provider: %s", provider, exc)
        return None
    lister = getattr(adapter, "list_models", None)
    if not callable(lister):
        return None
    try:
        result = lister()
    except Exception as exc:
        _logger.debug("model fetcher: %s.list_models() failed: %s", provider, exc)
        return None
    if not isinstance(result, list) or not all(isinstance(m, str) for m in result):
        _logger.debug("model fetcher: %s.list_models() returned non-list[str]", provider)
        return None
    return result


def validate_and_fetch_models(provider: str, api_key: str) -> tuple[bool, list[str], str]:
    """One-shot validation + model listing using `api_key`.

    Temporarily plants the key in the canonical env var for `provider`
    so the adapter (and its SDK) pick it up, calls `list_models()`, and
    restores the env. Returns:
      - (True, models, "") on success.
      - (True, curated_models, "") for providers without a list-models
        endpoint (Anthropic, CLI shims) — caller treats the key as
        "accepted without validation".
      - (False, [], message) when the adapter rejects the key or the
        request fails for any reason.

    Used by the TUI wizard to make API-key entry meaningful: the user
    finds out immediately if their key is wrong, and the model picker
    that follows shows the real catalogue rather than a curated guess.
    """
    if provider not in CLOUD_CACHEABLE and provider not in LOCAL_LIVE_ONLY:
        return True, known_models(provider), ""
    from veles.core.provider_factory import PROVIDER_API_KEY_ENVS

    env_names = PROVIDER_API_KEY_ENVS.get(provider, ())
    if not env_names and provider not in LOCAL_LIVE_ONLY:
        return True, known_models(provider), ""
    saved: dict[str, str | None] = {n: os.environ.get(n) for n in env_names}
    try:
        for name in env_names:
            os.environ[name] = api_key
        models = _try_live(provider)
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    if models is None:
        return False, [], "provider rejected the key or the request failed"
    if provider in CLOUD_CACHEABLE:
        models = _merge_with_curated(models, provider)
    return True, models, ""


def fetch_models(provider: str, *, refresh: bool = False) -> ModelList:
    """Return the model list to show in the picker for `provider`.

    `refresh=True` skips the cache for cloud-cacheable providers (local
    providers are always live anyway, so the flag is a no-op there).
    """
    if provider in CLOUD_CACHEABLE:
        if not refresh:
            cached = _read_cache(provider)
            if cached is not None:
                return ModelList(models=cached, source="cache")
        live = _try_live(provider)
        if live is not None:
            merged = _merge_with_curated(live, provider)
            try:
                _write_cache(provider, merged)
            except OSError as exc:
                _logger.debug("model fetcher: cannot write cache for %s: %s", provider, exc)
            return ModelList(models=merged, source="live")
        return ModelList(models=known_models(provider), source="curated")

    if provider in LOCAL_LIVE_ONLY:
        live = _try_live(provider)
        if live is not None:
            return ModelList(models=live, source="live")
        return ModelList(models=known_models(provider), source="curated")

    return ModelList(models=known_models(provider), source="curated")
