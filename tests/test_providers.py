"""M-R1.1: single source of truth for the provider catalogue.

`core/providers.py::ALL_PROVIDERS` is the canonical list every wizard
and model_naming.KNOWN_PROVIDERS derives from. These tests pin that
contract — invariants here catch silent drift if someone adds a new
provider directly to one wizard.
"""

from __future__ import annotations

from veles.core.model_naming import KNOWN_PROVIDERS
from veles.core.provider_factory import LOCAL_PROVIDERS, PROVIDER_API_KEY_ENVS
from veles.core.providers import (
    ALL_PROVIDERS,
    PROVIDER_VALUES,
    ProviderSpec,
    get_provider,
    tui_label,
)


def test_all_providers_unique_values() -> None:
    values = [p.value for p in ALL_PROVIDERS]
    assert len(values) == len(set(values))


def test_known_providers_matches_catalogue() -> None:
    """model_naming.KNOWN_PROVIDERS is derived from PROVIDER_VALUES;
    they must agree."""
    assert KNOWN_PROVIDERS == frozenset(PROVIDER_VALUES)


def test_every_provider_classified_somewhere() -> None:
    """Each catalogued provider must be in one of the three buckets:
    keyed API providers, local providers, or CLI delegates. Otherwise
    we have a provider that no adapter knows how to instantiate."""
    keyed = frozenset(PROVIDER_API_KEY_ENVS.keys())
    cli_delegates = frozenset({"claude-cli", "gemini-cli"})
    for spec in ALL_PROVIDERS:
        assert (
            spec.value in keyed
            or spec.value in LOCAL_PROVIDERS
            or spec.value in cli_delegates
        ), f"provider {spec.value!r} has no adapter category"


def test_get_provider_returns_spec() -> None:
    spec = get_provider("openrouter")
    assert isinstance(spec, ProviderSpec)
    assert spec.value == "openrouter"
    assert spec.label == "OpenRouter"


def test_get_provider_unknown_returns_none() -> None:
    assert get_provider("not-a-provider") is None


def test_tui_label_includes_tagline_when_present() -> None:
    spec = ProviderSpec(value="x", label="X", tagline="cool")
    assert tui_label(spec) == "X (cool)"


def test_tui_label_omits_empty_tagline() -> None:
    spec = ProviderSpec(value="x", label="X", tagline="")
    assert tui_label(spec) == "X"


def test_default_order_openrouter_first() -> None:
    """OpenRouter is the most common pick (multi-model gateway) — the
    picker presents it first so the typical user lands on it."""
    assert ALL_PROVIDERS[0].value == "openrouter"
