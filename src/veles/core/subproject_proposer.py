"""Agent-initiated subproject proposal (M62) — closes VISION §2.2.

VISION §2.2 says: "Декомпозицию инициирует агент: при росте контекста
или wiki видит смысловые кластеры и предлагает выделить подпроект;
пользователь одобряет." M41 shipped the *infrastructure* for vertical
subprojects (init/list/switch/remove + the registry + memory router
fan-out), but nothing inside Veles ever actually *proposes* that a
cluster of related wiki pages should be split off — the user had to
notice the clustering themselves and run `veles subproject init`.

M62 closes that behavioural gap with a deterministic, LLM-free cluster
detector. It walks the project's wiki pages in `concepts` + `entities`
(the categories VISION §5.2 calls "smysolovyye klastery"), tokenises
titles with the same stopword filter the M32 linter uses, builds a
similarity graph via title-token Jaccard ≥ threshold, and returns
connected components of size ≥ N as candidate subprojects.

Output side has three surfaces:

1. `detect_clusters(project, ...)` — pure function returning a list of
   `Cluster` objects. Used directly by the CLI verb
   `veles subproject suggest` and by the curator auto-trigger.
2. `write_proposals(project, clusters)` — persists each cluster as a
   markdown page under `.veles/memory/proposals/<slug>.md` (M160 —
   proposals are the agent's own memory, not user content) plus a
   system-ops journal entry.
3. `recent_proposals(project, max_age_days)` — lists existing
   proposals younger than `max_age_days`; used by both the CLI to
   avoid duplicate proposals and by the system-prompt block to
   surface fresh suggestions to the agent.

The detector is deterministic + cheap (tens of ms for a project with
hundreds of pages), so the auto-trigger can fire on every `veles run`
post-turn without LLM cost. Proposals reach the agent via the
`<subproject-proposals>` system-prompt block (`memory/injector.py`),
not via wiki FTS recall.
"""

from __future__ import annotations

import datetime as _dt
import re
import time
from dataclasses import dataclass
from pathlib import Path

from veles.core.memory.artefacts import (
    ProposalInfo,
    append_memory_log,
    list_proposals,
    proposals_dir,
    write_proposal,
)
from veles.core.project import Project
from veles.core.wiki import Wiki, WikiPageInfo

_CLUSTER_CATEGORIES = frozenset({"concepts", "entities"})
_DEFAULT_MIN_PAGES = 4
_DEFAULT_MIN_SIMILARITY = 0.25
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "this",
        "that",
        "page",
        "part",
        "about",
        "over",
    }
)


@dataclass(frozen=True, slots=True)
class Cluster:
    """One candidate subproject.

    `slug` is a deterministic kebab-case identifier derived from the
    most-common shared tokens in the cluster. `pages` are the
    `rel_path`s of the wiki pages forming the cluster. `score` is the
    mean pairwise Jaccard similarity inside the cluster (0..1).
    `rationale` is a one-line explanation suitable for the proposal
    page's body.
    """

    slug: str
    pages: list[str]
    score: float
    rationale: str


