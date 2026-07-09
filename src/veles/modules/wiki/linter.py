"""Deterministic wiki health checks — orphans, stale claims, duplicates.

PLAN.md §3.2 + §9 calls for an LLM-driven `veles lint` that finds
contradictions, stale claims, orphan pages, and duplicate skills.
The pre-M32 implementation was a single sub-Agent prompt that did
all four loosely; this module factors the cheap, deterministic
half — orphans, stale-by-date, and same-category duplicate clusters
— into pure Python so a `veles lint` invocation gives a structured
report in tens of milliseconds instead of an LLM round-trip.

What stays LLM-only and is *not* in this module:
- Contradictions between pages (needs reasoning over content).
- Subtle duplicates that share semantics but not surface tokens.

Both are reachable via `veles lint --llm`, which preserves the
pre-M32 sub-Agent path.

Excluded categories:
- `sessions/` — append-only journal of agent activity, naturally
  orphan and naturally dated. Flagging it would just add noise.
  (`insights` left wiki entirely in M161 — they live in the
  `insights` memory table now.)
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veles.modules.wiki.wiki import Wiki, WikiPageInfo


_DEFAULT_STALE_DAYS = 365
_DEFAULT_DUPLICATE_THRESHOLD = 0.6
_LINKABLE_CATEGORIES = frozenset({"concepts", "entities", "queries"})
_NOISE_CATEGORIES = frozenset({"sessions"})

_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {"the", "and", "for", "with", "from", "into", "this", "that", "page", "part"}
)


@dataclass(frozen=True, slots=True)
class LintFinding:
    """One issue produced by a deterministic linter.

    `pages` lists relative paths so the rendered report can deep-link.
    `kind` is a short tag (`"orphan"`, `"stale"`, `"duplicate"`) for
    machine-readable callers; `severity` is human-facing (`"high"`,
    `"medium"`, `"low"`).
    """

    severity: str
    kind: str
    pages: list[str]
    description: str


@dataclass(frozen=True, slots=True)
class LintReport:
    orphans: list[LintFinding] = field(default_factory=list)
    stale: list[LintFinding] = field(default_factory=list)
    duplicates: list[LintFinding] = field(default_factory=list)

    @property
    def all_findings(self) -> list[LintFinding]:
        return [*self.orphans, *self.stale, *self.duplicates]


def _title_tokens(s: str) -> set[str]:
    out = {t for t in _TOKEN_RE.findall(s.lower()) if len(t) > 2 and t not in _STOPWORDS}
    return out


def _find_oldest_date(text: str) -> _dt.datetime | None:
    """Return the earliest YYYY-MM-DD or 20XX year mention; None if absent."""
    earliest: _dt.datetime | None = None
    for m in _DATE_RE.finditer(text):
        try:
            d = _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=_dt.UTC)
        except (ValueError, OverflowError):
            continue
        if earliest is None or d < earliest:
            earliest = d
    if earliest is not None:
        return earliest
    for m in _YEAR_RE.finditer(text):
        try:
            d = _dt.datetime(int(m.group(1)), 1, 1, tzinfo=_dt.UTC)
        except (ValueError, OverflowError):
            continue
        if earliest is None or d < earliest:
            earliest = d
    return earliest


def find_orphans(wiki: Wiki) -> list[LintFinding]:
    """Pages in linkable categories with no inbound reference.

    A page is non-orphan if its `rel_path` substring appears in
    `INDEX.md` (which `Wiki.update_index` always rewrites) or in any
    other wiki page's body. The check is exact-substring on the
    relative path so renames don't generate false negatives.
    """
    pages = wiki.list_pages()
    candidates = [p for p in pages if p.category in _LINKABLE_CATEGORIES]
    if not candidates:
        return []
    index_text = wiki.index_text()
    referenced: set[str] = set()
    for cand in candidates:
        if cand.rel_path in index_text:
            referenced.add(cand.rel_path)
            continue
        for other in pages:
            if other.rel_path == cand.rel_path:
                continue
            try:
                body = wiki.read_page(other.rel_path)
            except (OSError, UnicodeDecodeError):
                continue
            if cand.rel_path in body:
                referenced.add(cand.rel_path)
                break
    out: list[LintFinding] = []
    for cand in candidates:
        if cand.rel_path in referenced:
            continue
        out.append(
            LintFinding(
                severity="medium",
                kind="orphan",
                pages=[cand.rel_path],
                description=(
                    f"{cand.rel_path} has no inbound links from INDEX.md or any other wiki page."
                ),
            )
        )
    return out


def find_stale(
    wiki: Wiki,
    *,
    max_age_days: int = _DEFAULT_STALE_DAYS,
    now: _dt.datetime | None = None,
) -> list[LintFinding]:
    """Pages whose oldest date marker (ISO or bare year) is older than threshold.

    Best-effort heuristic: a page citing `2018-01-01` will flag whether or
    not the citation context still applies. Excludes sessions/insights —
    those are timestamps of agent activity, not knowledge claims.
    """
    now = now or _dt.datetime.now(tz=_dt.UTC)
    cutoff = now - _dt.timedelta(days=max_age_days)
    out: list[LintFinding] = []
    for page in wiki.list_pages():
        if page.category in _NOISE_CATEGORIES:
            continue
        try:
            body = wiki.read_page(page.rel_path)
        except (OSError, UnicodeDecodeError):
            continue
        oldest = _find_oldest_date(body)
        if oldest is None or oldest >= cutoff:
            continue
        age_days = (now - oldest).days
        out.append(
            LintFinding(
                severity="low",
                kind="stale",
                pages=[page.rel_path],
                description=(
                    f"{page.rel_path} references date {oldest.date().isoformat()} "
                    f"({age_days} days old)."
                ),
            )
        )
    return out


def find_duplicates(
    wiki: Wiki, *, similarity_threshold: float = _DEFAULT_DUPLICATE_THRESHOLD
) -> list[LintFinding]:
    """Cluster pages whose title-token Jaccard similarity exceeds threshold.

    Same-category only — `concepts/agent.md` and `entities/agent.md` cover
    the same word under different lenses, and reporting cross-category
    matches produces too much noise. M28b will add skill-telemetry
    tiebreaker for resolving the cluster; for now the linter just
    surfaces the cluster.
    """
    pages = [p for p in wiki.list_pages() if p.category not in _NOISE_CATEGORIES]
    by_cat: dict[str, list[WikiPageInfo]] = {}
    for p in pages:
        by_cat.setdefault(p.category, []).append(p)
    out: list[LintFinding] = []
    for cat, group in by_cat.items():
        seen: set[int] = set()
        for i, a in enumerate(group):
            if i in seen:
                continue
            ta = _title_tokens(a.title)
            cluster = [a]
            for j in range(i + 1, len(group)):
                if j in seen:
                    continue
                tb = _title_tokens(group[j].title)
                if not ta or not tb:
                    continue
                jaccard = len(ta & tb) / len(ta | tb)
                if jaccard >= similarity_threshold:
                    cluster.append(group[j])
                    seen.add(j)
            if len(cluster) > 1:
                seen.add(i)
                out.append(
                    LintFinding(
                        severity="medium",
                        kind="duplicate",
                        pages=[c.rel_path for c in cluster],
                        description=(
                            f"{len(cluster)} pages in {cat} share similar titles: "
                            f"{[c.title for c in cluster]}"
                        ),
                    )
                )
    return out


def run_lint(
    wiki: Wiki,
    *,
    max_age_days: int = _DEFAULT_STALE_DAYS,
    duplicate_threshold: float = _DEFAULT_DUPLICATE_THRESHOLD,
    now: _dt.datetime | None = None,
) -> LintReport:
    """Run all deterministic checks and assemble a `LintReport`."""
    return LintReport(
        orphans=find_orphans(wiki),
        stale=find_stale(wiki, max_age_days=max_age_days, now=now),
        duplicates=find_duplicates(wiki, similarity_threshold=duplicate_threshold),
    )


def render_report(report: LintReport, *, now: _dt.datetime | None = None) -> str:
    """Render a `LintReport` as a markdown document suitable for stdout
    or a `.veles/memory/proposals/dream-lint-<ts>.md` page."""
    now = now or _dt.datetime.now(tz=_dt.UTC)
    lines = [
        "# Veles wiki lint report",
        "",
        f"Generated: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
    ]
    if not report.all_findings:
        lines.append("_No issues found._")
        return "\n".join(lines) + "\n"
    sections = [
        ("Orphans", report.orphans),
        ("Stale", report.stale),
        ("Duplicates", report.duplicates),
    ]
    for label, findings in sections:
        if not findings:
            continue
        lines.append(f"## {label} ({len(findings)})")
        lines.append("")
        for f in findings:
            lines.append(f"### [{f.severity}] {f.kind}")
            for p in f.pages:
                lines.append(f"- [{p}]({p})")
            lines.append(f"- {f.description}")
            lines.append("")
    return "\n".join(lines) + "\n"
