"""The wiki engine's `curator_target` and `subproject_source` contributions (moved
from `runtime/learning.py` / `core/subproject_proposer.py`): curated sessions land
as wiki pages (plus a memory insight); wiki pages feed subproject clustering."""

from __future__ import annotations

from veles.core.project import Project
from veles.modules.wiki.wiki import Wiki, WikiPageInfo


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
