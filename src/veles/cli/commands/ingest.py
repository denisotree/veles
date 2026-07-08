"""Shared ingest runner for `veles add` — read a source and write a wiki page
via agent. M85: kernel logic lives in `veles.modules.wiki.ingest`; this file is a thin
CLI wrapper. (The `veles ingest` deprecated alias was removed in
M117c-removal; `cmd_add` is the only caller of `_run_ingest_cli`.)"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from veles.core.layout.engines import wiki_enabled
from veles.core.project import Project

if TYPE_CHECKING:
    from veles.core.provider import Provider
from veles.modules.wiki.ingest import ingest_user_message
from veles.modules.wiki.wiki import Wiki

# Fallback only for the (unreachable-in-practice) case where the run prompt
# assembles empty — `veles add` is gated on `wiki_enabled`, and the run prompt
# always carries at least the identity header, so this is a belt-and-braces
# guard. It still states the content-aware contract, never a 1:1 dump.
_INGEST_FALLBACK_PROMPT = (
    "You are the Veles ingest agent. Read the source the user names, extract the"
    " distinct topics it is about, and for each topic find an existing wiki page"
    " by meaning (wiki_search) — patch it if found, otherwise create a topical"
    " page (wiki_write_page). A page's identity is the TOPIC, never the filename"
    " or a date. Relocate a raw file source into top-level sources/ with"
    " move_file, and wiki_append_log one line per page touched."
)


def ingest_system_prompt(
    project: Project,
    provider: Provider,
    tools: tuple[str, ...],
) -> str:
    """Content-aware ingest system prompt (M203).

    Routes `veles add` through `build_run_system_prompt` so the llm-wiki layout
    behaviour (topic extraction → find-or-create-or-patch, M190/M203) is
    injected — the same prompt a `veles run` migration turn gets — instead of
    the retired single-page `INGEST_SYSTEM_PROMPT`. The result is qualified for
    the provider's MCP tool namespace (claude-cli/gemini-cli)."""
    from veles.cli import _qualify_for_provider
    from veles.cli._runtime import build_run_system_prompt

    base = build_run_system_prompt(project, prompt="ingest a source into the wiki")
    if not base:
        base = _INGEST_FALLBACK_PROMPT
    return _qualify_for_provider(base, provider, tools)


def _run_batch_ingest_cli(args: argparse.Namespace, project: Project, *, source: str) -> int:
    """Recursive `veles add <dir> --recursive [--glob PATTERN]`.

    M204: the sequential loop lives in the module kernel
    (`modules/wiki/ingest.py::run_batch_ingest` — see its docstring for the
    strictly-sequential M203 dedup invariant); this CLI wrapper only supplies
    `spawn_one` = the single-source top-level runner, plus stderr progress.
    """
    from veles.modules.wiki.ingest import IngestOutcome, batch_ingest_files, run_batch_ingest

    root = Path(source)
    if not root.is_dir():
        print(
            f"error: --recursive needs a directory, but {source!r} is not one.",
            file=sys.stderr,
        )
        return 2
    pattern = getattr(args, "glob", "*") or "*"
    files = batch_ingest_files(root, pattern)
    if not files:
        print(f"no files under {source!r} match {pattern!r}; nothing to add.", file=sys.stderr)
        return 0
    print(f"batch add: {len(files)} file(s) under {source!r} matching {pattern!r}", file=sys.stderr)

    def spawn_one(path: Path) -> IngestOutcome:
        rc = _run_ingest_cli(args, project, source=str(path))
        return IngestOutcome(source=str(path), ok=rc == 0, detail=f"exit code {rc}" if rc else "")

    result = run_batch_ingest(
        files,
        spawn_one=spawn_one,
        on_progress=lambda i, total, path: print(f"[{i}/{total}] {path}", file=sys.stderr),
    )
    if result.failures:
        print(
            f"batch add finished with {len(result.failures)}/{result.total} failure(s).",
            file=sys.stderr,
        )
        return 1
    print(f"batch add finished: {result.total} file(s) ingested.", file=sys.stderr)
    return 0


def _run_ingest_cli(args: argparse.Namespace, project: Project, *, source: str) -> int:
    """Ingest runner used by `cmd_add` (read a source → write a wiki page)."""
    from veles.cli import (
        _INGEST_TOOLS,
        _PROVIDER_API_KEY_ENVS,
        _ensure_api_key,
        _print_run_summary,
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
            '.veles/project.toml, e.g. to "llm-wiki") or store the source '
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
        system_prompt=lambda provider: ingest_system_prompt(project, provider, _INGEST_TOOLS),
        check_api_key=False,
        tool_aware=True,
    )
    # B1 (2026-07-07 audit): the ingest toolset has no `fetch_url` — ingested
    # content is untrusted and must not be able to open an egress channel. A URL
    # source is fetched HERE (fetch_url wraps the body untrusted) and handed to
    # the agent inline; a local file the agent reads itself.
    if source.startswith(("http://", "https://")):
        from veles.core.tools.builtin.fetch_url import fetch_url

        user_msg = ingest_user_message(source, content=fetch_url(source))
    else:
        user_msg = ingest_user_message(source)
    result, budget = _run_agent_streaming_aware(agent, user_msg, args, project=project)
    _print_run_summary(args, result, budget)
    return 0 if result.stopped_reason == "completed" else 1
