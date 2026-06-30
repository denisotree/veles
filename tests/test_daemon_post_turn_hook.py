"""After every daemon run, the post-turn learning loop (curator,
insight extractor, proposer, ...) should fire — same set as
`cmd_run`'s post-run block. We mock all six hooks and assert each is
called once.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import ClassVar

import veles.cli as cli_mod
from veles.cli.commands.daemon import _make_post_turn_hook
from veles.core.project import init_project


def _stub_args() -> argparse.Namespace:
    return argparse.Namespace()


def test_post_turn_hook_fires_every_step(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path, name="postturn")
    calls: list[str] = []

    def _track(name: str):
        def _fn(*_args, **_kwargs):
            calls.append(name)

        return _fn

    monkeypatch.setattr(cli_mod, "_maybe_run_insight_extractor", _track("insight"))
    monkeypatch.setattr(cli_mod, "_maybe_run_post_turn_curator", _track("curator"))
    monkeypatch.setattr(cli_mod, "_maybe_run_subproject_proposer", _track("proposer"))
    monkeypatch.setattr(cli_mod, "_maybe_suggest_promotions", _track("promotions"))
    monkeypatch.setattr(cli_mod, "_maybe_refresh_nl_routing", _track("routing"))
    monkeypatch.setattr(cli_mod, "_maybe_refresh_self_doc", _track("self_doc"))

    hook = _make_post_turn_hook(_stub_args(), project)

    class _FakeResult:
        history: ClassVar[list] = []
        session_id = "ses-test"

    hook(_FakeResult())

    assert calls == ["insight", "curator", "proposer", "promotions", "routing", "self_doc"]


def test_post_turn_hook_keeps_going_when_one_step_fails(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = init_project(tmp_path, name="postturnfail")
    calls: list[str] = []

    def _ok(name: str):
        def _fn(*_a, **_kw):
            calls.append(name)

        return _fn

    def _raise(*_a, **_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_mod, "_maybe_run_insight_extractor", _raise)
    monkeypatch.setattr(cli_mod, "_maybe_run_post_turn_curator", _ok("curator"))
    monkeypatch.setattr(cli_mod, "_maybe_run_subproject_proposer", _ok("proposer"))
    monkeypatch.setattr(cli_mod, "_maybe_suggest_promotions", _ok("promotions"))
    monkeypatch.setattr(cli_mod, "_maybe_refresh_nl_routing", _ok("routing"))
    monkeypatch.setattr(cli_mod, "_maybe_refresh_self_doc", _ok("self_doc"))

    hook = _make_post_turn_hook(_stub_args(), project)

    class _FakeResult:
        history: ClassVar[list] = []
        session_id = "x"

    hook(_FakeResult())

    assert calls == ["curator", "proposer", "promotions", "routing", "self_doc"]
    err = capsys.readouterr().err
    assert "boom" in err


def test_post_turn_hook_resolves_provider_from_project_config(tmp_path: Path) -> None:
    """M184: the daemon/channel start Namespace has `provider=None` when no
    `--provider` is passed (provider flows from project config). The post-turn
    hook must resolve the effective provider into `args.provider`, otherwise
    the continuous-curator eligibility gate sees None and silently disables
    the curator — the bug that left a wiki-llm diary bot with 0 curated pages.
    """
    project = init_project(tmp_path, name="provres")
    (project.state_dir / "config.toml").write_text(
        '[provider]\ndefault = "ollama"\n', encoding="utf-8"
    )
    args = argparse.Namespace(provider=None, model=None)

    _make_post_turn_hook(args, project)

    assert args.provider == "ollama"


def test_post_turn_hook_keeps_explicit_provider(tmp_path: Path) -> None:
    """An explicit `--provider` on the daemon Namespace must win over the
    project-config default (mirrors the run.py resolution cascade)."""
    project = init_project(tmp_path, name="provexplicit")
    (project.state_dir / "config.toml").write_text(
        '[provider]\ndefault = "ollama"\n', encoding="utf-8"
    )
    args = argparse.Namespace(provider="anthropic", model=None)

    _make_post_turn_hook(args, project)

    assert args.provider == "anthropic"


async def test_run_agent_in_background_invokes_post_turn_hook(monkeypatch) -> None:
    """End-to-end: `run_agent_in_background` should call the hook after
    the worker completes, via `to_thread`."""
    from veles.core.agent import RunResult
    from veles.daemon.runner import new_run_handle, run_agent_in_background

    called: list[RunResult] = []

    def hook(result: RunResult) -> None:
        called.append(result)

    from tests.conftest import FakeAgent

    agent = FakeAgent(
        RunResult(text="ok", iterations=1, stopped_reason="completed", session_id="ses-x")
    )
    handle = new_run_handle()
    await run_agent_in_background(handle, agent=agent, prompt="hi", post_turn_hook=hook)
    assert len(called) == 1
    assert called[0].text == "ok"
