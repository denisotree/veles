"""Pre-turn recall of relevant project memory for system-prompt injection.

The router is the single entry point Veles uses to ask "what does our
project memory have that's relevant to this query?" — today it pulls
from two FTS5 indices:

1. `Wiki.search` — curated wiki pages (agent-authored summaries,
   insights, proposals, etc). The original M22 source.
2. `SessionStore.search_turns` — raw session turns (M58, this file's
   extension). Lets recall surface "that command I ran yesterday"
   without waiting for the curator to consolidate it into the wiki.

M41 fans recall *downward* into vertical subprojects too: each
registered child's wiki is searched with a smaller per-child cap. Hits
from subprojects are namespaced (`<slug>:<rel_path>`, `[slug] title`)
so the LLM can see which child a page came from.

The output is a single ranked `list[RecallHit]` of length ≤ `limit`,
interleaving wiki and turn hits one-for-one. The interleave keeps
fresh chat content from drowning out hard-won wiki knowledge and vice
versa. Recency / BM25-weighted merging is a future refinement.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace

from veles.core.memory import InsightHit, SessionStore, TurnHit, aio
from veles.core.memory.rerank import (
    DEFAULT_HALF_LIFE_SEC,
    DEFAULT_WEIGHTS,
    RerankWeights,
    rerank,
)
from veles.core.project import Project
from veles.core.safety import scan_for_injection
from veles.core.subproject import load_subprojects, resolve_subproject_path

logger = logging.getLogger(__name__)

# M264: how long the whole recall fan-out may take before the turn moves on
# with whatever finished. Two seconds mirrors the llama.cpp probe bound of
# M256b, for the same reason: this is the path of every turn.
_RECALL_DEADLINE_SEC = 2.0

_TURN_SUMMARY_CAP = 200
_TURN_RECENCY_WINDOW_SEC = 30 * 86_400  # only recall turns from the last 30 days
# M218: recall drops insights below this provenance confidence. Conservative —
# curated (1.0) and heuristic-recovery (0.6) insights survive; only genuinely
# low-trust future writers (speculative auto-insights) get pruned.
_INSIGHT_CONFIDENCE_FLOOR = 0.3


@dataclass(frozen=True, slots=True)
class RecallHit:
    rel_path: str
    title: str
    summary: str
    score: float = 0.0
    # M141 rerank input: `ts` is the recency signal (None → neutral).
    ts: float | None = None
    # M221 rerank input: provenance confidence in [0,1] (insights carry a real
    # one since M218; every other source is a neutral 1.0).
    confidence: float = 1.0


class MemoryRouter:
    def __init__(
        self,
        project: Project,
        *,
        store: SessionStore | None = None,
        extra_providers: list[object] | None = None,
    ) -> None:
        self._project = project
        # M265: recall reads memory through the port, so a project configured
        # onto a remote engine actually reaches it. Callers that still open
        # their own `SessionStore` (see the storage-port ratchet) keep working:
        # the store is wrapped, not reopened.
        self._store = _as_port(store)
        # M55: opt-in external memory plugins (Honcho, Mem0, ...). Stored as
        # `object` to avoid an import cycle with `memory_provider.MemoryProvider`
        # — every entry is duck-typed at call time.
        self._extra: list[object] = list(extra_providers or [])

    def recall(
        self, query: str, *, limit: int = 5, deadline_sec: float | None = None
    ) -> list[RecallHit]:
        if not query.strip():
            return []
        deadline = _load_recall_deadline(self._project) if deadline_sec is None else deadline_sec
        streams = aio.submit(
            self._collect_all(query, limit=limit, deadline_sec=deadline),
            # Backstop only: the per-collector deadline inside `_collect_all`
            # is what actually bounds the turn, and it returns partial results.
            # This one exists so a bug in that logic cannot hang a turn forever.
            timeout=deadline + 5.0,
        )
        # M141 scored rerank (relevance + recency + M221 confidence). M223 dropped
        # the `VELES_MEMORY_RERANK=0` round-robin fallback — a kill switch for a
        # default that has led since M141 and only got richer since.
        weights, half_life = _load_rerank_config(self._project)
        merged = rerank(
            streams,
            now=time.time(),
            limit=limit,
            weights=weights,
            half_life_sec=half_life,
        )
        final = merged[:limit]
        self._age_recalled_insights(final)
        # M145: scrub recall summaries before they enter the prompt — the one
        # memory surface that bypasses `scan_for_injection`. See
        # `_scrub_recall_hit`. Done on the final ≤limit hits only, so the cost
        # is a handful of regex passes per turn.
        return [_scrub_recall_hit(h) for h in final]

    async def _collect_all(
        self, query: str, *, limit: int, deadline_sec: float
    ) -> list[list[RecallHit]]:
        """Run every collector concurrently under one deadline (M264).

        Sequentially, the turn paid the sum of five sources; a single slow one
        — an external provider over the network, a KNN scan over a large
        corpus — moved the whole turn. Concurrently it pays the slowest, and
        past the deadline it pays the deadline and keeps whatever finished.

        Partial beats empty: a source that missed the cut is dropped with a
        warning, not silently, because a shorter list must never read as "there
        was nothing" (the M219 lesson, one layer down).

        Mixed shapes on purpose: the two collectors that read the store are
        coroutines, because the store may be a remote engine; the three that
        touch local files or plugin objects are synchronous and get a thread.
        The threaded ones may share one `sqlite3.Connection`, which is allowed
        — it is opened with `check_same_thread=False` and CPython 3.13 reports
        `sqlite3.threadsafety == 3` (SQLite serialises internally).
        """
        # The two that talk to the store are already coroutines (the port may
        # be a network call); the three that touch files or plugins are
        # synchronous and get a thread.
        tasks = {
            "insights": asyncio.ensure_future(self._collect_insights(query, limit=limit)),
            "turns": asyncio.ensure_future(self._collect_turns(query, limit=limit)),
        }
        tasks.update(
            {
                name: asyncio.ensure_future(asyncio.to_thread(fn, query, limit=limit))
                for name, fn in (
                    ("about", self._collect_about_veles),
                    ("wiki", self._collect_wiki),
                    ("extra", self._collect_extra),
                )
            }
        )
        await asyncio.wait(tasks.values(), timeout=deadline_sec)

        streams: list[list[RecallHit]] = []
        dropped: list[str] = []
        for name, task in tasks.items():
            if not task.done():
                # Cancelling stops us waiting; the worker thread itself runs to
                # completion, which is the price of wrapping sync code.
                task.cancel()
                dropped.append(f"{name} (deadline)")
                continue
            exc = task.exception()
            if exc is not None:
                dropped.append(f"{name} ({type(exc).__name__})")
                continue
            streams.append(task.result())
        if dropped:
            logger.warning("recall: dropped %s", ", ".join(dropped))
        return streams

    def _collect_extra(self, query: str, *, limit: int) -> list[RecallHit]:
        """Call every registered external provider, swallowing per-provider
        failures so one broken plugin can't tank the whole recall.

        M265: the providers run **concurrently**. Sequentially they shared one
        slot in the fan-out, so a single slow remote source consumed the whole
        recall deadline and its siblings returned nothing — the failure mode
        the deadline was supposed to prevent, one level down. Whatever has not
        answered when this collector is cancelled is simply not included.
        """
        if not self._extra:
            return []
        per_provider = max(1, limit // 2)

        def call(provider: object) -> list[RecallHit]:
            try:
                return list(provider.recall(query, limit=per_provider))  # type: ignore[attr-defined]
            except Exception as exc:
                logger.warning(
                    "recall: provider %s failed (%s: %s)",
                    getattr(provider, "name", type(provider).__name__),
                    type(exc).__name__,
                    exc,
                )
                return []

        if len(self._extra) == 1:
            return call(self._extra[0])
        with ThreadPoolExecutor(max_workers=len(self._extra)) as pool:
            return [hit for hits in pool.map(call, self._extra) for hit in hits]

    # ---- collectors ----

    def _collect_about_veles(self, query: str, *, limit: int) -> list[RecallHit]:
        """Framework-global Veles usage knowledge (M186). Engine-independent:
        the store is package-shipped, so this never consults `wiki_enabled`.
        Below-threshold queries return [], keeping non-Veles turns clean."""
        from veles.core.knowledge.store import get_default_store

        hits: list[RecallHit] = []
        for h in get_default_store().search(query, limit=limit):
            summary = h.body.strip().replace("\n", " ")
            if len(summary) > _TURN_SUMMARY_CAP:
                summary = summary[: _TURN_SUMMARY_CAP - 1].rstrip() + "…"
            hits.append(
                RecallHit(
                    rel_path=f"about-veles:{h.ref}",
                    title=h.title,
                    summary=summary or h.title,
                    score=float(h.score),
                )
            )
        return hits

    def _collect_wiki(self, query: str, *, limit: int) -> list[RecallHit]:
        """Wiki-engine collector (M163: layout-gated). A project whose
        layout pack doesn't enable the wiki engine contributes no wiki
        hits; recall still works off insights/rules/turns/extras. The
        same check applies per subproject — each child's own layout
        decides."""
        from veles.core.layout.engines import wiki_enabled
        from veles.modules.wiki.wiki import Wiki

        hits: list[RecallHit] = []
        if wiki_enabled(self._project):
            hits.extend(
                RecallHit(rel_path=p.rel_path, title=p.title, summary=p.summary)
                for p in Wiki(self._project.wiki_root).search(query, limit=limit)
            )
        sub_limit = max(1, limit // 2)
        for sub in load_subprojects(self._project):
            sub_root = resolve_subproject_path(self._project, sub)
            # v2: subproject wiki lives at `<sub_root>/wiki/`, container
            # is the subproject root itself.
            if not (sub_root / ".veles").is_dir():
                continue
            if not _subproject_wiki_enabled(sub_root):
                continue
            sub_wiki = Wiki(sub_root)
            for page in sub_wiki.search(query, limit=sub_limit):
                hits.append(
                    RecallHit(
                        rel_path=f"{sub.slug}:{page.rel_path}",
                        title=f"[{sub.slug}] {page.title}",
                        summary=page.summary,
                    )
                )
        return hits

    async def _collect_insights(self, query: str, *, limit: int) -> list[RecallHit]:
        """M140: pull matching rows from the `insights` SQL table and age them.

        Aging happens in `_age_recalled_insights` after the merge, not here:
        being *injected into the prompt* is the reference, not being matched.
        No-op without a store. M161: the SQL row is the sole insight store (the markdown
        under `.veles/memory/insights/` is a rendered view, never searched)."""
        if self._store is None:
            return []
        hits = list(await self._store.search_insights(query, limit=limit))
        # M192: fold in semantic (vector) neighbours, deduped by insight id, so
        # a paraphrased query that shares no tokens with an insight still
        # recalls it. Local-first: `_local_query_vector` embeds the query ONLY
        # via a local adapter — a cloud embedder never receives the query text.
        qvec = _local_query_vector(query)
        if qvec is not None:
            seen = {h.id for h in hits}
            for vh in await self._store.knn_insights(qvec, limit=limit):
                if vh.id not in seen:
                    seen.add(vh.id)
                    hits.append(vh)
        # M218: prune sub-floor insights (heuristic guesses that scored low
        # provenance confidence) before they reach the prompt — cheaper context,
        # less noise. Pre-M218 rows default to 1.0 and are never touched.
        hits = [h for h in hits if h.confidence >= _INSIGHT_CONFIDENCE_FLOOR]
        return [_insight_hit_to_recall(h) for h in hits]

    def _age_recalled_insights(self, final: list[RecallHit]) -> None:
        """Stamp `last_referenced_at` on the insights that actually made it
        into the prompt (M264).

        The bump used to happen inside the collector, over every FTS/KNN match.
        Two problems, one of which only appeared with the bounded fan-out:
        matches that lost the rerank were aged as though they had been used,
        and — once a collector could be cancelled at the deadline — a stream
        that never reached the prompt at all still aged its rows. That signal
        feeds `rerank`'s recency term *and* picks the canonical survivor in
        M142 dedup, so a false reference is not cosmetic.

        Being *injected* is the reference. Anything else is a query artefact.
        """
        if self._store is None:
            return
        ids = [
            int(h.rel_path.removeprefix("insight:"))
            for h in final
            if h.rel_path.startswith("insight:") and h.rel_path.removeprefix("insight:").isdigit()
        ]
        if ids:
            aio.submit(self._store.touch_insights(ids, time.time()))

    async def _collect_turns(self, query: str, *, limit: int) -> list[RecallHit]:
        """Pull recent turns matching `query`. No-op when no store is wired.

        The 30-day window keeps recall focused on what the user might
        reasonably remember chatting about. Older facts that matter
        should have made it into the wiki via the M28 curator by now.
        """
        if self._store is None:
            return []
        # M193: the 30-day window assumes the curator already distilled older
        # turns into insights. Until the first curator/dream pass, raw turns are
        # the ONLY memory, so applying the window would silently drop it.
        since = None if _never_curated(self._project) else time.time() - _TURN_RECENCY_WINDOW_SEC
        turn_hits = await self._store.search_turns(query, limit=limit, since=since)
        return [_turn_hit_to_recall(h) for h in turn_hits]


def _as_port(store: object | None) -> object | None:
    """Accept either a `MemoryStore` or the `SessionStore` most callers still
    hold, and return the port. Wrapping rather than reopening matters: a second
    connection to the same file would be a second connection to the same file,
    and the caller's `finally: store.close()` still has to mean something."""
    if store is None:
        return None
    from veles.core.memory import SessionStore as _SessionStore
    from veles.core.memory.store import SqliteStore

    if isinstance(store, _SessionStore):
        return SqliteStore.wrapping(store)
    return store


