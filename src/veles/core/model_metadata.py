"""OpenRouter's own catalogue as a fact source for per-model budgets (M267).

`model_budgets` classified reasoning models by substring — `glm-5`, `deepseek-r`,
`gpt-5` and nine more families. Measured against the live catalogue on
2026-09-22: of 442 models, **311** declare `reasoning` in `supported_parameters`
and **219 of those the substring list does not recognise**. `deepseek-v4` was one
of them, and the cost was not a slow request: it ran on 4096 completion tokens
while `glm-5.3-flash` ran on 32000, returned 5 empty verdicts out of 12, and the
comparison concluded the model was unfit. It was truncated — the failure this
module's sibling docstring already describes for GLM, reproduced on a second
model because the classifier did not know it thinks.

So the family list stops being the answer and becomes the fallback. It is still
the right fallback: it works offline, for providers that are not OpenRouter, and
for an id the catalogue has never heard of.

**Offline-first, never blocking a run.** The order is cache → one bounded fetch →
give up quietly. The endpoint is public (verified 2026-09-22: HTTP 200 with no
`Authorization` header), which matters more than it sounds: the cache that
already exists in `cli/repl/model_fetcher` is written only by the `/model` picker
and `veles models`, so a headless `veles run` — the very path that produced the
bad verdict — would never have warmed it. Needing no key means that path can warm
it itself.

A failure is memoised for the process just as a success is: a machine with no
network must pay the 3s once, not on every provider build.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, TypedDict

from veles.core.io_utils import read_fresh_json, write_stamped_json

_logger = logging.getLogger(__name__)


class ModelFacts(TypedDict):
    """What the catalogue knows about one model (the cached JSON shape)."""

    reasoning: bool  # can think when asked (`reasoning` in supported_parameters)
    reasoning_mandatory: bool  # thinks whether asked or not
    context_length: int | None


_MODELS_URL = "https://openrouter.ai/api/v1/models"
_FETCH_TIMEOUT_S = 3.0
_CACHE_TTL_SECONDS = 24 * 60 * 60  # same as the id cache next to it

# None = not looked up yet this process; {} = looked up and unavailable.
_memo: dict[str, ModelFacts] | None = None


def _cache_path() -> Path:
    from veles.core.user_paths import user_home

    return user_home() / "cache" / "models" / "openrouter.meta.json"


def _trim(payload: Any) -> dict[str, ModelFacts]:
    """Keep the fields budgets and context windows are made of, not the 2KB
    record per model. Two reasoning fields, because they answer different
    questions — see `ModelFacts`."""
    out: dict[str, ModelFacts] = {}
    for entry in payload.get("data", []) if isinstance(payload, dict) else []:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        if not isinstance(model_id, str) or not model_id:
            continue
        params = entry.get("supported_parameters")
        window = entry.get("context_length")
        reasoning = entry.get("reasoning")
        out[model_id] = {
            "reasoning": isinstance(params, list) and "reasoning" in params,
            "reasoning_mandatory": bool(isinstance(reasoning, dict) and reasoning.get("mandatory")),
            "context_length": window if isinstance(window, int) and window > 0 else None,
        }
    return out


def _read_cache() -> dict[str, ModelFacts] | None:
    payload = read_fresh_json(_cache_path(), max_age_s=_CACHE_TTL_SECONDS)
    models = payload.get("models") if payload else None
    return models if isinstance(models, dict) else None


def _write_cache(models: dict[str, ModelFacts]) -> None:
    """Atomic, because daemon sessions build providers concurrently and a reader
    must never see half a file (it would read as a miss and fetch again)."""
    try:
        write_stamped_json(_cache_path(), {"models": models})
    except OSError as exc:
        _logger.debug("cannot write model metadata cache %s: %s", _cache_path(), exc)


def _fetch() -> dict[str, ModelFacts] | None:
    """One bounded GET. Returns None on anything at all going wrong."""
    try:
        with urllib.request.urlopen(_MODELS_URL, timeout=_FETCH_TIMEOUT_S) as resp:
            models = _trim(json.loads(resp.read()))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        _logger.debug("model metadata fetch failed: %s", exc)
        return None
    return models or None


def _catalogue() -> dict[str, ModelFacts]:
    global _memo
    if _memo is None:
        cached = _read_cache()
        if cached is None:
            fetched = _fetch()
            if fetched is not None:
                _write_cache(fetched)
            _memo = fetched or {}
        else:
            _memo = cached
    return _memo


def refresh_cache(models_payload: Any) -> None:
    """Store a catalogue someone else already fetched (`model_fetcher`).

    Saves a second round trip on the path that was going to OpenRouter anyway."""
    global _memo
    trimmed = _trim(models_payload)
    if trimmed:
        _write_cache(trimmed)
        _memo = trimmed


def reset_for_tests() -> None:
    global _memo
    _memo = None


def model_facts(model: str | None) -> ModelFacts | None:
    """Catalogue facts for `model`, or None when they cannot be established.

    None means "no opinion" — the caller keeps whatever it did before. That
    covers an offline machine, a non-OpenRouter id, and a model too new or too
    private to be listed."""
    if not model:
        return None
    # Callers routinely carry a route prefix; `model_windows` tolerates it too.
    key = model.removeprefix("openrouter/")
    if "/" not in key:
        # Every OpenRouter id is `vendor/slug`, so a bare id — an ollama tag like
        # `qwen3.8:27b`, a direct-API id like `gpt-4o` or `claude-sonnet-4-6` —
        # can never be in this catalogue. Without this guard a fully local run
        # made an outbound request to openrouter.ai it could not benefit from
        # (found in review before 0.37.0), paying up to the fetch timeout on
        # every process where that connection hangs.
        # ponytail: an id with a slash on a non-OpenRouter backend (a llama.cpp
        # HF-style name) still triggers one lookup and misses; gate on the
        # active provider if that ever matters.
        return None
    return _catalogue().get(key)


__all__ = ["ModelFacts", "model_facts", "refresh_cache", "reset_for_tests"]
