"""Veles CLI — `init`, `run`, `add`, `sessions {…}`.

All commands except `init` require an active Veles project: a directory whose
`.veles/project.toml` is reachable by walking up from cwd. Override the lookup
with `--project-root <path>`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from veles.cli._agent_builder import build_command_agent

# Per-verb command modules (M46). Re-exported under their old private
# names for backward compatibility with tests that monkey-patch
# `veles.cli._cmd_*`. Each cmd_* function lives in its own module under
# `veles.cli.commands.*` so adding new verbs in Tier-gamma (M47 wizard,
# M48 TUI, M51 daemon, M52 channels) doesn't bloat this file.
from veles.cli._curator import (
    _CURATE_CHARS_LIMIT,
    _CURATE_QUIET_WINDOW_SEC,
    _CURATE_TOOLS,
    _CURATE_TURN_LIMIT,
    _CURATOR_IDLE_LIMIT,
    _CURATOR_IDLE_THRESHOLD_SEC,
    _CURATOR_POSTRUN_LIMIT,
    _PROPOSER_IDLE_THRESHOLD_SEC,
    _SELF_DOC_IDLE_SEC,
    _continuous_curator_eligible,
    _curate_one_session,
    _CuratorPassResult,
    _maybe_refresh_nl_routing,
    _maybe_refresh_self_doc,
    _maybe_run_idle_curator,
    _maybe_run_insight_extractor,
    _maybe_run_post_turn_curator,
    _maybe_run_subproject_proposer,
    _maybe_suggest_promotions,
    _run_curator_pass,
    _truncate_session_messages,
)
from veles.cli._parsers import build_parser as _build_parser
from veles.cli._parsers._common import (
    DEFAULT_COMPRESS_THRESHOLD_TOKENS,
    DEFAULT_COMPRESSOR_MODEL,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_TOKENS_TOTAL,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
)
from veles.cli._parsers._common import (
    PROVIDER_CHOICES as _PROVIDER_CHOICES,
)
from veles.cli._project import (
    _load_project_modules,
    _register_project,
    _resolve_active_project,
    _touch_active_project,
    _warn_if_agents_md_invalid,
)
from veles.cli._runtime import (
    _INDEX_INJECTION_CAP,
    _INGEST_TOOLS,
    _PLANNING_TOOLS,
    _RECALL_BLOCK_CHARS_CAP,
    _RECALL_LIMIT,
    _RUN_TOOLS,
    _budget_scope,
    _build_compressor,
    _build_run_system_prompt,
    _load_index_md,
    _load_skills,
    _make_tool_aware_provider,
    _maybe_apply_project_slash_prefix,
    _print_run_summary,
    _proposals_block,
    _qualify_for_provider,
    _recall_block,
    _run_agent_streaming_aware,
    build_compressor,
    build_run_system_prompt,
)
from veles.cli.commands.add import cmd_add as _cmd_add
from veles.cli.commands.autopilot import cmd_autopilot as _cmd_autopilot
from veles.cli.commands.browse import cmd_browse as _cmd_browse
from veles.cli.commands.channel import cmd_channel as _cmd_channel
from veles.cli.commands.curate import cmd_curate as _cmd_curate
from veles.cli.commands.daemon import cmd_daemon as _cmd_daemon
from veles.cli.commands.doctor import cmd_doctor as _cmd_doctor
from veles.cli.commands.dream import cmd_dream as _cmd_dream
from veles.cli.commands.goal import cmd_goal as _cmd_goal
from veles.cli.commands.init import cmd_init as _cmd_init
from veles.cli.commands.job import cmd_job as _cmd_job
from veles.cli.commands.layout import cmd_layout as _cmd_layout
from veles.cli.commands.mcp import cmd_mcp as _cmd_mcp
from veles.cli.commands.models import cmd_models as _cmd_models
from veles.cli.commands.modules import cmd_module as _cmd_module
from veles.cli.commands.organize import cmd_organize as _cmd_organize
from veles.cli.commands.portability import cmd_export as _cmd_export
from veles.cli.commands.portability import cmd_import as _cmd_import
from veles.cli.commands.projects import cmd_project as _cmd_project
from veles.cli.commands.repl import cmd_repl as _cmd_repl
from veles.cli.commands.research import cmd_research as _cmd_research
from veles.cli.commands.route import cmd_route as _cmd_route
from veles.cli.commands.run import cmd_run as _cmd_run
from veles.cli.commands.schema import cmd_schema_dispatch as _cmd_schema_dispatch
from veles.cli.commands.secrets import cmd_secret as _cmd_secret
from veles.cli.commands.self_doc import cmd_self_doc as _cmd_self_doc
from veles.cli.commands.sessions import cmd_sessions as _cmd_sessions
from veles.cli.commands.skills import cmd_skill as _cmd_skill
from veles.cli.commands.subprojects import cmd_subproject as _cmd_subproject
from veles.cli.commands.tool import cmd_tool as _cmd_tool
from veles.cli.commands.trust import cmd_trust as _cmd_trust
from veles.cli.commands.tui import cmd_tui as _cmd_tui
from veles.core.context import (
    reset_active_project,
    set_active_project,
)
from veles.core.curator import (
    _CURATE_DEFAULT_LIMIT,
    _render_message,
)
from veles.core.modules import (
    reset_module_registry,
    set_module_registry,
)
from veles.core.provider_factory import PROVIDER_API_KEY_ENVS as _PROVIDER_API_KEY_ENVS
from veles.core.provider_factory import has_api_key as _has_api_key_for_provider
from veles.core.provider_factory import make_provider as _make_provider

# Parser defaults + helpers live in veles.cli._parsers._common (M77). Re-imported
# above under their historical names so tests that monkey-patch or import
# `veles.cli._add_common_run_flags` etc. keep working.


# Backward-compat surface: every name extracted to a sibling module is
# re-exported here under its original `_<name>`. `__all__` suppresses the
# F401 "imported but unused" lint and documents the public-ish surface
# that tests + downstream code rely on (e.g. `monkeypatch.setattr(
# "veles.cli._run_agent_streaming_aware", ...)`).
__all__ = [
    "DEFAULT_COMPRESSOR_MODEL",
    # locally-defined utilities / parser entry points
    "DEFAULT_COMPRESS_THRESHOLD_TOKENS",
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_MAX_TOKENS_TOTAL",
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    # curator helpers + constants
    "_CURATE_CHARS_LIMIT",
    "_CURATE_DEFAULT_LIMIT",
    "_CURATE_QUIET_WINDOW_SEC",
    "_CURATE_TOOLS",
    "_CURATE_TURN_LIMIT",
    "_CURATOR_IDLE_LIMIT",
    "_CURATOR_IDLE_THRESHOLD_SEC",
    "_CURATOR_POSTRUN_LIMIT",
    # run-loop helpers + constants
    "_INDEX_INJECTION_CAP",
    "_INGEST_TOOLS",
    "_PLANNING_TOOLS",
    "_PROPOSER_IDLE_THRESHOLD_SEC",
    # provider factory aliases (live in core.provider_factory)
    "_PROVIDER_API_KEY_ENVS",
    "_PROVIDER_CHOICES",
    "_RECALL_BLOCK_CHARS_CAP",
    "_RECALL_LIMIT",
    "_RUN_TOOLS",
    "_SELF_DOC_IDLE_SEC",
    "_CuratorPassResult",
    "_budget_scope",
    "_build_compressor",
    "_build_parser",
    "_build_run_system_prompt",
    "_cmd_add",
    # verb dispatchers
    "_cmd_autopilot",
    "_cmd_browse",
    "_cmd_channel",
    "_cmd_curate",
    "_cmd_daemon",
    "_cmd_doctor",
    "_cmd_dream",
    "_cmd_export",
    "_cmd_goal",
    "_cmd_import",
    "_cmd_init",
    "_cmd_job",
    "_cmd_layout",
    "_cmd_mcp",
    "_cmd_models",
    "_cmd_module",
    "_cmd_organize",
    "_cmd_project",
    "_cmd_repl",
    "_cmd_research",
    "_cmd_route",
    "_cmd_run",
    "_cmd_schema_dispatch",
    "_cmd_secret",
    "_cmd_self_doc",
    "_cmd_sessions",
    "_cmd_skill",
    "_cmd_subproject",
    "_cmd_trust",
    "_cmd_tui",
    "_confirm",
    "_continuous_curator_eligible",
    "_curate_one_session",
    "_ensure_api_key",
    "_has_api_key_for_provider",
    "_load_index_md",
    # project lifecycle helpers
    "_load_project_modules",
    "_load_skills",
    "_make_provider",
    "_make_tool_aware_provider",
    "_maybe_apply_project_slash_prefix",
    "_maybe_refresh_nl_routing",
    "_maybe_refresh_self_doc",
    "_maybe_run_idle_curator",
    "_maybe_run_insight_extractor",
    "_maybe_run_post_turn_curator",
    "_maybe_run_subproject_proposer",
    "_maybe_suggest_promotions",
    "_print_run_summary",
    "_proposals_block",
    "_qualify_for_provider",
    "_recall_block",
    "_register_project",
    "_render_message",
    "_resolve_active_project",
    "_run_agent_streaming_aware",
    "_run_curator_pass",
    "_touch_active_project",
    "_truncate_session_messages",
    "_warn_if_agents_md_invalid",
    "build_command_agent",
    "build_compressor",
    "build_run_system_prompt",
    "main",
]


# ---------- entry ----------


def main(argv: list[str] | None = None) -> int:
    from veles.cli.wizard import maybe_run_first_run_wizard
    from veles.core.i18n import set_active_locale
    from veles.core.user_config import load_user_config

    _argv = list(sys.argv[1:]) if argv is None else list(argv)
    if not _argv:
        # M186: bare `veles` opens the inline streaming REPL (native terminal
        # scroll/selection/copy). The full-screen Textual `veles tui` stays
        # available explicitly.
        _argv = ["repl"]
    args = _build_parser().parse_args(_argv)
    # Resolve the active i18n locale before any user-facing string fires.
    # `set_active_locale` honours `VELES_LOCALE` env over the config so a
    # one-shot invocation can force a language without rewriting toml.
    cfg = load_user_config()
    set_active_locale(cfg.language if cfg and cfg.language else "en")
    maybe_run_first_run_wizard(args)
    if args.command == "init":
        return _cmd_init(args)
    if args.command == "project":
        return _cmd_project(args)
    if args.command == "schema":
        return _cmd_schema_dispatch(args)
    if args.command == "self-doc":
        return _cmd_self_doc(args, _resolve_active_project(args))
    if args.command == "import":
        return _cmd_import(args)
    if args.command == "daemon":
        return _cmd_daemon(args)
    if args.command == "channel":
        return _cmd_channel(args)
    if args.command == "autopilot":
        return _cmd_autopilot(args)
    if args.command == "doctor":
        # Doctor runs with or without an active project — None is a valid input.
        return _cmd_doctor(args, _resolve_active_project(args))
    if args.command == "browse":
        return _cmd_browse(args)
    if args.command == "secret":
        return _cmd_secret(args)
    if args.command == "trust":
        # Trust verbs accept (project | None); resolve permissively.
        return _cmd_trust(args, _resolve_active_project(args))
    if args.command == "models":
        # `models` is user-global (cache + curated lists), no project needed.
        return _cmd_models(args)

    project = _resolve_active_project(args)
    if project is None:
        from veles.cli.project_wizard import maybe_run_project_wizard

        project = maybe_run_project_wizard(args, Path.cwd())
    if project is None:
        # If the wizard ran and the user consciously declined to init a
        # project here, exit cleanly — the user already knows what they
        # did, so showing the generic "no project" error is noise.
        if getattr(args, "_wizard_user_chose_no_project", False):
            print(
                "<no project initialised; nothing to do.>",
                file=sys.stderr,
            )
            return 0
        print(
            f"error: no Veles project found at {Path.cwd()} or any parent.\n"
            "       Run `veles init` to create one in the current directory.",
            file=sys.stderr,
        )
        return 2

    token = set_active_project(project)
    mod_token = set_module_registry(_load_project_modules(project))
    try:
        if args.command == "run":
            return _cmd_run(args, project)
        if args.command == "research":
            return _cmd_research(args, project)
        if args.command == "add":
            return _cmd_add(args, project)
        if args.command == "organize":
            return _cmd_organize(args, project)
        if args.command == "layout":
            return _cmd_layout(args, project)
        if args.command == "curate":
            return _cmd_curate(args, project)
        if args.command == "skill":
            return _cmd_skill(args, project)
        if args.command == "module":
            return _cmd_module(args, project)
        if args.command == "sessions":
            return _cmd_sessions(args, project)
        if args.command == "subproject":
            return _cmd_subproject(args, project)
        if args.command == "tool":
            return _cmd_tool(args, project)
        if args.command == "mcp":
            return _cmd_mcp(args, project)
        if args.command == "goal":
            return _cmd_goal(args, project)
        if args.command == "job":
            return _cmd_job(args, project)
        if args.command == "dream":
            return _cmd_dream(args, project)
        if args.command == "tui":
            return _cmd_tui(args, project)
        if args.command == "repl":
            return _cmd_repl(args, project)
        if args.command == "route":
            return _cmd_route(args, project)
        if args.command == "export":
            return _cmd_export(args, project)
    finally:
        reset_module_registry(mod_token)
        reset_active_project(token)
    return 2


# ---------- init ----------


# agent-loop verb bodies — live under cli/commands/{init,run,add,curate}.py


# curator helpers — bodies live in cli/_curator.py


def _confirm(prompt: str) -> bool:
    try:
        answer = input(prompt + " ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


# ---------- helpers ----------


def _ensure_api_key(provider: str = "openrouter", *, project: str | None = None) -> bool:
    """Check that a key is reachable for the chosen direct provider.

    Consults the same cascade as `core.provider_factory.has_api_key`:
    keychain (project scope) → keychain (default scope) → legacy keychain
    entries → env vars. A user who configured the key via the TUI wizard
    (M92/M100) keeps it in the OS keychain — env-only check would miss it.
    """
    envs = _PROVIDER_API_KEY_ENVS.get(provider)
    if envs is None:
        return True
    if _has_api_key_for_provider(provider, project=project):
        return True
    label = " (or ".join(envs) + ")" if len(envs) > 1 else envs[0]
    print(
        f"error: no API key for --provider {provider} "
        f"(set {label} or store via `veles secret set {provider}`)",
        file=sys.stderr,
    )
    return False


# run-loop helpers — bodies live in cli/_runtime.py
