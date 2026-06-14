"""Shared agent-construction spine for agent-driven CLI verbs (M152).

`cmd_run` and `_run_ingest_cli` (and any future agent verb) repeat the
same construction sequence: ensure the provider API key → make the
provider → resolve the system prompt → optionally build a history
compressor → load project skills into a tool registry → construct the
`Agent`. `build_command_agent` is that sequence, parametrised by the
points where the two commands actually differ (toolset, provider
bridging, compressor presence, prompt source, session persistence).

Monkeypatch contract: every helper is resolved lazily off the
`veles.cli` package (`cli._make_provider`, `cli._load_skills`, ...) so
`monkeypatch.setattr("veles.cli._<helper>", fake)` keeps winning at
call time — same contract the extracted command bodies follow (see the
note in `cli/_runtime.py`).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

from veles.core.agent import Agent
from veles.core.memory import SessionStore
from veles.core.project import Project
from veles.core.provider import Provider
from veles.core.tools.registry import Registry


def build_command_agent(
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

    Returns ``None`` (after `_ensure_api_key` printed its error) when
    ``check_api_key`` is set and no key is reachable for ``args.provider``
    — callers translate that to exit code 2. Commands that already gate
    the key earlier in their flow (e.g. `cmd_run` checks before the
    manager path / idle curator) pass ``check_api_key=False``.

    - ``tool_aware``: build the provider via `_make_tool_aware_provider`
      (MCP-bridged for cli-delegates) instead of `_make_provider`.
    - ``system_prompt``: a ready string, or a callable taking the built
      provider (for prompts that need provider-specific tool
      qualification, e.g. ingest's `_qualify_for_provider`).
    - ``with_compressor``: build the routed history compressor
      (`_build_compressor`); off for short single-task runs like ingest.
    - ``registry``: pre-built tool registry; default loads project
      skills on top of ``tools`` via `_load_skills`.
    """
    # Lazy package import so `monkeypatch.setattr("veles.cli._<helper>", ...)`
    # is picked up at call time, not at module-import time.
    import veles.cli as cli

    if (
        check_api_key
        and args.provider in cli._PROVIDER_API_KEY_ENVS
        and not cli._ensure_api_key(args.provider)
    ):
        return None

    if tool_aware:
        provider = cli._make_tool_aware_provider(args.provider, project, skill_model=args.model)
    else:
        provider = cli._make_provider(args.provider, args.model)

    if callable(system_prompt):
        system_prompt = system_prompt(provider)

    compressor = cli._build_compressor(args, project, provider) if with_compressor else None

    if registry is None:
        registry = cli._load_skills(project, tools, provider=provider, model=args.model)

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
