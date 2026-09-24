"""Shared agent-construction spine for agent-driven CLI verbs (M152).

`cmd_run` and `_run_ingest_cli` (and any future agent verb) repeat the
same construction sequence: ensure the provider API key → make the
provider → resolve the system prompt → optionally build a history
compressor → load project skills into a tool registry → construct the
`Agent`. `build_command_agent` is that sequence, parametrised by the
points where the two commands actually differ (toolset, provider
bridging, compressor presence, prompt source, session persistence).

Monkeypatch contract: every helper is looked up on its owning module at call
time (`veles.runtime.registry`, `veles.runtime.run`,
`veles.core.provider_factory`, `veles.cli._console`), so tests patch it there.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

from veles.core.agent import Agent
from veles.core.memory import SessionStore
from veles.core.project import Project
from veles.core.provider import Provider
from veles.core.tools.registry import Registry


def build_command_agent(  # noqa: PLR0913
    args: argparse.Namespace,
    project: Project,
    *,
    tools: tuple[str, ...],
    system_prompt: str | None | Callable[[Provider], str | None] = None,
    check_api_key: bool = True,
    tool_aware: bool = False,
    with_compressor: bool = False,
    store: SessionStore | None = None,
    session_id: str | None = None,
    plan_mode: bool = False,
    registry: Registry | None = None,
) -> Agent | None:
    """Build the Agent every agent-driven CLI verb constructs by hand.

    Returns ``None`` (after `ensure_api_key` printed its error) when
    ``check_api_key`` is set and no key is reachable for ``args.provider``
    — callers translate that to exit code 2. Commands that already gate
    the key earlier in their flow (e.g. `cmd_run` checks before the
    manager path / idle curator) pass ``check_api_key=False``.

    - ``tool_aware``: build the provider via `make_tool_aware_provider`
      (MCP-bridged for cli-delegates) instead of `make_provider`.
    - ``system_prompt``: a ready string, or a callable taking the built
      provider (for prompts that need provider-specific tool
      qualification, e.g. ingest's `qualify_for_provider`).
    - ``with_compressor``: build the routed history compressor
      (`compressor_from_args`); off for short single-task runs like ingest.
    - ``registry``: pre-built tool registry; default loads project
      skills on top of ``tools`` via `load_skills`.
    """
    # Helpers are looked up on their owning modules at call time, so a test's
    # `monkeypatch.setattr` on that module is picked up.
    from veles.cli import _console
    from veles.core import provider_factory
    from veles.runtime import registry as run_registry
    from veles.runtime import run

    if check_api_key and not _console.ensure_api_key(args.provider):
        return None

    if tool_aware:
        provider = run_registry.make_tool_aware_provider(
            args.provider, project, skill_model=args.model
        )
    else:
        provider = provider_factory.make_provider(args.provider, args.model)

    if callable(system_prompt):
        system_prompt = system_prompt(provider)

    compressor = run.compressor_from_args(args, project, provider) if with_compressor else None

    if registry is None:
        registry = run_registry.load_skills(project, tools, provider=provider, model=args.model)

    return Agent(
        provider=provider,
        registry=registry,
        model=args.model,
        max_iterations=args.max_iterations,
        system_prompt=system_prompt,
        verbose=args.verbose,
        store=store,
        session_id=session_id,
        compressor=compressor,
        plan_mode=plan_mode,
    )


def make_worker_factory(
    args: argparse.Namespace,
    *,
    provider: Provider,
    registry: Registry,
    base_system: str | None,
    compressor: Callable | None,
) -> Callable[..., Agent]:
    """A `factory(system_prompt=…)` for orchestration workers (manager spawn,
    research explorers): each worker gets the base system prompt with its
    role prompt appended, so it keeps the project context."""

    def factory(**kwargs: object) -> Agent:
        worker_system = str(kwargs.get("system_prompt") or "")
        full_system = (
            f"{base_system}\n\n---\n\n{worker_system}"
            if base_system and worker_system
            else (worker_system or base_system or "")
        )
        return Agent(
            provider=provider,
            registry=registry,
            model=args.model,
            max_iterations=args.max_iterations,
            system_prompt=full_system,
            verbose=args.verbose,
            compressor=compressor,
        )

    return factory
