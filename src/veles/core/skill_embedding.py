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

2. Cache in memory.db (`skill_embeddings` table; was the JSON file
   `<project>/.veles/skill_embeddings.json`, imported once and deleted).
   Keyed on `sha256(name + description + body)` so an unchanged skill
   reuses its vector across runs; editing the body changes the hash.
   `save_cache` replaces the set, so stale entries don't accumulate.

3. `OpenAIEmbeddingAdapter` against the `openai` SDK works for both
   direct OpenAI and any OpenAI-compatible relay (set `base_url` to
   `https://openrouter.ai/api/v1` to use OpenRouter's embedding
   passthrough; same for Azure / custom proxies).
"""

from __future__ import annotations

import hashlib
import json
import struct
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
    """Return `{fingerprint: _CacheEntry}` for the given model, from memory.db.

    A different model's vectors are never returned — two models' vector spaces
    aren't comparable. A legacy `.veles/skill_embeddings.json` is imported on
    first use and deleted (a corrupt one is just deleted)."""
    from veles.core.memory.store import local_connection

    with local_connection(project) as conn:
        _import_legacy_json(project, conn)
        rows = conn.execute(
            "SELECT fingerprint, name, vector FROM skill_embeddings WHERE model = ?", (model,)
        ).fetchall()
    return {fp: _CacheEntry(name=name, vector=_unpack(blob)) for fp, name, blob in rows}


def save_cache(project: Project, *, model: str, vectors: dict[str, _CacheEntry]) -> None:
    """Replace the stored vectors with `vectors` (one model at a time, as before)."""
    from veles.core.memory.store import local_connection

    with local_connection(project) as conn:
        conn.execute("DELETE FROM skill_embeddings")
        conn.executemany(
            "INSERT INTO skill_embeddings(fingerprint, model, name, vector) VALUES (?, ?, ?, ?)",
            [(fp, model, e.name, _pack(e.vector)) for fp, e in sorted(vectors.items())],
        )
        conn.commit()


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}d", *vector)


def _unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 8}d", blob))


def _import_legacy_json(project: Project, conn) -> None:
    path = cache_path(project)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = None
    model = data.get("model") if isinstance(data, dict) else None
    raw = data.get("vectors") if isinstance(data, dict) else None
    if isinstance(model, str) and isinstance(raw, dict):
        rows = [
            (fp, model, e["name"], _pack([float(v) for v in e["vector"]]))
            for fp, e in raw.items()
            if isinstance(fp, str)
            and isinstance(e, dict)
            and isinstance(e.get("name"), str)
            and isinstance(e.get("vector"), list)
            and all(isinstance(v, int | float) for v in e["vector"])
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO skill_embeddings(fingerprint, model, name, vector)"
            " VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    path.unlink(missing_ok=True)


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
