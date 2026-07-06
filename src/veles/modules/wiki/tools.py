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

import contextlib

from veles.core.context import current_project
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool
from veles.modules.wiki.wiki import Wiki


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

    `category` must be an allowed category for this project — the core defaults
    (concepts, entities, sources, queries, sessions, self-doc) plus any declared
    for the project (in `.veles/wiki.toml`, e.g. diary/tasks/projects). Nested
    paths like `projects/work` are allowed. To use a NEW category first declare
    it with `wiki_add_category`. `content` is the markdown body (H1 added if
    missing). INDEX.md is rewritten after the write.
    """
    try:
        rel = _default_wiki().write_page(category=category, slug=slug, title=title, content=content)
    except ValueError as exc:
        return f"<error: {exc}>"
    return f"wrote {rel}"


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, sensitive=True, side_effects=["filesystem"])
def wiki_add_category(name: str) -> str:
    """Declare a NEW wiki category for THIS project and create its directory.

    The framework ships no project-specific categories — this is how you extend
    the wiki structure for a kind of data the user describes (diary, tasks,
    projects, meetings, …). The declaration is persisted to `.veles/wiki.toml`
    (so it survives and is picked up by every wiki write), and the directory is
    created. Nested paths like `projects/work` are allowed. After this,
    `wiki_write_page(category="<name>", …)` works. Idempotent.
    """
    from veles.modules.wiki.wiki import add_project_category

    proj = current_project()
    if proj is None:
        return "<error: no active Veles project>"
    added, result = add_project_category(proj.wiki_root, name)
    if result.startswith("<error"):
        return result
    _default_wiki().ensure_layout()  # materialize the new dir(s)
    if not added:
        return f"category {result!r} already available (wiki/{result}/)"
    return f"declared category {result!r} and created wiki/{result}/"


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, sensitive=True, side_effects=["filesystem"])
def wiki_rename_page(rel_path: str, new_category: str, new_slug: str) -> str:
    """Move/rename a wiki page and repair references to it (M175).

    Re-files `rel_path` (e.g. 'wiki/sources/foo.md') to
    `wiki/<new_category>/<new_slug>.md`, rewrites every `[[old-slug]]`
    wikilink across the wiki to `[[new-slug]]`, deletes the old file, and
    refreshes INDEX.md. `new_category` must be a valid wiki category
    (concepts / entities / sources). Use this instead of `move_file` for
    wiki pages so inbound links and the index don't go stale.

    Returns the new relative path, or a `<error: ...>` marker.
    """
    wiki = _default_wiki()
    old_slug = rel_path.rsplit("/", 1)[-1].removesuffix(".md")
    try:
        title = next(
            (p.title for p in wiki.list_pages() if p.rel_path == rel_path),
            old_slug,
        )
        content = wiki.read_page(rel_path)
    except (FileNotFoundError, ValueError) as exc:
        return f"<error: {exc}>"
    try:
        new_rel = wiki.write_page(
            category=new_category, slug=new_slug, title=title, content=content
        )
    except ValueError as exc:
        return f"<error: {exc}>"
    if new_rel == rel_path:
        return f"<error: target {new_rel} is the same page (no-op)>"
    # Remove the old file now that the new one is written.
    old_path = wiki.root / rel_path
    with contextlib.suppress(OSError):
        old_path.unlink()
    # Repair inbound [[old-slug]] links across every page, then reindex.
    clean_new_slug = new_rel.rsplit("/", 1)[-1].removesuffix(".md")
    repaired = 0
    if clean_new_slug != old_slug:
        for page in wiki.list_pages():
            ppath = wiki.root / page.rel_path
            try:
                text = ppath.read_text(encoding="utf-8")
            except OSError:
                continue
            updated = text.replace(f"[[{old_slug}]]", f"[[{clean_new_slug}]]")
            if updated != text:
                ppath.write_text(updated, encoding="utf-8")
                repaired += 1
    wiki.update_index()
    wiki.append_log(op="rename", summary=f"{rel_path} -> {new_rel} ({repaired} links repaired)")
    return f"renamed {rel_path} -> {new_rel} ({repaired} link(s) repaired)"


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["filesystem"])
def wiki_append_log(op: str, summary: str) -> str:
    """Append a journal entry to LOG.md."""
    _default_wiki().append_log(op=op, summary=summary)
    return f"logged {op}"


@tool(risk_class=RiskClass.WRITE_LOCAL_PROJECT, side_effects=["network", "filesystem"])
def wiki_ingest(
    source: str,
    category: str = "concepts",
    slug: str | None = None,
    title: str | None = None,
) -> str:
    """M86: one-shot ingest — fetch a URL (or read a local file) and save
    it as a wiki page.

    `source` is either a URL (http:// / https://) or a path. `category`
    defaults to 'concepts'; use 'entities' for people/orgs/works, or a topical
    project category. (M203: there is no `sources` page category — raw
    originals live in the top-level `sources/` tree, not the wiki.) `slug`
    defaults to a kebab-case form of `title` or the source basename. The page
    body is the raw text when no `title` is supplied, or a minimal markdown
    wrap otherwise.

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
