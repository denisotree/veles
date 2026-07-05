"""Per-verb argparse subparser registrations for the `veles` CLI.

`_build_parser` in `veles.cli` historically held an 896-line argparse
configuration block. M77 extracts it into one module per verb-group so
adding/changing a verb stays a localised edit. `build_parser()` here is
the new orchestrator; `veles.cli._build_parser` is a thin backward-compat
alias for tests that monkey-patch or import the old name.
"""

from __future__ import annotations

import argparse

from veles.cli._parsers import (
    agent_loop,
    autopilot,
    browse,
    channel,
    daemon,
    doctor,
    dream,
    goal,
    job,
    layout,
    mcp,
    models,
    module,
    portability,
    project,
    route,
    schema,
    secret,
    self_doc,
    sessions,
    skill,
    subproject,
    tool,
    trust,
)

__all__ = ["build_parser"]

_REGISTRARS = (
    agent_loop.register,
    skill.register,
    module.register,
    portability.register,
    models.register,
    route.register,
    schema.register,
    self_doc.register,
    project.register,
    subproject.register,
    sessions.register,
    daemon.register,
    autopilot.register,
    doctor.register,
    secret.register,
    goal.register,
    job.register,
    layout.register,
    dream.register,
    browse.register,
    trust.register,
    channel.register,
    tool.register,
    mcp.register,
)


def build_parser() -> argparse.ArgumentParser:
    from veles import __version__

    parser = argparse.ArgumentParser(prog="veles", description="Veles agent.")
    parser.add_argument(
        "--version",
        action="version",
        version=f"veles {__version__}",
    )
    parser.add_argument(
        "--no-wizard",
        action="store_true",
        help=(
            "Skip the first-run setup wizard even if `~/.veles/config.toml` "
            "is missing. The wizard is also gated on a TTY and on the env var "
            "`VELES_NO_WIZARD=1`."
        ),
    )
    # Bare `veles` (no subcommand) launches the inline interactive REPL, so its
    # flags live on the top-level parser and subcommands are optional.
    agent_loop.add_interactive_flags(parser)
    sub = parser.add_subparsers(dest="command", required=False)
    for register in _REGISTRARS:
        register(sub)
    return parser
