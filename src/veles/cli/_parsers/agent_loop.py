"""Parsers for the agent-loop verbs: init, run, add, tui, curate.

(`ingest`/`query`/`lint` were deprecated aliases — M117c — and physically
removed in M117c-removal; the canonical paths are `veles add` and
`veles run "<skill>"` from the active layout-pack.)"""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import (
    DEFAULT_COMPRESS_THRESHOLD_TOKENS,
    DEFAULT_COMPRESSOR_MODEL,
    add_common_run_flags,
)


def _register_init(sub: argparse._SubParsersAction) -> None:
    init = sub.add_parser("init", help="Create a new Veles project in the cwd.")
    init.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Project name (default: cwd basename, normalised).",
    )
    init.add_argument(
        "--layout",
        default="llm-wiki",
        help=(
            "Layout pack for the user-content scaffold (default: llm-wiki). "
            "Discovered from ~/.veles/layouts/ and the builtin packs."
        ),
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="Recreate .veles/ even if it already exists.",
    )


def _register_run(sub: argparse._SubParsersAction) -> None:
    run = sub.add_parser("run", help="Run a single prompt end-to-end.")
    run.add_argument("prompt", help="The user prompt.")
    add_common_run_flags(run)
    run.add_argument("--resume", metavar="ID", default=None, help="Continue an existing session.")
    run.add_argument(
        "--manager",
        action="store_true",
        help=(
            "Decompose the prompt via the multi-agent manager (explorer→writer) "
            "instead of a single agent. Off by default; also enabled by "
            "VELES_MANAGER_MODE=1."
        ),
    )
    run.add_argument(
        "--verify",
        action="store_true",
        help=(
            "After the run, have the routed advisor model judge the answer; on a "
            "confident failure, re-run the prompt on that stronger model (fallback "
            "on hallucinations). Forces buffered output. Off by default; also "
            "enabled by VELES_VERIFY_MODE=1."
        ),
    )
    run.add_argument(
        "--no-agents-md",
        action="store_true",
        help="Skip auto-injection of AGENTS.md into the system prompt.",
    )
    run.add_argument(
        "--no-index", action="store_true", help="Skip auto-injection of the wiki INDEX.md."
    )
    run.add_argument(
        "--no-compress",
        action="store_true",
        help="Disable sliding-window context compression for this run.",
    )
    run.add_argument(
        "--no-curator",
        action="store_true",
        help=(
            "Disable continuous curator triggers (idle pre-run + post-turn) "
            "for this invocation. The explicit `veles curate` command is unaffected."
        ),
    )
    run.add_argument(
        "--no-insights",
        action="store_true",
        help=(
            "Disable post-run insight extraction (the `insights` memory table) for this invocation."
        ),
    )
    run.add_argument(
        "--no-proposer",
        action="store_true",
        help=(
            "Disable the subproject proposer auto-trigger (it normally "
            "refreshes `.veles/memory/proposals/` at most once every 7 days)."
        ),
    )
    run.add_argument(
        "--no-route-refresh",
        action="store_true",
        help=(
            "Disable the natural-language routing refresh that re-parses "
            "AGENTS.md hints into `routing.nl.toml` on every AGENTS.md edit."
        ),
    )
    run.add_argument(
        "--no-suggest-promote",
        action="store_true",
        help=(
            "Disable the auto-promote suggester (it normally refreshes "
            "`.veles/memory/proposals/promote-*.md` at most once every 7 days)."
        ),
    )
    run.add_argument(
        "--compressor-model",
        default=None,
        help=(
            "Override the routed compressor model (default: routed via "
            f"`veles route show`, fallback {DEFAULT_COMPRESSOR_MODEL})."
        ),
    )
    run.add_argument(
        "--compress-threshold-tokens",
        type=int,
        default=DEFAULT_COMPRESS_THRESHOLD_TOKENS,
        metavar="N",
        help=(
            f"Estimated history token count that triggers compression "
            f"(default: {DEFAULT_COMPRESS_THRESHOLD_TOKENS})."
        ),
    )
    run.add_argument(
        "--plan",
        action="store_true",
        help=(
            "Run in Planning mode: the agent may read, search, compute, "
            "and draft, but mutation tools are blocked by the Permission "
            "Engine until you exit planning."
        ),
    )


