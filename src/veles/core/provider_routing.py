"""API-mode detection for provider endpoints (Tier δ, M56 second half).

When a user points Veles at a non-canonical endpoint (a self-hosted vLLM,
a corporate OpenAI-compatible gateway, an Anthropic-via-Bedrock proxy),
the adapter picks need to know which wire protocol to speak. Existing
adapters (`adapters/anthropic.py`, `adapters/openai_direct.py`, etc.)
each know their own canonical mode, but a future generic adapter or
provider-router can use this helper to pick the right one from
`(base_url, model_name)`.

The function is a pure heuristic — no I/O, no caching, no SDK probing.
It looks at the URL host and the model name and returns one of five
modes. Unrecognised combinations fall back to `openai-chat`, the most
widely-spoken protocol; this matches the de-facto behaviour of most
"OpenAI-compatible" services.
"""

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

ApiMode = Literal[
    "openai-chat",  # /v1/chat/completions — OpenAI, OpenRouter, vLLM, most OSS gateways
    "openai-responses",  # /v1/responses — OpenAI Responses API (o1/o3 reasoning)
    "anthropic",  # /v1/messages — Anthropic native (api.anthropic.com)
    "anthropic-bedrock",  # AWS Bedrock + Anthropic models
    "gemini",  # generativelanguage.googleapis.com — Gemini native
]


# Host suffix → mode. Most-specific first; the matcher returns on first hit.
_HOST_RULES: list[tuple[str, ApiMode]] = [
    ("api.anthropic.com", "anthropic"),
    ("bedrock-runtime.", "anthropic-bedrock"),  # bedrock-runtime.us-east-1.amazonaws.com
    ("generativelanguage.googleapis.com", "gemini"),
    ("openrouter.ai", "openai-chat"),
    ("api.openai.com", "openai-chat"),  # may be overridden by model-name rule below
]


# Model-name rules. When a host doesn't decide, these can either set or
# upgrade the mode (e.g. OpenAI `o1*`/`o3*` → openai-responses).
_MODEL_RULES: list[tuple[re.Pattern[str], ApiMode]] = [
    (re.compile(r"^(?:openai/)?o[0-9](?:-|$)", re.IGNORECASE), "openai-responses"),
    (re.compile(r"^anthropic/|claude", re.IGNORECASE), "anthropic"),
    (re.compile(r"^google/|^gemini", re.IGNORECASE), "gemini"),
]


def detect_api_mode(base_url: str | None, model_name: str | None) -> ApiMode:
    """Pick the API mode for `(base_url, model_name)`.

    Either argument may be None / empty — we degrade as gracefully as the
    available signal allows. When *both* are empty we return
    `openai-chat` (the default for unknown OpenAI-compatible endpoints).

    Returned mode is one of `ApiMode`. The function never raises.
    """
    host_mode = _match_host(base_url)
    model_mode = _match_model(model_name)

    # Host wins for the obvious cases (anthropic.com, generativelanguage.*).
    # OpenAI's host is generic — the model name should be allowed to refine
    # it (o1 / o3 push us into the Responses API).
    if host_mode == "openai-chat" and model_mode == "openai-responses":
        return "openai-responses"
    if host_mode is not None:
        return host_mode
    if model_mode is not None:
        return model_mode
    return "openai-chat"


def _match_host(base_url: str | None) -> ApiMode | None:
    if not base_url:
        return None
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    for needle, mode in _HOST_RULES:
        if needle in host:
            return mode
    return None


def _match_model(model_name: str | None) -> ApiMode | None:
    if not model_name:
        return None
    for pat, mode in _MODEL_RULES:
        if pat.search(model_name):
            return mode
    return None


__all__ = ["ApiMode", "detect_api_mode"]
