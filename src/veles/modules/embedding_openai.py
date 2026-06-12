"""OpenAI-shape embedding adapter for the M-multimodal registry.

Wraps the existing M61 `core.skill_embedding.OpenAIEmbeddingAdapter`
under the `EmbeddingAdapter` Protocol so the cloud-provider path
participates in the same lookup. Two reasons to wrap rather than
just have callers use the M61 class directly:

1. **Uniform interface.** Path ranking / pattern detection consult
   `get_embedding_adapter()` once and don't care if the answer is
   Ollama, OpenAI, or future fastembed.
2. **Lazy import of `openai` SDK.** When the user has neither key
   nor Ollama nor any embedding need, we never pull in `openai`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from veles.modules.embedding import EmbeddingError

logger = logging.getLogger(__name__)


# Default model — small/cheap/good-enough; ~5x cheaper than -large
# and 1536d (well-supported across sqlite-vec / numpy / pure-python
# cosine on the storage side).
_DEFAULT_MODEL = "text-embedding-3-small"
_DEFAULT_DIM = 1536


@dataclass(slots=True)
class OpenAIEmbeddingProviderAdapter:
    """Thin wrapper around M61's `OpenAIEmbeddingAdapter` that
    conforms to the M-multimodal `EmbeddingAdapter` Protocol.
    Catches the SDK's exceptions and re-raises as `EmbeddingError`
    so call sites only need one except clause."""

    model: str = _DEFAULT_MODEL
    api_key: str | None = None
    base_url: str | None = None
    dim: int = _DEFAULT_DIM

    @property
    def name(self) -> str:
        host = self.base_url or "openai.com"
        return f"openai:{self.model}@{host}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            from veles.core.skill_embedding import OpenAIEmbeddingAdapter
        except ImportError as exc:
            raise EmbeddingError(f"openai SDK not installed: {exc}") from exc
        delegate = OpenAIEmbeddingAdapter(
            model=self.model, api_key=self.api_key, base_url=self.base_url
        )
        try:
            vecs = delegate.embed(texts)
        except Exception as exc:
            raise EmbeddingError(f"openai embed failed: {exc}") from exc
        if vecs and self.dim != len(vecs[0]):
            self.dim = len(vecs[0])
        return vecs


def build_from_env() -> OpenAIEmbeddingProviderAdapter | None:
    """Construct an adapter from env, or return None when no
    credentials are available. Used by `embedding_autodetect.py`
    as the cloud fallback."""
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openrouter_key:
        return OpenAIEmbeddingProviderAdapter(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        )
    if openai_key:
        return OpenAIEmbeddingProviderAdapter(api_key=openai_key)
    return None


__all__ = [
    "OpenAIEmbeddingProviderAdapter",
    "build_from_env",
]
