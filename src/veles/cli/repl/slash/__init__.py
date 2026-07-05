"""Slash-command framework + the default registry shipped with Veles."""

from veles.cli.repl.slash.builtin import build_default_registry
from veles.cli.repl.slash.registry import (
    SlashCommand,
    SlashContext,
    SlashHandler,
    SlashRegistry,
    SlashResult,
)

__all__ = [
    "SlashCommand",
    "SlashContext",
    "SlashHandler",
    "SlashRegistry",
    "SlashResult",
    "build_default_registry",
]
