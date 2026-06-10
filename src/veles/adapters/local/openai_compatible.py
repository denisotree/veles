"""Generic OpenAI-compatible adapter — any server speaking the OpenAI
Chat Completions wire format.

Covers vLLM, LM Studio, text-generation-webui's OpenAI extension, and any
other backend a user happens to run locally or in their network. Unlike
`OllamaProvider` / `LlamaCppProvider`, there is no sensible default URL —
the user MUST supply one via `base_url=` or the `OPENAI_COMPAT_BASE_URL`
env var. The empty `DEFAULT_BASE_URL` makes the base-class `__init__`
fail fast otherwise ("base_url is required").

Tool calling is OFF by default; flip with `enable_tools=True` when the
backing model and server combination is known to support OpenAI tools.
"""

from __future__ import annotations

from typing import ClassVar

from veles.adapters.local._base import _OpenAICompatibleBase


class OpenAICompatibleProvider(_OpenAICompatibleBase):
    """Provider backed by an arbitrary OpenAI-compatible HTTP endpoint."""

    name: str = "openai-compat"
    DEFAULT_BASE_URL: ClassVar[str] = ""
    BASE_URL_ENV: ClassVar[str | None] = "OPENAI_COMPAT_BASE_URL"
