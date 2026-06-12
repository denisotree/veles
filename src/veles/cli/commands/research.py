"""`veles research "<question>"` — M147 deep-research command.

Plan → parallel explore → synthesize over the core orchestrator
(`core/orchestration/research.py`). Explorers run on a restricted
read+network+wiki-read registry (no `write_file`/`run_shell`); since the user
explicitly opted into web research by running this command, trust is
pre-authorised for the run (parallel explorers would otherwise interleave
trust-ladder prompts, and a non-TTY run would refuse the network tools
outright). The restricted registry means only the network class is ever
auto-allowed — no write/exec capability reaches the workers.

The `VELES_TRUST_AUTO_ALLOW` flip is process-global, so this command is
CLI-one-shot only — not safe to call concurrently (e.g. from the daemon)
without scoping the override differently.
"""

from __future__ import annotations

import argparse
import os
import sys

from veles.core.agent import Agent
from veles.core.project import Project


def cmd_research(args: argparse.Namespace, project: Project) -> int:
    from veles.cli import (
        _PROVIDER_API_KEY_ENVS,
        _budget_scope,
        _build_compressor,
        _ensure_api_key,
        _make_provider,
        build_run_system_prompt,
    )
    from veles.core.orchestration.research import (
        RESEARCH_EXPLORER_TOOLS,
        make_llm_planner,
        run_deep_research,
    )
    from veles.core.tools import registry as builtin_registry

    question = (getattr(args, "question", "") or "").strip()
    if not question:
        sys.stderr.write("error: a research question is required\n")
        return 2

    if args.provider in _PROVIDER_API_KEY_ENVS and not _ensure_api_key(args.provider):
        return 2

    provider = _make_provider(args.provider)
    base_system = build_run_system_prompt(
        project, prompt=question, include_agents_md=True, include_index=True
    )
    # Read + network + wiki-read only, built straight off the builtin singleton
    # (no project skills — explorers gather, they don't run skill sub-agents).
    # M163: wiki-engine tools drop out when the layout doesn't enable them.
    from veles.core.layout.engines import wiki_enabled
    from veles.core.tools.toolsets import TOOLSETS

    explorer_tools = list(RESEARCH_EXPLORER_TOOLS)
    if not wiki_enabled(project):
        gated = set(TOOLSETS.get("engine-wiki", ()))
        explorer_tools = [t for t in explorer_tools if t not in gated]
    research_registry = builtin_registry.subset(explorer_tools)
    # Each explorer fans out web_search/fetch_url calls; without a compressor a
    # multi-fetch explorer can overflow the model context. Same compressor the
    # single-agent / manager run paths use.
    compressor = _build_compressor(args, project, provider)

    def factory(**kwargs):  # noqa: ANN003
        worker_system = kwargs.get("system_prompt") or ""
        full_system = (
            f"{base_system}\n\n---\n\n{worker_system}"
            if base_system and worker_system
            else (worker_system or base_system)
        )
        return Agent(
            provider=provider,
            registry=research_registry,
            model=args.model,
            max_iterations=args.max_iterations,
            system_prompt=full_system,
            verbose=args.verbose,
            compressor=compressor,
        )

    planner = make_llm_planner(provider, args.model, max_subquestions=args.max_subquestions)

    sys.stderr.write(f"researching: {question}\n")
    # The user opted into web research; pre-authorise trust for the run so the
    # parallel explorers don't interleave prompts (or get refused in a non-TTY).
    prev = os.environ.get("VELES_TRUST_AUTO_ALLOW")
    os.environ["VELES_TRUST_AUTO_ALLOW"] = "1"
    try:
        # `--max-tokens-total` cap shared across the planner, every explorer,
        # and the writer. `spawn_parallel` propagates this budget ContextVar
        # into the worker threads (M148 follow-up), so the cap is cumulative.
        with _budget_scope(args, project=project):
            result = run_deep_research(
                question,
                agent_factory=factory,
                planner=planner,
                max_subquestions=args.max_subquestions,
            )
    finally:
        if prev is None:
            os.environ.pop("VELES_TRUST_AUTO_ALLOW", None)
        else:
            os.environ["VELES_TRUST_AUTO_ALLOW"] = prev

    if result.error or not result.final_text:
        sys.stderr.write(f"error: research failed: {result.error or 'no output'}\n")
        return 1
    sys.stdout.write(result.final_text)
    if not result.final_text.endswith("\n"):
        sys.stdout.write("\n")
    return 0
