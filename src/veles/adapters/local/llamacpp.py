"""llama.cpp adapter — for the OpenAI-compatible HTTP server shipped with
llama.cpp (`llama-server`).

Default base URL is `http://localhost:8080/v1`; override with
`LLAMACPP_BASE_URL` or `base_url=` kwarg. llama-server hosts exactly one
loaded model and ignores the `model` field of OpenAI requests — you can
pass any string (commonly `"default"`).

Tool calling is OFF by default (`supports_tools=False`). Native tool
support in llama-server depends on the loaded model's chat template and
grammar; flip via `enable_tools=True` only after verifying your specific
setup handles OpenAI-shaped `tools=` correctly.
"""

from __future__ import annotations

from typing import ClassVar

from veles.adapters.local._base import _OpenAICompatibleBase


class LlamaCppProvider(_OpenAICompatibleBase):
    """Provider backed by a local llama.cpp `llama-server`."""

    name: str = "llamacpp"
    DEFAULT_BASE_URL: ClassVar[str] = "http://localhost:8080/v1"
    BASE_URL_ENV: ClassVar[str | None] = "LLAMACPP_BASE_URL"