def _tokens(title: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(title.lower()) if len(t) > 2 and t not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def detect_clusters(
    project: Project,
    *,
    min_pages: int = _DEFAULT_MIN_PAGES,
    min_similarity: float = _DEFAULT_MIN_SIMILARITY,
) -> list[Cluster]:
    """Find thematic clusters in `wiki/concepts/` + `wiki/entities/`.

    Two pages are connected when their title-token Jaccard similarity
    is ≥ `min_similarity`. Connected components of size ≥ `min_pages`
    become clusters. Returns clusters sorted by score descending.
    """
    wiki = Wiki(project.wiki_root)
    pages = [p for p in wiki.list_pages() if p.category in _CLUSTER_CATEGORIES]
    if len(pages) < min_pages:
        return []

    tokens_by_index: dict[int, set[str]] = {}
    for i, p in enumerate(pages):
        tokens_by_index[i] = _tokens(p.title)

    parent = list(range(len(pages)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    edges: list[tuple[int, int, float]] = []
    for i in range(len(pages)):
        for j in range(i + 1, len(pages)):
            sim = _jaccard(tokens_by_index[i], tokens_by_index[j])
            if sim >= min_similarity:
                union(i, j)
                edges.append((i, j, sim))

    components: dict[int, list[int]] = {}
    for i in range(len(pages)):
        components.setdefault(find(i), []).append(i)

    clusters: list[Cluster] = []
    for indices in components.values():
        if len(indices) < min_pages:
            continue
        sims = [sim for i, j, sim in edges if i in indices and j in indices]
        if not sims:
            continue
        score = sum(sims) / len(sims)
        cluster_pages = sorted(pages[idx].rel_path for idx in indices)
        slug, rationale = _build_cluster_summary([pages[idx] for idx in indices])
        clusters.append(Cluster(slug=slug, pages=cluster_pages, score=score, rationale=rationale))

    clusters.sort(key=lambda c: (-c.score, c.slug))
    return clusters


def _build_cluster_summary(pages: list[WikiPageInfo]) -> tuple[str, str]:
    """Pick a slug + one-line rationale for a cluster.

    Slug = the 1-2 most-frequent shared tokens across cluster titles
    (kebab-joined). Rationale enumerates the page count + the leading
    shared topic so the agent + user can decide on relevance.
    """
    token_counts: dict[str, int] = {}
    for p in pages:
        for tok in _tokens(p.title):
            token_counts[tok] = token_counts.get(tok, 0) + 1
    threshold = max(2, len(pages) // 2)
    common = sorted(
        ((tok, n) for tok, n in token_counts.items() if n >= threshold),
        key=lambda kv: (-kv[1], kv[0]),
    )
    leading = [tok for tok, _ in common[:2]]
    slug = "-".join(leading) if leading else "cluster"
    rationale = (
        f"{len(pages)} wiki pages share thematic tokens "
        f"{', '.join(leading) or '(generic)'}; consider extracting into a subproject."
    )
    return slug, rationale


def proposal_page_path(project: Project, cluster: Cluster) -> Path:
    return proposals_dir(project) / f"{cluster.slug}.md"


def _render_proposal(cluster: Cluster) -> tuple[str, str]:
    """Return (title, body) for a proposal markdown page."""
    title = f"Subproject proposal: {cluster.slug}"
    lines = [
        f"# {title}",
        "",
        f"**Generated:** {_dt.datetime.now(tz=_dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"**Cohesion score:** {cluster.score:.2f}",
        "",
        cluster.rationale,
        "",
        "## Pages in this cluster",
        "",
    ]
    lines.extend(f"- {rel}" for rel in cluster.pages)
    lines.extend(
        [
            "",
            "## Suggested action",
            "",
            f"Initialise a subproject with: `veles subproject init {cluster.slug}`",
            "",
            "Move the pages above into the new subproject's `wiki/` once you "
            "confirm the clustering reflects a real semantic boundary.",
        ]
    )
    return title, "\n".join(lines) + "\n"


def write_proposals(project: Project, clusters: list[Cluster]) -> list[str]:
    """Persist each cluster as `.veles/memory/proposals/<slug>.md`.

    Returns the written paths relative to the project root. Idempotent
    rewrites: an existing proposal with the same slug is overwritten so
    the cohesion score / page list stay current. Each write is
    journalled to the system-ops log.
    """
    written: list[str] = []
    for cluster in clusters:
        title, body = _render_proposal(cluster)
        path = write_proposal(project, slug=cluster.slug, title=title, content=body)
        append_memory_log(
            project,
            op="subproject-proposal",
            summary=(
                f"proposed subproject '{cluster.slug}' "
                f"({len(cluster.pages)} pages, score {cluster.score:.2f})"
            ),
        )
        written.append(path.relative_to(project.root).as_posix())
    return written


def recent_proposals(project: Project, *, max_age_days: int = 7) -> list[ProposalInfo]:
    """Return proposal pages whose mtime is newer than `max_age_days` ago."""
    cutoff = time.time() - max_age_days * 86_400
    out: list[ProposalInfo] = []
    for page in list_proposals(project):
        try:
            mtime = page.path.stat().st_mtime
        except OSError:
            continue
        if mtime >= cutoff:
            out.append(page)
    return out
