"""Embedding provider + cache for skill-similarity work (M61).

VISION §5.5 + PLAN.md §11.1 list M61 (was M28b) as the deferred upgrade
to skill duplicate detection. M28 curator currently dedups skills via
title-token Jaccard only — it misses synonym pairs (`auth` vs
`authentication`, `db` vs `database`). M61 lifts that constraint by
embedding each skill's `name + description + body` and comparing
cosine distances. Embeddings are *optional*: when no API key for the
routed embedding provider is available, callers degrade to TF-IDF
cosine via `skill_dedup` — accuracy drops but the user still gets the
feature.

Two surfaces:

1. `EmbeddingProvider` Protocol with one method `embed(texts) ->
   list[list[float]]`. Kept separate from `core.provider.Provider`
   (which is text-completion shaped) so a future Voyage / Cohere /
   sentence-transformers adapter slots in without touching the LLM
   protocol.

2. JSON cache at `<project>/.veles/skill_embeddings.json`. Keyed on
   `sha256(name + description + body)` so an unchanged skill reuses
   its vector across runs. Cache invalidation is implicit: editing the
   skill body changes the hash, orphaning the old cache entry.
   Orphans accumulate over time but cost ~6KB per stale entry; a
   future `veles skill dedup --vacuum` can prune them.

3. `OpenAIEmbeddingAdapter` against the `openai` SDK works for both
   direct OpenAI and any OpenAI-compatible relay (set `base_url` to
   `https://openrouter.ai/api/v1` to use OpenRouter's embedding
   passthrough; same for Azure / custom proxies).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from veles.core.project import Project
from veles.core.skills import Skill

_CACHE_FILENAME = "skill_embeddings.json"
_DEFAULT_BATCH_SIZE = 32


class EmbeddingProvider(Protocol):
    """Anything that can embed a list of strings into fixed-length vectors."""

    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


# ---- adapters ----


@dataclass(slots=True)
class OpenAIEmbeddingAdapter:
    """OpenAI-shape embedding API (works against direct OpenAI + OpenRouter relay).

    `base_url=None` → direct OpenAI; pass
    `base_url="https://openrouter.ai/api/v1"` to route through OpenRouter
    (their embeddings endpoint is OpenAI-compatible).
    """

    model: str
    api_key: str | None = None
    base_url: str | None = None
    batch_size: int = _DEFAULT_BATCH_SIZE

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Import inside the method so tests with no openai dep can stub the
        # adapter wholesale without pulling the SDK on import.
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        out: list[list[float]] = []
        for batch in _chunks(texts, self.batch_size):
            response = client.embeddings.create(model=self.model, input=batch)
            out.extend([list(d.embedding) for d in response.data])
        return out


def _chunks(items: list[str], n: int) -> Iterable[list[str]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


# ---- cache ----


def cache_path(project: Project) -> Path:
    return project.state_dir / _CACHE_FILENAME


@dataclass(slots=True)
class _CacheEntry:
    name: str
    vector: list[float]


def skill_fingerprint(skill: Skill) -> str:
    """Stable SHA256 of the skill's identifying surface.

    Includes `name`, `description`, and `body` — the three fields the
    LLM actually reads. Tool list and parameter schema are deliberately
    excluded; they're metadata about the skill, not its semantic
    content, and rotating tools shouldn't invalidate the cached vector.
    """
    payload = f"{skill.name}\n---\n{skill.description}\n---\n{skill.body}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def skill_embed_text(skill: Skill, *, body_cap: int = 4_000) -> str:
    """Concatenate name + description + (capped) body for the embedding call.

    Real-world skill bodies can run to thousands of lines (entire
    workflows + examples); the embedding model has a hard token limit
    (~8K for text-embedding-3-small), so we cap the body and let the
    name+description dominate the vector. `body_cap` defaults to 4000
    chars ≈ 1K tokens, comfortably under provider limits.
    """
    body = skill.body or ""
    if len(body) > body_cap:
        body = body[: body_cap - 3] + "..."
    return f"{skill.name}\n\n{skill.description}\n\n{body}".strip()


def load_cache(project: Project, *, model: str) -> dict[str, _CacheEntry]:
    """Return `{fingerprint: _CacheEntry}` for the given model.

    Cache misses for *different* models silently return empty — the
    cache stores one model at a time. Switching the routed model
    therefore invalidates the cache wholesale (which is the desired
    behaviour: two models' vector spaces aren't comparable).
    """
    path = cache_path(project)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    if data.get("model") != model:
        return {}
    raw = data.get("vectors")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, _CacheEntry] = {}
    for fp, entry in raw.items():
        if not isinstance(fp, str) or not isinstance(entry, dict):
            continue
        name = entry.get("name")
        vector = entry.get("vector")
        if not isinstance(name, str) or not isinstance(vector, list):
            continue
        if not all(isinstance(v, int | float) for v in vector):
            continue
        out[fp] = _CacheEntry(name=name, vector=[float(v) for v in vector])
    return out


def save_cache(
    project: Project, *, model: str, vectors: dict[str, _CacheEntry]
) -> None:
    path = cache_path(project)
    project.state_dir.mkdir(parents=True, exist_ok=True)
    body = {
        "model": model,
        "vectors": {
            fp: {"name": entry.name, "vector": entry.vector}
            for fp, entry in sorted(vectors.items())
        },
    }
    text = json.dumps(body, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


# ---- top-level driver ----


def compute_skill_vectors(
    skills: list[Skill],
    *,
    provider: EmbeddingProvider,
    project: Project | None = None,
) -> dict[str, list[float]]:
    """Return `{skill.name: vector}` for every input skill.

    Uses the on-disk cache when `project` is supplied; skills with a
    cache hit on their current fingerprint skip the embedding call
    entirely. Cache misses are batched into a single provider call
    (the adapter handles internal batching too).
    """
    cache: dict[str, _CacheEntry] = (
        load_cache(project, model=provider.model) if project is not None else {}
    )
    name_to_vector: dict[str, list[float]] = {}
    misses: list[tuple[str, str, Skill]] = []  # (fingerprint, embed_text, skill)
    for skill in skills:
        fp = skill_fingerprint(skill)
        hit = cache.get(fp)
        if hit is not None:
            name_to_vector[skill.name] = hit.vector
            continue
        misses.append((fp, skill_embed_text(skill), skill))
    if misses:
        new_vectors = provider.embed([m[1] for m in misses])
        for (fp, _txt, skill), vec in zip(misses, new_vectors, strict=False):
            name_to_vector[skill.name] = vec
            cache[fp] = _CacheEntry(name=skill.name, vector=vec)
        if project is not None:
            save_cache(project, model=provider.model, vectors=cache)
    return name_to_vector


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity ∈ [-1, 1]. Zero-norm inputs → 0.0 (no signal)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
