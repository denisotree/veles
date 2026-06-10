"""Single source of truth for the list of LLM providers Veles supports.

Adding a new provider used to require five edits (CLI stdin wizard,
project stdin wizard, TUI user wizard, TUI project wizard, plus the
KNOWN_PROVIDERS frozenset in `core/model_naming.py`). Each list could
drift independently — `cli/wizard.py` listed providers as bare strings,
TUI wizards as `ChoiceItem` objects with different label conventions.

This module centralises the catalogue. `ALL_PROVIDERS` is the canonical
ordered tuple; the wizards build their own UI primitives (`ChoiceItem`,
plain strings) from it. `core/model_naming.py::KNOWN_PROVIDERS` is
re-derived here as well so the strip-prefix logic stays in sync.

Order matters — it's the order users see in the provider picker, with
the most common choice (OpenRouter) first.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """One LLM provider that Veles can route to."""

    value: str
    """Internal id used in config, env vars, adapter dispatch."""

    label: str
    """Short display name. Goes into wizard pickers and status bars."""

    tagline: str = ""
    """One-line descriptor for the TUI first-run wizard, where users
    often need a hint about what each provider does. Project-level
    pickers stay compact and ignore this."""


ALL_PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec("openrouter", "OpenRouter", "multi-model gateway"),
    ProviderSpec("anthropic", "Anthropic", "Claude direct"),
    ProviderSpec("openai", "OpenAI", "GPT direct"),
    ProviderSpec("gemini", "Google Gemini", ""),
    ProviderSpec("claude-cli", "Claude CLI", "subprocess"),
    ProviderSpec("gemini-cli", "Gemini CLI", "subprocess"),
    ProviderSpec("ollama", "Ollama", "local, no key"),
    ProviderSpec("llamacpp", "llama.cpp", "local, no key"),
    ProviderSpec("openai-compat", "OpenAI-compatible", "custom endpoint"),
)


PROVIDER_VALUES: tuple[str, ...] = tuple(p.value for p in ALL_PROVIDERS)


def get_provider(value: str) -> ProviderSpec | None:
    """Return the spec for `value`, or None if unknown."""
    for spec in ALL_PROVIDERS:
        if spec.value == value:
            return spec
    return None


def tui_label(spec: ProviderSpec) -> str:
    """Render the label TUI first-run wizard expects: '<name> (<tagline>)'
    when a tagline exists, plain `label` otherwise."""
    if spec.tagline:
        return f"{spec.label} ({spec.tagline})"
    return spec.label


__all__ = [
    "ALL_PROVIDERS",
    "PROVIDER_VALUES",
    "ProviderSpec",
    "get_provider",
    "tui_label",
]
