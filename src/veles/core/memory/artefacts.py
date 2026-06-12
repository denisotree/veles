"""The agent's own memory artefacts under `<project>/.veles/memory/`.

VISION §5.1: project memory is a structured artefact that lives in
*parallel* to user content and works under any layout. Before M160 the
system wrote its artefacts (insight pages, session compactions,
proposals, ops journal) into the user's `wiki/` tree — entangling the
agent's memory with one particular user-content layout. This module is
the single owner of the system-side paths:

    .veles/
    ├── memory/
    │   ├── LOG.md               append-only system-ops journal
    │   ├── insights/<slug>.md   rendered views of `insights` rows
    │   ├── sessions/<id>.md     compaction summaries (compressor)
    │   └── proposals/<slug>.md  skill-promotion + subproject proposals
    └── jobs/                    scheduled-job outputs (`project.jobs_dir`)

Format follows wiki best practices (H1 title, short scannable body),
but ownership is system-side: where a SQL table exists (`insights`) the
row is canonical and the file is a regenerable view; journals and
documents nothing queries (sessions, proposals, LOG.md) are file-only.
Never write user-content (`wiki/`) paths from this module.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from veles.core.slug import normalize_slug

if TYPE_CHECKING:
    from veles.core.project import Project

_LOG_FILE = "LOG.md"
_INSIGHTS_DIR = "insights"
_SESSIONS_DIR = "sessions"
_PROPOSALS_DIR = "proposals"
_SUMMARY_CHAR_CAP = 200


@dataclass(slots=True)
class ProposalInfo:
    """One persisted proposal page under `.veles/memory/proposals/`."""

    slug: str
    title: str
    summary: str
    path: Path


def _now_iso_z() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def memory_log_path(project: Project) -> Path:
    return project.memory_dir / _LOG_FILE


def insights_dir(project: Project) -> Path:
    return project.memory_dir / _INSIGHTS_DIR


def sessions_dir(project: Project) -> Path:
    return project.memory_dir / _SESSIONS_DIR


def proposals_dir(project: Project) -> Path:
    return project.memory_dir / _PROPOSALS_DIR


def ensure_memory_dirs(project: Project) -> None:
    for d in (insights_dir(project), sessions_dir(project), proposals_dir(project)):
        d.mkdir(parents=True, exist_ok=True)


def append_memory_log(project: Project, *, op: str, summary: str) -> None:
    """Append one entry to the system-ops journal (`.veles/memory/LOG.md`).

    Same entry shape as the wiki content journal so both stay greppable
    with one pattern. System ops (insight extraction, curator passes,
    autopilot dispatches, dream cycles) land here; the user-facing wiki
    `LOG.md` keeps *content* ops only (ingest, wiki_write_page).
    """
    project.memory_dir.mkdir(parents=True, exist_ok=True)
    entry = f"## [{_now_iso_z()}] {op}\n   {summary}\n\n"
    with memory_log_path(project).open("a", encoding="utf-8") as f:
        f.write(entry)


def _write_page(dir_path: Path, *, slug: str, title: str, content: str) -> Path:
    clean = normalize_slug(slug)
    dir_path.mkdir(parents=True, exist_ok=True)
    body = content if content.lstrip().startswith("#") else f"# {title}\n\n{content}"
    path = dir_path / f"{clean}.md"
    path.write_text(body, encoding="utf-8")
    return path


def write_proposal(project: Project, *, slug: str, title: str, content: str) -> Path:
    """Persist (or idempotently overwrite) one proposal page."""
    return _write_page(proposals_dir(project), slug=slug, title=title, content=content)


def write_session_summary(project: Project, *, slug: str, title: str, content: str) -> Path:
    """Persist one session-compaction summary."""
    return _write_page(sessions_dir(project), slug=slug, title=title, content=content)


def write_insight_view(project: Project, *, slug: str, title: str, body: str) -> Path:
    """Render the markdown view of one `insights` row.

    The SQL row is canonical (recall, aging, dedup all read SQL); this
    file is a best-effort human-readable mirror, regenerable from the row.
    """
    return _write_page(insights_dir(project), slug=slug, title=title, content=body)


def list_proposals(project: Project) -> list[ProposalInfo]:
    d = proposals_dir(project)
    if not d.is_dir():
        return []
    out: list[ProposalInfo] = []
    for md in sorted(d.glob("*.md")):
        try:
            content = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        title, summary = _title_and_summary(content, fallback=md.stem)
        out.append(ProposalInfo(slug=md.stem, title=title, summary=summary, path=md))
    return out


def _title_and_summary(content: str, fallback: str) -> tuple[str, str]:
    """H1 line + first paragraph, capped — mirrors the wiki page parser."""
    title = fallback
    summary_lines: list[str] = []
    seen_h1 = False
    for line in content.splitlines():
        stripped = line.strip()
        if not seen_h1 and stripped.startswith("# "):
            title = stripped[2:].strip() or fallback
            seen_h1 = True
            continue
        if seen_h1 and stripped:
            if stripped.startswith("#"):
                if summary_lines:
                    break
                continue
            summary_lines.append(stripped)
            if sum(len(s) for s in summary_lines) >= _SUMMARY_CHAR_CAP:
                break
    summary = " ".join(summary_lines).strip()
    if len(summary) > _SUMMARY_CHAR_CAP:
        summary = summary[: _SUMMARY_CHAR_CAP - 1].rstrip() + "…"
    return title, summary
