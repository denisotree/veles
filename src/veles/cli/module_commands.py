"""`veles <verb>` for verbs that modules add (`cli_command` contributions).

Verbs are fixed when argv is parsed, before a project and its modules are known.
So when the first positional of argv is not a builtin verb, `prepare` resolves the
project, loads its modules once, and adds their verbs to the parser; the command
then runs inside that project with that same registry. A verb that no loaded
module adds but an uninstalled registry extension provides gets an install hint
instead of argparse's "invalid choice".
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from veles.core.contributions import CliCommand
from veles.core.modules import ModuleRegistry
from veles.core.project import Project


@dataclass(frozen=True, slots=True)
class ModuleVerbs:
    registry: ModuleRegistry
    commands: dict[str, CliCommand]


def prepare(
    parser: argparse.ArgumentParser, argv: list[str], builtin: set[str]
) -> ModuleVerbs | None:
    """Add the project's module verbs to `parser` when argv asks for a non-builtin
    verb; None when it doesn't (or there is no project to load modules from)."""
    verb = _first_positional(parser, argv)
    if verb is None or verb in builtin:
        return None
    project = _project_for(argv)
    if project is None:
        return None
    from veles.core.contributions import contributions
    from veles.core.module_loading import load_project_modules
    from veles.core.modules import reset_module_registry, set_module_registry

    registry = load_project_modules(project)
    token = set_module_registry(registry)
    try:
        found = contributions("cli_command")
    finally:
        reset_module_registry(token)
    commands: dict[str, CliCommand] = {}
    for c in found:
        if c.name in builtin:
            print(
                f"warning: module {c.module} can't add `veles {c.name}` — a builtin verb has it",
                file=sys.stderr,
            )
            continue
        assert isinstance(c.obj, CliCommand)
        commands.setdefault(c.name, c.obj)
    if verb not in commands:
        _exit_with_install_hint(verb, project)
    _add_parsers(parser, commands)
    return ModuleVerbs(registry, commands)


def runner(cmd: CliCommand) -> Callable[[argparse.Namespace, Project], int]:
    def run(args: argparse.Namespace, project: Project) -> int:
        return cmd.run(args, project, CliHost(args, project))

    return run


class CliHost:
    """`CommandHost` for the CLI: agents are built like `veles run` builds them."""

    def __init__(self, args: argparse.Namespace, project: Project) -> None:
        self._args = args
        self._project = project

    def run_agent(
        self,
        message: str | Callable[[], str],
        *,
        tools: tuple[str, ...],
        prompt_hint: str,
        fallback_prompt: str = "",
    ) -> int:
        from veles.cli._agent_builder import build_command_agent
        from veles.cli._console import ensure_api_key
        from veles.runtime.run import print_run_summary, run_agent_streaming_aware

        args, project = self._args, self._project
        if not ensure_api_key(args.provider):
            return 2
        agent = build_command_agent(
            args,
            project,
            tools=tools,
            system_prompt=lambda provider: module_system_prompt(
                project, provider, tools, prompt_hint, fallback_prompt
            ),
            check_api_key=False,
            tool_aware=True,
        )
        assert agent is not None  # the key was checked above
        text = message() if callable(message) else message
        result, budget = run_agent_streaming_aware(agent, text, args, project=project)
        print_run_summary(args, result, budget)
        return 0 if result.stopped_reason == "completed" else 1


def module_system_prompt(
    project: Project, provider, tools: tuple[str, ...], hint: str, fallback: str
) -> str:
    """The project's run system prompt for `hint` (so the layout's behaviour rides
    along), qualified for the provider's MCP tool namespace (claude-cli)."""
    from veles.runtime.prompt import build_run_system_prompt
    from veles.runtime.registry import qualify_for_provider

    base = build_run_system_prompt(project, prompt=hint) or fallback
    return qualify_for_provider(base, provider, tools)


def _add_parsers(parser: argparse.ArgumentParser, commands: dict[str, CliCommand]) -> None:
    from veles.cli._parsers._common import add_common_run_flags

    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    for name, cmd in commands.items():
        p = sub.add_parser(name, help=cmd.help)
        cmd.add_arguments(p)
        if cmd.run_flags:
            add_common_run_flags(p)


def _exit_with_install_hint(verb: str, project: Project) -> None:
    """An extension that isn't installed provides `verb` (per the cached
    catalogs), or the project itself is missing its layout/engine (e.g. an
    llm-wiki project after upgrading, before any `registry update`): say what to
    install. Otherwise argparse reports an ordinary unknown verb."""
    from veles.core.registry.catalog import providers_of
    from veles.core.registry.ensure import install_hint

    refs = providers_of(f"cli_command:{verb}")
    if refs:
        installs = " or ".join(f"`veles registry install {ref}`" for ref in refs)
        reason = f"comes from an extension that isn't installed — {installs}"
    else:
        hint = install_hint(project)
        if hint is None:
            return
        reason = f"is unknown, and this project's layout isn't fully installed — `{hint}`"
    print(f"veles: error: `veles {verb}` {reason}", file=sys.stderr)
    raise SystemExit(2)


def _first_positional(parser: argparse.ArgumentParser, argv: list[str]) -> str | None:
    takes_value = {
        opt
        for a in parser._actions
        if a.option_strings and a.nargs != 0
        for opt in a.option_strings
    }
    skip = False
    for token in argv:
        if skip:
            skip = False
        elif token == "--":
            return None
        elif token.startswith("-"):
            skip = token in takes_value
        else:
            return token
    return None


def _project_for(argv: list[str]) -> Project | None:
    from veles.core.project import ProjectNotFound, find_project_root, load_project

    root: Path | None = None
    for i, token in enumerate(argv):
        if token == "--project-root" and i + 1 < len(argv):
            root = Path(argv[i + 1]).resolve()
        elif token.startswith("--project-root="):
            root = Path(token.split("=", 1)[1]).resolve()
    if root is None:
        root = find_project_root()
    if root is None:
        return None
    try:
        return load_project(root)
    except ProjectNotFound:
        return None
