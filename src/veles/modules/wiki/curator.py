"""The wiki engine's `curator_target` and `subproject_source` contributions (moved
from `runtime/learning.py` / `core/subproject_proposer.py`): curated sessions land
as wiki pages (plus a memory insight); wiki pages feed subproject clustering."""

from __future__ import annotations

from pathlib import Path

from veles.sdk import Project
from veles.sdk.layout import LayoutManifest

from .wiki import Wiki, WikiPageInfo


def prepare(project: Project) -> None:
    Wiki(project.wiki_root).ensure_layout()


def instructions(project: Project, session_id: str) -> tuple[str, str, str]:
    persist_steps = (
        f'- Call wiki_write_page(category="sessions", slug="{session_id}",'
        " title=..., content=...).\n"
        "- Call memory_save_insight(title=<same title>, body=<a 2-4 sentence"
        ' summary>, category="curated-session", file_path=<the wiki page path>)'
        " so the insight surfaces in /insights and recall.\n"
    )
    log_step = (
        '- Call wiki_append_log(op="curate",'
        f' summary="<one-line summary>: session {session_id}").\n'
        "- Reply with one sentence confirming the page path.\n\n"
    )
    intro = "Distill this Veles session into a single persistent wiki page."
    return intro, persist_steps, log_step


def pages(project: Project) -> list[WikiPageInfo]:
    return Wiki(project.wiki_root).list_pages()


def write_page(project: Project, category: str, slug: str, title: str, content: str) -> str:
    """The `page_store` contribution's writer: `wiki/<category>/<slug>.md`."""
    return Wiki(project.wiki_root).write_page(
        category=category, slug=slug, title=title, content=content
    )


def read_page(project: Project, category: str, slug: str) -> str | None:
    try:
        return Wiki(project.wiki_root).read_page(f"wiki/{category}/{slug}.md")
    except (OSError, ValueError):
        return None


def scaffold(root: Path, manifest: LayoutManifest) -> None:
    """The `scaffold` contribution: the wiki tree for a pack that asks for the engine.
    No FTS index here — search falls back to a page scan until dream's reindex
    step builds one, so init leaves no index file behind."""
    if manifest.engine_enabled("wiki"):
        Wiki(root).ensure_layout()