def _register_add(sub: argparse._SubParsersAction) -> None:
    add = sub.add_parser("add", help="Read a source and write a wiki page.")
    add.add_argument(
        "source",
        help="A file path, directory, or URL (http://, https://) to add.",
    )
    add.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="When SOURCE is a directory, ingest matching files under it (one page each).",
    )
    add.add_argument(
        "--glob",
        default="*",
        metavar="PATTERN",
        help="With --recursive, only ingest files matching this glob (default: '*').",
    )
    add_common_run_flags(add)


def _register_organize(sub: argparse._SubParsersAction) -> None:
    org = sub.add_parser(
        "organize",
        help="Reorganize project content per the active layout (propose-then-apply).",
    )
    org.add_argument(
        "scope",
        nargs="?",
        default=None,
        help="Optional path to restrict the reorganization to a subtree.",
    )
    org.add_argument(
        "--apply",
        action="store_true",
        help="Execute the reorganization (move/rename/relink). Default: propose only.",
    )
    add_common_run_flags(org)


def add_interactive_flags(parser: argparse.ArgumentParser) -> None:
    """Flags for the default interactive REPL, added to the TOP-LEVEL parser.

    The inline streaming REPL (normal screen buffer, native terminal scroll/
    selection/copy) is what bare `veles` launches — there is no separate `repl`
    or `tui` subcommand. Putting the flags at the top level lets `veles`,
    `veles -c`, `veles --provider X` all start it without a subcommand."""
    add_common_run_flags(parser)
    parser.set_defaults(model=None)  # None → persisted/default resolved at runtime
    parser.add_argument("--resume", metavar="ID", default=None, help="Resume an existing session.")
    parser.add_argument(
        "-c",
        "--continue",
        dest="continue_last",
        action="store_true",
        help="Resume the most recent session in this project (its last activity).",
    )
    parser.add_argument(
        "--no-agents-md",
        action="store_true",
        help="Skip auto-injection of AGENTS.md into the system prompt.",
    )
    parser.add_argument(
        "--no-index", action="store_true", help="Skip auto-injection of the wiki INDEX.md."
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Disable sliding-window context compression for this run.",
    )
    parser.add_argument(
        "--compressor-model",
        default=None,
        help=(
            "Override the routed compressor model (default: routed via "
            f"`veles route show`, fallback {DEFAULT_COMPRESSOR_MODEL})."
        ),
    )
    parser.add_argument(
        "--compress-threshold-tokens",
        type=int,
        default=DEFAULT_COMPRESS_THRESHOLD_TOKENS,
        metavar="N",
        help=(
            f"Estimated history token count that triggers compression "
            f"(default: {DEFAULT_COMPRESS_THRESHOLD_TOKENS})."
        ),
    )


def _register_curate(sub: argparse._SubParsersAction) -> None:
    from veles.core.curator import _CURATE_DEFAULT_LIMIT

    curate = sub.add_parser(
        "curate",
        help=(
            "Distill unprocessed sessions into durable memory (wiki page per "
            "session when the layout has the wiki engine, SQL insights always)."
        ),
    )
    curate.add_argument(
        "--limit",
        type=int,
        default=_CURATE_DEFAULT_LIMIT,
        metavar="N",
        help=f"Max sessions to curate per run (default: {_CURATE_DEFAULT_LIMIT}).",
    )
    add_common_run_flags(curate)


def _register_research(sub: argparse._SubParsersAction) -> None:
    research = sub.add_parser(
        "research",
        help="Deep research: plan → parallel web explore → synthesised report.",
    )
    research.add_argument("question", help="The research question.")
    research.add_argument(
        "--max-subquestions",
        type=int,
        default=4,
        metavar="N",
        help="Max research angles to investigate in parallel (default: 4).",
    )
    add_common_run_flags(research)


def register(sub: argparse._SubParsersAction) -> None:
    _register_init(sub)
    _register_run(sub)
    _register_add(sub)
    _register_organize(sub)
    _register_curate(sub)
    _register_research(sub)
