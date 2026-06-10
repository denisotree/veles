"""M61 — embedding adapter + cache + cosine similarity."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import Project, init_project
from veles.core.skill_embedding import (
    _CacheEntry,
    compute_skill_vectors,
    cosine_similarity,
    load_cache,
    save_cache,
    skill_embed_text,
    skill_fingerprint,
)
from veles.core.skills import Skill


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


def _make_skill(
    name: str,
    description: str = "describe",
    body: str = "body content",
    *,
    use_count: int = 0,
    success_count: int = 0,
) -> Skill:
    return Skill(
        name=name,
        description=description,
        body=body,
        path=Path("/tmp/skill"),
        use_count=use_count,
        success_count=success_count,
    )


# ---- helpers ----


def test_skill_fingerprint_stable() -> None:
    s1 = _make_skill("auth", "do auth", "step 1\nstep 2")
    s2 = _make_skill("auth", "do auth", "step 1\nstep 2")
    assert skill_fingerprint(s1) == skill_fingerprint(s2)


def test_skill_fingerprint_changes_on_body_edit() -> None:
    s1 = _make_skill("auth", "do auth", "v1")
    s2 = _make_skill("auth", "do auth", "v2")
    assert skill_fingerprint(s1) != skill_fingerprint(s2)


def test_skill_embed_text_caps_long_body() -> None:
    big_body = "x" * 9_000
    s = _make_skill("big", "desc", big_body)
    out = skill_embed_text(s, body_cap=100)
    assert len(out) < 9_000
    assert out.startswith("big")
    assert "..." in out


def test_cosine_similarity_identical_vectors() -> None:
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_zero_norm() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_similarity_mismatched_length() -> None:
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0


# ---- cache ----


def test_load_cache_empty_when_missing(project: Project) -> None:
    assert load_cache(project, model="m1") == {}


def test_load_cache_returns_entries(project: Project) -> None:
    save_cache(
        project,
        model="m1",
        vectors={"hash1": _CacheEntry(name="auth", vector=[0.1, 0.2])},
    )
    out = load_cache(project, model="m1")
    assert "hash1" in out
    assert out["hash1"].name == "auth"
    assert out["hash1"].vector == [0.1, 0.2]


def test_load_cache_invalidates_on_model_mismatch(project: Project) -> None:
    save_cache(
        project,
        model="m1",
        vectors={"hash1": _CacheEntry(name="x", vector=[0.0])},
    )
    assert load_cache(project, model="m2") == {}


def test_load_cache_permissive_on_corrupt_json(project: Project) -> None:
    from veles.core.skill_embedding import cache_path

    path = cache_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    assert load_cache(project, model="m1") == {}


# ---- compute_skill_vectors ----


def _stub_provider(model: str = "stub-model"):
    """Returns an EmbeddingProvider whose embed() yields deterministic vectors."""

    class _Stub:
        def __init__(self, m: str) -> None:
            self.model = m
            self.calls: list[list[str]] = []

        def embed(self, texts: list[str]) -> list[list[float]]:
            self.calls.append(list(texts))
            return [[float(len(t) % 7), float(len(t) % 11), 1.0] for t in texts]

    return _Stub(model)


def test_compute_skill_vectors_populates_cache(project: Project) -> None:
    provider = _stub_provider()
    skills = [_make_skill("auth"), _make_skill("db")]
    out = compute_skill_vectors(skills, provider=provider, project=project)
    assert set(out) == {"auth", "db"}
    cached = load_cache(project, model=provider.model)
    assert len(cached) == 2


def test_compute_skill_vectors_reuses_cache(project: Project) -> None:
    provider = _stub_provider()
    skills = [_make_skill("auth"), _make_skill("db")]
    compute_skill_vectors(skills, provider=provider, project=project)
    # Second call against the same provider+skills must not embed.
    provider2 = _stub_provider()
    out = compute_skill_vectors(skills, provider=provider2, project=project)
    assert provider2.calls == []
    assert set(out) == {"auth", "db"}


def test_compute_skill_vectors_only_embeds_misses(project: Project) -> None:
    """Editing one skill's body should invalidate only its entry."""
    provider = _stub_provider()
    skills = [_make_skill("auth"), _make_skill("db", body="orig")]
    compute_skill_vectors(skills, provider=provider, project=project)
    # Edit db body → new fingerprint.
    edited = [_make_skill("auth"), _make_skill("db", body="EDITED")]
    provider2 = _stub_provider()
    compute_skill_vectors(edited, provider=provider2, project=project)
    assert len(provider2.calls) == 1
    assert len(provider2.calls[0]) == 1  # only the edited skill
