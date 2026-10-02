"""`veles add` — the wiki engine's `cli_command` (moved from `cli/commands/add.py`
+ `ingest.py`, M85/M203/M204): read a source and route its topics into the wiki.

The agent is built by the CLI host (`CommandHost.run_agent`) the way `veles run`
builds it, with the project's run system prompt so the layout's ingest behaviour
(topic extraction → find-or-create-or-patch) rides along."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from veles.sdk import Project
from veles.sdk.contributions import CliCommand, CommandHost
from veles.sdk.tools import TOOLSETS

from .ingest import (
    IngestOutcome,
    batch_ingest_files,
    ingest_user_message,
    run_batch_ingest,
)
from .wiki import Wiki, wiki_enabled

# Used only if the run prompt assembles empty (it always carries at least the
# identity header). It still states the content-aware contract, never a 1:1 dump.
_INGEST_FALLBACK_PROMPT = (
    "You are the Veles ingest agent. Read the source the user names, extract the"
    " distinct topics it is about, and for each topic find an existing wiki page"
    " by meaning (wiki_search) — patch it if found, otherwise create a topical"
    " page (wiki_write_page). A page's identity is the TOPIC, never the filename"
    " or a date. Relocate a raw file source into top-level sources/ with"
    " move_file, and wiki_append_log one line per page touched."
)


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", help="A file path, directory, or URL (http://, https://) to add.")
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="When SOURCE is a directory, ingest matching files under it (one page each).",
    )
    parser.add_argument(
        "--glob",
        default="*",
        metavar="PATTERN",
        help="With --recursive, only ingest files matching this glob (default: '*').",
    )


def _add(args: argparse.Namespace, project: Project, host: CommandHost) -> int:
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
    if getattr(args, "recursive", False):
        return _add_tree(args, project, host)
    return _add_one(project, host, args.source)


def _add_one(project: Project, host: CommandHost, source: str) -> int:
    Wiki(project.wiki_root).ensure_layout()

    def message() -> str:
        # B1 (2026-07-07 audit): the ingest toolset has no `fetch_url` — ingested
        # content is untrusted and must not open an egress channel. A URL source is
        # fetched HERE (fetch_url wraps the body untrusted) and handed over inline;
        # a local file the agent reads itself.
        if source.startswith(("http://", "https://")):
            from veles.sdk.tools import fetch_url

            return ingest_user_message(source, content=fetch_url(source))
        return ingest_user_message(source)

    return host.run_agent(
        message,
        tools=tuple(TOOLSETS["ingest"]),
        prompt_hint="ingest a source into the wiki",
        fallback_prompt=_INGEST_FALLBACK_PROMPT,
    )


def _add_tree(args: argparse.Namespace, project: Project, host: CommandHost) -> int:
    """`veles add <dir> --recursive [--glob PATTERN]` — the strictly sequential
    batch kernel (`ingest.run_batch_ingest`), one top-level run per file."""
    root = Path(args.source)
    if not root.is_dir():
        print(
            f"error: --recursive needs a directory, but {args.source!r} is not one.",
            file=sys.stderr,
        )
        return 2
    pattern = getattr(args, "glob", "*") or "*"
    files = batch_ingest_files(root, pattern)
    if not files:
        print(f"no files under {args.source!r} match {pattern!r}; nothing to add.", file=sys.stderr)
        return 0
    print(
        f"batch add: {len(files)} file(s) under {args.source!r} matching {pattern!r}",
        file=sys.stderr,
    )

    def spawn_one(path: Path) -> IngestOutcome:
        rc = _add_one(project, host, str(path))
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


ADD_COMMAND = CliCommand(
    help="Read a source and write a wiki page.",
    add_arguments=_add_arguments,
    run=_add,
    run_flags=True,
)
