"""Skill duplicate detection (M61) — embedding or TF-IDF cosine clustering.

Closes the M28b gap left in the M32 wiki linter: title-Jaccard misses
synonym pairs (`auth` vs `authentication`). M61 adds two stronger
similarity signals:

1. **TF-IDF cosine** over `name + description + body`. Pure-Python,
   no external API. Catches whole-body co-occurrence (a skill about
   `auth` that mentions `login`/`signin`/`signup` clusters with one
   about `authentication` mentioning the same vocabulary). Doesn't
   catch true synonyms across separate corpora.

2. **Embedding cosine** via `skill_embedding.OpenAIEmbeddingAdapter`.
   Catches true synonyms; costs one embedding API call per skill on a
   cold cache, then cache reads thereafter.

`find_duplicate_skills(skills, *, threshold, mode)` is the public
entry point. `mode='auto'` (default) tries embeddings via the routed
`embedding` task and falls back to TF-IDF when the routed provider is
unreachable. Use `mode='tfidf'` to force the deps-free path,
`mode='embedding'` to require embeddings (raises on failure).

The output is a list of clusters: `list[SkillCluster]`, where a
cluster carries the contributing `Skill`s plus the mean pairwise
similarity score. Single-skill "clusters" are dropped — only ≥2.

Tiebreaker for downstream consumers: when the user/curator picks
which skill in a cluster to keep, rank by
`use_count * success_rate` (M25 telemetry). M61 surfaces clusters;
the curator's promotion/archival decision logic is M61b.
"""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.project import Project
from veles.core.skills import Skill
from veles.core.text_cluster import cluster_indices, sparse_cosine, tfidf_vectors

_DEFAULT_EMBEDDING_THRESHOLD = 0.85
_DEFAULT_TFIDF_THRESHOLD = 0.50


@dataclass(frozen=True, slots=True)
class SkillCluster:
    """One group of skills judged to be near-duplicates of each other."""

    skills: list[Skill]
    score: float  # mean pairwise similarity, 0..1
    mode: str  # 'embedding' or 'tfidf' — which signal produced the cluster


# ---- TF-IDF (pure-Python, no API) ----
#
# M142: the TF-IDF math (tokens / vectors / cosine) and the union-find
# clustering moved to `core/text_cluster.py` so insight dedup shares one
# implementation. This module keeps only the skill-specific document shaping
# and the `SkillCluster` wrapping.


def _document_text(skill: Skill, *, body_cap: int = 4_000) -> str:
    body = skill.body or ""
    if len(body) > body_cap:
        body = body[:body_cap]
    return f"{skill.name} {skill.description} {body}"


def _tfidf_vectors(skills: list[Skill]) -> dict[str, dict[str, float]]:
    """Return `{skill.name: {token: tf-idf weight}}`."""
    if not skills:
        return {}
    vecs = tfidf_vectors([_document_text(s) for s in skills])
    return {s.name: vecs[i] for i, s in enumerate(skills)}


def find_duplicates_tfidf(
    skills: list[Skill], *, threshold: float = _DEFAULT_TFIDF_THRESHOLD
) -> list[SkillCluster]:
    """TF-IDF cosine clustering. No external API, deterministic."""
    if len(skills) < 2:
        return []
    vectors = _tfidf_vectors(skills)
    return _cluster_by_pairwise(skills, vectors, sparse_cosine, threshold, mode="tfidf")


# ---- embedding-based ----


def find_duplicates_embedding(
    skills: list[Skill],
    *,
    provider,  # EmbeddingProvider
    project: Project | None = None,
    threshold: float = _DEFAULT_EMBEDDING_THRESHOLD,
) -> list[SkillCluster]:
    """Embedding cosine clustering. Routes through `compute_skill_vectors`."""
    from veles.core.skill_embedding import compute_skill_vectors, cosine_similarity

    if len(skills) < 2:
        return []
    name_to_vec = compute_skill_vectors(skills, provider=provider, project=project)
    if not name_to_vec:
        return []
    return _cluster_by_pairwise(
        skills,
        {s.name: name_to_vec.get(s.name, []) for s in skills},
        cosine_similarity,
        threshold,
        mode="embedding",
    )


