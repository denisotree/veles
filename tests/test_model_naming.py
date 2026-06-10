"""M107: strip_provider_prefix peels a leading `<known-provider>/`
segment off a model id so the status bar doesn't show stale wrappers
like `openai/openrouter/gpt-4o`."""

from __future__ import annotations

from veles.core.model_naming import KNOWN_PROVIDERS, strip_provider_prefix


def test_strip_known_prefix() -> None:
    # Only one level peeled — inner `anthropic/...` is an OpenRouter
    # route name and is meaningful to the user.
    assert (
        strip_provider_prefix("openrouter/anthropic/claude-sonnet-4.6")
        == "anthropic/claude-sonnet-4.6"
    )


def test_strip_openai_prefix() -> None:
    assert strip_provider_prefix("openai/gpt-4o") == "gpt-4o"


def test_no_prefix_preserved() -> None:
    assert strip_provider_prefix("gpt-4o") == "gpt-4o"


def test_unknown_prefix_preserved() -> None:
    # `foobar` isn't a known provider — leave the string untouched.
    assert strip_provider_prefix("foobar/something") == "foobar/something"


def test_none_returns_empty_string() -> None:
    assert strip_provider_prefix(None) == ""


def test_empty_string_passthrough() -> None:
    assert strip_provider_prefix("") == ""


def test_known_providers_includes_all_wizard_options() -> None:
    # Every option offered in the wizard's _PROVIDER_CHOICES must be
    # recognised so we strip its prefix correctly.
    expected = {
        "openrouter",
        "anthropic",
        "openai",
        "gemini",
        "claude-cli",
        "gemini-cli",
        "ollama",
        "llamacpp",
        "openai-compat",
    }
    assert expected <= KNOWN_PROVIDERS


def test_only_slash_with_known_provider_strips() -> None:
    # Trailing slash without a model body — leave it alone.
    assert strip_provider_prefix("openai/") == "openai/"
