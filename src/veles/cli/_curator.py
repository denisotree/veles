"""Curator + insight extractor (M21 / M28 / M31) — extracted in M46 final.

Hosts the per-session curator (`_curate_one_session`), the pass-coordinator
(`_run_curator_pass`), the M28 continuous triggers (`_maybe_run_idle_curator`,
`_maybe_run_post_turn_curator`), the M31 insight extractor
(`_maybe_run_insight_extractor`), and shared helpers used by `tests/test_curator.py`
(`_truncate_session_messages`, `_render_message`).

`_curate_one_session` and the `_maybe_run_*` triggers depend on run-loop
helpers (`_make_tool_aware_provider`, `_load_skills`, `_qualify_for_provider`,
`_run_agent_streaming_aware`, `_print_run_summary`) plus the API-key check
(`_has_api_key_for_provider`). To keep `monkeypatch.setattr("veles.cli._foo",
fake)` effective for tests, those references are looked up via lazy imports
from `veles.cli` *inside* the function bodies — the patched attribute is
visible at call time. The same applies to `_run_curator_pass`, which itself
gets patched in idle / post-turn tests.

`cli/__init__.py` re-exports every `_<name>` so existing test imports
(`from veles.cli import _curate_one_session`) keep working.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import sys
import time

from veles.core.agent import Agent
from veles.core.curator import (
    _CURATE_CHARS_LIMIT,
    _CURATE_QUIET_WINDOW_SEC,
    _CURATE_TOOLS,
    _CURATE_TURN_LIMIT,
    _CURATOR_IDLE_LIMIT,
    _CURATOR_IDLE_THRESHOLD_SEC,
    _CURATOR_POSTRUN_LIMIT,
    _CuratorPassResult,
    _truncate_session_messages,
)
from veles.core.curator_state import CuratorState
from veles.core.curator_state import load as load_curator_state
from veles.core.curator_state import save_atomic as save_curator_state
from veles.core.insight_extractor import make_insight_extractor
from veles.core.memory import SessionInfo, SessionStore
from veles.core.memory.artefacts import append_memory_log
from veles.core.project import Project
from veles.core.provider import Message
from veles.core.routing import route
from veles.modules.wiki.wiki import Wiki

# ---- CLI-only state file constants ----
# These remain in CLI because they describe argparse-driven state files
# scoped to the `veles run` invocation. Domain-level curator constants
# (CURATE_TOOLS, CURATOR_IDLE_LIMIT, etc.) live in `core/curator.py`.

# M62: subproject proposer rerun cadence — 7d between automatic refreshes
# of `.veles/memory/proposals/`. The detector is cheap (~tens of ms), but
# we still avoid hammering it on every `veles run` so proposal pages
# don't churn their mtimes (the freshness window keys on mtime).
_PROPOSER_IDLE_THRESHOLD_SEC = 7 * 24 * 3600
_PROPOSER_STATE_FILE = "proposer.state.json"
# M61: skill auto-promote suggestion also uses a 7-day cadence so
# `.veles/memory/proposals/promote-*.md` mtimes stay stable.
_PROMOTE_SUGGEST_IDLE_THRESHOLD_SEC = 7 * 24 * 3600
_PROMOTE_SUGGEST_STATE_FILE = "promote_suggest.state.json"


def _run_curator_pass(
    args: argparse.Namespace,
    project: Project,
    *,
    max_sessions: int,
    mode_label: str,
) -> _CuratorPassResult:
    """Curate up to `max_sessions` quiet sessions newer than `last_curated_at`.

    Shared by `veles curate` (M21 batch entry-point) and the M28
    continuous-trigger paths (`_maybe_run_idle_curator`,
    `_maybe_run_post_turn_curator`). The function is silent on its own
    — callers print the user-facing summary so each entry-point keeps
    its existing tone.
    """
    from veles.core.layout.engines import wiki_enabled

    if wiki_enabled(project):
        Wiki(project.wiki_root).ensure_layout()
    state_path = project.state_dir / "curator.state.json"
    state = load_curator_state(state_path)
    cutoff = time.time() - _CURATE_QUIET_WINDOW_SEC

    next_cursor = state.last_curated_at
    successes = 0

    with SessionStore(project.memory_db_path) as store:
        candidates = [
            s
            for s in store.list_sessions_since(state.last_curated_at, limit=max_sessions)
            if s.turn_count > 0 and s.last_activity_at < cutoff
        ]
        if not candidates:
            return _CuratorPassResult(
                successes=0,
                had_candidates=False,
                advanced_to=state.last_curated_at,
                starting_cursor=state.last_curated_at,
            )
        for session in candidates:
            ok = _curate_one_session(store, session, args, project)
            if not ok:
                print(
                    f"<curate ({mode_label}) failed for {session.id}; stopping>",
                    file=sys.stderr,
                )
                break
            next_cursor = session.last_activity_at
            successes += 1

    if successes > 0:
        save_curator_state(
            state_path,
            CuratorState(
                last_curated_at=next_cursor,
                sessions_curated_total=state.sessions_curated_total + successes,
            ),
        )
        append_memory_log(
            project,
            op=f"curate-{mode_label}",
            summary=f"{successes} session(s) curated, cursor → {next_cursor}",
        )
    return _CuratorPassResult(
        successes=successes,
        had_candidates=True,
        advanced_to=next_cursor,
        starting_cursor=state.last_curated_at,
    )


def _continuous_curator_eligible(args: argparse.Namespace) -> bool:
    """Gate `_maybe_run_*` helpers. Continuous curation runs whenever the
    active provider can drive the curator sub-agents:

    - direct-API providers (`openrouter`/`anthropic`/`openai`/`gemini`) with
      the right API key configured;
    - local providers (`ollama`/`llamacpp`/`openai-compat`), which authenticate
      via their own runtime — `has_api_key` returns True for them.

    cli-delegate providers (`claude-cli`/`gemini-cli`) can't drive arbitrary
    models for the sub-agents (`has_api_key` returns False), and `--resume`
    runs are user-driven refinement where extra LLM noise is unwelcome.

    M184: this keys off `has_api_key(provider)` rather than membership in
    `PROVIDER_API_KEY_ENVS`. The old membership check silently excluded local
    providers, so a daemon/channel diary bot on ollama never curated. `provider`
    must be the *resolved* effective provider — daemon/channel callers resolve
    it into `args.provider` before the post-turn loop runs (a bare None — the
    daemon-start default — stays ineligible).
    """
    from veles.core.provider_factory import has_api_key

    if getattr(args, "no_curator", False):
        return False
    if getattr(args, "resume", None) is not None:
        return False
    provider = getattr(args, "provider", None)
    if not provider:
        return False
    return has_api_key(provider)


def _maybe_run_idle_curator(args: argparse.Namespace, project: Project) -> None:
    """Force a curator pass when the cursor is older than the idle
    threshold. Runs synchronously before the user's actual turn — the
    rationale is that a stale-by-a-day backlog signals the agent has
    been collecting context the user expected to be queryable."""
    if not _continuous_curator_eligible(args):
        return
    state_path = project.state_dir / "curator.state.json"
    state = load_curator_state(state_path)
    if time.time() - state.last_curated_at < _CURATOR_IDLE_THRESHOLD_SEC:
        return
    print(
        f"<idle curator: cursor stale ≥{_CURATOR_IDLE_THRESHOLD_SEC // 3600}h, "
        f"running pass over up to {_CURATOR_IDLE_LIMIT} session(s)>",
        file=sys.stderr,
    )
    # Lazy lookup so monkey-patches at `veles.cli._run_curator_pass` win.
    from veles.cli import _run_curator_pass as _patched_run_curator_pass

    try:
        _patched_run_curator_pass(
            args, project, max_sessions=_CURATOR_IDLE_LIMIT, mode_label="idle"
        )
    except Exception as exc:
        append_memory_log(
            project,
            op="curate-skip",
            summary=f"idle curator failed: {type(exc).__name__}: {exc}",
        )


def _maybe_run_post_turn_curator(args: argparse.Namespace, project: Project) -> None:
    """Curate one stale session right after the user's turn completes.
    Quiet-window filter (60s) means the just-finished session is *not*
    picked up — instead older quiet sessions get processed, so each
    `veles run` gradually drains the backlog without competing with the
    session it just produced."""
    if not _continuous_curator_eligible(args):
        return
    # Lazy lookup so monkey-patches at `veles.cli._run_curator_pass` win.
    from veles.cli import _run_curator_pass as _patched_run_curator_pass

    try:
        _patched_run_curator_pass(
            args, project, max_sessions=_CURATOR_POSTRUN_LIMIT, mode_label="post-turn"
        )
    except Exception as exc:
        append_memory_log(
            project,
            op="curate-skip",
            summary=f"post-turn curator failed: {type(exc).__name__}: {exc}",
        )
    # M121d: surface any newly-emerged skill suggestions from the
    # pattern detector into the `insights` table. The next `/save`
    # / TUI insights list picks them up. Best-effort; never blocks
    # the user's turn even if memory.db is locked.
    _maybe_surface_skill_suggestions(project)
    # M76 post-turn dream — cheap-only (no consolidation), throttled to
    # once per `_POST_TURN_DEFAULT_INTERVAL_SEC`. Never blocks the run.
    _maybe_run_post_turn_dream(args, project)


def _maybe_surface_skill_suggestions(project: Project) -> None:
    """M121d hook: pattern detector → insights table.

    Runs after each post-turn curator pass. The suggester is
    idempotent — only newly-discovered clusters land as fresh
    insight rows. Failure logs and continues so a sqlite lock or
    a missing table doesn't break the user's turn.
    """
    try:
        from veles.core.memory import SessionStore
        from veles.core.skill_suggester import surface_skill_suggestions
    except ImportError:
        return
    try:
        store = SessionStore(project.memory_db_path)
        surface_skill_suggestions(store._conn)
    except Exception as exc:
        # Same posture as the curator-skip log: don't fail the turn.
        with contextlib.suppress(Exception):
            append_memory_log(
                project,
                op="skill-suggest-skip",
                summary=f"{type(exc).__name__}: {exc}",
            )

    # Embedding setup-hint: when no embedding backend is configured,
    # write a one-time setup hint into `insights` so the user
    # discovers the upgrade path via the regular insights surface.
    # `maybe_surface_embedding_setup_hint` is idempotent — only
    # writes the row when it doesn't already exist.
    try:
        from veles.core.embedding_notice import maybe_surface_embedding_setup_hint
        from veles.modules import autodetect_embedding_adapter

        if autodetect_embedding_adapter() is None:
            maybe_surface_embedding_setup_hint(project)
    except Exception:
        pass


def _maybe_run_post_turn_dream(args: argparse.Namespace, project: Project) -> None:
    """Light dream pass: dedup + promote + lint refresh. No LLM consolidation."""
    if getattr(args, "no_dream", False):
        return
    if not _continuous_curator_eligible(args):
        return
    from veles.core.curator_state import load as _load_state
    from veles.core.dreaming import _POST_TURN_DEFAULT_INTERVAL_SEC, dream_cycle

    state_path = project.state_dir / "curator.state.json"
    state = _load_state(state_path)
    now = time.time()
    if now - state.last_post_turn_dream_at < _POST_TURN_DEFAULT_INTERVAL_SEC:
        return
    try:
        dream_cycle(
            project,
            include_consolidation=False,
            skip_insights=True,  # insight extractor already runs from cli/_curator
            now=now,
        )
    except Exception as exc:
        append_memory_log(
            project,
            op="dream-skip",
            summary=f"post-turn dream failed: {type(exc).__name__}: {exc}",
        )


def _maybe_run_subproject_proposer(args: argparse.Namespace, project: Project) -> None:
    """M62 — refresh `wiki/proposals/` periodically so the agent sees fresh suggestions.

    Closes VISION §2.2: the agent — not the user — initiates
    decomposition. Runs after the user's turn completes, gated by the
    same eligibility check as the curator (so cli-delegate paths and
    `--resume` skip it) and a 7-day idle threshold so successful
    runs don't churn proposal mtimes.

    The detector is deterministic and LLM-free, so this is genuinely
    cheap to call. Failure appends `op="proposer-skip"` to LOG.md and
    never propagates.
    """
    if not _continuous_curator_eligible(args):
        return
    if getattr(args, "no_proposer", False):
        return
    from veles.core.layout.engines import wiki_enabled

    # The subproject proposer clusters wiki pages — a no-op on layouts whose
    # wiki engine is off (bare/notes). Gating here keeps `detect_clusters`
    # (which constructs a Wiki) from ever running on a non-wiki layout.
    if not wiki_enabled(project):
        return

    state_path = project.state_dir / _PROPOSER_STATE_FILE
    last_ran = _read_proposer_state(state_path)
    now = time.time()
    if now - last_ran < _PROPOSER_IDLE_THRESHOLD_SEC:
        return

    from veles.core.subproject_proposer import detect_clusters, write_proposals

    try:
        clusters = detect_clusters(project)
        if clusters:
            write_proposals(project, clusters)
    except Exception as exc:
        append_memory_log(
            project,
            op="proposer-skip",
            summary=f"subproject proposer failed: {type(exc).__name__}: {exc}",
        )
        return
    _write_proposer_state(state_path, now)


def _read_proposer_state(path) -> float:
    import json

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0.0
    last = data.get("last_ran_at") if isinstance(data, dict) else None
    return float(last) if isinstance(last, int | float) else 0.0


def _write_proposer_state(path, ts: float) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_ran_at": ts}) + "\n", encoding="utf-8")


def _maybe_suggest_promotions(args: argparse.Namespace, project: Project) -> None:
    """M61 — refresh `wiki/proposals/promote-*.md` when project skills cross the bar.

    Cheap path: `find_promote_candidates` reads only SKILL.md
    frontmatter, no LLM call. Gated by:
    - `_continuous_curator_eligible(args)` (same gate as proposer / curator).
    - `--no-suggest-promote` per-run kill switch.
    - 7-day idle threshold via `promote_suggest.state.json` so mtimes
      remain stable for memory recall surfacing.

    Failure path appends `op="promote-suggest-skip"` to LOG.md and
    never propagates.
    """
    if not _continuous_curator_eligible(args):
        return
    if getattr(args, "no_suggest_promote", False):
        return
    state_path = project.state_dir / _PROMOTE_SUGGEST_STATE_FILE
    last_ran = _read_proposer_state(state_path)
    now = time.time()
    if now - last_ran < _PROMOTE_SUGGEST_IDLE_THRESHOLD_SEC:
        return
    try:
        from veles.core.skill_promotion import (
            find_promote_candidates,
            write_promote_proposals,
        )

        candidates = find_promote_candidates(project)
        if candidates:
            write_promote_proposals(project, candidates)
    except Exception as exc:
        append_memory_log(
            project,
            op="promote-suggest-skip",
            summary=f"skill promote-suggester failed: {type(exc).__name__}: {exc}",
        )
        return
    _write_proposer_state(state_path, now)


def _maybe_refresh_nl_routing(args: argparse.Namespace, project: Project) -> None:
    """M43b — re-parse AGENTS.md routing hints into `routing.nl.toml` when it changed.

    Gated by:
    - `_continuous_curator_eligible(args)` (openrouter + API key + not `--resume`).
    - `--no-route-refresh` per-run kill switch.
    - SHA-256 of AGENTS.md vs the stored nl-state (skip if unchanged).

    Idempotent: the sub-Agent runs at most once per AGENTS.md edit.
    Failures append `op="route-refresh-skip"` to LOG.md and never
    propagate.
    """
    if not _continuous_curator_eligible(args):
        return
    if getattr(args, "no_route_refresh", False):
        return

    from veles.core.project import load_agents_md
    from veles.core.routing import (
        agents_md_sha256,
        load_nl_state,
        make_nl_extractor,
        refresh_nl_routing,
        route,
    )

    agents_md = load_agents_md(project) or ""
    if not agents_md.strip():
        return
    if agents_md_sha256(agents_md) == load_nl_state(project).agents_md_sha256:
        return

    from veles.cli import _has_api_key_for_provider, _make_provider
    from veles.core.model_resolver import ConfigurationError

    try:
        routed_provider, routed_model = route("default", project)
    except ConfigurationError:
        return
    if not _has_api_key_for_provider(routed_provider):
        return
    try:
        provider = _make_provider(routed_provider)
    except Exception as exc:
        append_memory_log(
            project,
            op="route-refresh-skip",
            summary=f"failed to build provider {routed_provider!r}: {exc}",
        )
        return

    try:
        extractor = make_nl_extractor(provider=provider, model=routed_model)
        refresh_nl_routing(project, agents_md, extractor=extractor)
    except Exception as exc:
        append_memory_log(
            project,
            op="route-refresh-skip",
            summary=f"nl routing refresh failed: {type(exc).__name__}: {exc}",
        )


def _maybe_run_insight_extractor(
    args: argparse.Namespace,
    project: Project,
    history: list[Message],
    session_id: str | None,
) -> None:
    """Extract durable lessons from the just-finished run.

    Same eligibility gate as the continuous curator (openrouter +
    API key + not `--resume`); `--no-insights` is the per-run kill
    switch. A failure logs `op="insight-skip"` to `LOG.md` and never
    propagates — the parent run already returned to the user.
    """
    from veles.core.provider_factory import has_api_key, make_provider

    if getattr(args, "no_insights", False):
        return
    if getattr(args, "resume", None) is not None:
        return
    from veles.core.model_resolver import ConfigurationError

    try:
        routed_provider, routed_model = route("insights", project)
    except ConfigurationError:
        return
    if not has_api_key(routed_provider):
        return
    explicit_model = getattr(args, "compressor_model", None)
    model = explicit_model or routed_model
    try:
        extractor = make_insight_extractor(
            provider=make_provider(routed_provider, model=model),
            model=model,
            project=project,
        )
        extractor(history, session_id)
    except Exception as exc:
        append_memory_log(
            project,
            op="insight-skip",
            summary=f"insight extraction failed: {type(exc).__name__}: {exc}",
        )


def _curate_one_session(
    store: SessionStore,
    session: SessionInfo,
    args: argparse.Namespace,
    project: Project,
) -> bool:
    # Lazy imports so monkey-patches at `veles.cli._<helper>` win.
    from veles.cli import (
        _load_skills,
        _make_tool_aware_provider,
        _print_run_summary,
        _qualify_for_provider,
        _run_agent_streaming_aware,
    )
    from veles.core.layout.engines import wiki_enabled

    messages = store.load_messages(session.id)
    serialized = _truncate_session_messages(messages, _CURATE_TURN_LIMIT, _CURATE_CHARS_LIMIT)
    created_iso = _dt.datetime.fromtimestamp(session.created_at, tz=_dt.UTC).isoformat()
    # M163: the wiki-page half of curation exists only when the layout
    # pack enables the wiki engine; without it the distillation lands in
    # SQL memory alone (memory_save_insight / memory_save_rule).
    if wiki_enabled(project):
        persist_steps = (
            f'- Call wiki_write_page(category="sessions", slug="{session.id}",'
            " title=..., content=...).\n"
            "- Call memory_save_insight(title=<same title>, body=<a 2-4 sentence"
            ' summary>, category="curated-session", file_path=<the wiki page path>)'
            " so the insight surfaces in /insights and recall.\n"
        )
        log_step = (
            '- Call wiki_append_log(op="curate",'
            f' summary="<one-line summary>: session {session.id}").\n'
            "- Reply with one sentence confirming the page path.\n\n"
        )
        intro = "Distill this Veles session into a single persistent wiki page."
    else:
        persist_steps = (
            "- Call memory_save_insight(title=<same title>, body=<the distilled"
            ' content>, category="curated-session") so it surfaces in /insights'
            " and recall.\n"
        )
        log_step = "- Reply with one sentence confirming the insight was saved.\n\n"
        intro = "Distill this Veles session into one durable memory insight."
    system_prompt = (
        f"You are the Veles curator. {intro}"
        " Skip greetings, error retries, and tool noise;"
        " keep only durable facts, decisions, learnings, and references that a"
        " future agent should be able to recall.\n\n"
        "Workflow:\n"
        "- Choose a short H1 title that names the topic.\n"
        "- Write 3-8 bullet points or short paragraphs covering the durable"
        " signal. Cite tool outputs only when load-bearing.\n"
        f"{persist_steps}"
        "- If the session reveals a stable behavioral preference or constraint"
        ' (e.g. "user prefers terse responses", "always use real DB in tests",'
        ' "never invoke X without confirmation"), additionally call'
        f' memory_save_rule(kind="preference", body=<rule text>,'
        f' source="session-{session.id}"). Use kind="format" for response shape,'
        ' "do" for always-do, "dont" for never-do, "preference" for taste.\n'
        f"{log_step}"
        "Session metadata:\n"
        f"  id={session.id}\n"
        f"  created_at={created_iso}\n"
        f"  turn_count={session.turn_count}\n\n"
        "Session turns (chronological):\n"
        f"{serialized}"
    )
    provider = _make_tool_aware_provider(args.provider, project, skill_model=args.model)
    system_prompt = _qualify_for_provider(system_prompt, provider, _CURATE_TOOLS)
    agent = Agent(
        provider=provider,
        registry=_load_skills(project, _CURATE_TOOLS, provider=provider, model=args.model),
        model=args.model,
        max_iterations=args.max_iterations,
        system_prompt=system_prompt,
        verbose=args.verbose,
    )
    result, budget = _run_agent_streaming_aware(
        agent,
        f"Curate session {session.id}.",
        args,
        project=project,
    )
    if args.verbose:
        _print_run_summary(args, result, budget)
    return result.stopped_reason == "completed"


_SELF_DOC_IDLE_SEC = 3600  # refresh at most once per hour


def _maybe_refresh_self_doc(project: Project) -> None:
    """Refresh wiki/self-doc/overview.md if stale (> 1h since last refresh).

    Runs silently; all failures are swallowed so a broken sub-component
    never surfaces to the user during `veles run`.
    """
    import json
    import time

    state_path = project.state_dir / "self-doc.state.json"
    now = time.time()
    if state_path.is_file():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            if now - float(data.get("refreshed_at", 0)) < _SELF_DOC_IDLE_SEC:
                return
        except Exception:
            pass
    try:
        from veles.core.self_doc import refresh_self_doc

        refresh_self_doc(project)
        state_path.write_text(json.dumps({"refreshed_at": now}), encoding="utf-8")
    except Exception:
        pass
