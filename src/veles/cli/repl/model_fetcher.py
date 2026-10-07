"""Resolve the model list for a given provider for the `/model` picker
and the `veles models` CLI verb.

Three strategies, named by the catalogue entry's `model_list`:

- **`cached`** (`openrouter`, `openai`, `gemini`) — fetch via
  the adapter's `list_models()`, cache the result on disk at
  `~/.veles/cache/models/<provider>.json` with a 24h TTL. Open the
  picker fast on cache hits; force a refresh via `refresh=True`
  (mapped from `/model refresh` or `veles models … --refresh`). Cloud
  results are merged with the curated fallback so familiar names stay
  visible even if the live API trims them.
- **`live`** (`ollama`, `llamacpp`, `openai-compat`) — fetch
  every time, **never cache**. A model installed locally (e.g. via
  `ollama pull`) must show up in the picker without a refresh dance,
  and the localhost round-trip is cheap enough that a cache only adds
  staleness. Live results are returned as-is (no merge with curated),
  because for local providers "what the server reports" is the ground
  truth.
- **`curated`** (`anthropic`, `claude-cli`) — no
  network call. Anthropic's SDK does expose a listing endpoint, but
  the curated table is kept by an explicit project decision; cli
  delegates have no listing surface at all.

All failure modes (missing API key, network error, unexpected adapter
shape) collapse to the curated list with a clear source label so the
caller can tell the user why they're seeing the fallback.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from veles.cli.repl.model_catalog import known_models
from veles.core.io_utils import read_fresh_json, write_stamped_json

_logger = logging.getLogger(__name__)

Source = Literal["live", "cache", "curated"]
FetchStatus = Literal["ok", "rejected", "unreachable"]

CACHE_TTL_SECONDS = 24 * 60 * 60
FETCH_TIMEOUT_S = 10.0


def _strategy(provider: str) -> str:
    """`cached` / `live` / `curated` — the catalogue entry's `model_list`."""
    from veles.core.providers import find_provider

    spec = find_provider(provider)
    return spec.model_list if spec else "curated"


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
    payload = read_fresh_json(_cache_path(provider), max_age_s=CACHE_TTL_SECONDS)
    models = payload.get("models") if payload else None
    if not isinstance(models, list) or not all(isinstance(m, str) for m in models):
        return None
    return models


def _write_cache(provider: str, models: list[str]) -> None:
    write_stamped_json(_cache_path(provider), {"models": models})


def _merge_with_curated(live: list[str], provider: str) -> list[str]:
    """Cloud merge: live first, curated names appended if not already present."""
    seen = set(live)
    merged = list(live)
    for m in known_models(provider):
        if m not in seen:
            merged.append(m)
            seen.add(m)
    return merged


def _list_live(provider: str) -> list[str] | None:
    """Build the adapter and call `list_models()`; `None` when there is no adapter or
    no listing, the request's own error propagates."""
    from veles.core.provider_factory import make_provider as _make_provider

    try:
        adapter = _make_provider(provider)
    except Exception as exc:
        _logger.debug("model fetcher: cannot build %s provider: %s", provider, exc)
        return None
    lister = getattr(adapter, "list_models", None)
    if not callable(lister):
        return None
    result = lister()
    if not isinstance(result, list) or not all(isinstance(m, str) for m in result):
        _logger.debug("model fetcher: %s.list_models() returned non-list[str]", provider)
        return None
    return result


def _bounded(fn: Callable[[], list[str] | None], timeout: float) -> list[str] | None:
    """Run `fn` in a daemon thread for at most `timeout` s — the SDKs default to minutes
    with retries, and a closed network froze the wizard. A daemon thread never blocks
    process exit; raises TimeoutError, or `fn`'s own error."""
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:  # carried to the caller
            box["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise TimeoutError
    if "error" in box:
        raise box["error"]
    return box.get("value")


def _try_live(provider: str) -> list[str] | None:
    """`_list_live` within `FETCH_TIMEOUT_S`; `None` on any failure (the picker falls
    back to the curated list)."""
    try:
        return _bounded(lambda: _list_live(provider), FETCH_TIMEOUT_S)
    except Exception as exc:
        _logger.debug("model fetcher: %s.list_models() failed: %s", provider, exc)
        return None


def _rejected(exc: BaseException) -> bool:
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return code in (401, 403)


def validate_and_fetch_models(provider: str, api_key: str) -> tuple[FetchStatus, list[str], str]:
    """One-shot validation + model listing using `api_key`, within `FETCH_TIMEOUT_S`.

    Temporarily plants the key in the canonical env var for `provider`
    so the adapter (and its SDK) pick it up, calls `list_models()`, and
    restores the env. Returns:
      - ("ok", models, "") on success — curated models for providers without a
        list-models endpoint (Anthropic, CLI shims): "accepted without validation".
      - ("rejected", [], message) when the provider refuses the key (401/403).
      - ("unreachable", [], message) when it doesn't answer in time or the
        request fails otherwise — the key may well be fine.

    Used by the TUI wizard to make API-key entry meaningful: the user
    finds out immediately if their key is wrong, and the model picker
    that follows shows the real catalogue rather than a curated guess.
    """
    strategy = _strategy(provider)
    if strategy == "curated":
        return "ok", known_models(provider), ""
    from veles.core.providers import find_provider

    spec = find_provider(provider)
    env_names = spec.key_env if spec else ()
    if not env_names and strategy != "live":
        return "ok", known_models(provider), ""

    def with_key() -> list[str] | None:
        saved: dict[str, str | None] = {n: os.environ.get(n) for n in env_names}
        try:
            for name in env_names:
                os.environ[name] = api_key
            return _list_live(provider)
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    try:
        models = _bounded(with_key, FETCH_TIMEOUT_S)
    except TimeoutError:
        return "unreachable", [], f"{provider} didn't answer in {FETCH_TIMEOUT_S:.0f}s"
    except Exception as exc:
        if _rejected(exc):
            return "rejected", [], "the provider rejected the key"
        return "unreachable", [], f"couldn't reach {provider}: {exc}"
    if models is None:
        return "rejected", [], "provider rejected the key or the request failed"
    if strategy == "cached":
        models = _merge_with_curated(models, provider)
    return "ok", models, ""


def fetch_models(provider: str, *, refresh: bool = False) -> ModelList:
    """Return the model list to show in the picker for `provider`.

    `refresh=True` skips the cache for cloud-cacheable providers (local
    providers are always live anyway, so the flag is a no-op there).
    """
    strategy = _strategy(provider)
    if strategy == "cached":
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

    if strategy == "live":
        live = _try_live(provider)
        if live is not None:
            return ModelList(models=live, source="live")
        return ModelList(models=known_models(provider), source="curated")

    return ModelList(models=known_models(provider), source="curated")
