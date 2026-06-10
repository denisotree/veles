"""Dreaming (M76) — background memory consolidation.

The dream cycle is the orchestrator the user thinks of as "sleep": while the
agent is idle, walk the recent insights, look for duplicate skills, refresh
promote-candidates, lint the wiki, and (optionally) ask a cheap-model
sub-agent to consolidate related insights into umbrella skills.

Two callers exist:

1. The CLI command `veles dream` — synchronous one-shot. Useful for testing,
   for running off a personal cron, or for users who'd rather drive it
   manually.

2. The daemon's idle-timer task (`daemon.dream_runner`) — checks
   `state.last_activity_at`; once the idle threshold elapses, runs a deep
   cycle (with consolidation) at most once per `deep_interval_seconds`.

Both contracts converge on `dream_cycle(project, ...)`. The function never
mutates active sessions; outputs land in `wiki/insights/`, `wiki/proposals/`,
and `wiki/LOG.md`. A file lock (`<project>/.veles/dream.lock`) prevents a
CLI invocation from racing the daemon.

Pipeline:

    1. extract_insights (free; reuses M31 insight_extractor)
    2. find_dedup_clusters (cheap; skill_dedup TF-IDF / embedding)
    3. refresh_promote_candidates (cheap; skill_promotion)
    4. lint_wiki (cheap; wiki_linter)
    5. consolidate (LLM; cheap model, only when include_consolidation=True)

Steps 1-4 are I/O-bound and millisecond-fast. Step 5 calls a sub-agent on a
cheap model (default `anthropic/claude-haiku-4.5`) with a tight prompt
asking for umbrella-skill suggestions. The sub-agent has NO tools — its
output is appended to `wiki/proposals/dream-consolidate-<ts>.md` so a
follow-up human/agent review owns the merge decisions.
"""

from __future__ import annotations

import datetime as _dt
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from veles.core.curator_state import CuratorState, load, save_atomic
from veles.core.file_lock import file_lock
from veles.core.wiki import Wiki

if TYPE_CHECKING:
    from collections.abc import Callable

    from veles.core.project import Project
    from veles.core.provider import Provider

logger = logging.getLogger(__name__)

_DEEP_DEFAULT_INTERVAL_SEC = 6 * 3600.0
_POST_TURN_DEFAULT_INTERVAL_SEC = 30 * 60.0
_DEEP_DEFAULT_IDLE_SEC = 600.0
# M142: codex-style "don't process the whole corpus blindly" cap. The insight
# step extracts from at most this many transcripts per cycle; older sessions
# are deferred to the next cycle (logged — no silent truncation).
_MAX_TRANSCRIPTS_PER_CYCLE = 100
# M142: insight dedup — cluster at most this many recent insights, link
# near-duplicates (TF-IDF cosine ≥ threshold) to a canonical survivor.
_INSIGHT_DEDUP_LIMIT = 200
_INSIGHT_DEDUP_THRESHOLD = 0.5
_CONSOLIDATE_PROMPT = (
    "You are Veles' background dreaming agent — a memory consolidator. "
    "You will not touch active sessions. Read the recent insights and "
    "dedup-cluster proposals below and produce a markdown report that:\n"
    "  1. Groups closely-related insights into umbrella themes.\n"
    "  2. For each umbrella, lists the constituent insight slugs and a "
    "one-sentence merged claim.\n"
    "  3. Flags any contradictions you notice.\n"
    "Be concise — short bullet lists are better than essays. If nothing "
    "is worth consolidating, output `SKIP` on a single line."
)


