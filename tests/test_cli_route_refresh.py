"""M43b — `veles route refresh` CLI verb + curator auto-trigger."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli.commands import route as route_cmd
from veles.core.project import Project, init_project
from veles.core.routing import load_nl_routing_config, load_nl_state, set_project_route
from veles.core.routing.nl_override import _NLEntry


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    yield


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


def _ns(**fields):
    return type("A", (), fields)()


def _write_agents_md(project: Project, text: str) -> None:
    project.agents_md_path.write_text(text, encoding="utf-8")


def _patch_extractor(monkeypatch, entries: list[_NLEntry]) -> None:
    """Replace the sub-Agent factory with a stub that returns canned entries."""

    def _stub_factory(*, provider, model):
        return lambda _text: list(entries)

    monkeypatch.setattr("veles.core.routing.nl_override.make_nl_extractor", _stub_factory)
    # `route_cmd._refresh` imports from `veles.core.routing` directly, which
    # re-exports the same name; patch that too so both reference sites win.
    monkeypatch.setattr("veles.core.routing.make_nl_extractor", _stub_factory)


def test_refresh_with_empty_agents_md_returns_1(project, capsys) -> None:
    # init_project writes a default AGENTS.md template — clear it to test the empty path.
    project.agents_md_path.write_text("", encoding="utf-8")
    args = _ns(route_command="refresh", force=False)
    rc = route_cmd.cmd_route(args, project)
    assert rc == 1
    assert "missing or empty" in capsys.readouterr().err


def test_refresh_writes_nl_toml(project, capsys, monkeypatch) -> None:
    _write_agents_md(
        project,
        "## Routing\n\nUse haiku for compression.\n",
    )
    _patch_extractor(
        monkeypatch,
        [_NLEntry(task="compressor", provider="anthropic", model="claude-haiku-4-5")],
    )
    args = _ns(route_command="refresh", force=False)
    rc = route_cmd.cmd_route(args, project)
    assert rc == 0
    cfg = load_nl_routing_config(project)
    assert cfg.tasks == {"compressor": "anthropic:claude-haiku-4-5"}
    state = load_nl_state(project)
    assert state.entries_count == 1
    assert "1 entries" in capsys.readouterr().err


def test_refresh_no_actionable_hints_reports_zero(project, capsys, monkeypatch) -> None:
    _write_agents_md(project, "## Layout\n\nNothing about routing here.\n")
    _patch_extractor(monkeypatch, [])
    args = _ns(route_command="refresh", force=False)
    rc = route_cmd.cmd_route(args, project)
    assert rc == 0
    assert "no actionable hints" in capsys.readouterr().err


def test_refresh_short_circuits_when_unchanged(project, monkeypatch) -> None:
    _write_agents_md(project, "## Routing\n\nUse haiku.\n")
    call_count = {"n": 0}

    def _stub_factory(*, provider, model):
        def _ex(_text):
            call_count["n"] += 1
            return [_NLEntry(task="compressor", provider="anthropic", model="haiku")]

        return _ex

    monkeypatch.setattr("veles.core.routing.nl_override.make_nl_extractor", _stub_factory)
    monkeypatch.setattr("veles.core.routing.make_nl_extractor", _stub_factory)

    route_cmd.cmd_route(_ns(route_command="refresh", force=False), project)
    route_cmd.cmd_route(_ns(route_command="refresh", force=False), project)
    assert call_count["n"] == 1  # second call skipped via SHA match


def test_refresh_force_reruns(project, monkeypatch) -> None:
    _write_agents_md(project, "## Routing\n\nUse haiku.\n")
    call_count = {"n": 0}

    def _stub_factory(*, provider, model):
        def _ex(_text):
            call_count["n"] += 1
            return []

        return _ex

    monkeypatch.setattr("veles.core.routing.nl_override.make_nl_extractor", _stub_factory)
    monkeypatch.setattr("veles.core.routing.make_nl_extractor", _stub_factory)

    route_cmd.cmd_route(_ns(route_command="refresh", force=False), project)
    route_cmd.cmd_route(_ns(route_command="refresh", force=True), project)
    assert call_count["n"] == 2


def test_refresh_missing_api_key_returns_2(project, capsys, monkeypatch) -> None:
    _write_agents_md(project, "## Routing\n\nUse haiku.\n")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    rc = route_cmd.cmd_route(_ns(route_command="refresh", force=False), project)
    assert rc == 2
    assert "no API key" in capsys.readouterr().err


# ---- show command surfaces nl source ----


def test_show_marks_nl_source(project, capsys, monkeypatch) -> None:
    """`veles route show` should label entries from routing.nl.toml as `nl`."""
    from veles.core.routing import RoutingConfig, save_nl_routing_config

    save_nl_routing_config(project, RoutingConfig(tasks={"compressor": "openai:gpt-4o-mini"}))
    rc = route_cmd.cmd_route(_ns(route_command="show"), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "compressor" in out
    assert "openai:gpt-4o-mini" in out
    assert " nl" in out


def test_show_manual_wins_over_nl_label(project, capsys) -> None:
    from veles.core.routing import RoutingConfig, save_nl_routing_config

    save_nl_routing_config(project, RoutingConfig(tasks={"compressor": "openai:gpt-4o-mini-NL"}))
    set_project_route(project, "compressor", "openai:gpt-4o-mini-MANUAL")
    route_cmd.cmd_route(_ns(route_command="show"), project)
    out = capsys.readouterr().out
    # Manual line wins → label should be `project`, not `nl`.
    compressor_line = next(line for line in out.splitlines() if "compressor" in line)
    assert "MANUAL" in compressor_line
    assert "project" in compressor_line
    assert "NL" not in compressor_line


# ---- curator auto-trigger ----


def test_auto_trigger_skipped_on_resume(project, monkeypatch) -> None:
    """`--resume` short-circuits the eligibility check; nl refresh stays a no-op."""
    from veles.cli._curator import _maybe_refresh_nl_routing

    _write_agents_md(project, "## Routing\n\nUse haiku.\n")
    called = {"n": 0}

    def _stub_factory(*, provider, model):
        def _ex(_text):
            called["n"] += 1
            return []

        return _ex

    monkeypatch.setattr("veles.core.routing.nl_override.make_nl_extractor", _stub_factory)
    monkeypatch.setattr("veles.core.routing.make_nl_extractor", _stub_factory)

    args = _ns(provider="openrouter", resume="ses-x", no_route_refresh=False)
    _maybe_refresh_nl_routing(args, project)
    assert called["n"] == 0


def test_auto_trigger_skipped_by_flag(project, monkeypatch) -> None:
    from veles.cli._curator import _maybe_refresh_nl_routing

    _write_agents_md(project, "## Routing\n\nUse haiku.\n")
    called = {"n": 0}

    def _stub_factory(*, provider, model):
        def _ex(_text):
            called["n"] += 1
            return []

        return _ex

    monkeypatch.setattr("veles.core.routing.nl_override.make_nl_extractor", _stub_factory)
    monkeypatch.setattr("veles.core.routing.make_nl_extractor", _stub_factory)
    args = _ns(provider="openrouter", resume=None, no_route_refresh=True)
    _maybe_refresh_nl_routing(args, project)
    assert called["n"] == 0


def test_auto_trigger_fires_on_first_run(project, monkeypatch) -> None:
    from veles.cli._curator import _maybe_refresh_nl_routing

    _write_agents_md(project, "## Routing\n\nUse haiku.\n")
    captured: list[_NLEntry] = []

    def _stub_factory(*, provider, model):
        def _ex(_text):
            captured.append(_NLEntry(task="compressor", provider="anthropic", model="haiku-7"))
            return list(captured)

        return _ex

    monkeypatch.setattr("veles.core.routing.nl_override.make_nl_extractor", _stub_factory)
    monkeypatch.setattr("veles.core.routing.make_nl_extractor", _stub_factory)

    args = _ns(provider="openrouter", resume=None, no_route_refresh=False)
    _maybe_refresh_nl_routing(args, project)
    cfg = load_nl_routing_config(project)
    assert cfg.tasks.get("compressor") == "anthropic:haiku-7"


def test_auto_trigger_skips_when_sha_unchanged(project, monkeypatch) -> None:
    from veles.cli._curator import _maybe_refresh_nl_routing

    _write_agents_md(project, "## Routing\n\nUse haiku.\n")
    calls = {"n": 0}

    def _stub_factory(*, provider, model):
        def _ex(_text):
            calls["n"] += 1
            return []

        return _ex

    monkeypatch.setattr("veles.core.routing.nl_override.make_nl_extractor", _stub_factory)
    monkeypatch.setattr("veles.core.routing.make_nl_extractor", _stub_factory)
    args = _ns(provider="openrouter", resume=None, no_route_refresh=False)
    _maybe_refresh_nl_routing(args, project)
    _maybe_refresh_nl_routing(args, project)
    assert calls["n"] == 1
