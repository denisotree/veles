"""Shared ingest runner for `veles add` — read a source and write a wiki page
via agent. M85: kernel logic lives in `veles.core.ingest`; this file is a thin
CLI wrapper. (The `veles ingest` deprecated alias was removed in
M117c-removal; `cmd_add` is the only caller of `_run_ingest_cli`.)"""

from __future__ import annotations

import argparse
import sys

from veles.core.ingest import INGEST_SYSTEM_PROMPT, ingest_user_message
from veles.core.layout.engines import wiki_enabled
from veles.core.project import Project
from veles.core.wiki import Wiki


def _run_ingest_cli(
    args: argparse.Namespace, project: Project, *, source: str
) -> int:
    """Ingest runner used by `cmd_add` (read a source → write a wiki page)."""
    from veles.cli import (
        _INGEST_TOOLS,
        _PROVIDER_API_KEY_ENVS,
        _ensure_api_key,
        _print_run_summary,
        _qualify_for_provider,
        _run_agent_streaming_aware,
        _warn_if_agents_md_invalid,
        build_command_agent,
    )

    # M162: ingest is a wiki-engine operation — the active layout pack
    # must declare it ([layout.engines] wiki = true).
    if not wiki_enabled(project):
        print(
            f"error: `veles add` needs the wiki content engine, but the active "
            f"layout pack {project.layout_name!r} does not enable it.\n"
            "Switch the project to a wiki layout (edit `layout` in "
            ".veles/project.toml, e.g. to \"llm-wiki\") or store the source "
            "yourself and reference it from AGENTS.md.",
            file=sys.stderr,
        )
        return 2

    if args.provider in _PROVIDER_API_KEY_ENVS and not _ensure_api_key(args.provider):
        return 2
    _warn_if_agents_md_invalid(project)
    Wiki(project.wiki_root).ensure_layout()
    # M152: shared construction spine. The key was already gated above
    # (before the AGENTS.md warning / wiki-layout side effects), so the
    # factory must not re-check it. The system prompt needs the built
    # provider for MCP tool-name qualification, hence the callable.
    agent = build_command_agent(
        args,
        project,
        tools=_INGEST_TOOLS,
        system_prompt=lambda provider: _qualify_for_provider(
            INGEST_SYSTEM_PROMPT, provider, _INGEST_TOOLS
        ),
        check_api_key=False,
        tool_aware=True,
    )
    result, budget = _run_agent_streaming_aware(
        agent, ingest_user_message(source), args, project=project
    )
    _print_run_summary(args, result, budget)
    return 0 if result.stopped_reason == "completed" else 1