@dataclass(slots=True)
class DreamResult:
    insights_written: int = 0
    dedup_clusters: int = 0
    promote_candidates: int = 0
    lint_findings: int = 0
    consolidated: bool = False
    consolidation_path: str | None = None
    reindexed_pages: int = 0
    insight_dedup_clusters: int = 0
    skipped: bool = False
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.skipped:
            return "dream skipped"
        parts = [
            f"insights={self.insights_written}",
            f"dedup={self.dedup_clusters}",
            f"promote={self.promote_candidates}",
            f"lint={self.lint_findings}",
        ]
        if self.reindexed_pages:
            parts.append(f"reindex={self.reindexed_pages}")
        if self.insight_dedup_clusters:
            parts.append(f"insight_dedup={self.insight_dedup_clusters}")
        if self.consolidated:
            parts.append("consolidated")
        return "dream: " + " ".join(parts)


def _dream_state_path(project: Project) -> Path:
    return project.state_dir / "curator.state.json"


def _dream_lock_path(project: Project) -> Path:
    return project.state_dir / "dream.lock"


def _consolidation_dir(project: Project) -> Path:
    # `Wiki` writes proposals under `<wiki_root>/wiki/<category>/`; the
    # bare `wiki_root / "proposals"` path (pre-v2 leftover) pointed at
    # an unused dir alongside `.veles/wiki/`. Match Wiki's layout.
    return project.wiki_root / "wiki" / "proposals"


@contextmanager
def _maybe_lock(project: Project, *, blocking: bool):
    """Hold the dream-lock for the body. If `blocking=False` and the lock is
    contended, yield None so callers can skip."""
    lock_path = _dream_lock_path(project)
    if blocking:
        with file_lock(lock_path):
            yield True
        return
    # Non-blocking: best-effort. The simplest portable signal is to attempt
    # the blocking lock with no contention assumed — if another dream is
    # active, the caller can detect it via a sentinel timestamp. For now we
    # just block briefly and rely on the throttle to keep contention rare.
    with file_lock(lock_path):
        yield True


_DEFAULT_CONSOLIDATION_MODEL = "anthropic/claude-haiku-4.5"


def _run_dream_step(name: str, step: Callable[[], None], result: DreamResult) -> None:
    """Run one dream step, capturing failures as a `notes` entry.

    Every step (insights / dedup / promote / lint / consolidate) is best-effort:
    one failing step must not poison the others. The original error is logged
    with traceback and surfaced in `result.notes` for the user to inspect.
    """
    try:
        step()
    except Exception as exc:  # pragma: no cover - best-effort
        result.notes.append(f"{name} step failed: {exc}")
        logger.exception("dream: %s step failed", name)


def _persist_dream_state(
    *,
    state_path: Path,
    state: CuratorState,
    wiki: Wiki,
    result: DreamResult,
    at: float,
    include_consolidation: bool,
    dry_run: bool,
) -> None:
    new_state = CuratorState(
        last_curated_at=state.last_curated_at,
        sessions_curated_total=state.sessions_curated_total,
        last_post_turn_dream_at=at if not include_consolidation else state.last_post_turn_dream_at,
        last_deep_dream_at=at if include_consolidation else state.last_deep_dream_at,
        dream_count=state.dream_count + 1,
    )
    if dry_run:
        return
    save_atomic(state_path, new_state)
    wiki.append_log(
        op="dream_deep" if include_consolidation else "dream_post_turn",
        summary=result.summary(),
    )


