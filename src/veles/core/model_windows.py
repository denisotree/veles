"""Per-model context-window registry (M177).

A single source of truth for "how big is this model's context window?", used
by both the TUI status chip (to show live context occupancy as a sane %) and
the runtime hard-ceiling guard (to cap the request below the provider limit).

**M268: the catalogue answers first, the table is the fallback.** The table is
substring-based on the model id (provider prefixes like `openrouter/` are
tolerated) and was accurate only for the families someone had thought to add —
everything else fell back to 200k. That default is the safe direction for a
model whose window is unknown and simply wrong for one that is known: measured
2026-09-22, `deepseek/deepseek-v4-flash` has a 1 048 576-token window and was
being held to 200k, so the emergency-truncation guard dropped history at 180k —
roughly five times earlier than it had to. `core/model_metadata.py` already
carries `context_length` per model (the same fetch M267 uses for reasoning), so
this costs a lookup, not a request.

The table stays for the two cases the catalogue cannot serve: no network, and a
model it does not list (local backends, private routes). An unknown model still
gets the conservative 200k.

Note a real OpenRouter route may serve slightly less than the nominal window —
the catalogue reports the model's figure, and individual endpoints vary by a few
per cent. `_HARD_CEILING_FRACTION` (0.9) is the headroom that absorbs it; a route
that serves *materially* less is a routing problem, fixed by pinning the backend
(`[engine.request.openrouter.provider]`), not by lowering a constant here.
"""

from __future__ import annotations

_DEFAULT_WINDOW = 200_000

# Fraction of the window we allow a request to occupy before the Agent's
# emergency-truncation guard drops oldest turns. Leaves headroom for the
# response and for token-estimate error.
_HARD_CEILING_FRACTION = 0.9


def context_window_for(model: str | None) -> int:
    """Best-effort context-window size (tokens) for `model`.

    Asks the provider's catalogue first (M268); falls back to the substring
    table when it has no answer."""
    if not model:
        return _DEFAULT_WINDOW
    from veles.core.model_metadata import model_facts

    facts = model_facts(model)
    if facts is not None:
        window = facts.get("context_length")
        if isinstance(window, int) and window > 0:
            return window
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
