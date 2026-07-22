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

import datetime as _dt
import os
import time
from dataclasses import dataclass, replace

from veles.core.memory import InsightHit, SessionStore, TurnHit
from veles.core.memory.rerank import (
    DEFAULT_HALF_LIFE_SEC,
    DEFAULT_WEIGHTS,
    RerankWeights,
    rerank,
)
from veles.core.project import Project
from veles.core.safety import scan_for_injection
from veles.core.subproject import load_subprojects, resolve_subproject_path

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
        self._store = store
        # M55: opt-in external memory plugins (Honcho, Mem0, ...). Stored as
        # `object` to avoid an import cycle with `memory_provider.MemoryProvider`
        # — every entry is duck-typed at call time.
        self._extra: list[object] = list(extra_providers or [])

    def recall(self, query: str, *, limit: int = 5) -> list[RecallHit]:
        if not query.strip():
            return []
        about_hits = self._collect_about_veles(query, limit=limit)
        wiki_hits = self._collect_wiki(query, limit=limit)
        insight_hits = self._collect_insights(query, limit=limit)
        turn_hits = self._collect_turns(query, limit=limit)
        extra_hits = self._collect_extra(query, limit=limit)
        streams = [about_hits, wiki_hits, insight_hits, turn_hits, extra_hits]
        # M141: scored rerank by default; `VELES_MEMORY_RERANK=0` falls back to
        # the round-robin merge. (M161 made insights SQL-only, so the old
        # wiki↔insight title dedupe is gone — the streams no longer overlap.)
        if _rerank_enabled():
            weights, half_life = _load_rerank_config(self._project)
            merged = rerank(
                streams,
                now=time.time(),
                limit=limit,
                weights=weights,
                half_life_sec=half_life,
            )
        else:
            merged = _interleave_many(streams, limit)
        final = merged[:limit]
        # M145: scrub recall summaries before they enter the prompt — the one
        # memory surface that bypasses `scan_for_injection`. See
        # `_scrub_recall_hit`. Done on the final ≤limit hits only, so the cost
        # is a handful of regex passes per turn.
        return [_scrub_recall_hit(h) for h in final]

    def _collect_extra(self, query: str, *, limit: int) -> list[RecallHit]:
        """Call every registered external provider, swallowing per-provider
        failures so one slow / broken plugin can't tank the whole recall."""
        out: list[RecallHit] = []
        per_provider = max(1, limit // 2)
        for p in self._extra:
            try:
                hits = p.recall(query, limit=per_provider)  # type: ignore[attr-defined]
            except Exception:
                continue
            out.extend(hits)
        return out

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

    def _collect_insights(self, query: str, *, limit: int) -> list[RecallHit]:
        """M140: pull matching rows from the `insights` SQL table and age them.

        Every matched insight is `touch`ed (its `last_referenced_at` bumped)
        as a side effect — being retrieved *is* a reference. No-op without a
        store. M161: the SQL row is the sole insight store (the markdown
        under `.veles/memory/insights/` is a rendered view, never searched)."""
        if self._store is None:
            return []
        hits = list(self._store.search_insights(query, limit=limit))
        # M192: fold in semantic (vector) neighbours, deduped by insight id, so
        # a paraphrased query that shares no tokens with an insight still
        # recalls it. Local-first: `_local_query_vector` embeds the query ONLY
        # via a local adapter — a cloud embedder never receives the query text.
        qvec = _local_query_vector(query)
        if qvec is not None:
            seen = {h.id for h in hits}
            for vh in self._store.knn_insights(qvec, limit=limit):
                if vh.id not in seen:
                    seen.add(vh.id)
                    hits.append(vh)
        # M218: prune sub-floor insights (heuristic guesses that scored low
        # provenance confidence) before they reach the prompt — cheaper context,
        # less noise. Pre-M218 rows default to 1.0 and are never touched.
        hits = [h for h in hits if h.confidence >= _INSIGHT_CONFIDENCE_FLOOR]
        if hits:
            self._store.touch_insights([h.id for h in hits], time.time())
        return [_insight_hit_to_recall(h) for h in hits]

    def _collect_turns(self, query: str, *, limit: int) -> list[RecallHit]:
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
        turn_hits = self._store.search_turns(query, limit=limit, since=since)
        return [_turn_hit_to_recall(h) for h in turn_hits]


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


def _interleave_many(streams: list[list[RecallHit]], limit: int) -> list[RecallHit]:
    """Round-robin merge across N streams, capped at `limit`.

    Order matters: earlier streams are sampled first within each cycle, so
    the leading stream's #1 hit always lands before any other source's #1.
    Wiki being first preserves the M55 design intent (curated knowledge
    leads, raw turns next, external plugins after).
    """
    out: list[RecallHit] = []
    indices = [0] * len(streams)
    progressed = True
    while progressed and len(out) < limit:
        progressed = False
        for s, stream in enumerate(streams):
            if indices[s] < len(stream):
                out.append(stream[indices[s]])
                indices[s] += 1
                progressed = True
                if len(out) >= limit:
                    break
    return out


def _rerank_enabled() -> bool:
    """M141: rerank is on unless `VELES_MEMORY_RERANK` is a falsy string."""
    return os.environ.get("VELES_MEMORY_RERANK", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
        "",
    )


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
