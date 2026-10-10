"""Ollama adapter — talks to a local Ollama server's OpenAI-compatible endpoint.

Ollama exposes two surfaces:

- `/v1/chat/completions` — OpenAI-compatible (what we use for chat).
- `/api/tags` — native, lists installed models (used by `list_models`).

Default base URL is `http://localhost:11434/v1`; override with `OLLAMA_BASE_URL`
or `base_url=` kwarg. No API key is required — Ollama doesn't authenticate.

Tool calling is OFF by default (`supports_tools=False`). Many models served
via Ollama don't speak OpenAI tool-call format reliably; flip via
`enable_tools=True` (or the `VELES_LOCAL_TOOLS=1` env var that the provider
factory inspects) only when you've picked a tool-capable model
(e.g. llama3.1+, qwen2.5+, mistral-nemo).
"""

from __future__ import annotations

from typing import ClassVar

import httpx

from veles.adapters.local._base import LocalOpenAIBase
from veles.core.provider import ServerFacts


class OllamaProvider(LocalOpenAIBase):
    """Provider backed by a local Ollama server."""

    name: str = "ollama"
    DEFAULT_BASE_URL: ClassVar[str] = "http://localhost:11434/v1"
    BASE_URL_ENV: ClassVar[str | None] = "OLLAMA_BASE_URL"

    # ---- error hints (M132b) ----

    def _connection_error_hint(self) -> str:
        return (
            "is Ollama running? Start it with `ollama serve` (or open the "
            "Ollama app). Override the URL with OLLAMA_BASE_URL."
        )

    def _server_error_hint(self, status: int | str) -> str:
        # The 500 users hit is Ollama failing to launch its *own* internal
        # model runner (`llama-server`) — veles never requires that binary.
        # Two common causes: model not pulled, or a broken Ollama install
        # whose bundled runner is missing.
        return (
            "Ollama failed to serve the model. Check the model is pulled "
            "(`ollama pull <model>`); if the error mentions a missing "
            "`llama-server` runner, your Ollama install is broken — "
            "reinstall it (`brew install --cask ollama` or the installer "
            "from ollama.com)."
        )

    def list_models(self) -> list[str]:
        """Return names of locally-installed Ollama models via `/api/tags`.

        Useful for wizard UX and `veles route` to surface options. Returns
        an empty list if the server has no models or the endpoint is
        unreachable from this client's perspective (the HTTP error is
        re-raised — caller decides how to handle a dead server).
        """
        resp = httpx.get(f"{self._server_root()}/api/tags", timeout=10.0)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]

    def server_facts(self, model: str) -> ServerFacts | None:
        """What Ollama's `/api/show` says about `model`.

        Its `capabilities` array lists `"tools"` for models that speak the OpenAI
        tool-call format (e.g. `qwen3`, `llama3.1`, `qwen2.5`) — the provider
        factory enables tool calling from it, no `VELES_LOCAL_TOOLS` flag needed
        — and `"thinking"` for models that reason (M325), which raises their
        completion cap whatever the tag is called.

        `n_ctx` stays None: the context Ollama actually runs a model with is its
        `num_ctx` setting, not the trained length `/api/show` reports.

        Conservative on failure: a missing model, an old Ollama without the
        `capabilities` field, or an unreachable server all return None so
        auto-detection never wrongly enables tools or blocks startup.
        """
        if not model:
            return None
        try:
            resp = httpx.post(
                f"{self._server_root()}/api/show", json={"model": model}, timeout=10.0
            )
            resp.raise_for_status()
            caps = resp.json().get("capabilities")
        except Exception:
            return None
        if not isinstance(caps, list):
            return ServerFacts()
        return ServerFacts(tools="tools" in caps, reasoning="thinking" in caps)