def dream_cycle(
    project: Project,
    *,
    include_consolidation: bool = False,
    skip_insights: bool = False,
    skip_dedup: bool = False,
    skip_promote: bool = False,
    skip_lint: bool = False,
    skip_reindex: bool = False,
    dry_run: bool = False,
    provider: Provider | None = None,
    consolidation_model: str | None = None,
    insight_history_loader=None,
    runtime_session_loader=None,
    now: float | None = None,
) -> DreamResult:
    """Run one dream cycle. Returns a `DreamResult` summary.

    `provider` is only required when `include_consolidation=True` — the
    other steps are LLM-free heuristics. `insight_history_loader` is an
    optional callable `() -> list[(session_id, history)]` used to drive
    insight extraction; the daemon/CLI wiring supplies one that walks the
    SessionStore for sessions newer than `CuratorState.last_curated_at`.
    """
    at = now if now is not None else time.time()
    result = DreamResult()
    # M128-followup: if the project marker is gone (project deleted out from
    # under a still-running daemon), bail before any filesystem touch so the
    # cycle can't `mkdir` a marker-less zombie `.veles/` back into existence
    # (`_maybe_lock`/state write would otherwise recreate the state dir).
    if not project.project_toml_path.is_file():
        result.notes.append("skipped: project marker (project.toml) missing")
        return result
    state_path = _dream_state_path(project)
    state = load(state_path)
    wiki = Wiki(project.wiki_root)
    model = consolidation_model or _DEFAULT_CONSOLIDATION_MODEL

    with _maybe_lock(project, blocking=True):
        if not skip_insights and insight_history_loader is not None and provider is not None:
            _run_dream_step(
                "insights",
                lambda: _step_insights(project, provider, model, insight_history_loader, result),
                result,
            )
        if runtime_session_loader is not None:
            _run_dream_step(
                "runtime_sessions",
                lambda: _step_runtime_sessions(
                    project, runtime_session_loader, result, dry_run=dry_run, at=at
                ),
                result,
            )
        if not skip_dedup:
            _run_dream_step(
                "dedup", lambda: _step_dedup(project, wiki, result, dry_run=dry_run), result
            )
        if not skip_promote:
            _run_dream_step(
                "promote", lambda: _step_promote(project, wiki, result, dry_run=dry_run), result
            )
        if not skip_lint:
            _run_dream_step(
                "lint", lambda: _step_lint(project, wiki, result, dry_run=dry_run), result
            )
        if not skip_reindex and not dry_run:
            _run_dream_step(
                "reindex", lambda: _step_reindex(wiki, result), result
            )
        if include_consolidation:
            _run_dream_step(
                "insight_dedup",
                lambda: _step_insight_dedup(project, result, dry_run=dry_run),
                result,
            )
        if include_consolidation and provider is not None:
            _run_dream_step(
                "consolidation",
                lambda: _step_consolidate(
                    project, wiki, provider, model, result, dry_run=dry_run
                ),
                result,
            )

        _persist_dream_state(
            state_path=state_path,
            state=state,
            wiki=wiki,
            result=result,
            at=at,
            include_consolidation=include_consolidation,
            dry_run=dry_run,
        )

    return result


# ---- step implementations ----


def _step_insights(
    project: Project,
    provider: Provider,
    model: str,
    history_loader,
    result: DreamResult,
) -> None:
    from veles.core.insight_extractor import make_insight_extractor

    extractor = make_insight_extractor(provider=provider, model=model, project=project)
    written = 0
    for i, (session_id, history) in enumerate(history_loader()):
        if i >= _MAX_TRANSCRIPTS_PER_CYCLE:
            result.notes.append(
                f"insight step: capped at {_MAX_TRANSCRIPTS_PER_CYCLE} transcripts/cycle; "
                "older sessions deferred to next cycle"
            )
            break
        try:
            written += extractor(history, session_id)
        except Exception as exc:  # pragma: no cover - extractor handles its own errors
            result.notes.append(f"insight extractor on {session_id}: {exc}")
    result.insights_written = written


