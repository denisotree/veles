"""The CLI-delegate base: stdin is /dev/null, and a CLI that reports its own
error in its event stream is heard even when it exits non-zero."""

from __future__ import annotations

import io
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

import pytest

from veles.adapters.cli._common import CLIProvider
from veles.core.provider import Message, ProviderResponse, StreamEnd, TokenUsage


@dataclass
class _State:
    text: str = ""
    error: str | None = None

    def absorb(self, event: dict[str, Any]) -> str:
        if event.get("type") == "msg":
            self.text += event["text"]
            return event["text"]
        if event.get("type") == "failed":
            self.error = event["message"]
        return ""

    def to_response(self, *, raw: Any) -> ProviderResponse:
        text = self.text or (f"<fake error: {self.error}>" if self.error else "")
        reason = "error" if self.error else "stop"
        return ProviderResponse(text=text, tool_calls=[], usage=TokenUsage(), finish_reason=reason)


class _Fake(CLIProvider):
    name = "fake"

    def __init__(self) -> None:
        super().__init__(binary="fake", timeout=5, extra_args=(), tools_config=None)

    def _build_cmd(self, messages, model, *, stream):  # type: ignore[override]
        return ["fake", "go"]

    def _new_state(self) -> _State:
        return _State()


@dataclass
class _Proc:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@pytest.fixture(autouse=True)
def _binary_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/fake")


def test_run_gives_the_cli_no_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return _Proc(stdout='{"type":"msg","text":"hi"}\n')

    monkeypatch.setattr(subprocess, "run", fake_run)
    _Fake().create_message([Message(role="user", content="x")], model="m")
    assert seen["stdin"] is subprocess.DEVNULL


def test_a_reported_error_beats_a_bare_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    out = '{"type":"failed","message":"401 Unauthorized"}\n'
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Proc(1, out, "noise"))
    reply = _Fake().create_message([Message(role="user", content="x")], model="m")
    assert reply.finish_reason == "error" and "401 Unauthorized" in (reply.text or "")


def test_an_exit_code_without_events_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Proc(1, "", "boom"))
    with pytest.raises(RuntimeError, match=r"exited 1.*boom"):
        _Fake().create_message([Message(role="user", content="x")], model="m")


def test_streaming_keeps_the_reported_error(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = '{"type":"failed","message":"401 Unauthorized"}\n'
    seen: dict = {}

    class _Popen:
        def __init__(self, *a, **kw) -> None:
            seen.update(kw)
            self.stdout = io.StringIO(lines)
            self.stderr = io.StringIO("stderr noise")
            self.returncode = 1

        def wait(self, timeout=None) -> int:
            return 1

        def poll(self) -> int:
            return 1

        def terminate(self) -> None: ...

        def kill(self) -> None: ...

    monkeypatch.setattr(subprocess, "Popen", _Popen)
    events = list(_Fake().stream_message([Message(role="user", content="x")], model="m"))
    end = next(e for e in events if isinstance(e, StreamEnd))
    assert "401 Unauthorized" in (end.response.text or "")
    assert seen["stdin"] is subprocess.DEVNULL
