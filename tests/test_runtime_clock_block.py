"""M208 — the volatile runtime clock block anchors the model's calendar.

Without a clock in context the model resolves "tomorrow at 11:00" from
training-data priors (a real Telegram reminder landed in the previous year).
The block is volatile — after the cache breakpoint — so its per-minute churn
never fragments the stable prefix.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from veles.core.project import init_project


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return init_project(tmp_path / "p", name="p")


def test_clock_block_always_present(project) -> None:
    from veles.cli._runtime import build_run_system_prompt

    before = _dt.datetime.now(tz=_dt.UTC)
    prompt = build_run_system_prompt(project, prompt="remind me tomorrow")
    after = _dt.datetime.now(tz=_dt.UTC)

    assert prompt is not None
    assert "<runtime-context>" in prompt
    # Date assertion tolerant of a midnight rollover mid-test.
    dates = {before.strftime("%Y-%m-%d"), after.strftime("%Y-%m-%d")}
    assert any(d in prompt for d in dates)


def test_clock_block_is_volatile_not_stable(project) -> None:
    """The clock must sit AFTER the cache breakpoint — a per-minute timestamp
    in the stable prefix would fragment the prompt cache every turn."""
    from veles.cli._runtime import build_run_system_prompt
    from veles.core.cache_hints import CACHE_BREAKPOINT_SENTINEL

    prompt = build_run_system_prompt(project, prompt="hi")
    assert prompt is not None
    assert CACHE_BREAKPOINT_SENTINEL in prompt
    _stable, volatile = prompt.split(CACHE_BREAKPOINT_SENTINEL, 1)
    assert "<runtime-context>" in volatile
    assert "<runtime-context>" not in _stable
