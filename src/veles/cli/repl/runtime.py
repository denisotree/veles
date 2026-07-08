"""Provider/model resolution + per-turn Agent factory for the inline REPL.

`_build_runtime` gates the API key, resolves the effective provider/model,
loads the skill registries, and returns the `(state, factory, store,
subagent_factory)` tuple the REPL loop drives. The per-turn `factory`
rebuilds the system prompt each turn via `turn._repl_turn_system_prompt`
(one-directional import — `turn` is a lower leaf).
"""

from __future__ import annotations

import argparse
import sys

from veles.cli.repl.turn import _repl_turn_system_prompt
from veles.core.project import Project


def _build_runtime(args: argparse.Namespace, project: Project):
    """Resolve provider/model, gate the API key, and build the per-turn Agent
    factory + AppState + store for the interactive REPL.

    Returns ``(state, factory, store)`` or ``None`` when the key gate fails.
    """
    from veles.cli import (
        _PLANNING_TOOLS,
        _PROVIDER_API_KEY_ENVS,
        _RUN_TOOLS,
        _build_compressor,
        _ensure_api_key,
        _load_skills,
        _make_provider,
        _touch_active_project,
        _warn_if_agents_md_invalid,
    )
    from veles.core.agent import Agent
    from veles.core.memory import SessionStore
    from veles.core.model_resolver import (
        ConfigurationError,
        ensure_model_configured,
        resolve_effective_model,
        resolve_effective_provider,
    )
    from veles.core.model_windows import default_hard_ceiling_for
    from veles.core.modes import get_mode
    from veles.core.session_state import AppState

    args.provider = resolve_effective_provider(args, project)
    try:
        args.model = ensure_model_configured(resolve_effective_model(args, project))
    except ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None
    if args.provider in _PROVIDER_API_KEY_ENVS and not _ensure_api_key(args.provider):
        return None
    _touch_active_project(project)
    _warn_if_agents_md_invalid(project)

    # Pass the resolved model so local providers auto-detect native tool-call
    # support (provider_factory._apply_local_tool_policy probes ollama's
    # /api/show). Without it the REPL forced supports_tools=False and pushed
    # every local model through the fragile fenced-tools path (live
    # 2026-07-08) while `veles run`/curator already used native calls. NOTE:
    # detection is bound to the STARTUP model — an in-session /model switch
    # keeps the provider instance (pre-existing behaviour).
    provider = _make_provider(args.provider, model=args.model)
    compressor = _build_compressor(args, project, provider)
    registries = {
        "writing": _load_skills(project, _RUN_TOOLS, provider=provider, model=args.model),
        "planning": _load_skills(project, _PLANNING_TOOLS, provider=provider, model=args.model),
    }
    store = SessionStore(project.memory_db_path)

    def factory(state, *, mode_override=None, extra_system=None, query=None):
        active = mode_override or state.mode
        mode = get_mode(active)
        is_planning = active == "planning"
        registry_key = "planning" if is_planning else "writing"
        # M186: rebuild the system prompt EVERY turn (not only when the session
        # is fresh), so the *current* mode's block reaches the model. Agent's
        # `_bootstrap_history` refreshes history[0] with a passed system prompt
        # on resume. Without this, the strict PLANNING block baked on a first
        # planning turn stays frozen for the whole session and the model keeps
        # insisting it can't execute even after the turn routed to writing.
        # M191: `query` (the raw user prompt, passed by the mode) drives the
        # per-turn `<memory-context>` recall — empty before M191, so the REPL
        # never recalled project memory.
        system_prompt = _repl_turn_system_prompt(
            args, project, mode=mode, query=query, extra_system=extra_system
        )
        return Agent(
            provider=provider,
            registry=registries[registry_key],
            model=state.model,
            max_iterations=args.max_iterations,
            system_prompt=system_prompt,
            verbose=getattr(args, "verbose", False),
            store=store,
            session_id=state.session_id,
            compressor=compressor,
            hard_ceiling_tokens=default_hard_ceiling_for(state.model),
            plan_mode=is_planning,
        )

    def subagent_factory(*, system_prompt, tools):
        """Build an ephemeral, context-isolated worker for the `delegate` tool.
        Same provider/model as the root; a NARROW registry (scoped from the FULL
        global registry so wiki_* etc. are reachable); no SessionStore (workers
        are disposable)."""
        from veles.core.tools.registry import registry as _global_registry

        return Agent(
            provider=provider,
            registry=_global_registry.subset(tools),
            model=args.model,
            max_iterations=min(args.max_iterations, 200),  # generous: a batch worker isn't 20 calls
            system_prompt=system_prompt,
            store=None,
            compressor=compressor,
            hard_ceiling_tokens=default_hard_ceiling_for(args.model),
        )

    from veles.core.user_config import load_user_config

    # -c / --continue: resume this project's most recent NON-EMPTY session (one
    # with at least one turn — skip empty sessions from an aborted launch). An
    # explicit --resume ID wins. Nothing to resume → start fresh.
    resume_id = getattr(args, "resume", None)
    if resume_id is None and getattr(args, "continue_last", False):
        recent = [s for s in store.list_sessions(limit=50) if s.turn_count > 0]
        if recent:
            latest = recent[0]  # list_sessions is ordered by last_activity DESC
            resume_id = latest.id
            print(f"continuing session {resume_id[:8]} ({latest.title or 'untitled'})")
        else:
            print("no previous session with content in this project — starting fresh")

    user_cfg = load_user_config()
    state = AppState(
        session_id=resume_id,
        provider_name=args.provider,
        model=args.model,
        theme_name=(user_cfg.tui_theme if user_cfg and user_cfg.tui_theme else "everforest"),
    )
    return state, factory, store, subagent_factory
