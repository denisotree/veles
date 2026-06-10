"""New Veles TUI - Textual-based REPL with collapsible inspector.

The legacy prompt_toolkit + rich REPL was retired in milestone M64
(see MILESTONES.md). `veles tui` always boots this module now.
"""

from __future__ import annotations

import argparse
import os

from veles.core.project import Project
from veles.core.project_config import get_section, load_project_config


def _register_tui_session(project: Project):
    """Register/refresh this interactive run as a `kind=tui` runtime session
    (M138) so the TUI shows up alongside daemon sessions in the runtime-session
    manager. Best-effort: a store failure must never block the REPL. Returns
    `(store, rid)` to mark stopped on exit, or None."""
    try:
        from veles.core.runtime_sessions import RuntimeSessionStore

        store = RuntimeSessionStore(project.memory_db_path)
        rec = store.get_by_name("tui", kind="tui")
        if rec is None:
            rec = store.create("tui", "tui")
        store.mark_started(rec.id, pid=os.getpid())
        return store, rec.id
    except Exception:  # noqa: BLE001 — runtime-session tracking is best-effort
        return None


def _load_project_default_provider(project: Project) -> str | None:
    """Return `[provider] default` from `<project>/.veles/config.toml`,
    or None if the file is absent / malformed / has no provider section.

    Thin wrapper kept for backward-compat — `core/model_resolver.py`
    consumes the same data through the cascade helper. Tests still
    import this name."""
    provider_section = get_section(load_project_config(project), "provider")
    raw = provider_section.get("default")
    return raw if isinstance(raw, str) and raw else None


def run_tui(args: argparse.Namespace, project: Project) -> int:
    """Boot the new Textual TUI for an interactive session.

    Returns the App's exit code. 0 on clean exit; 2 if a required API
    key is missing (mirrors the legacy `cmd_tui` contract so the CLI
    layer doesn't need to special-case the new path).
    """
    # Imports are deferred so `veles --help` (which imports this module
    # transitively) doesn't pay the Textual / provider SDK boot cost.
    from veles.cli import (
        _PLANNING_TOOLS,
        _PROVIDER_API_KEY_ENVS,
        _RUN_TOOLS,
        _build_compressor,
        _build_run_system_prompt,
        _ensure_api_key,
        _load_skills,
        _make_provider,
        _touch_active_project,
        _warn_if_agents_md_invalid,
    )
    from veles.core.agent import Agent
    from veles.core.memory import SessionStore
    from veles.core.model_resolver import (
        resolve_effective_model,
        resolve_effective_provider,
    )
    from veles.core.modes import get_mode
    from veles.core.tui_state import load_for_project
    from veles.tui.app import TuiApp
    from veles.tui.state import AppState

    # Provider + model both cascade through argparse → project config →
    # user wizard → built-in default. Without the cascade, picking OpenAI
    # in the wizard but launching `veles tui` (no --provider flag) would
    # still boot on argparse's "openrouter" default.
    args.provider = resolve_effective_provider(args, project)

    if args.provider in _PROVIDER_API_KEY_ENVS and not _ensure_api_key(args.provider):
        return 2
    _touch_active_project(project)
    _warn_if_agents_md_invalid(project)

    persisted = load_for_project(project)
    effective_model = resolve_effective_model(
        args, project, persisted_model=persisted.model
    )
    args.model = effective_model

    provider = _make_provider(args.provider)
    compressor = _build_compressor(args, project, provider)
    # Two registries built once at boot; the factory picks one per turn
    # depending on the active mode. Skills are baked into both so the
    # user's project-level tools are available in both modes.
    registries = {
        "writing": _load_skills(
            project, _RUN_TOOLS, provider=provider, model=args.model
        ),
        "planning": _load_skills(
            project, _PLANNING_TOOLS, provider=provider, model=args.model
        ),
    }
    store = SessionStore(project.memory_db_path)

    def factory(
        state: AppState,
        *,
        mode_override: str | None = None,
        extra_system: str | None = None,
    ) -> Agent:
        # `mode_override` lets a Mode pin a specific configuration
        # without flipping `state.mode` (AutoMode's sub-dispatch,
        # GoalMode's per-phase PLAN-vs-EXECUTE-vs-INTERVIEW). Default:
        # read `state.mode`.
        #
        # `extra_system` is a per-call addendum prepended below the
        # mode block — GoalMode uses this to inject phase-specific
        # instructions (interview prompt, execute step text, etc.)
        # without modifying the mode's class-level `system_block`.
        active = mode_override or state.mode
        mode = get_mode(active)
        is_planning = active == "planning"
        registry_key = "planning" if is_planning else "writing"

        # Fresh sessions get the mode block (+ optional extra) baked
        # into the constructor system prompt. Resumed sessions get the
        # mode block injected at runtime via the Mode's prompt wrapper,
        # but `extra_system` (which is per-turn) we always pass through
        # to ensure phase-specific guidance reaches the model.
        sys_chunks: list[str] = []
        if state.session_id is None:
            sys_chunks.append(_build_run_system_prompt(args, project))
            if mode.system_block.strip():
                sys_chunks.append(mode.system_block.strip())
        if extra_system and extra_system.strip():
            sys_chunks.append(extra_system.strip())
        system_prompt: str | None = (
            "\n\n".join(sys_chunks) if sys_chunks else None
        )

        return Agent(
            provider=provider,
            registry=registries[registry_key],
            model=state.model,
            max_iterations=args.max_iterations,
            system_prompt=system_prompt,
            verbose=args.verbose,
            store=store,
            session_id=state.session_id,
            compressor=compressor,
            plan_mode=is_planning,
        )

    state = AppState(
        session_id=getattr(args, "resume", None),
        provider_name=args.provider,
        model=effective_model,
        mode=persisted.mode,  # type: ignore[arg-type]
        active_goal_id=persisted.active_goal_id,
    )
    app = TuiApp(state=state, agent_factory=factory, project=project, store=store)
    # M138: record this run as a kind=tui runtime session for the duration of
    # the REPL; mark it stopped on exit (best-effort, never blocks).
    tui_session = _register_tui_session(project)
    # `mouse=False`: don't emit SGR mouse-mode escape sequences at boot.
    # Terminal stays out of mouse-reporting → native drag-select + system
    # ⌘C (macOS) / Shift+drag (Linux) work via the terminal itself.
    # Trade-off (continuation of M115.3): scroll wheel and click-to-focus
    # are gone — PageUp/PageDown/arrows/Tab are the canonical navigation.
    try:
        return app.run(mouse=False) or 0
    finally:
        if tui_session is not None:
            rt_store, rid = tui_session
            try:
                rt_store.mark_stopped(rid)
            finally:
                rt_store.close()


__all__ = ["run_tui"]
