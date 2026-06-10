"""Unit tests for ClaudeCLIProvider — no real claude subprocess."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

import pytest

from veles.adapters.cli.claude_cli import (
    ClaudeCLIProvider,
    _format_messages_as_prompt,
    _parse_stream,
)
from veles.core.provider import Message


@dataclass
class _FakeProc:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


def _patch_run(monkeypatch, captured: dict, stdout: str = "", returncode: int = 0):
    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        captured["kwargs"] = kwargs
        return _FakeProc(returncode=returncode, stdout=stdout)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/claude")


def test_provider_supports_tools_is_false() -> None:
    p = ClaudeCLIProvider()
    assert p.supports_tools is False
    assert p.name == "claude-cli"


def test_provider_raises_when_binary_missing(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    p = ClaudeCLIProvider()
    with pytest.raises(RuntimeError, match="not found in PATH"):
        p.create_message([Message(role="user", content="hi")], model="m")


def test_create_message_passes_prompt_via_p_flag(monkeypatch) -> None:
    captured: dict = {}
    _patch_run(
        monkeypatch,
        captured,
        stdout='{"type":"result","subtype":"success","result":"ok"}\n',
    )
    p = ClaudeCLIProvider()
    p.create_message([Message(role="user", content="hello world")], model="claude-sonnet-4.6")
    assert "-p" in captured["cmd"]
    p_idx = captured["cmd"].index("-p")
    assert "hello world" in captured["cmd"][p_idx + 1]


def test_create_message_uses_stream_json_format(monkeypatch) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout='{"type":"result","result":"x"}\n')
    p = ClaudeCLIProvider()
    p.create_message([Message(role="user", content="x")], model="m")
    assert "--output-format" in captured["cmd"]
    fmt_idx = captured["cmd"].index("--output-format")
    assert captured["cmd"][fmt_idx + 1] == "stream-json"
    assert "--verbose" in captured["cmd"]


def test_create_message_passes_model_when_given(monkeypatch) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout='{"type":"result","result":"x"}\n')
    p = ClaudeCLIProvider()
    p.create_message([Message(role="user", content="x")], model="claude-haiku-4.5")
    assert "--model" in captured["cmd"]
    m_idx = captured["cmd"].index("--model")
    assert captured["cmd"][m_idx + 1] == "claude-haiku-4.5"


def test_parse_stream_returns_result_event_text() -> None:
    stdout = (
        '{"type":"system","subtype":"init"}\n'
        '{"type":"result","subtype":"success","result":"hello there"}\n'
    )
    text, usage = _parse_stream(stdout)
    assert text == "hello there"
    assert usage.total_tokens == 0


def test_parse_stream_falls_back_to_assistant_text() -> None:
    stdout = (
        '{"type":"system","subtype":"init"}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"part1 "}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"part2"}]}}\n'
    )
    text, _ = _parse_stream(stdout)
    assert text == "part1 part2"


def test_parse_stream_skips_invalid_json_lines() -> None:
    stdout = 'garbage line\n{"type":"result","result":"clean"}\nanother garbage\n'
    text, _ = _parse_stream(stdout)
    assert text == "clean"


def test_parse_stream_extracts_token_usage() -> None:
    stdout = '{"type":"result","result":"hi","usage":{"input_tokens":10,"output_tokens":5}}\n'
    text, usage = _parse_stream(stdout)
    assert text == "hi"
    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 5
    assert usage.total_tokens == 15


def test_create_message_warns_and_ignores_tools(monkeypatch, capsys) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout='{"type":"result","result":"x"}\n')
    p = ClaudeCLIProvider()
    resp = p.create_message(
        [Message(role="user", content="x")],
        tools=[{"type": "function", "function": {"name": "fake_tool"}}],
        model="m",
    )
    assert resp.tool_calls == []
    err = capsys.readouterr().err
    assert "claude-cli does not support custom tools" in err


def test_create_message_raises_on_nonzero_exit(monkeypatch) -> None:
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return _FakeProc(returncode=1, stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/claude")
    p = ClaudeCLIProvider()
    with pytest.raises(RuntimeError, match=r"exited 1.*boom"):
        p.create_message([Message(role="user", content="x")], model="m")


def test_supports_tools_property_reflects_mcp_config(tmp_path) -> None:
    p_no = ClaudeCLIProvider()
    assert p_no.supports_tools is False
    p_yes = ClaudeCLIProvider(mcp_config_path=tmp_path / "mcp.json")
    assert p_yes.supports_tools is True


def test_create_message_passes_mcp_config_when_given(monkeypatch, tmp_path) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout='{"type":"result","result":"ok"}\n')
    cfg = tmp_path / "mcp.json"
    cfg.write_text("{}")
    p = ClaudeCLIProvider(mcp_config_path=cfg)
    p.create_message([Message(role="user", content="x")], model="m")
    assert "--mcp-config" in captured["cmd"]
    idx = captured["cmd"].index("--mcp-config")
    assert captured["cmd"][idx + 1] == str(cfg)


def test_tools_warning_suppressed_when_mcp_config_present(monkeypatch, tmp_path, capsys) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout='{"type":"result","result":"ok"}\n')
    cfg = tmp_path / "mcp.json"
    cfg.write_text("{}")
    p = ClaudeCLIProvider(mcp_config_path=cfg)
    p.create_message(
        [Message(role="user", content="x")],
        tools=[{"type": "function", "function": {"name": "fake"}}],
        model="m",
    )
    err = capsys.readouterr().err
    assert "does not support custom tools" not in err


def test_supports_streaming_is_true() -> None:
    assert ClaudeCLIProvider().supports_streaming is True


def test_stream_message_emits_text_deltas_and_stream_end(monkeypatch) -> None:
    from veles.core.provider import StreamEnd, TextDelta

    events = [
        '{"type":"system","subtype":"init"}\n',
        '{"type":"assistant","message":{"content":[{"type":"text","text":"hello "}]}}\n',
        '{"type":"assistant","message":{"content":[{"type":"text","text":"world"}]}}\n',
        '{"type":"result","subtype":"success","result":"hello world",'
        '"usage":{"input_tokens":3,"output_tokens":2}}\n',
    ]
    _patch_streaming_popen(monkeypatch, events)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/claude")
    p = ClaudeCLIProvider()
    out = list(p.stream_message([Message(role="user", content="hi")], model="m"))
    deltas = [e for e in out if isinstance(e, TextDelta)]
    ends = [e for e in out if isinstance(e, StreamEnd)]
    assert [d.text for d in deltas] == ["hello ", "world"]
    assert len(ends) == 1
    resp = ends[0].response
    assert resp.text == "hello world"
    assert resp.usage.prompt_tokens == 3
    assert resp.usage.completion_tokens == 2
    assert resp.usage.total_tokens == 5


def test_stream_message_yields_stream_end_even_when_no_result_event(monkeypatch) -> None:
    from veles.core.provider import StreamEnd, TextDelta

    events = [
        '{"type":"assistant","message":{"content":[{"type":"text","text":"partial"}]}}\n',
    ]
    _patch_streaming_popen(monkeypatch, events)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/claude")
    p = ClaudeCLIProvider()
    out = list(p.stream_message([Message(role="user", content="x")], model="m"))
    assert any(isinstance(e, TextDelta) and e.text == "partial" for e in out)
    ends = [e for e in out if isinstance(e, StreamEnd)]
    assert len(ends) == 1
    assert ends[0].response.text == "partial"


def _patch_streaming_popen(monkeypatch, lines: list[str], returncode: int = 0) -> None:
    import io

    class _FakePopen:
        def __init__(self) -> None:
            self.stdout = io.StringIO("".join(lines))
            self.stderr = io.StringIO("")
            self.returncode = returncode
            self._rc = returncode

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = self._rc
            return self._rc

        def poll(self) -> int | None:
            return self._rc

        def terminate(self) -> None:
            pass

        def kill(self) -> None:
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: _FakePopen())


def test_format_messages_handles_all_roles() -> None:
    msgs = [
        Message(role="system", content="be helpful"),
        Message(role="user", content="hi"),
        Message(role="assistant", content="hello"),
        Message(role="tool", content="should-not-appear", tool_call_id="t1"),
    ]
    out = _format_messages_as_prompt(msgs)
    assert "# System" in out
    assert "be helpful" in out
    assert "# User" in out
    assert "hi" in out
    assert "# Assistant" in out
    assert "hello" in out
    assert "should-not-appear" not in out