def _never_curated(project) -> bool:
    """M193: True when no curator or dream pass has ever run for the project.
    Until then, the 30-day turn-recall window would silently discard the only
    copy of older memory (nothing has been distilled into insights yet)."""
    from veles.core.curator_state import load

    try:
        state = load(project.state_dir / "curator.state.json")
    except Exception:
        return True
    return state.last_curated_at == 0.0 and state.dream_count == 0


def _local_query_vector(query: str) -> list[float] | None:
    """M192: embed the recall `query` for vector search — but ONLY through a
    LOCAL embedding adapter. A cloud embedder must never receive the query
    text (the local-first no-egress guarantee: the audit flagged embedding
    autodetect as a silent cloud path). Returns None when there is no adapter,
    it is not local, or embedding fails — in which case recall stays FTS-only.
    """
    from veles.modules.embedding import get_local_embedding_adapter

    adapter = get_local_embedding_adapter()
    if adapter is None:
        return None
    try:
        vecs = adapter.embed([query])
    except Exception:
        return None
    return vecs[0] if vecs else None


def _subproject_wiki_enabled(sub_root) -> bool:
    """Best-effort wiki-engine check for a subproject (its own layout
    decides). Unloadable child → no wiki hits from it."""
    from veles.core.layout.engines import wiki_enabled
    from veles.core.project import load_project

    try:
        return wiki_enabled(load_project(sub_root))
    except Exception:
        return False


