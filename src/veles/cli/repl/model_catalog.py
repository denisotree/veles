"""Curated fallback model catalogue, keyed by provider.

Used when the live API isn't reachable (no key, network error) — see
`model_fetcher.py` for the full live/cache/curated strategy — and by
the `ModelPickerScreen` / inline REPL model picker as the last-resort
list. Tests can stub `known_models` via `monkeypatch.setattr(...)` to
avoid hitting the wire.
"""

from __future__ import annotations

_CURATED_MODELS_BY_PROVIDER: dict[str, list[str]] = {
    "openrouter": [
        "anthropic/claude-sonnet-4.6",
        "anthropic/claude-opus-4.7",
        "anthropic/claude-haiku-4.5",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "google/gemini-2.5-pro",
        "google/gemini-2.5-flash",
        "meta-llama/llama-3.3-70b-instruct",
        "deepseek/deepseek-r1",
    ],
    "anthropic": [
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "claude-haiku-4.5",
    ],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o4-mini", "o3"],
    "gemini": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
    "claude-cli": [],
    "gemini-cli": [],
}


def known_models(provider: str) -> list[str]:
    """Curated fallback list. The fetcher uses this when the live API
    isn't reachable (no key, network error) and tests can stub it via
    `monkeypatch.setattr(...)` to avoid hitting the wire."""
    return list(_CURATED_MODELS_BY_PROVIDER.get(provider, []))
