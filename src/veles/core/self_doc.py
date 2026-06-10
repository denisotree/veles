"""Self-documentation generator for Veles projects.

`generate_self_doc` collects runtime state (sessions, wiki pages, skills,
tools, routing, insights, LOG.md tail) into a `SelfDocReport` dataclass.
`render_self_doc` converts it to a markdown page.
`refresh_self_doc` calls both and persists the result to
`wiki/self-doc/overview.md`, returning the rel_path.

The page is FTS5-indexed and surfaces via memory recall when the agent asks
questions about project capabilities ("what tools do I have?", "which skills
are installed?").
"""

from __future__ import annotations

import datetime as _dt
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from veles.core.project import Project


@dataclass(frozen=True, slots=True)
class SelfDocReport:
    project_name: str
    created_at: str  # ISO-8601
    session_count: int
    wiki_page_count: int
    skills: list[tuple[str, str]]  # (name, description)
    tools: list[tuple[str, str]]  # (name, description) — passed in by caller
    routing: dict[str, str]  # task → "provider:model"
    wiki_categories: dict[str, int]  # category → page count
    recent_insights: list[str]  # rel_paths, ≤5
    log_tail: list[str]  # last 10 lines of LOG.md


def generate_self_doc(
    project: Project,
    *,
    tools: list[tuple[str, str]] | None = None,
) -> SelfDocReport:
    """Collect all project self-knowledge into a `SelfDocReport`."""
    from veles.core.memory import SessionStore
    from veles.core.routing import DEFAULT_TASKS, route
    from veles.core.skills import discover_skills
    from veles.core.wiki import Wiki

    # --- project meta ---
    created_iso = _dt.datetime.fromtimestamp(project.created_at, tz=_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # --- sessions ---
    with SessionStore(project.memory_db_path) as store:
        sessions = store.list_sessions(limit=99_999)
    session_count = len(sessions)

    # --- wiki pages ---
    wiki = Wiki(project.wiki_root)
    pages = wiki.list_pages()
    wiki_page_count = len(pages)

    # --- skills ---
    raw_skills = discover_skills(project)
    skills = [(s.name, s.description) for s in raw_skills]

    # --- tools ---
    if tools is None:
        tools = []

    # --- routing: one line per task in DEFAULT_TASKS ---
    routing: dict[str, str] = {}
    for task in DEFAULT_TASKS:
        try:
            provider, model = route(task, project)
            routing[task] = f"{provider}:{model}"
        except Exception:
            pass

    # --- wiki categories aggregation ---
    wiki_categories: dict[str, int] = {}
    for page in pages:
        wiki_categories[page.category] = wiki_categories.get(page.category, 0) + 1

    # --- recent insights (last 5 by mtime) ---
    insight_pages = [p for p in pages if p.category == "insights"]
    insight_paths = [project.wiki_root / p.rel_path for p in insight_pages]
    insight_paths.sort(key=lambda p: os.path.getmtime(p) if p.exists() else 0.0, reverse=True)
    recent_insights = [
        str(Path(p).relative_to(project.wiki_root)) for p in insight_paths[:5]
    ]

    # --- log tail ---
    log_path = project.wiki_root / "LOG.md"
    log_tail: list[str] = []
    if log_path.is_file():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        log_tail = lines[-10:]

    return SelfDocReport(
        project_name=project.name,
        created_at=created_iso,
        session_count=session_count,
        wiki_page_count=wiki_page_count,
        skills=skills,
        tools=tools,
        routing=routing,
        wiki_categories=wiki_categories,
        recent_insights=recent_insights,
        log_tail=log_tail,
    )


def _render_list_section(
    lines: list[str],
    header: str,
    items: Iterable[Any],
    *,
    formatter: Callable[[Any], str],
    empty: str,
) -> None:
    """Append `## header` + bullet list (or `empty` placeholder) + blank line.

    Used by every list-shaped section in the self-doc report (skills, tools,
    routing, categories, recent-insights). The Activity Log block has a
    different shape (fenced code) and stays inline in `render_self_doc`.
    """
    lines.extend(("## " + header, ""))
    materialised = list(items)
    if materialised:
        lines.extend(formatter(item) for item in materialised)
    else:
        lines.append(empty)
    lines.append("")


def _name_desc_bullet(pair: tuple[str, str | None]) -> str:
    name, desc = pair
    return f"- `{name}` — {desc}" if desc else f"- `{name}`"


def render_self_doc(report: SelfDocReport) -> str:
    """Render a `SelfDocReport` to markdown. Starts with `# Self-Documentation`."""
    now = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        "# Self-Documentation",
        "",
        f"Generated: {now}",
        "",
        "## Project Status",
        "",
        f"- **Name:** {report.project_name}",
        f"- **Created:** {report.created_at}",
        f"- **Sessions:** {report.session_count}  |  **Wiki pages:** {report.wiki_page_count}",
        "",
    ]
    _render_list_section(
        lines, "Available Skills", report.skills, formatter=_name_desc_bullet, empty="_(no skills)_"
    )
    _render_list_section(
        lines,
        "Tool Capabilities",
        report.tools,
        formatter=_name_desc_bullet,
        empty="_(tool list unavailable)_",
    )
    _render_list_section(
        lines,
        "Routing Configuration",
        sorted(report.routing.items()),
        formatter=lambda ts: f"- `{ts[0]}` → {ts[1]}",
        empty="_(no routing configuration)_",
    )
    _render_list_section(
        lines,
        "Knowledge Summary",
        sorted(report.wiki_categories.items()),
        formatter=lambda cc: f"- `{cc[0]}`: {cc[1]} page{'s' if cc[1] != 1 else ''}",
        empty="_(wiki is empty)_",
    )
    _render_list_section(
        lines,
        "Recent Insights",
        report.recent_insights,
        formatter=lambda rel: f"- {rel}",
        empty="_(no insights yet)_",
    )

    lines.extend(("## Activity Log", ""))
    if report.log_tail:
        lines.append("```")
        lines.extend(report.log_tail)
        lines.append("```")
    else:
        lines.append("_(no activity logged yet)_")
    lines.append("")
    return "\n".join(lines)


def refresh_self_doc(
    project: Project,
    *,
    tools: list[tuple[str, str]] | None = None,
) -> str:
    """Generate, render, write to wiki/self-doc/overview.md. Returns rel_path."""
    from veles.core.wiki import Wiki

    report = generate_self_doc(project, tools=tools)
    content = render_self_doc(report)
    wiki = Wiki(project.wiki_root)
    rel_path = wiki.write_page(
        category="self-doc",
        slug="overview",
        title="Self-Documentation",
        content=content,
    )
    wiki.append_log(
        op="self-doc",
        summary=(
            f"{report.session_count} sessions, "
            f"{report.wiki_page_count} wiki pages, "
            f"{len(report.skills)} skills"
        ),
    )
    return rel_path