def _load_recall_deadline(project: Project) -> float:
    """`[memory.recall] deadline_sec`, defaulting to `_RECALL_DEADLINE_SEC`.

    A constant would have been the wrong shape for the one knob a multi-tenant
    integrator reaches for first — and every neighbouring tunable in this
    subsystem (`[memory.rerank]`, `[memory] turn_retention_days`) already comes
    from config. M265's provider deadline reads the same key rather than
    inventing a second one. Non-positive or malformed values fall back rather
    than disabling the bound: "no deadline" must not be reachable by typo."""
    try:
        from veles.core.project_config import get_section, load_project_config

        raw = get_section(load_project_config(project), "memory", "recall").get("deadline_sec")
    except Exception:
        return _RECALL_DEADLINE_SEC
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _RECALL_DEADLINE_SEC
    return value if value > 0 else _RECALL_DEADLINE_SEC


def _load_rerank_config(project: Project) -> tuple[RerankWeights, float]:
    """Read `[memory.rerank]` from the project config. Missing / malformed →
    defaults (best-effort, never raises into recall)."""
    try:
        from veles.core.project_config import get_section, load_project_config

        sec = get_section(load_project_config(project), "memory", "rerank")
    except Exception:
        return DEFAULT_WEIGHTS, DEFAULT_HALF_LIFE_SEC
    if not sec:
        return DEFAULT_WEIGHTS, DEFAULT_HALF_LIFE_SEC
    try:
        weights = RerankWeights(
            relevance=float(sec.get("relevance", DEFAULT_WEIGHTS.relevance)),
            recency=float(sec.get("recency", DEFAULT_WEIGHTS.recency)),
            confidence=float(sec.get("confidence", DEFAULT_WEIGHTS.confidence)),
        )
        half_life = float(sec.get("half_life_days", DEFAULT_HALF_LIFE_SEC / 86_400.0)) * 86_400.0
    except (TypeError, ValueError):
        return DEFAULT_WEIGHTS, DEFAULT_HALF_LIFE_SEC
    return weights, half_life