# ---- auto mode ----


def find_duplicate_skills(
    skills: list[Skill],
    *,
    project: Project | None = None,
    mode: str = "auto",
    embedding_threshold: float = _DEFAULT_EMBEDDING_THRESHOLD,
    tfidf_threshold: float = _DEFAULT_TFIDF_THRESHOLD,
) -> tuple[list[SkillCluster], str]:
    """Public entry point. Returns `(clusters, mode_actually_used)`.

    `mode='auto'`: try embeddings via routed `embedding` task; if that
    raises / no API key / no project / provider construction fails,
    fall back to TF-IDF. The second element of the return tuple
    reports which path was taken so the CLI can mention it.

    `mode='tfidf'`: skip embeddings entirely.

    `mode='embedding'`: refuse to fall back — propagate the underlying
    error so the user knows their routing isn't working.
    """
    if mode not in ("auto", "tfidf", "embedding"):
        raise ValueError(f"mode must be 'auto' / 'tfidf' / 'embedding', got {mode!r}")
    if mode == "tfidf":
        return find_duplicates_tfidf(skills, threshold=tfidf_threshold), "tfidf"
    if mode == "embedding":
        provider = _build_embedding_provider(project)
        return (
            find_duplicates_embedding(
                skills,
                provider=provider,
                project=project,
                threshold=embedding_threshold,
            ),
            "embedding",
        )
    # auto
    try:
        provider = _build_embedding_provider(project)
        clusters = find_duplicates_embedding(
            skills,
            provider=provider,
            project=project,
            threshold=embedding_threshold,
        )
        return clusters, "embedding"
    except Exception:
        return find_duplicates_tfidf(skills, threshold=tfidf_threshold), "tfidf"


def _build_embedding_provider(project: Project | None):
    """Construct an `EmbeddingProvider` from the routed `embedding` task.

    Resolution: `route("embedding", project)` → `(provider_name, model)`.
    Currently only `openai` and `openrouter` produce a working adapter
    (both are OpenAI-shape); other provider names raise so `auto` mode
    can degrade.
    """
    if project is None:
        raise RuntimeError("embedding mode requires an active project for routing")
    from veles.core.provider_factory import PROVIDER_API_KEY_ENVS
    from veles.core.routing import route
    from veles.core.skill_embedding import OpenAIEmbeddingAdapter

    provider_name, model = route("embedding", project)
    env_names = PROVIDER_API_KEY_ENVS.get(provider_name) or ()
    api_key: str | None = None
    import os

    for env_name in env_names:
        api_key = os.environ.get(env_name)
        if api_key:
            break
    if not api_key and provider_name in ("openai", "openrouter"):
        raise RuntimeError(f"no API key for routed embedding provider {provider_name!r}")
    base_url = "https://openrouter.ai/api/v1" if provider_name == "openrouter" else None
    if provider_name not in ("openai", "openrouter"):
        raise RuntimeError(
            f"embedding provider {provider_name!r} is not supported; route to openai or openrouter"
        )
    return OpenAIEmbeddingAdapter(model=model, api_key=api_key, base_url=base_url)


# ---- clustering ----


def _cluster_by_pairwise(
    skills: list[Skill],
    vectors: dict,
    similarity_fn,
    threshold: float,
    *,
    mode: str,
) -> list[SkillCluster]:
    """Cluster skills via the shared `text_cluster.cluster_indices` (M142).

    A missing vector for either skill yields similarity 0.0 (that pair never
    clusters), preserving the M61 behaviour of skipping vector-less skills.
    Re-sorts by `(-score, first-skill-name)` to keep the M61 tiebreak."""

    def sim(i: int, j: int) -> float:
        va = vectors.get(skills[i].name)
        vb = vectors.get(skills[j].name)
        if not va or not vb:
            return 0.0
        return similarity_fn(va, vb)

    clusters = [
        SkillCluster(skills=[skills[i] for i in indices], score=score, mode=mode)
        for indices, score in cluster_indices(len(skills), sim, threshold)
    ]
    clusters.sort(key=lambda c: (-c.score, c.skills[0].name))
    return clusters
