"""Autodetect the best available embedding backend.

Run once at daemon / CLI startup. Priority order:

1. **Ollama** — `localhost:11434/api/tags` answers. Cheapest path:
   no pip dep, no network egress, no API key. Picks the user's
   declared model via `VELES_OLLAMA_EMBED_MODEL` env (default
   `nomic-embed-text`).
2. **OpenRouter / OpenAI** — `OPENROUTER_API_KEY` or `OPENAI_API_KEY`
   env present. Same SDK Veles uses for chat completions; the user
   already paid the dependency cost.
3. **None** — no backend. Ranking call sites fall back to their
   token-based path, and `notice.maybe_surface_embedding_setup_hint`
   writes a **one-time** `setup-hint` insight so the user sees a
   friendly "embeddings would improve ranking; here's how" message
   without log spam.

The autodetect result is cached for the process lifetime — repeated
calls don't re-probe Ollama or re-read env. Tests can reset via
`reset_embedding_adapter()` from `veles.modules.embedding`.
"""

from __future__ import annotations

import logging

from veles.modules.embedding import (
    EmbeddingAdapter,
    get_embedding_adapter,
    register_embedding_adapter,
)
from veles.modules.embedding_ollama import OllamaEmbeddingAdapter, probe_ollama
from veles.modules.embedding_openai import build_from_env

logger = logging.getLogger(__name__)


def autodetect_embedding_adapter(
    *,
    force: bool = False,
) -> EmbeddingAdapter | None:
    """Pick the best available backend and register it. Returns the
    adapter (or None if nothing answers). Subsequent calls return
    the cached pick unless `force=True`.

    Order: Ollama → OpenAI/OpenRouter → None.

    Notes on the no-backend case: we deliberately do NOT raise.
    Ranking call sites have valid token-based fallbacks; the user
    sees a one-time `setup-hint` insight from
    `embedding_notice.py` instead of an error.
    """
    if not force:
        cached = get_embedding_adapter()
        if cached is not None:
            return cached

    # Tier 1: Ollama
    if probe_ollama():
        adapter = OllamaEmbeddingAdapter()
        register_embedding_adapter(adapter)
        logger.info("embedding backend: %s (Ollama detected)", adapter.name)
        return adapter

    # Tier 2: OpenAI / OpenRouter (cloud)
    cloud = build_from_env()
    if cloud is not None:
        register_embedding_adapter(cloud)
        logger.info("embedding backend: %s (env credentials)", cloud.name)
        return cloud

    # Tier 3: nothing — ranking falls back to token-based mode and
    # `embedding_notice` writes a one-time setup hint.
    register_embedding_adapter(None)
    logger.info(
        "embedding backend: not configured (token-based ranking active; "
        "see Veles setup hint in insights for upgrade options)"
    )
    return None


__all__ = ["autodetect_embedding_adapter"]