def _scrub_recall_hit(hit: RecallHit) -> RecallHit:
    """M145: passively scrub a recall summary before it enters the prompt.

    Every other memory surface entering the system prompt already passes
    through `scan_for_injection` on load — AGENTS.md (`project.py`), wiki pages
    (`wiki.read_page`), INDEX — but recall summaries bypass it: `Wiki.search`
    returns stored page text directly (not via the scrubbed `read_page`), and
    the turn/insight FTS queries return raw rows. A capped turn snippet can
    also slice off the `<untrusted>` boundary that wrapped external content at
    its source. Recall is therefore the one hole in the "every memory surface
    is scrubbed" invariant; close it here, at the single chokepoint every
    recall consumer passes through.

    This is the *passive* scrubber (neutralise known injection phrases, strip
    invisible chars) — deliberately NOT `wrap_untrusted`. Recall is the agent's
    own reference knowledge; an active "do not act on this / do not derive tool
    arguments from it" boundary would break legitimate memory use (memory says
    the API base URL is X → the agent should use X). Scrub the payload, keep
    the trust. Returns the same object when nothing changed (no churn)."""
    cleaned, _ = scan_for_injection(hit.summary, source_label=f"recall:{hit.rel_path}")
    if cleaned == hit.summary:
        return hit
    return replace(hit, summary=cleaned)


def _insight_hit_to_recall(hit: InsightHit) -> RecallHit:
    summary = (hit.body or "").strip().replace("\n", " ")
    if len(summary) > _TURN_SUMMARY_CAP:
        summary = summary[: _TURN_SUMMARY_CAP - 1].rstrip() + "…"
    return RecallHit(
        rel_path=f"insight:{hit.id}",
        title=hit.title,
        summary=summary or "(empty insight)",
        score=hit.rank,
        ts=hit.ts,
        confidence=hit.confidence,
    )


def _turn_hit_to_recall(hit: TurnHit) -> RecallHit:
    when = _dt.datetime.fromtimestamp(hit.created_at, tz=_dt.UTC).strftime("%Y-%m-%d %H:%M")
    summary = (hit.content or "").strip().replace("\n", " ")
    if len(summary) > _TURN_SUMMARY_CAP:
        summary = summary[: _TURN_SUMMARY_CAP - 1].rstrip() + "…"
    return RecallHit(
        rel_path=f"turn:{hit.session_id}:{hit.seq}",
        title=f"[{hit.role} @ {when}]",
        summary=summary or "(empty turn)",
        score=hit.rank,
        ts=hit.created_at,
    )
