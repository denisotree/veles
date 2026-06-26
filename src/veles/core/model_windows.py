"""Per-model context-window registry (M177).

A single source of truth for "how big is this model's context window?", used
by both the TUI status chip (to show live context occupancy as a sane %) and
the runtime hard-ceiling guard (to cap the request below the provider limit).

The lookup is substring-based on the model id (provider prefixes like
`openrouter/` are tolerated) — adapter metadata isn't uniformly available
across providers, so this is a best-effort table biased *conservative*: when
unsure we return a smaller window, which makes the hard ceiling stricter (the
safe direction) rather than letting a request blow the real limit.
"""

from __future__ import annotations

_DEFAULT_WINDOW = 200_000

# Fraction of the window we allow a request to occupy before the Agent's
# emergency-truncation guard drops oldest turns. Leaves headroom for the
# response and for token-estimate error.
_HARD_CEILING_FRACTION = 0.9


def context_window_for(model: str | None) -> int:
    """Best-effort context-window size (tokens) for `model`."""
    if not model:
        return _DEFAULT_WINDOW
    m = model.lower()
    # Anthropic: Sonnet 4.6 / Opus 4.6+ / Fable are 1M; Haiku and older are 200k.
    if "claude" in m or "sonnet" in m or "opus" in m or "haiku" in m or "fable" in m:
        if "haiku" in m:
            return 200_000
        if any(tag in m for tag in ("4-6", "4.6", "4-7", "4.7", "4-8", "4.8", "fable")):
            return 1_000_000
        return 200_000
    if "gpt-4o" in m or "gpt-4.1" in m or "gpt-4-1" in m:
        return 128_000
    if "gpt-5" in m:
        return 400_000
    if "gemini" in m:
        return 1_000_000 if ("1.5" in m or "2." in m or "2-" in m) else 200_000
    return _DEFAULT_WINDOW


def default_hard_ceiling_for(model: str | None) -> int:
    """Token ceiling the request must stay under (≈90% of the window)."""
    return int(context_window_for(model) * _HARD_CEILING_FRACTION)
