"""M186 prototype: `veles repl` — inline streaming REPL.

These cover the testable seams (slash dispatch, the streaming turn, parser
wiring). The interactive prompt_toolkit loop itself isn't unit-driven; the
turn path is exercised through `_run_turn` with a fake agent.
"""

from __future__ import annotations

import argparse

import pytest

from veles.cli.commands.repl import _dispatch_slash, _run_turn
from veles.core.agent import RunResult


@pytest.mark.parametrize(
    "line,expected",
    [
        ("hello there", "run"),
        ("  not a slash", "run"),  # already stripped by caller, but be safe
        ("/help", "help"),
        ("/quit", "quit"),
        ("/exit", "quit"),
        ("/QUIT", "quit"),
        ("/clear", "clear"),
        ("/quit now", "quit"),
        ("/bogus", "unknown"),
    ],
)
def test_dispatch_slash(line: str, expected: str) -> None:
    assert _dispatch_slash(line) == expected


class _FakeAgent:
    """Minimal stand-in: streams two deltas then returns a completed result."""

    _session_id = "s1"

    def run(self, prompt, *, on_text_delta=None, event_listener=None):
        if on_text_delta is not None:
            on_text_delta("hello ")
            on_text_delta("world")
        return RunResult(
            text="hello world", iterations=1, stopped_reason="completed", session_id="s1"
        )


def _args() -> argparse.Namespace:
    return argparse.Namespace(stream=True, max_tokens_total=0, provider="openrouter")


def test_run_turn_streams_answer_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    _run_turn(_FakeAgent(), "hi", _args())
    out = capsys.readouterr().out
    assert "assistant>" in out
    assert "hello world" in out


def test_run_turn_survives_provider_error(capsys: pytest.CaptureFixture[str]) -> None:
    from veles.core.provider import ProviderError

    class _Boom:
        _session_id = "s1"

        def run(self, *_a, **_kw):
            raise ProviderError("upstream 503")

    _run_turn(_Boom(), "hi", _args())
    err = capsys.readouterr().err
    assert "upstream 503" in err  # printed, not raised — REPL stays alive


def test_repl_command_registered() -> None:
    from veles.cli._parsers.agent_loop import register

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register(sub)
    assert "repl" in sub.choices
    ns = parser.parse_args(["repl", "--resume", "abc"])
    assert ns.command == "repl"
    assert ns.resume == "abc"
