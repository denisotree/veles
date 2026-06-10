"""Smoke tests for veles CLI parser flag wiring."""

from __future__ import annotations

from veles.cli import _build_parser


def test_run_accepts_stream_flag() -> None:
    args = _build_parser().parse_args(["run", "--stream", "hi"])
    assert args.command == "run"
    assert args.stream is True


def test_add_accepts_stream_flag() -> None:
    args = _build_parser().parse_args(["add", "--stream", "./TASK.md"])
    assert args.command == "add"
    assert args.stream is True


def test_removed_deprecated_verbs_no_longer_parse() -> None:
    """M117c-removal: `ingest`/`query`/`lint` were deleted; M149 removed
    the `wiki` alias too — argparse now rejects them all (canonical:
    `veles add` and `veles run "<skill>"`)."""
    import pytest

    for verb in ("ingest", "query", "lint", "wiki"):
        with pytest.raises(SystemExit):
            _build_parser().parse_args([verb, "x"])


def test_curate_subcommand_parses_with_limit() -> None:
    args = _build_parser().parse_args(["curate", "--limit", "5"])
    assert args.command == "curate"
    assert args.limit == 5
    assert args.provider == "openrouter"


def test_skill_add_parses_with_name_and_yes() -> None:
    args = _build_parser().parse_args(
        ["skill", "add", "https://github.com/u/r.git", "--name", "custom", "--yes"]
    )
    assert args.command == "skill"
    assert args.skill_command == "add"
    assert args.source == "https://github.com/u/r.git"
    assert args.name == "custom"
    assert args.yes is True


def test_skill_remove_parses_with_yes() -> None:
    args = _build_parser().parse_args(["skill", "remove", "greet", "-y"])
    assert args.command == "skill"
    assert args.skill_command == "remove"
    assert args.name == "greet"
    assert args.yes is True


def test_module_add_parses_with_name_and_yes() -> None:
    args = _build_parser().parse_args(["module", "add", "/local/mod", "--name", "logger", "--yes"])
    assert args.command == "module"
    assert args.module_command == "add"
    assert args.source == "/local/mod"
    assert args.name == "logger"
    assert args.yes is True


def test_module_remove_parses_with_yes() -> None:
    args = _build_parser().parse_args(["module", "remove", "logger", "-y"])
    assert args.command == "module"
    assert args.module_command == "remove"
    assert args.name == "logger"
    assert args.yes is True
