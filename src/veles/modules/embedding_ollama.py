"""Ollama-backed embedding adapter.

HTTP-only — no pip dependency. The user installs Ollama separately
(`brew install ollama` / `curl -fsSL https://ollama.com/install.sh
| sh`) and pulls a model (`ollama pull nomic-embed-text`). Veles
probes `http://localhost:11434/api/tags` at startup to detect the
daemon; if present, this adapter wins.

Default model: **nomic-embed-text** (137M parameters, ~274MB,
768-dim, multilingual). The user can override via the
`VELES_OLLAMA_EMBED_MODEL` env var to swap in
`mxbai-embed-large` (1024-dim, ~670MB) or any other Ollama-known
embedding model.

Why HTTP and not the `ollama-python` library: the library is a thin
wrapper around the same HTTP endpoints, and avoiding it keeps Veles
free of an extra runtime dependency. `urllib.request` from stdlib
handles the call.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from veles.modules.embedding import EmbeddingError

logger = logging.getLogger(__name__)


_DEFAULT_MODEL = "nomic-embed-text"
_DEFAULT_HOST = "http://localhost:11434"
_DEFAULT_DIM = 768  # nomic-embed-text default; auto-detected on first call


class OllamaEmbeddingAdapter:
    """Implements the `EmbeddingAdapter` Protocol over a local Ollama
    daemon. Stateless after `__init__` — no connection is held; each
    `embed` call opens a fresh HTTP request, which is fine for the
    expected batch shapes (≤100 strings per call)."""

    # M192: marks this adapter as on-device — recall/backfill only send text
    # (queries, insight bodies) to `is_local` adapters, so a cloud embedder
    # never receives project content (local-first no-egress guarantee).
    is_local = True

    def __init__(
        self,
        *,
        model: str | None = None,
        host: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.model = model or os.environ.get("VELES_OLLAMA_EMBED_MODEL") or _DEFAULT_MODEL
        self.host = (host or os.environ.get("OLLAMA_HOST") or _DEFAULT_HOST).rstrip("/")
        self.timeout = timeout
        # Probed on first successful embed; kept as a class attr so
        # downstream callers can size their KNN matrix correctly.
        self.dim: int = _DEFAULT_DIM
        self.name = f"ollama:{self.model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Hit `/api/embeddings` for each text. Ollama's single-string
        endpoint is the cross-version-safe path; the batch endpoint
        (`/api/embed`) exists on newer Ollama but isn't universal."""
        if not texts:
            return []
        out: list[list[float]] = []
        url = f"{self.host}/api/embeddings"
        for text in texts:
            payload = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read()
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                raise EmbeddingError(f"ollama embed request failed: {exc}") from exc
            try:
                data = json.loads(body)
            except json.JSONDecodeError as exc:
                raise EmbeddingError(f"ollama returned non-JSON: {exc}") from exc
            vec = data.get("embedding")
            if not isinstance(vec, list):
                raise EmbeddingError(f"ollama embedding response missing 'embedding': {data}")
            floats = [float(x) for x in vec]
            if floats and self.dim != len(floats):
                self.dim = len(floats)
            out.append(floats)
        return out


def probe_ollama(host: str | None = None, *, timeout: float = 1.5) -> bool:
    """Best-effort liveness check. True when an Ollama daemon answers
    `/api/tags` (cheap; doesn't load any model). False on any error —
    autodetect treats that as "Ollama not available, try next tier"."""
    base = (host or os.environ.get("OLLAMA_HOST") or _DEFAULT_HOST).rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False
    except Exception:
        return False


__all__ = ["OllamaEmbeddingAdapter", "probe_ollama"]
