"""Wiki-aware tools: read/write/search the project's LLM Wiki.

The wiki root is resolved on every call via `_default_wiki()` (no caching),
which reads the active project from a ContextVar in `core.context`. The CLI
sets the active project before invoking the agent; tests can do the same via
`set_active_project()`.

Read-only tools (`wiki_list_pages`, `wiki_read_page`, `wiki_search`) are safe
for any context. Write tools (`wiki_write_page`, `wiki_append_log`) are only
exposed during `veles ingest` via Registry.subset filtering — the agent in
`veles run` cannot call them.
"""

from __future__ import annotations

from veles.core.context import current_project
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool
from veles.core.wiki import Wiki


def _default_wiki() -> Wiki:
    proj = current_project()
    if proj is None:
        raise RuntimeError("no active Veles project; run `veles init` and ensure cwd is inside it")
    return Wiki(proj.wiki_root)


@tool(risk_class=RiskClass.READ_ONLY)
def wiki_list_pages() -> str:
    """List every wiki page grouped by category. Returns markdown bullets."""
    pages = _default_wiki().list_pages()
    if not pages:
        return "(wiki is empty)"
    lines: list[str] = []
    last_cat: str | None = None
    for p in pages:
        if p.category != last_cat:
            if last_cat is not None:
                lines.append("")
            lines.append(f"## {p.category}")
            last_cat = p.category
        summary = p.summary or "—"
        lines.append(f"- [{p.title}]({p.rel_path}) — {summary}")
    return "\n".join(lines)


@tool(risk_class=RiskClass.READ_ONLY)
def wiki_read_page(rel_path: str) -> str:
    """Read a wiki page by relative path (e.g. 'wiki/concepts/foo.md')."""
    try:
        return _default_wiki().read_page(rel_path)
    except (FileNotFoundError, ValueError) as exc:
        return f"<error: {exc}>"


@tool(risk_class=RiskClass.SEARCH_ONLY)
def wiki_search(query: str, limit: int = 10) -> str:
    """Substring-search wiki by title/slug/summary. Returns markdown matches."""
    hits = _default_wiki().search(query, limit=limit)
    if not hits:
        return f"(no matches for {query!r})"
    return "\n".join(
        f"- [{p.title}]({p.rel_path}) [{p.category}] — {p.summary or '—'}" for p in hits
    )


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["filesystem"])
def wiki_write_page(category: str, slug: str, title: str, content: str) -> str:
    """Create or overwrite wiki/<category>/<slug>.md.

    `category` must be one of: concepts, entities, sources.
    `content` is the markdown body. The H1 line is added automatically if
    missing. INDEX.md is rewritten atomically after the write.
    """
    try:
        rel = _default_wiki().write_page(category=category, slug=slug, title=title, content=content)
    except ValueError as exc:
        return f"<error: {exc}>"
    return f"wrote {rel}"


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["filesystem"])
def wiki_append_log(op: str, summary: str) -> str:
    """Append a journal entry to LOG.md."""
    _default_wiki().append_log(op=op, summary=summary)
    return f"logged {op}"


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["network", "filesystem"])
def wiki_ingest(
    source: str,
    category: str = "sources",
    slug: str | None = None,
    title: str | None = None,
) -> str:
    """M86: one-shot ingest — fetch a URL (or read a local file) and save
    it as a wiki page.

    `source` is either a URL (http:// / https://) or a path. `category`
    defaults to 'sources' (raw inputs); use 'concepts' / 'entities' when
    you've distilled the material. `slug` defaults to a kebab-case form
    of `title` or the source basename. The page body is the raw text
    when no `title` is supplied, or a minimal markdown wrap otherwise.

    Call this when the user shares a link / file worth preserving, or
    when you discover an authoritative reference mid-turn — it short-cuts
    the otherwise three-step fetch / read / write_page dance.
    """
    text: str
    fetched_url: str | None = None
    if source.startswith(("http://", "https://")):
        from veles.core.tools.builtin.fetch_url import fetch_url

        text = fetch_url(source)
        fetched_url = source
    else:
        from veles.core.tools.builtin.read_file import read_file

        text = read_file(source)
    inferred_title = title or _infer_title_from_text(text) or source.rsplit("/", 1)[-1]
    inferred_slug = slug or _kebab(inferred_title)
    if not inferred_slug:
        return "<error: could not derive slug from source>"
    body = text if title is None else f"# {inferred_title}\n\n{text}"
    wiki = _default_wiki()
    try:
        rel = wiki.write_page(
            category=category,
            slug=inferred_slug,
            title=inferred_title,
            content=body,
            source_url=fetched_url,
            trust="external" if fetched_url else "authoritative",
        )
    except ValueError as exc:
        return f"<error: {exc}>"
    wiki.append_log(op="ingest", summary=f"-> {rel}")
    return f"ingested {source!r} -> {rel}"


def _infer_title_from_text(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("# ").strip()
        return stripped[:80]
    return None


def _kebab(value: str) -> str:
    import re

    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return cleaned[:60]
