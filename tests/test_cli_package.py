"""M46 — `veles.cli` package structure smoke tests.

Confirms that the package (vs the original single-file module) keeps its
public surface intact: backward-compat re-exports, parser smoke, command
modules importable on their own, and circular-import-free.
"""

from __future__ import annotations

import importlib

import pytest

_COMMAND_MODULES = (
    "curate",
    "init",
    "modules",
    "portability",
    "projects",
    "route",
    "run",
    "schema",
    "sessions",
    "skills",
    "subprojects",
    "tui",
)

_HELPER_MODULES = (
    "_curator",
    "_project",
    "_runtime",
)


def test_cli_package_loads() -> None:
    cli = importlib.import_module("veles.cli")
    assert hasattr(cli, "main")
    assert hasattr(cli, "_build_parser")


@pytest.mark.parametrize("name", _COMMAND_MODULES)
def test_each_command_module_importable(name: str) -> None:
    mod = importlib.import_module(f"veles.cli.commands.{name}")
    # Every command module must expose at least one cmd_* entry.
    callables = [a for a in dir(mod) if a.startswith("cmd_")]
    assert callables, f"command module {name!r} has no cmd_* function"


def test_backward_compat_reexports_present() -> None:
    """Tests / external users monkey-patch `veles.cli._cmd_*` —
    every extracted verb must still be reachable under that name."""
    from veles.cli import (
        _cmd_curate,
        _cmd_export,
        _cmd_import,
        _cmd_init,
        _cmd_module,
        _cmd_project,
        _cmd_route,
        _cmd_run,
        _cmd_schema_dispatch,
        _cmd_sessions,
        _cmd_skill,
        _cmd_subproject,
        _cmd_tui,
    )

    for fn in (
        _cmd_curate,
        _cmd_export,
        _cmd_import,
        _cmd_init,
        _cmd_module,
        _cmd_project,
        _cmd_route,
        _cmd_run,
        _cmd_schema_dispatch,
        _cmd_sessions,
        _cmd_skill,
        _cmd_subproject,
        _cmd_tui,
    ):
        assert callable(fn)
        assert fn.__module__.startswith("veles.cli.commands."), fn.__module__


@pytest.mark.parametrize("name", _HELPER_MODULES)
def test_helper_modules_importable(name: str) -> None:
    importlib.import_module(f"veles.cli.{name}")


def test_monkey_patch_surface_reachable() -> None:
    """The set of helpers that `tests/test_curator.py` monkey-patches
    must remain reachable as `veles.cli._<name>` — extracted command
    bodies do lazy `from veles.cli import _foo` so a runtime patch on
    `veles.cli._foo` propagates. Any future regression in that surface
    breaks the curator tests; this test catches it earlier."""
    from veles.cli import (
        _CURATE_QUIET_WINDOW_SEC,
        _CURATOR_IDLE_THRESHOLD_SEC,
        _continuous_curator_eligible,
        _curate_one_session,
        _CuratorPassResult,
        _load_skills,
        _make_tool_aware_provider,
        _maybe_run_idle_curator,
        _maybe_run_post_turn_curator,
        _qualify_for_provider,
        _render_message,
        _run_agent_streaming_aware,
        _run_curator_pass,
        _truncate_session_messages,
    )

    for symbol in (
        _continuous_curator_eligible,
        _curate_one_session,
        _maybe_run_idle_curator,
        _maybe_run_post_turn_curator,
        _run_curator_pass,
        _truncate_session_messages,
        _render_message,
        _load_skills,
        _make_tool_aware_provider,
        _qualify_for_provider,
        _run_agent_streaming_aware,
    ):
        assert callable(symbol)
    assert isinstance(_CURATE_QUIET_WINDOW_SEC, float)
    assert isinstance(_CURATOR_IDLE_THRESHOLD_SEC, int)
    assert _CuratorPassResult.__name__ == "_CuratorPassResult"


def test_parser_lists_all_top_level_verbs() -> None:
    """Smoke check: the monolithic `_build_parser` still wires every verb."""
    from veles.cli import _build_parser

    parser = _build_parser()
    # argparse stores subparsers under a private attribute; walk it.
    sub_actions = [a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction"]
    assert sub_actions, "no subparsers registered"
    choices = set(sub_actions[0].choices.keys())
    expected = {
        "init",
        "run",
        "curate",
        "skill",
        "module",
        "sessions",
        "project",
        "subproject",
        "schema",
        "route",
        "export",
        "import",
        "tui",
    }
    missing = expected - choices
    assert not missing, f"parser is missing verbs: {missing}"


def test_help_does_not_raise(capsys: pytest.CaptureFixture[str]) -> None:
    """`veles --help` should produce a usage line without raising."""
    from veles.cli import _build_parser

    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "veles" in out
