"""Post-turn learning: the curator and its continuous triggers, insight extraction,
proposals, NL-routing and self-doc refresh.

Hosts the per-session curator (`_curate_one_session`), the pass-coordinator
(`_run_curator_pass`) and the post-turn `_maybe_*` steps. Every step follows one
shape: an eligibility gate, an optional throttle (`_ran_recently` / `_stamp`),
then the work inside `_logged_skip`, so a failure becomes a LOG.md line and
never reaches the user's turn.

`_curate_one_session` uses `runtime/registry.py` and `runtime/run.py`, imported
inside the function so a test's patch on those modules applies.
Shared by the CLI (`veles run`, `veles curate`, the REPL) and the daemon's
post-turn hook.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as _dt
import sys
import time
from collections.abc import Iterator

from veles.core.agent import Agent
from veles.core.curator import (
    _CURATE_CHARS_LIMIT,
    _CURATE_QUIET_WINDOW_SEC,
    _CURATE_TOKEN_BUDGET,
    _CURATE_TOOLS,
    _CURATE_TURN_LIMIT,
    _CURATOR_IDLE_LIMIT,
    _CURATOR_IDLE_THRESHOLD_SEC,
    _CURATOR_POSTRUN_LIMIT,
    _CuratorPassResult,
    _truncate_session_messages,
)
from veles.core.curator_state import load as load_curator_state
from veles.core.curator_state import save_atomic as save_curator_state
from veles.core.insight_extractor import make_insight_extractor
from veles.core.io_utils import read_fresh_json, write_stamped_json
from veles.core.memory import SessionInfo, SessionStore
from veles.core.memory.artefacts import append_memory_log
from veles.core.project import Project
from veles.core.provider import Message
from veles.core.routing import route
from veles.modules.wiki.wiki import Wiki

# Subproject proposer rerun cadence — 7d between automatic refreshes of
# `.veles/memory/proposals/`. The detector is cheap (~tens of ms), but
# proposal pages must not churn their mtimes (the freshness window keys on
# mtime). Skill promote suggestions use the same cadence for the same reason.
_PROPOSER_IDLE_THRESHOLD_SEC = 7 * 24 * 3600
_PROPOSER_STATE_FILE = "proposer.state.json"
_PROMOTE_SUGGEST_IDLE_THRESHOLD_SEC = 7 * 24 * 3600
_PROMOTE_SUGGEST_STATE_FILE = "promote_suggest.state.json"
_SELF_DOC_IDLE_SEC = 3600  # refresh at most once per hour
_SELF_DOC_STATE_FILE = "self-doc.state.json"
# Poison-pill guard: consecutive curation failures before a session is
# abandoned (cursor advances past it) instead of blocking the queue forever.
_CURATE_MAX_ATTEMPTS = 3


@contextlib.contextmanager
def _logged_skip(project: Project, op: str, what: str) -> Iterator[None]:
    """Run a learning step whose failure must never reach the user's turn:
    an exception is recorded as an `op` line in LOG.md and swallowed."""
    try:
        yield
    except Exception as exc:
        with contextlib.suppress(Exception):
            append_memory_log(project, op=op, summary=f"{what}: {type(exc).__name__}: {exc}")


def _ran_recently(project: Project, state_file: str, interval_s: float) -> bool:
    """True when the step that owns `state_file` stamped it less than `interval_s` ago."""
    return read_fresh_json(project.state_dir / state_file, max_age_s=interval_s) is not None


def _stamp(project: Project, state_file: str) -> None:
    write_stamped_json(project.state_dir / state_file, {})


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
    failed = dict(state.failed_attempts)

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
                # Poison-pill guard (live 2026-07-08): one persistently failing
                # session used to block the queue FOREVER — every pass retried
                # it, failed, and stopped, so nothing behind it ever got
                # curated. Track consecutive failures; after
                # `_CURATE_MAX_ATTEMPTS` give up on that session and advance
                # the cursor past it.
                attempts = failed.get(session.id, 0) + 1
                if attempts >= _CURATE_MAX_ATTEMPTS:
                    print(
                        f"<curate ({mode_label}) failed for {session.id} "
                        f"{attempts} times; giving up on it and moving on>",
                        file=sys.stderr,
                    )
                    failed.pop(session.id, None)
                    next_cursor = session.last_activity_at
                    continue
                failed[session.id] = attempts
                print(
                    f"<curate ({mode_label}) failed for {session.id}; stopping>",
                    file=sys.stderr,
                )
                break
            failed.pop(session.id, None)
            next_cursor = session.last_activity_at
            successes += 1

    state_changed = (
        successes > 0 or next_cursor != state.last_curated_at or failed != state.failed_attempts
    )
    if state_changed:
        # dataclasses.replace: keep the dream cursors — rebuilding CuratorState
        # from scratch here used to silently reset last_*_dream_at every pass.
        save_curator_state(
            state_path,
            dataclasses.replace(
                state,
                last_curated_at=next_cursor,
                sessions_curated_total=state.sessions_curated_total + successes,
                failed_attempts=failed,
            ),
        )
    if successes > 0:
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
    with _logged_skip(project, "curate-skip", "idle curator failed"):
        _run_curator_pass(args, project, max_sessions=_CURATOR_IDLE_LIMIT, mode_label="idle")


def _maybe_run_post_turn_curator(args: argparse.Namespace, project: Project) -> None:
    """Curate one stale session right after the user's turn completes.
    Quiet-window filter (60s) means the just-finished session is *not*
    picked up — instead older quiet sessions get processed, so each
    `veles run` gradually drains the backlog without competing with the
    session it just produced."""
    if not _continuous_curator_eligible(args):
        return
    with _logged_skip(project, "curate-skip", "post-turn curator failed"):
        _run_curator_pass(
            args, project, max_sessions=_CURATOR_POSTRUN_LIMIT, mode_label="post-turn"
        )
    # Surface newly-emerged skill suggestions from the pattern detector into
    # the `insights` table, then a cheap throttled dream pass (no LLM
    # consolidation). Neither may block the user's turn.
    _maybe_surface_skill_suggestions(project)
    _maybe_run_post_turn_dream(args, project)


def _maybe_surface_skill_suggestions(project: Project) -> None:
    """M121d hook: pattern detector → insights table.

    Runs after each post-turn curator pass. The suggester is
    idempotent — only newly-discovered clusters land as fresh
    insight rows. Failure logs and continues so a sqlite lock or
    a missing table doesn't break the user's turn.
    """
    from veles.core.memory.store import local_connection
    from veles.core.skill_suggester import surface_skill_suggestions

    with (
        _logged_skip(project, "skill-suggest-skip", "skill suggestions failed"),
        local_connection(project) as conn,
    ):
        surface_skill_suggestions(conn)

    # Embedding setup-hint: when semantic recall is not actually available,
    # write a one-time setup hint into `insights` so the user discovers the
    # upgrade path via the regular insights surface.
    # `maybe_surface_embedding_setup_hint` is idempotent — only writes the row
    # when it doesn't already exist.
    #
    # M231: gate on the **local** adapter, not on "any adapter detected". M192
    # accepts an on-device embedder only (project text must never reach a cloud
    # one), so an API key alone leaves recall keyword-only — while autodetect
    # happily returns a cloud adapter, which used to silence this hint in
    # exactly the setup that needed it.
    with contextlib.suppress(Exception):
        from veles.core.embedding_notice import maybe_surface_embedding_setup_hint
        from veles.modules.embedding import get_local_embedding_adapter

        if get_local_embedding_adapter() is None:
            maybe_surface_embedding_setup_hint(project)


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
    with _logged_skip(project, "dream-skip", "post-turn dream failed"):
        dream_cycle(
            project,
            include_consolidation=False,
            skip_insights=True,  # the insight extractor runs as its own post-turn step
            now=now,
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

    if _ran_recently(project, _PROPOSER_STATE_FILE, _PROPOSER_IDLE_THRESHOLD_SEC):
        return

    from veles.core.subproject_proposer import detect_clusters, write_proposals

    with _logged_skip(project, "proposer-skip", "subproject proposer failed"):
        clusters = detect_clusters(project)
        if clusters:
            write_proposals(project, clusters)
        _stamp(project, _PROPOSER_STATE_FILE)


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
    if _ran_recently(project, _PROMOTE_SUGGEST_STATE_FILE, _PROMOTE_SUGGEST_IDLE_THRESHOLD_SEC):
        return
    from veles.core.skill_promotion import find_promote_candidates, write_promote_proposals

    with _logged_skip(project, "promote-suggest-skip", "skill promote-suggester failed"):
        candidates = find_promote_candidates(project)
        if candidates:
            write_promote_proposals(project, candidates)
        _stamp(project, _PROMOTE_SUGGEST_STATE_FILE)


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

    from veles.core.model_resolver import ConfigurationError
    from veles.core.provider_factory import has_api_key, make_provider

    try:
        routed_provider, routed_model = route("default", project)
    except ConfigurationError:
        return
    if not has_api_key(routed_provider):
        return
    with _logged_skip(project, "route-refresh-skip", "nl routing refresh failed"):
        extractor = make_nl_extractor(provider=make_provider(routed_provider), model=routed_model)
        refresh_nl_routing(project, agents_md, extractor=extractor)


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
    with _logged_skip(project, "insight-skip", "insight extraction failed"):
        extractor = make_insight_extractor(
            provider=make_provider(routed_provider, model=model),
            model=model,
            project=project,
        )
        extractor(history, session_id)


def _curate_one_session(
    store: SessionStore,
    session: SessionInfo,
    args: argparse.Namespace,
    project: Project,
) -> bool:
    # Imported at call time so a test's patch on the owning module applies.
    from veles.core.layout.engines import wiki_enabled
    from veles.runtime.registry import load_skills, make_tool_aware_provider, qualify_for_provider
    from veles.runtime.run import print_run_summary, run_agent_streaming_aware

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
    provider = make_tool_aware_provider(args.provider, project, skill_model=args.model)
    system_prompt = qualify_for_provider(system_prompt, provider, _CURATE_TOOLS)
    agent = Agent(
        provider=provider,
        registry=load_skills(project, _CURATE_TOOLS, provider=provider, model=args.model),
        model=args.model,
        max_iterations=args.max_iterations,
        system_prompt=system_prompt,
        verbose=args.verbose,
    )
    # The curator is a system task: it gets its own token budget (the caller's
    # --max-tokens-total guards the USER'S run — the ~24k-token curate prompt
    # re-counts every round and blew the 100k default mid-pass, live
    # 2026-07-08) and runs silently (emit_output=False; its raw result text,
    # e.g. "<budget exhausted: …>", used to print straight into the chat).
    curate_args = argparse.Namespace(**vars(args))
    curate_args.max_tokens_total = _CURATE_TOKEN_BUDGET
    result, budget = run_agent_streaming_aware(
        agent,
        f"Curate session {session.id}.",
        curate_args,
        project=project,
        emit_output=False,
    )
    if args.verbose:
        print_run_summary(curate_args, result, budget)
    if result.stopped_reason == "completed":
        return True
    # Live 2026-07-08 (ollama qwen3.5:9b): a thinking model does all the
    # persist work and then ends the run with empty final content, or a
    # budget/iteration stop lands AFTER the page was written. Judging success
    # by non-empty final prose re-curated the same session after every turn,
    # duplicating wiki pages forever — the real criterion is "did the
    # distillation persist", i.e. did a persist tool actually run.
    return bool({"wiki_write_page", "memory_save_insight"} & result.invoked_tools)


def _maybe_refresh_self_doc(project: Project) -> None:
    """Refresh wiki/self-doc/overview.md at most once per `_SELF_DOC_IDLE_SEC`.

    Silent: a failure is swallowed so a broken sub-component never surfaces to
    the user during `veles run`.
    """
    if _ran_recently(project, _SELF_DOC_STATE_FILE, _SELF_DOC_IDLE_SEC):
        return
    with contextlib.suppress(Exception):
        from veles.core.self_doc import refresh_self_doc

        refresh_self_doc(project)
        _stamp(project, _SELF_DOC_STATE_FILE)
