"""Wiki recall — the engine's `recall` contribution (moved from `core/memory/router.py`).

A project whose layout pack doesn't enable the wiki engine contributes no wiki
hits; recall still works off insights/rules/turns/extras. The same check applies
per subproject — each child's own layout decides.
"""

from __future__ import annotations

from veles.modules.wiki.wiki import Wiki, wiki_enabled
from veles.sdk import Project, load_project
from veles.sdk.layout import load_subprojects, resolve_subproject_path
from veles.sdk.memory import RecallHit


def wiki_recall(project: Project, query: str, *, limit: int) -> list[RecallHit]:
    hits: list[RecallHit] = []
    if wiki_enabled(project):
        hits.extend(
            RecallHit(rel_path=p.rel_path, title=p.title, summary=p.summary)
            for p in Wiki(project.wiki_root).search(query, limit=limit)
        )
    sub_limit = max(1, limit // 2)
    for sub in load_subprojects(project):
        sub_root = resolve_subproject_path(project, sub)
        # v2: subproject wiki lives at `<sub_root>/wiki/`, container
        # is the subproject root itself.
        if not (sub_root / ".veles").is_dir():
            continue
        if not _subproject_wiki_enabled(sub_root):
            continue
        for page in Wiki(sub_root).search(query, limit=sub_limit):
            hits.append(
                RecallHit(
                    rel_path=f"{sub.slug}:{page.rel_path}",
                    title=f"[{sub.slug}] {page.title}",
                    summary=page.summary,
                )
            )
    return hits


def _subproject_wiki_enabled(sub_root) -> bool:
    """Best-effort wiki-engine check for a subproject (its own layout
    decides). Unloadable child → no wiki hits from it."""
    try:
        return wiki_enabled(load_project(sub_root))
    except Exception:
        return False
