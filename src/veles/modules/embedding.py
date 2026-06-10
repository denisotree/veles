"""Embedding adapter interface + singleton registry.

Mirrors the STT/Vision module pattern: an abstract Protocol that any
provider can implement, plus process-global register/get/reset
helpers so daemon startup can wire the right backend without the
call sites caring which one is active.

Concrete adapters live alongside in this package:
- `embedding_ollama.py` — HTTP to a local Ollama daemon
  (`localhost:11434/api/embeddings`). Zero pip dependency; the user
  installs the model (`ollama pull nomic-embed-text`).
- `embedding_openai.py` — wraps the M61 `OpenAIEmbeddingAdapter` so
  the cloud provider path (OpenRouter / OpenAI) participates in the
  same Protocol-based registry.

`core/embedding_autodetect.py` runs at daemon startup and picks the
first responding backend, leaving the slot None when nothing
answers — in which case `core/embedding_notice.py` writes a
**one-time** setup hint into the `insights` table so the user
sees a "ranking would benefit from embeddings; here's how" notice
without log spam.

`get_embedding_adapter()` returns None when nothing is configured —
callers (path ranking, pattern detection) check that and fall back
to their token-based ranking, never crashing.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingAdapter(Protocol):
    """Turn a batch of strings into float vectors. Synchronous —
    embeddings are CPU-/network-bound but per-call short; threadpool
    wrapping happens at the call site for parallel batches."""

    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input string, in the same order.
        Raises `EmbeddingError` on failure; the call site catches
        and falls through to non-embedding ranking."""
        ...


class EmbeddingError(RuntimeError):
    """Adapter failure (network, model not loaded, auth, …). Always
    caught by ranking call sites — never bubbles out to break a
    user's turn."""


_REGISTERED: EmbeddingAdapter | None = None


def register_embedding_adapter(adapter: EmbeddingAdapter | None) -> None:
    """Install (or clear with None) the process-global embedding
    adapter. Called once at daemon startup by the autodetect path;
    tests use `reset_embedding_adapter` to keep state isolated."""
    global _REGISTERED
    _REGISTERED = adapter


def get_embedding_adapter() -> EmbeddingAdapter | None:
    """Return the registered adapter, or None when no embedding
    backend is configured for this install. Callers MUST handle
    None — fall back to token-based ranking with a setup hint."""
    return _REGISTERED


def reset_embedding_adapter() -> None:
    """Test helper — clear any installed adapter."""
    global _REGISTERED
    _REGISTERED = None


__all__ = [
    "EmbeddingAdapter",
    "EmbeddingError",
    "get_embedding_adapter",
    "register_embedding_adapter",
    "reset_embedding_adapter",
]
