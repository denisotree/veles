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
# B2 (2026-07-07 audit): distinguishes "autodetect has not run yet" from
# "autodetect ran and found no backend" — both leave `_REGISTERED is None`.
# Without this, `get_local_embedding_adapter` couldn't know whether to probe,
# so vector recall stayed inert until the post-turn curator happened to run
# autodetect (never on REPL turn 1 or a single-shot `veles run`).
_AUTODETECTED = False


def register_embedding_adapter(adapter: EmbeddingAdapter | None) -> None:
    """Install (or clear with None) the process-global embedding
    adapter. Called once at daemon startup by the autodetect path;
    tests use `reset_embedding_adapter` to keep state isolated."""
    global _REGISTERED, _AUTODETECTED
    _REGISTERED = adapter
    _AUTODETECTED = True  # an explicit install counts as detection — no lazy probe


def _ensure_autodetected() -> None:
    """Run backend autodetection once (lazily) if nothing has registered an
    adapter yet. Cached via `_AUTODETECTED` so recall probes at most once per
    process, not on every turn. Best-effort — a probe failure leaves the
    token-based fallback intact."""
    global _AUTODETECTED
    if _AUTODETECTED:
        return
    _AUTODETECTED = True  # set first so a failing probe never retries per-call
    try:
        from veles.modules.embedding_autodetect import autodetect_embedding_adapter

        autodetect_embedding_adapter()
    except Exception:
        pass


def get_embedding_adapter() -> EmbeddingAdapter | None:
    """Return the registered adapter, or None when no embedding
    backend is configured for this install. Callers MUST handle
    None — fall back to token-based ranking with a setup hint."""
    return _REGISTERED


def get_local_embedding_adapter() -> EmbeddingAdapter | None:
    """M192: the registered adapter only if it is on-device (`is_local`).

    The single gate for "may I send text to this embedder without egress?".
    Recall (query text) and backfill (insight bodies) both use it so a cloud
    embedder never receives project content. Returns None for a cloud adapter
    or no adapter — callers then stay on FTS-only recall."""
    _ensure_autodetected()  # B2: self-initialise so recall isn't inert on turn 1
    adapter = _REGISTERED
    if adapter is not None and getattr(adapter, "is_local", False):
        return adapter
    return None


def reset_embedding_adapter() -> None:
    """Test helper — clear any installed adapter AND the autodetect latch, so
    the next `get_local_embedding_adapter` re-probes from a clean slate."""
    global _REGISTERED, _AUTODETECTED
    _REGISTERED = None
    _AUTODETECTED = False


__all__ = [
    "EmbeddingAdapter",
    "EmbeddingError",
    "get_embedding_adapter",
    "get_local_embedding_adapter",
    "register_embedding_adapter",
    "reset_embedding_adapter",
]
