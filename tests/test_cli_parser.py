"""Smoke tests for veles CLI parser flag wiring."""

from __future__ import annotations

import pytest

from veles.cli import _build_parser
from veles.cli._parsers._common import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_TOKENS_TOTAL,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
)


def test_version_flag_prints_and_exits(capsys) -> None:
    import pytest

    from veles import __version__

    with pytest.raises(SystemExit) as exc:
        _build_parser().parse_args(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"veles {__version__}"


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


# --- M227: flags given before the verb must survive the subparser -------------
#
# `add_common_run_flags` is attached to the top-level parser (bare `veles` is the
# REPL) AND to every agent-loop subparser. argparse copies the sub-namespace onto
# the parent, so subparser DEFAULTS used to overwrite root-parsed values:
# `veles --provider anthropic run "x"` silently ran on openrouter.


_COMMON_FLAGS = [
    ["--verbose"],
    ["--stream"],
    ["--model", "some/model"],
    ["--provider", "anthropic"],
    ["--max-tokens-total", "5"],
    ["--max-iterations", "7"],
    ["--project-root", "/tmp/p"],
]


@pytest.mark.parametrize("flag", _COMMON_FLAGS, ids=lambda f: f[0])
def test_common_flag_before_verb_equals_after_verb(flag: list[str]) -> None:
    parser = _build_parser()
    before = parser.parse_args([*flag, "run", "x"])
    after = parser.parse_args(["run", *flag, "x"])
    assert vars(before) == vars(after)


def test_provider_explicit_marker_tracks_actual_use() -> None:
    """`_provider_explicit` must mean "user typed --provider", in either position.

    The old bug set it True while the *value* was clobbered back to the default,
    so `resolve_effective_provider` passed openrouter off as a deliberate choice
    and overrode the project's configured provider.
    """
    parser = _build_parser()
    for argv in (["--provider", "anthropic", "run", "x"], ["run", "--provider", "anthropic", "x"]):
        args = parser.parse_args(argv)
        assert args.provider == "anthropic"
        assert getattr(args, "_provider_explicit", False) is True
    plain = parser.parse_args(["run", "x"])
    assert plain.provider == DEFAULT_PROVIDER
    assert getattr(plain, "_provider_explicit", False) is False


def test_common_flag_survives_nested_subparser() -> None:
    assert _build_parser().parse_args(["--verbose", "job", "tick"]).verbose is True


def test_run_defaults_unchanged_without_flags() -> None:
    """SUPPRESS on the subparser must not strip the defaults themselves."""
    args = _build_parser().parse_args(["run", "x"])
    assert args.model == DEFAULT_MODEL
    assert args.provider == DEFAULT_PROVIDER
    assert args.max_iterations == DEFAULT_MAX_ITERATIONS
    assert args.max_tokens_total == DEFAULT_MAX_TOKENS_TOTAL
    assert args.project_root is None
    assert args.verbose is False
    assert args.stream is False