def _step_insight_dedup(project: Project, result: DreamResult, *, dry_run: bool) -> None:
    """M142: collapse near-duplicate insights into supersede-links.

    Clusters the most-recent insights by TF-IDF cosine (shared
    `text_cluster.cluster_texts`); within each cluster the highest
    `last_referenced_at` (most-used / most-recent) is the canonical survivor,
    and every other member gets an `insight_refs(from=dup, to=canonical)` row.
    Recall (`MemoryRouter._collect_insights`) then excludes superseded rows, so
    duplicates stop drowning the canonical without deleting the audit trail.
    Idempotent via the `insight_refs` PK + `INSERT OR IGNORE`."""
    import sqlite3

    from veles.core.text_cluster import cluster_texts

    conn = sqlite3.connect(str(project.memory_db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, title, body, COALESCE(last_referenced_at, created_at) AS ts"
            " FROM insights"
            " WHERE id NOT IN (SELECT from_insight_id FROM insight_refs)"
            " ORDER BY created_at DESC LIMIT ?",
            (_INSIGHT_DEDUP_LIMIT,),
        ).fetchall()
        if len(rows) < 2:
            return
        texts = [f"{r['title']} {r['body']}" for r in rows]
        clusters = cluster_texts(texts, threshold=_INSIGHT_DEDUP_THRESHOLD)
        result.insight_dedup_clusters = len(clusters)
        if not clusters or dry_run:
            return
        for indices, _score in clusters:
            canonical = max(indices, key=lambda i: rows[i]["ts"])
            canonical_id = int(rows[canonical]["id"])
            for i in indices:
                if i == canonical:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO insight_refs(from_insight_id, to_insight_id)"
                    " VALUES (?, ?)",
                    (int(rows[i]["id"]), canonical_id),
                )
        conn.commit()
        result.notes.append(f"insight-dedup: {len(clusters)} cluster(s) collapsed")
    except sqlite3.Error as exc:
        result.notes.append(f"insight-dedup failed: {exc}")
    finally:
        conn.close()


def _step_runtime_sessions(
    project: Project,
    runtime_loader,
    result: DreamResult,
    *,
    dry_run: bool,
    at: float,
) -> None:
    """M135-dream (ISSUES 3a): persist a snapshot of every runtime session ever
    launched (active + soft-deleted) into the learnable `insights` corpus, so an
    active daemon's dream is aware of the full fleet rather than losing deleted
    sessions. One living snapshot per project (category `daemon-fleet`),
    replaced each cycle. `runtime_loader` is `() -> str | None`."""
    import sqlite3

    try:
        digest = runtime_loader()
    except Exception as exc:  # noqa: BLE001 — loader is best-effort
        result.notes.append(f"runtime-sessions loader failed: {exc}")
        return
    if not digest:
        return
    if dry_run:
        result.notes.append("runtime-sessions: fleet snapshot (dry-run, not written)")
        return
    conn = sqlite3.connect(str(project.memory_db_path))
    try:
        conn.execute("DELETE FROM insights WHERE category = 'daemon-fleet'")
        conn.execute(
            "INSERT INTO insights(title, body, category, created_at) VALUES (?, ?, ?, ?)",
            ("daemon fleet snapshot", digest, "daemon-fleet", at),
        )
        conn.commit()
    except sqlite3.Error as exc:
        result.notes.append(f"runtime-sessions write failed: {exc}")
        return
    finally:
        conn.close()
    result.notes.append("runtime-sessions: fleet snapshot recorded")


def _step_dedup(project: Project, wiki: Wiki, result: DreamResult, *, dry_run: bool) -> None:
    from veles.core.skill_dedup import find_duplicate_skills
    from veles.core.skills import discover_skills

    skills = discover_skills(project)
    try:
        clusters, mode = find_duplicate_skills(skills, project=project, mode="auto")
    except Exception as exc:
        result.notes.append(f"dedup discovery failed: {exc}")
        return
    result.dedup_clusters = len(clusters)
    if not clusters:
        return
    if dry_run:
        return
    body_lines = [
        "# Dream: duplicate-skill clusters",
        "",
        f"_Generated: {_now_iso()}_",
        f"_Mode: {mode}_",
        "",
    ]
    for cluster in clusters:
        names = ", ".join(sorted(s.name for s in cluster.skills))
        body_lines.append(f"- **cluster** ({len(cluster.skills)}): {names}")
    slug = f"dream-dedup-{_now_slug()}"
    wiki.write_page(
        category="proposals",
        slug=slug,
        title="Dream: duplicate-skill clusters",
        content="\n".join(body_lines) + "\n",
    )
    wiki.append_log(op="dream_dedup", summary=f"{len(clusters)} clusters")


