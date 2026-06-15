"""M61 — TF-IDF + embedding clustering."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import Project, init_project
from veles.core.skill_dedup import (
    SkillCluster,
    find_duplicate_skills,
    find_duplicates_embedding,
    find_duplicates_tfidf,
)
from veles.core.skills import Skill


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


def _make_skill(name: str, description: str, body: str = "") -> Skill:
    return Skill(name=name, description=description, body=body, path=Path("/tmp"))


# ---- TF-IDF clustering ----


def test_tfidf_returns_empty_below_two_skills() -> None:
    assert find_duplicates_tfidf([_make_skill("only", "alone")]) == []


def test_tfidf_clusters_overlapping_skills() -> None:
    skills = [
        _make_skill(
            "auth-login",
            "user login flow",
            "login button signup register password reset",
        ),
        _make_skill(
            "auth-signup",
            "user signup flow",
            "login signup register password reset email",
        ),
        _make_skill(
            "build-pipeline",
            "ci/cd build",
            "docker compose pipeline deploy artifact",
        ),
    ]
    clusters = find_duplicates_tfidf(skills, threshold=0.3)
    assert len(clusters) == 1
    names = {s.name for s in clusters[0].skills}
    assert names == {"auth-login", "auth-signup"}


def test_tfidf_high_threshold_yields_nothing() -> None:
    skills = [
        _make_skill("a", "one", "alpha beta"),
        _make_skill("b", "two", "beta gamma"),
    ]
    assert find_duplicates_tfidf(skills, threshold=0.99) == []


def test_tfidf_handles_empty_bodies() -> None:
    skills = [
        _make_skill("a", "", ""),
        _make_skill("b", "", ""),
    ]
    # No tokens → no edges → no clusters; must not crash.
    assert find_duplicates_tfidf(skills) == []


# ---- embedding clustering ----


class _StubEmbedProvider:
    """Returns synthetic vectors so the cluster math is deterministic."""

    def __init__(self, mapping: dict[str, list[float]]):
        self.model = "stub"
        self.mapping = mapping
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        # The skill name is the first token of the embed text.
        out = []
        for t in texts:
            name = t.split("\n", 1)[0]
            out.append(self.mapping.get(name, [0.0, 0.0, 1.0]))
        return out


def test_embedding_clusters_high_cosine_neighbours(project: Project) -> None:
    skills = [
        _make_skill("auth", "do auth", "body1"),
        _make_skill("authentication", "do authentication", "body1"),
        _make_skill("billing", "do billing", "body3"),
    ]
    # auth ~ authentication (almost parallel vectors), billing orthogonal.
    provider = _StubEmbedProvider(
        {
            "auth": [1.0, 0.1, 0.0],
            "authentication": [0.99, 0.05, 0.0],
            "billing": [0.0, 0.0, 1.0],
        }
    )
    clusters = find_duplicates_embedding(skills, provider=provider, project=project, threshold=0.9)
    assert len(clusters) == 1
    names = {s.name for s in clusters[0].skills}
    assert names == {"auth", "authentication"}


def test_embedding_threshold_separates_clusters(project: Project) -> None:
    skills = [
        _make_skill("auth", "x", "y"),
        _make_skill("authentication", "x", "y"),
    ]
    provider = _StubEmbedProvider(
        {
            "auth": [1.0, 0.0],
            "authentication": [0.5, 1.0],  # cosine ~0.45
        }
    )
    # High threshold → no cluster.
    clusters = find_duplicates_embedding(skills, provider=provider, project=project, threshold=0.9)
    assert clusters == []


# ---- auto mode ----


def test_auto_mode_falls_back_to_tfidf_without_api_key(project: Project, monkeypatch) -> None:
    """Auto mode degrades to TF-IDF when the routed embedding provider has no key."""
    for env in ("OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    skills = [
        _make_skill("auth-login", "user login", "login signin password reset"),
        _make_skill("auth-signup", "user signup", "login signin password reset"),
    ]
    clusters, mode = find_duplicate_skills(skills, project=project, mode="auto")
    assert mode == "tfidf"
    assert len(clusters) == 1


def test_explicit_tfidf_mode_does_not_touch_embedding(project: Project) -> None:
    skills = [
        _make_skill("a", "x", "alpha beta gamma"),
        _make_skill("b", "x", "alpha beta gamma"),
    ]
    clusters, mode = find_duplicate_skills(skills, project=project, mode="tfidf")
    assert mode == "tfidf"
    assert len(clusters) == 1


def test_explicit_embedding_mode_propagates_error(project: Project, monkeypatch) -> None:
    """`mode='embedding'` refuses to fall back — propagates the error. With no
    `[routing.tasks].embedding` configured (M165d: no hardcoded default) that's a
    clear ConfigurationError, not a silent tfidf fallback."""
    for env in ("OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    skills = [_make_skill("a", "x"), _make_skill("b", "x")]
    with pytest.raises(Exception, match="no model configured"):
        find_duplicate_skills(skills, project=project, mode="embedding")


def test_auto_mode_uses_embedding_when_provider_available(project: Project, monkeypatch) -> None:
    """If a stubbed embedding adapter works, auto mode picks it."""
    monkeypatch.setenv("OPENAI_API_KEY", "stub")
    from veles.core import skill_dedup

    def _fake_builder(_project):
        return _StubEmbedProvider({"auth": [1.0, 0.1], "authentication": [0.99, 0.05]})

    monkeypatch.setattr(skill_dedup, "_build_embedding_provider", _fake_builder)
    skills = [
        _make_skill("auth", "x", "y"),
        _make_skill("authentication", "x", "y"),
    ]
    clusters, mode = find_duplicate_skills(skills, project=project, mode="auto")
    assert mode == "embedding"
    assert len(clusters) == 1


# ---- output shape ----


def test_clusters_carry_mode_label() -> None:
    skills = [
        _make_skill("a", "alpha", "alpha beta gamma"),
        _make_skill("b", "alpha", "alpha beta gamma"),
    ]
    clusters = find_duplicates_tfidf(skills, threshold=0.5)
    assert clusters
    assert all(isinstance(c, SkillCluster) for c in clusters)
    assert clusters[0].mode == "tfidf"
    # Float-arith tolerance: cosine math can land at 1.0 + tiny epsilon.
    assert -0.01 <= clusters[0].score <= 1.01
