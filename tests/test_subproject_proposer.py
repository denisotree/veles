"""M62 — detect_clusters + write_proposals + recent_proposals + memory injector."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from veles.core.memory.injector import build_proposals_block
from veles.core.project import Project, init_project
from veles.core.subproject_proposer import (
    Cluster,
    detect_clusters,
    recent_proposals,
    write_proposals,
)
from veles.core.wiki import Wiki


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


def _seed_pages(wiki: Wiki, pages: list[tuple[str, str, str]]) -> None:
    for category, slug, title in pages:
        wiki.write_page(category=category, slug=slug, title=title, content="placeholder body")


# ---- detect_clusters ----


def test_returns_empty_when_no_pages(project: Project) -> None:
    assert detect_clusters(project) == []


def test_returns_empty_below_min_pages(project: Project) -> None:
    wiki = Wiki(project.wiki_root)
    _seed_pages(
        wiki,
        [
            ("concepts", "frontend-auth", "Frontend auth"),
            ("concepts", "frontend-routes", "Frontend routes"),
        ],
    )
    assert detect_clusters(project) == []


def test_detects_single_cluster_in_concepts(project: Project) -> None:
    wiki = Wiki(project.wiki_root)
    _seed_pages(
        wiki,
        [
            ("concepts", "frontend-auth", "Frontend authentication"),
            ("concepts", "frontend-routes", "Frontend routes"),
            ("concepts", "frontend-state", "Frontend state management"),
            ("concepts", "frontend-build", "Frontend build pipeline"),
        ],
    )
    clusters = detect_clusters(project, min_pages=3, min_similarity=0.2)
    assert len(clusters) == 1
    assert "frontend" in clusters[0].slug
    assert len(clusters[0].pages) == 4
    assert all("frontend" in p for p in clusters[0].pages)


def test_detects_two_distinct_clusters(project: Project) -> None:
    wiki = Wiki(project.wiki_root)
    _seed_pages(
        wiki,
        [
            # Cluster A: frontend
            ("concepts", "frontend-auth", "Frontend authentication"),
            ("concepts", "frontend-routes", "Frontend routes"),
            ("concepts", "frontend-state", "Frontend state management"),
            # Cluster B: database
            ("concepts", "database-schema", "Database schema migrations"),
            ("concepts", "database-replication", "Database replication"),
            ("concepts", "database-backup", "Database backup strategy"),
        ],
    )
    clusters = detect_clusters(project, min_pages=3, min_similarity=0.2)
    assert len(clusters) == 2
    slugs = {c.slug for c in clusters}
    assert any("frontend" in s for s in slugs)
    assert any("database" in s for s in slugs)


def test_ignores_unrelated_categories(project: Project) -> None:
    wiki = Wiki(project.wiki_root)
    # Sessions / sources / insights are excluded by design (M32 _NOISE_CATEGORIES analog).
    _seed_pages(
        wiki,
        [
            ("sessions", "session-1", "Frontend auth"),
            ("sessions", "session-2", "Frontend routes"),
            ("sessions", "session-3", "Frontend state"),
            ("sessions", "session-4", "Frontend build"),
        ],
    )
    assert detect_clusters(project) == []


def test_entities_are_also_clustered(project: Project) -> None:
    wiki = Wiki(project.wiki_root)
    _seed_pages(
        wiki,
        [
            ("entities", "stripe", "Stripe payment provider"),
            ("entities", "paypal", "PayPal payment provider"),
            ("entities", "adyen", "Adyen payment provider"),
            ("entities", "braintree", "Braintree payment provider"),
        ],
    )
    clusters = detect_clusters(project, min_pages=3, min_similarity=0.2)
    assert len(clusters) == 1
    assert "payment" in clusters[0].slug or "provider" in clusters[0].slug


def test_high_similarity_threshold_yields_no_clusters(project: Project) -> None:
    wiki = Wiki(project.wiki_root)
    _seed_pages(
        wiki,
        [
            ("concepts", "a", "Auth flows"),
            ("concepts", "b", "Routing patterns"),
            ("concepts", "c", "State containers"),
            ("concepts", "d", "Build pipelines"),
        ],
    )
    # Each title is unique → Jaccard ~0, no edges → no clusters.
    assert detect_clusters(project, min_similarity=0.9) == []


def test_clusters_sorted_by_score_desc(project: Project) -> None:
    wiki = Wiki(project.wiki_root)
    # Strong cluster: 5 pages all with frontend+auth tokens
    _seed_pages(
        wiki,
        [
            ("concepts", "fa-1", "Frontend auth login"),
            ("concepts", "fa-2", "Frontend auth logout"),
            ("concepts", "fa-3", "Frontend auth signup"),
            ("concepts", "fa-4", "Frontend auth recovery"),
        ],
    )
    # Weaker cluster: 3 pages with shared 'database' but distinct extra tokens
    _seed_pages(
        wiki,
        [
            ("concepts", "db-1", "Database alpha schema"),
            ("concepts", "db-2", "Database beta replication"),
            ("concepts", "db-3", "Database gamma backup"),
        ],
    )
    clusters = detect_clusters(project, min_pages=3, min_similarity=0.2)
    assert len(clusters) >= 2
    # Strong (frontend auth) should be first.
    assert clusters[0].score >= clusters[-1].score


# ---- write_proposals ----


def test_write_proposals_creates_pages_in_memory_dir(project: Project) -> None:
    cluster = Cluster(
        slug="frontend-stack",
        pages=["wiki/concepts/a.md", "wiki/concepts/b.md"],
        score=0.5,
        rationale="2 pages share thematic tokens frontend.",
    )
    written = write_proposals(project, [cluster])
    assert len(written) == 1
    page_path = project.root / written[0]
    assert page_path.is_file()
    assert page_path.parent == project.memory_dir / "proposals"
    body = page_path.read_text(encoding="utf-8")
    assert "Subproject proposal" in body
    assert "veles subproject init frontend-stack" in body


def test_write_proposals_idempotent_rewrites(project: Project) -> None:
    cluster = Cluster(
        slug="frontend",
        pages=["wiki/concepts/a.md"],
        score=0.5,
        rationale="reason 1",
    )
    write_proposals(project, [cluster])
    cluster2 = Cluster(slug="frontend", pages=["wiki/concepts/a.md"], score=0.8, rationale="r2")
    write_proposals(project, [cluster2])
    body = (project.memory_dir / "proposals" / "frontend.md").read_text(encoding="utf-8")
    assert "0.80" in body


def test_write_proposals_appends_log(project: Project) -> None:
    cluster = Cluster(slug="cluster-x", pages=["wiki/concepts/a.md"], score=0.3, rationale="r")
    write_proposals(project, [cluster])
    log = (project.memory_dir / "LOG.md").read_text(encoding="utf-8")
    assert "subproject-proposal" in log
    assert "cluster-x" in log


# ---- recent_proposals ----


def test_recent_proposals_filters_by_age(project: Project) -> None:
    cluster = Cluster(slug="x", pages=["wiki/concepts/a.md"], score=0.3, rationale="r")
    write_proposals(project, [cluster])
    fresh = recent_proposals(project, max_age_days=7)
    assert len(fresh) == 1
    # Backdate the file 30 days
    page = project.memory_dir / "proposals" / "x.md"
    old = time.time() - 30 * 86400
    import os

    os.utime(page, (old, old))
    stale = recent_proposals(project, max_age_days=7)
    assert stale == []


def test_recent_proposals_empty_when_none(project: Project) -> None:
    assert recent_proposals(project) == []


# ---- memory injector ----


def test_build_proposals_block_returns_none_for_empty() -> None:
    assert build_proposals_block([]) is None


def test_build_proposals_block_renders_tag_and_slugs(project: Project) -> None:
    cluster = Cluster(slug="abc", pages=["wiki/concepts/a.md"], score=0.5, rationale="r")
    write_proposals(project, [cluster])
    pages = recent_proposals(project)
    block = build_proposals_block(pages)
    assert block is not None
    assert "<subproject-proposals>" in block
    assert "</subproject-proposals>" in block
    assert "abc" in block
    assert "veles subproject init" in block


def test_build_proposals_block_truncates_when_too_large() -> None:
    from pathlib import Path

    from veles.core.memory.artefacts import ProposalInfo

    huge = "x" * 5000
    pages = [
        ProposalInfo(
            slug=f"p{i}",
            title="title",
            summary=huge,
            path=Path(f"/nonexistent/p{i}.md"),
        )
        for i in range(20)
    ]
    block = build_proposals_block(pages, max_chars=400)
    assert block is not None
    assert len(block) <= 400
    assert "<subproject-proposals>" in block
    assert "</subproject-proposals>" in block