def _step_promote(project: Project, wiki: Wiki, result: DreamResult, *, dry_run: bool) -> None:
    from veles.core.skill_promotion import find_promote_candidates, write_promote_proposals

    candidates = find_promote_candidates(project)
    result.promote_candidates = len(candidates)
    if not candidates or dry_run:
        return
    write_promote_proposals(project, candidates)


def _step_lint(project: Project, wiki: Wiki, result: DreamResult, *, dry_run: bool) -> None:
    from veles.core.wiki_linter import render_report, run_lint

    report = run_lint(wiki)
    result.lint_findings = len(report.all_findings)
    if result.lint_findings == 0 or dry_run:
        return
    rendered = render_report(report)
    slug = f"dream-lint-{_now_slug()}"
    wiki.write_page(
        category="proposals",
        slug=slug,
        title="Dream: wiki lint",
        content=rendered,
    )
    wiki.append_log(op="dream_lint", summary=f"{result.lint_findings} findings")


def _step_reindex(wiki: Wiki, result: DreamResult) -> None:
    """M84: refresh the wiki FTS index when dream notices it's stale.
    Cheap when fresh (mtime check), full rebuild otherwise."""
    result.reindexed_pages = wiki.reindex_if_stale()


_CONSOLIDATION_INSIGHTS_LIMIT = 20


def _collect_insight_snippets(project: Project, *, limit: int) -> list[str]:
    """Return the `limit` most-recent insight files as `## title\\nbody` blocks.

    `Wiki` writes pages under `<wiki_root>/wiki/<category>/`, so the actual
    on-disk insights dir is `<wiki_root>/wiki/insights`. Files that won't read
    are skipped, not raised — the consolidator runs on a best-effort budget.
    """
    insights_dir = project.wiki_root / "wiki" / "insights"
    if not insights_dir.is_dir():
        return []
    files = sorted(insights_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    snippets: list[str] = []
    for path in files[:limit]:
        try:
            snippets.append(f"## {path.stem}\n{path.read_text(encoding='utf-8')}")
        except OSError:
            continue
    return snippets


def _step_consolidate(
    project: Project,
    wiki: Wiki,
    provider: Provider,
    model: str,
    result: DreamResult,
    *,
    dry_run: bool,
) -> None:
    from veles.core.agent import Agent
    from veles.core.tools.registry import Registry

    snippets = _collect_insight_snippets(project, limit=_CONSOLIDATION_INSIGHTS_LIMIT)
    if not snippets:
        result.notes.append("consolidation skipped: no insights to consolidate")
        return

    sub = Agent(
        provider=provider,
        registry=Registry(),
        model=model,
        max_iterations=1,
        system_prompt=_CONSOLIDATE_PROMPT,
        max_tokens=2048,
    )
    try:
        run_result = sub.run("\n\n".join(snippets))
    except Exception as exc:
        result.notes.append(f"consolidation sub-agent failed: {exc}")
        return

    text = (run_result.text or "").strip()
    if not text or text.upper().startswith("SKIP"):
        result.notes.append("consolidation: model returned SKIP / empty")
        return

    if dry_run:
        result.consolidated = True
        return

    slug = f"dream-consolidate-{_now_slug()}"
    page_rel = wiki.write_page(
        category="proposals",
        slug=slug,
        title="Dream: consolidation proposals",
        content=f"# Dream: consolidation proposals\n\n_Generated: {_now_iso()}_\n\n{text}\n",
    )
    result.consolidated = True
    result.consolidation_path = str(project.wiki_root / page_rel)
    wiki.append_log(op="dream_consolidate", summary=f"-> {page_rel}")


def _now_slug() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).isoformat()


__all__ = [
    "DreamResult",
    "_DEEP_DEFAULT_IDLE_SEC",
    "_DEEP_DEFAULT_INTERVAL_SEC",
    "_POST_TURN_DEFAULT_INTERVAL_SEC",
    "dream_cycle",
]
