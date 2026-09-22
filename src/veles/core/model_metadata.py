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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_MODELS_URL = "https://openrouter.ai/api/v1/models"
_FETCH_TIMEOUT_S = 3.0
_CACHE_TTL_SECONDS = 24 * 60 * 60  # same as the id cache next to it

# None = not looked up yet this process; {} = looked up and unavailable.
_memo: dict[str, dict[str, Any]] | None = None


def _cache_path() -> Path:
    from veles.core.user_paths import user_home

    return user_home() / "cache" / "models" / "openrouter.meta.json"


def _trim(payload: Any) -> dict[str, dict[str, Any]]:
    """Keep the two fields a budget is made of, not the 2KB record per model.

    Two reasoning fields, because they answer different questions.
    `supported_parameters` contains `reasoning` when the model *can* think if
    asked; `reasoning.mandatory` is true when it thinks whether asked or not.
    `context_length` has no consumer yet — it is stored because it is the same
    parsed field, and leaving it out would mean changing the cache format (and
    invalidating every cache) the moment something asks for it."""
    out: dict[str, dict[str, Any]] = {}
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


def _read_cache() -> dict[str, dict[str, Any]] | None:
    path = _cache_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        if (datetime.now(UTC) - fetched_at).total_seconds() >= _CACHE_TTL_SECONDS:
            return None
        models = payload["models"]
        return models if isinstance(models, dict) else None
    except Exception as exc:  # corrupt/partial cache — a miss, never a crash
        _logger.debug("model metadata cache %s unreadable: %s", path, exc)
        return None


def _write_cache(models: dict[str, dict[str, Any]]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"fetched_at": datetime.now(UTC).isoformat(timespec="seconds"), "models": models},
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        _logger.debug("cannot write model metadata cache %s: %s", path, exc)


def _fetch() -> dict[str, dict[str, Any]] | None:
    """One bounded GET. Returns None on anything at all going wrong."""
    try:
        with urllib.request.urlopen(_MODELS_URL, timeout=_FETCH_TIMEOUT_S) as resp:
            models = _trim(json.loads(resp.read()))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        _logger.debug("model metadata fetch failed: %s", exc)
        return None
    return models or None


def _catalogue() -> dict[str, dict[str, Any]]:
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


def model_facts(model: str | None) -> dict[str, Any] | None:
    """Catalogue facts for `model`, or None when they cannot be established.

    None means "no opinion" — the caller keeps whatever it did before. That
    covers an offline machine, a non-OpenRouter id, and a model too new or too
    private to be listed."""
    if not model:
        return None
    facts = _catalogue().get(model)
    if facts is None and model.startswith("openrouter/"):
        # Callers routinely carry a route prefix; `model_windows` tolerates it too.
        facts = _catalogue().get(model.removeprefix("openrouter/"))
    return facts


__all__ = ["model_facts", "refresh_cache", "reset_for_tests"]
