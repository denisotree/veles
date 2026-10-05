"""Veles CLI entry point: parse argv and dispatch to one `cli/commands/<verb>.py`.

Most verbs need an active Veles project: a directory whose `.veles/project.toml`
is reachable by walking up from cwd (override with `--project-root <path>`).
Each command module is imported only when its verb runs, so `veles --help` and
a single verb do not pay for loading every other command.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Literal

__all__ = ["main"]

_ProjectNeed = Literal["none", "optional", "required"]

# verb → (module, function, project need). Module names are spelled out in
# full so a grep (and the unwired-code test) finds each command's entry point.
# "none" verbs take `(args)`; "optional" take `(args, project | None)`;
# "required" take `(args, project)` and run inside the project + module context.
# `None` is bare `veles`, the interactive REPL.
_COMMANDS: dict[str | None, tuple[str, str, _ProjectNeed]] = {
    "init": ("veles.cli.commands.init", "cmd_init", "none"),
    "project": ("veles.cli.commands.projects", "cmd_project", "none"),
    "schema": ("veles.cli.commands.schema", "cmd_schema_dispatch", "none"),
    "import": ("veles.cli.commands.portability", "cmd_import", "none"),
    "daemon": ("veles.cli.commands.daemon", "cmd_daemon", "none"),
    "channel": ("veles.cli.commands.channel", "cmd_channel", "none"),
    "autopilot": ("veles.cli.commands.autopilot", "cmd_autopilot", "none"),
    "registry": ("veles.cli.commands.registry", "cmd_registry", "optional"),
    "secret": ("veles.cli.commands.secrets", "cmd_secret", "none"),
    "models": ("veles.cli.commands.models", "cmd_models", "none"),
    "self-doc": ("veles.cli.commands.self_doc", "cmd_self_doc", "none"),
    "doctor": ("veles.cli.commands.doctor", "cmd_doctor", "optional"),
    "trust": ("veles.cli.commands.trust", "cmd_trust", "optional"),
    "run": ("veles.cli.commands.run", "cmd_run", "required"),
    "research": ("veles.cli.commands.research", "cmd_research", "required"),
    "organize": ("veles.cli.commands.organize", "cmd_organize", "required"),
    "layout": ("veles.cli.commands.layout", "cmd_layout", "required"),
    "curate": ("veles.cli.commands.curate", "cmd_curate", "required"),
    "skill": ("veles.cli.commands.skills", "cmd_skill", "required"),
    "module": ("veles.cli.commands.modules", "cmd_module", "required"),
    "sessions": ("veles.cli.commands.sessions", "cmd_sessions", "required"),
    "subproject": ("veles.cli.commands.subprojects", "cmd_subproject", "required"),
    "tool": ("veles.cli.commands.tool", "cmd_tool", "required"),
    "mcp": ("veles.cli.commands.mcp", "cmd_mcp", "required"),
    "goal": ("veles.cli.commands.goal", "cmd_goal", "required"),
    "job": ("veles.cli.commands.job", "cmd_job", "required"),
    "dream": ("veles.cli.commands.dream", "cmd_dream", "required"),
    "route": ("veles.cli.commands.route", "cmd_route", "required"),
    "export": ("veles.cli.commands.portability", "cmd_export", "required"),
    None: ("veles.cli.commands.repl", "cmd_repl", "required"),
}


def main(argv: list[str] | None = None) -> int:
    from veles.cli import module_commands
    from veles.cli._parsers import build_parser
    from veles.cli._project import _resolve_active_project
    from veles.cli.wizard import maybe_run_first_run_wizard
    from veles.core.i18n import set_active_locale
    from veles.core.user_config import load_user_config

    argv = list(sys.argv[1:]) if argv is None else list(argv)
    parser = build_parser()
    builtin = {verb for verb in _COMMANDS if verb is not None}
    module_verbs = module_commands.prepare(parser, argv, builtin)
    args = parser.parse_args(argv)
    # Resolve the i18n locale before any user-facing string fires.
    # `set_active_locale` honours `VELES_LOCALE` over the config.
    cfg = load_user_config()
    set_active_locale(cfg.language if cfg and cfg.language else "en")
    maybe_run_first_run_wizard(args)

    if module_verbs is not None and args.command in module_verbs.commands:
        command = module_commands.runner(module_verbs.commands[args.command])
        return _run_in_project(args, command, modules=module_verbs.registry)
    entry = _COMMANDS.get(args.command)
    if entry is None:
        return 2
    module_name, func_name, need = entry
    command = getattr(importlib.import_module(module_name), func_name)
    if need == "none":
        return command(args)
    if need == "optional":
        return command(args, _resolve_active_project(args))
    return _run_in_project(args, command)


def _run_in_project(args, command, modules=None) -> int:
    """Resolve (or bootstrap) the project, then run `command` inside its context.
    `modules`: the project's already-loaded module registry, if the caller has it."""
    from veles.cli._project import _load_project_modules, _resolve_active_project
    from veles.core.context import reset_active_project, set_active_project
    from veles.core.modules import reset_module_registry, set_module_registry

    project = _resolve_active_project(args)
    if project is None:
        from veles.cli.project_wizard import maybe_run_project_wizard

        project = maybe_run_project_wizard(args, Path.cwd())
    if project is None:
        # The wizard ran and the user declined to init a project here: they
        # know what they did, so the generic "no project" error is noise.
        if getattr(args, "_wizard_user_chose_no_project", False):
            print("<no project initialised; nothing to do.>", file=sys.stderr)
            return 0
        print(
            f"error: no Veles project found at {Path.cwd()} or any parent.\n"
            "       Run `veles init` to create one in the current directory.",
            file=sys.stderr,
        )
        return 2

    token = set_active_project(project)
    loaded = modules or _load_project_modules(project)
    mod_token = set_module_registry(loaded)
    from veles.core.registry.ensure import ensure_project_extensions

    # A missing layout or engine is offered for install when a session starts at a
    # terminal (REPL, `veles run`); every other verb just warns once and goes on.
    interactive = args.command in (None, "run") and sys.stdin.isatty()
    if ensure_project_extensions(project, interactive=interactive):
        # Only what was just installed loads — the live registry is already set.
        _load_project_modules(project, loaded)
    try:
        return command(args, project)
    finally:
        reset_module_registry(mod_token)
        reset_active_project(token)
