"""`veles.cli` package structure smoke tests.

The package root is only the entry point: `main` plus a verb → command-module
dispatch table. Every command module must import on its own, the table must
point at real functions, and the parser must wire every verb.
"""

from __future__ import annotations

import importlib

import pytest

from veles.cli import _COMMANDS
from veles.cli._parsers import build_parser


def test_cli_package_exposes_only_main() -> None:
    cli = importlib.import_module("veles.cli")
    assert cli.__all__ == ["main"]
    assert callable(cli.main)


@pytest.mark.parametrize("verb", sorted(_COMMANDS, key=str))
def test_every_dispatch_entry_resolves(verb: str | None) -> None:
    module_name, func_name, _need = _COMMANDS[verb]
    assert callable(getattr(importlib.import_module(module_name), func_name))


def test_dispatch_table_covers_every_parsed_verb() -> None:
    parser = build_parser()
    sub_actions = [a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction"]
    assert sub_actions, "no subparsers registered"
    verbs = set(sub_actions[0].choices.keys())
    missing = verbs - set(_COMMANDS)
    assert not missing, f"parsed verbs with no dispatch entry: {missing}"


def test_help_does_not_raise(capsys: pytest.CaptureFixture[str]) -> None:
    """`veles --help` should produce a usage line without raising."""
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["--help"])
    assert exc_info.value.code == 0
    assert "veles" in capsys.readouterr().out
