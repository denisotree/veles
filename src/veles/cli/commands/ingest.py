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


def _batch_ingest_files(root: Path, pattern: str) -> list[Path]:
    """Files under `root` matching `pattern`, skipping dot-dirs (.git/.veles/…).

    Sorted for deterministic ordering. A dotfile or any path with a
    dot-prefixed component is skipped so we never ingest VCS internals or
    Veles' own state tree.
    """
    out: list[Path] = []
    for p in sorted(root.rglob(pattern)):
        if not p.is_file():
            continue
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        out.append(p)
    return out


def _run_batch_ingest_cli(args: argparse.Namespace, project: Project, *, source: str) -> int:
    """Recursive `veles add <dir> --recursive [--glob PATTERN]`.

    Iterates each matching file through the single-source runner.

    **Must stay strictly sequential (M203).** Content-aware ingestion dedups by
    `wiki_search` before writing: file N+1's search only sees file N's pages if
    N has already finished. Parallelizing this loop would race two same-topic
    files past each other's search → duplicate topic pages, defeating
    find-or-create-or-patch. Each ingest is still its own agent task (no shared
    turn context); the on-disk wiki is the only cross-file state, and that is
    exactly what makes create-vs-patch work across files.
    """
    root = Path(source)
    if not root.is_dir():
        print(
            f"error: --recursive needs a directory, but {source!r} is not one.",
            file=sys.stderr,
        )
        return 2
    pattern = getattr(args, "glob", "*") or "*"
    files = _batch_ingest_files(root, pattern)
    if not files:
        print(f"no files under {source!r} match {pattern!r}; nothing to add.", file=sys.stderr)
        return 0
    print(f"batch add: {len(files)} file(s) under {source!r} matching {pattern!r}", file=sys.stderr)
    failures = 0
    for i, path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {path}", file=sys.stderr)
        if _run_ingest_cli(args, project, source=str(path)) != 0:
            failures += 1
    if failures:
        print(f"batch add finished with {failures}/{len(files)} failure(s).", file=sys.stderr)
        return 1
    print(f"batch add finished: {len(files)} file(s) ingested.", file=sys.stderr)
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
    result, budget = _run_agent_streaming_aware(
        agent, ingest_user_message(source), args, project=project
    )
    _print_run_summary(args, result, budget)
    return 0 if result.stopped_reason == "completed" else 1
