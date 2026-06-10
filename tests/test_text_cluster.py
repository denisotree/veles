"""M142: generic TF-IDF cosine clustering, factored out of skill_dedup (M61)."""

from __future__ import annotations

import pytest

from veles.core.text_cluster import cluster_texts, sparse_cosine, tfidf_vectors


def test_cluster_groups_near_duplicates() -> None:
    texts = [
        "bump nginx worker_connections to handle more concurrent sockets",
        "increase nginx worker_connections for concurrent socket handling",
        "the lunch menu has sandwiches and coffee today",
    ]
    clusters = cluster_texts(texts, threshold=0.2)
    # the two nginx texts cluster; the lunch text is a dropped singleton
    assert len(clusters) == 1
    indices, score = clusters[0]
    assert set(indices) == {0, 1}
    assert 0.0 < score <= 1.0


def test_cluster_empty_when_all_unrelated() -> None:
    texts = ["apples oranges bananas", "quantum entanglement physics", "tax forms deadline"]
    assert cluster_texts(texts, threshold=0.3) == []


def test_cluster_singleton_input() -> None:
    assert cluster_texts(["only one document here"], threshold=0.1) == []


def test_sparse_cosine_identical_is_one() -> None:
    [v] = tfidf_vectors(["same words same words"])
    assert sparse_cosine(v, v) == pytest.approx(1.0)
