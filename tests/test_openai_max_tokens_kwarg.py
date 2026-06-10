"""M112: reasoning-family OpenAI models reject `max_tokens` and require
`max_completion_tokens` — both the direct and the OpenRouter adapter
pick the right kwarg per model id."""

from __future__ import annotations

from veles.adapters.openai_direct import (
    _max_tokens_kwarg_for as _kwarg_direct,
)
from veles.adapters.openrouter import (
    _max_tokens_kwarg_for as _kwarg_openrouter,
)


def test_legacy_gpt4_uses_max_tokens() -> None:
    assert _kwarg_direct("gpt-4o-mini") == "max_tokens"
    assert _kwarg_direct("gpt-4.1") == "max_tokens"
    assert _kwarg_direct("gpt-3.5-turbo") == "max_tokens"


def test_gpt5_uses_max_completion_tokens() -> None:
    assert _kwarg_direct("gpt-5") == "max_completion_tokens"
    assert _kwarg_direct("gpt-5.4-mini") == "max_completion_tokens"


def test_o_series_uses_max_completion_tokens() -> None:
    assert _kwarg_direct("o1-mini") == "max_completion_tokens"
    assert _kwarg_direct("o3-mini") == "max_completion_tokens"
    assert _kwarg_direct("o4-mini") == "max_completion_tokens"


def test_provider_prefix_stripped_before_match() -> None:
    """OpenRouter passes qualified ids like `openai/gpt-5.x`; the
    helper looks at the segment after the last `/`."""
    assert _kwarg_openrouter("openai/gpt-5.4-mini") == "max_completion_tokens"
    assert _kwarg_openrouter("openai/gpt-4o") == "max_tokens"
    assert _kwarg_openrouter("anthropic/claude-sonnet-4.6") == "max_tokens"


def test_case_insensitive() -> None:
    assert _kwarg_direct("GPT-5") == "max_completion_tokens"
    assert _kwarg_direct("O1-MINI") == "max_completion_tokens"


def test_both_adapters_agree() -> None:
    """The two implementations are intentionally identical — keep
    them in sync."""
    for model in ("gpt-4o", "gpt-5", "o1-mini", "openai/gpt-5.4-mini"):
        assert _kwarg_direct(model) == _kwarg_openrouter(model), model
