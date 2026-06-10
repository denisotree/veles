"""Helpers for normalising provider-qualified model identifiers.

The wizard's model picker stores its selection as a fully-qualified id —
e.g. `openrouter/anthropic/claude-sonnet-4.6` — because the same name
can resolve to different routes across providers. The status bar and
some other display paths want just the model portion (`anthropic/...`)
so we don't end up printing `openai/openrouter/...` when the user has
switched providers but is still pointed at an older default.

Single helper, no class. Keep callers thin.
"""

from __future__ import annotations

from veles.core.providers import PROVIDER_VALUES

# Every provider name Veles knows about. Used to detect & strip a leading
# provider prefix on model strings. Single source of truth is
# `core/providers.py::ALL_PROVIDERS`; this is just a frozenset projection.
KNOWN_PROVIDERS: frozenset[str] = frozenset(PROVIDER_VALUES)


def strip_provider_prefix(
    model: str | None,
    *,
    known: frozenset[str] = KNOWN_PROVIDERS,
) -> str:
    """Return `model` without a leading `<provider>/` segment, if any.

    Only strips one level — `openrouter/anthropic/claude-sonnet-4.6`
    becomes `anthropic/claude-sonnet-4.6`, not just `claude-sonnet-4.6`.
    The inner `anthropic/` segment is OpenRouter's route name and is
    meaningful to the user; we only peel the outer routing layer.

    Returns the original string (or empty for None) when the prefix is
    not a known provider, so unrelated `/`-separated ids pass through.
    """
    if not model:
        return ""
    head, sep, rest = model.partition("/")
    if sep and head in known and rest:
        return rest
    return model


__all__ = ["KNOWN_PROVIDERS", "strip_provider_prefix"]
