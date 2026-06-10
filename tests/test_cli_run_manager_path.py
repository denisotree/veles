"""M122e + M124: `veles run` manager-spawn path (auto-activated)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from veles.cli.commands.run import _maybe_run_via_manager
from veles.core.project import init_project


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def _ns(**fields: Any):
    return type("A", (), fields)()


# ---- gate decisions ----


def test_manager_path_skipped_for_short_unkeyworded_prompt(
    isolated_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M124: heuristic now active by default — but short prompts
    without research-keyword still bypass manager (single-shot)."""
    monkeypatch.delenv("VELES_MANAGER_MODE", raising=False)
    project = init_project(tmp_path / "proj", name="proj")
    args = _ns(prompt="hi", provider="openrouter", model="x")
    assert _maybe_run_via_manager(args, project) is False


def test_manager_path_disabled_explicitly(
    isolated_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`VELES_MANAGER_MODE=0` is the kill switch — even
    research-keyword prompts skip manager."""
    monkeypatch.setenv("VELES_MANAGER_MODE", "0")
    project = init_project(tmp_path / "proj", name="proj")
    args = _ns(prompt="research the whole thing thoroughly", provider="openrouter", model="x")
    assert _maybe_run_via_manager(args, project) is False


def test_manager_path_activates_with_flag(
    isolated_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M122f opt-in: `--manager` (args.manager=True) forces the manager path;
    caller builds the worker factory and dispatches. We mock everything past
    the gate to assert the dispatch happened, not that the LLM ran."""
    monkeypatch.delenv("VELES_MANAGER_MODE", raising=False)
    project = init_project(tmp_path / "proj", name="proj")
    args = _ns(
        prompt="research the auth module",
        provider="openrouter",
        model="x",
        max_iterations=10,
        verbose=False,
        manager=True,
    )

    # Stub out everything beyond the gate so the test doesn't hit
    # the LLM. The manager dispatcher itself is fully exercised in
    # `test_orchestration_manager.py` — here we verify the wiring.
    fake_result = MagicMock(
        error=None, final_text="synthesised answer from writer worker"
    )
    monkeypatch.setattr(
        "veles.cli.commands.run.Agent", MagicMock(return_value=MagicMock())
    )

    captured = {}

    def fake_decompose(prompt, *, agent_factory, **kwargs):
        captured["prompt"] = prompt
        captured["agent_factory"] = agent_factory
        return fake_result

    monkeypatch.setattr(
        "veles.core.orchestration.decompose_and_run", fake_decompose
    )
    monkeypatch.setattr("veles.cli._make_provider", lambda _: MagicMock())
    monkeypatch.setattr("veles.cli._build_compressor", lambda *a, **kw: None)
    monkeypatch.setattr("veles.cli._build_run_system_prompt", lambda *a, **kw: "base")
    monkeypatch.setattr("veles.cli._load_skills", lambda *a, **kw: MagicMock())

    result = _maybe_run_via_manager(args, project)
    assert result is True
    assert captured["prompt"] == "research the auth module"
    assert callable(captured["agent_factory"])


def test_manager_path_activates_via_env(
    isolated_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M122f opt-in: `VELES_MANAGER_MODE=1` activates the manager path even
    without the `--manager` flag (and regardless of prompt length/keywords)."""
    monkeypatch.setenv("VELES_MANAGER_MODE", "1")
    project = init_project(tmp_path / "proj", name="proj")
    args = _ns(
        prompt="a short prompt",
        provider="openrouter",
        model="x",
        max_iterations=10,
        verbose=False,
    )

    fake_result = MagicMock(error=None, final_text="done")
    monkeypatch.setattr("veles.cli.commands.run.Agent", MagicMock())
    monkeypatch.setattr(
        "veles.core.orchestration.decompose_and_run",
        lambda *a, **kw: fake_result,
    )
    monkeypatch.setattr("veles.cli._make_provider", lambda _: MagicMock())
    monkeypatch.setattr("veles.cli._build_compressor", lambda *a, **kw: None)
    monkeypatch.setattr("veles.cli._build_run_system_prompt", lambda *a, **kw: "base")
    monkeypatch.setattr("veles.cli._load_skills", lambda *a, **kw: MagicMock())

    assert _maybe_run_via_manager(args, project) is True


def test_manager_failure_returns_false_so_caller_falls_back(
    isolated_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When decompose_and_run errors or returns no output, the helper
    returns False — caller continues with the legacy direct path.
    Manager hiccups never break the user's turn."""
    monkeypatch.delenv("VELES_MANAGER_MODE", raising=False)
    project = init_project(tmp_path / "proj", name="proj")
    args = _ns(
        prompt="research something interesting",
        provider="openrouter",
        model="x",
        max_iterations=10,
        verbose=False,
        manager=True,  # opt-in so we reach decompose and test the fallback
    )

    failed_result = MagicMock(error="provider down", final_text=None)
    monkeypatch.setattr("veles.cli.commands.run.Agent", MagicMock())
    monkeypatch.setattr(
        "veles.core.orchestration.decompose_and_run",
        lambda *a, **kw: failed_result,
    )
    monkeypatch.setattr("veles.cli._make_provider", lambda _: MagicMock())
    monkeypatch.setattr("veles.cli._build_compressor", lambda *a, **kw: None)
    monkeypatch.setattr("veles.cli._build_run_system_prompt", lambda *a, **kw: "base")
    monkeypatch.setattr("veles.cli._load_skills", lambda *a, **kw: MagicMock())

    assert _maybe_run_via_manager(args, project) is False


# ---- should_use_manager wiring ----


def test_should_use_manager_heuristic_flag_still_supported() -> None:
    """The `should_use_manager` *function* still supports an opt-in heuristic
    mode (callers may pass `use_heuristic_default=True`). M122f production
    wiring no longer uses it (opt-in via flag/env), but the capability stays."""
    from veles.core.orchestration import should_use_manager

    long = "research and compare " * 10
    assert should_use_manager(long, use_heuristic_default=True) is True


def test_should_use_manager_kill_switch_overrides_heuristic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`VELES_MANAGER_MODE=0` beats heuristic — explicit user opt-out
    always wins."""
    from veles.core.orchestration import should_use_manager

    monkeypatch.setenv("VELES_MANAGER_MODE", "0")
    assert should_use_manager("research a thing", use_heuristic_default=True) is False


def test_should_use_manager_short_prompts_skip_even_with_heuristic() -> None:
    """Heuristic stays conservative: short prompts without keywords
    don't trigger manager — they're cheaper as single-shot."""
    from veles.core.orchestration import should_use_manager

    assert should_use_manager("short", use_heuristic_default=True) is False
