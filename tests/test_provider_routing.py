"""Tests for core/provider_routing.py — Tier δ M56 second half."""

from __future__ import annotations

import pytest

from veles.core.provider_routing import detect_api_mode


# ---------- host-driven matches ----------


def test_anthropic_canonical_host() -> None:
    assert detect_api_mode("https://api.anthropic.com", "claude-sonnet-4-5") == "anthropic"


def test_openrouter_host() -> None:
    assert detect_api_mode("https://openrouter.ai/api/v1", "anthropic/claude") == "openai-chat"


def test_gemini_host() -> None:
    assert (
        detect_api_mode("https://generativelanguage.googleapis.com/v1", "gemini-1.5-pro")
        == "gemini"
    )


def test_bedrock_host_matches_anthropic_bedrock() -> None:
    assert (
        detect_api_mode(
            "https://bedrock-runtime.us-east-1.amazonaws.com",
            "anthropic.claude-3-sonnet-20240229-v1:0",
        )
        == "anthropic-bedrock"
    )


# ---------- model-driven matches ----------


def test_openai_o1_upgrades_to_responses_api() -> None:
    """OpenAI's host is generic; the model name pushes the o-series into the
    Responses API explicitly."""
    assert detect_api_mode("https://api.openai.com/v1", "o1-preview") == "openai-responses"
    assert detect_api_mode("https://api.openai.com/v1", "o3-mini") == "openai-responses"


def test_openai_regular_model_stays_chat() -> None:
    assert detect_api_mode("https://api.openai.com/v1", "gpt-4o") == "openai-chat"


def test_model_name_alone_resolves_when_no_host() -> None:
    assert detect_api_mode(None, "anthropic/claude-3-haiku") == "anthropic"
    assert detect_api_mode("", "gemini-1.5-flash") == "gemini"


def test_o_series_without_host_still_responses() -> None:
    assert detect_api_mode(None, "o1") == "openai-responses"


# ---------- fallback behaviour ----------


def test_both_empty_falls_back_to_openai_chat() -> None:
    assert detect_api_mode(None, None) == "openai-chat"
    assert detect_api_mode("", "") == "openai-chat"


def test_unknown_host_unknown_model() -> None:
    """Local vLLM endpoint serving Llama — falls back to openai-chat."""
    assert detect_api_mode("http://localhost:8000/v1", "llama-3-70b") == "openai-chat"


def test_unknown_host_known_model() -> None:
    """Self-hosted gateway serving Claude — the model name resolves it."""
    assert detect_api_mode("http://internal-gw.corp/v1", "claude-3-opus") == "anthropic"


def test_malformed_url_does_not_raise() -> None:
    assert detect_api_mode("not a url", None) == "openai-chat"
    assert detect_api_mode("ftp://x", "claude") == "anthropic"


def test_case_insensitive_model_match() -> None:
    assert detect_api_mode(None, "CLAUDE-3-HAIKU") == "anthropic"
    assert detect_api_mode(None, "O1-PREVIEW") == "openai-responses"


def test_host_match_takes_priority_over_model_when_unambiguous() -> None:
    """If the host is explicitly Anthropic but someone names the model
    something OpenAI-looking, the host wins — they really did point at
    api.anthropic.com."""
    assert detect_api_mode("https://api.anthropic.com", "gpt-strange-name") == "anthropic"


@pytest.mark.parametrize(
    "model,expected",
    [
        ("claude-3-5-sonnet-20241022", "anthropic"),
        ("anthropic/claude-haiku-4-5", "anthropic"),
        ("gemini-2.0-flash-exp", "gemini"),
        ("google/gemini-pro", "gemini"),
        ("openai/gpt-4o", "openai-chat"),
    ],
)
def test_model_table(model: str, expected: str) -> None:
    """A small table of common (model_only) names mapping cleanly."""
    # Use a generic URL so host doesn't decide.
    assert detect_api_mode("http://gateway.local", model) == expected
