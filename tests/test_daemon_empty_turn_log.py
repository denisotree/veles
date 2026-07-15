"""M214 (B3) — a blank-turn finalization is surfaced in the daemon log.

B2 forces one answer round; reaching stopped_reason='empty' means the model
stayed mute even after the nudge. That must be observable (the #2/#3 class), not
silent — so the daemon emits a WARNING.
"""

from __future__ import annotations

from veles.core.agent import RunResult
from veles.daemon.runner import RunHandle, run_agent_in_background


class _EmptyAgent:
    def run(self, prompt, on_text_delta=None):
        return RunResult(text="", iterations=2, stopped_reason="empty", session_id="s1")


class _OkAgent:
    def run(self, prompt, on_text_delta=None):
        return RunResult(text="done", iterations=1, stopped_reason="completed", session_id="s1")


async def test_empty_turn_emits_warning(caplog):
    handle = RunHandle(run_id="run-empty", session_id="s1")
    with caplog.at_level("WARNING", logger="veles.daemon"):
        await run_agent_in_background(handle, agent=_EmptyAgent(), prompt="hi")
    assert handle.stopped_reason == "empty"
    assert any("EMPTY answer" in r.getMessage() for r in caplog.records)


async def test_completed_turn_does_not_warn(caplog):
    handle = RunHandle(run_id="run-ok", session_id="s1")
    with caplog.at_level("WARNING", logger="veles.daemon"):
        await run_agent_in_background(handle, agent=_OkAgent(), prompt="hi")
    assert handle.stopped_reason == "completed"
    assert not any("EMPTY answer" in r.getMessage() for r in caplog.records)
