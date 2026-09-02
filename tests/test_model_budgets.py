"""M247: response budgets are per-model, not flat constants.

Both constants they replace were measured wrong on `z-ai/glm-5.3-flash`
(2026-09-02): at max_tokens=16000 it returned `completion == 16000` with an
EMPTY content field twice — the whole budget went to the hidden reasoning
channel — and at the flat 120s timeout the per-chunk read timeout killed a
2.7-hour research run mid-stream.
"""

from __future__ import annotations

from veles.core.model_budgets import (
    default_max_tokens_for,
    is_reasoning_model,
    request_timeout_for,
)


def test_reasoning_families_are_recognised() -> None:
    for model in (
        "z-ai/glm-5.3-flash",
        "z-ai/glm-5",
        "deepseek/deepseek-r2",
        "qwen/qwen3.8-27b",
        "openai/o3-mini",
        "qwen/qwen3-30b-a3b-thinking-2507",
    ):
        assert is_reasoning_model(model) is True, model


def test_plain_models_are_not_reasoning() -> None:
    for model in (
        "anthropic/claude-sonnet-4.6",
        "moonshotai/kimi-k3",
        "openai/gpt-4o",
        "mistralai/mistral-large",
    ):
        assert is_reasoning_model(model) is False, model


def test_reasoning_models_get_a_bigger_completion_cap() -> None:
    """The visible answer is the tail of the budget, not the whole of it."""
    assert default_max_tokens_for("z-ai/glm-5.3-flash") > default_max_tokens_for(
        "anthropic/claude-sonnet-4.6"
    )
    assert default_max_tokens_for("anthropic/claude-sonnet-4.6") == 4096


def test_a_flash_variant_still_gets_the_big_cap() -> None:
    """Being fast per token says nothing about how many thinking tokens it
    emits — glm-5.3-flash is exactly the model that returned an empty answer."""
    assert default_max_tokens_for("z-ai/glm-5.3-flash") == default_max_tokens_for("z-ai/glm-5")


def test_reasoning_models_get_a_longer_timeout() -> None:
    assert request_timeout_for("deepseek/deepseek-r2") > request_timeout_for("moonshotai/kimi-k3")
    assert request_timeout_for("moonshotai/kimi-k3") == 120.0


def test_fast_reasoning_variants_get_a_shorter_timeout_than_full_ones() -> None:
    assert request_timeout_for("z-ai/glm-5.3-flash") < request_timeout_for("z-ai/glm-5")
    assert request_timeout_for("z-ai/glm-5.3-flash") > request_timeout_for("openai/gpt-4o")


def test_unknown_and_empty_models_fall_back_to_the_conservative_defaults() -> None:
    for model in (None, "", "some/unheard-of-model"):
        assert default_max_tokens_for(model) == 4096
        assert request_timeout_for(model) == 120.0


def test_agent_resolves_max_tokens_from_the_model() -> None:
    """The default was flat 4096 and no interactive path overrode it."""
    from tests.conftest import StubProvider
    from veles.core.agent import Agent
    from veles.core.tools.registry import Registry

    plain = Agent(StubProvider(), Registry(), model="anthropic/claude-sonnet-4.6")
    reasoning = Agent(StubProvider(), Registry(), model="z-ai/glm-5.3-flash")
    assert plain._max_tokens == 4096
    assert reasoning._max_tokens == default_max_tokens_for("z-ai/glm-5.3-flash")


def test_explicit_max_tokens_still_wins() -> None:
    from tests.conftest import StubProvider
    from veles.core.agent import Agent
    from veles.core.tools.registry import Registry

    agent = Agent(StubProvider(), Registry(), model="z-ai/glm-5.3-flash", max_tokens=512)
    assert agent._max_tokens == 512
