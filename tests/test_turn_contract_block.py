"""M214 (B1) — the turn-completion contract sits in the stable system prompt.

The model must be told that a turn ends the moment it replies without tool
calls, so a prose promise of deferred work never executes — do it now or
schedule a reminder. Stable (cacheable), so it belongs BEFORE the cache
breakpoint.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import init_project


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return init_project(tmp_path / "p", name="p")


def test_turn_contract_present_and_stable(project) -> None:
    from veles.cli._runtime import build_run_system_prompt
    from veles.core.cache_hints import CACHE_BREAKPOINT_SENTINEL

    prompt = build_run_system_prompt(project, prompt="hi")
    assert prompt is not None
    assert "Turn-completion contract:" in prompt
    assert "task_add" in prompt
    # It's invariant → must be in the stable (cached) prefix, not volatile.
    stable, _volatile = prompt.split(CACHE_BREAKPOINT_SENTINEL, 1)
    assert "Turn-completion contract:" in stable
