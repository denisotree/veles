"""Unit tests for GeminiCLIProvider — no real gemini subprocess."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

import pytest

from veles.adapters.cli.gemini_cli import GeminiCLIProvider
from veles.core.provider import Message, StreamEnd, TextDelta


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
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/gemini")


def test_provider_supports_tools_is_false() -> None:
    p = GeminiCLIProvider()
    assert p.supports_tools is False
    assert p.supports_streaming is True
    assert p.name == "gemini-cli"


def test_provider_raises_when_binary_missing(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    p = GeminiCLIProvider()
    with pytest.raises(RuntimeError, match="not found in PATH"):
        p.create_message([Message(role="user", content="hi")], model="m")


def test_create_message_passes_prompt_via_p_flag(monkeypatch) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout="hello\n")
    p = GeminiCLIProvider()
    p.create_message([Message(role="user", content="ping")], model="gemini-2.5-flash")
    assert "-p" in captured["cmd"]
    p_idx = captured["cmd"].index("-p")
    assert "ping" in captured["cmd"][p_idx + 1]


def test_create_message_passes_model_when_given(monkeypatch) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout="ok")
    p = GeminiCLIProvider()
    p.create_message([Message(role="user", content="x")], model="gemini-2.5-pro")
    assert "--model" in captured["cmd"]
    m_idx = captured["cmd"].index("--model")
    assert captured["cmd"][m_idx + 1] == "gemini-2.5-pro"


def test_create_message_does_not_pass_stream_json_format(monkeypatch) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout="ok")
    p = GeminiCLIProvider()
    p.create_message([Message(role="user", content="x")], model="m")
    assert "--output-format" not in captured["cmd"]
    assert "stream-json" not in captured["cmd"]


def test_create_message_returns_stripped_stdout(monkeypatch) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout="\n\nhello world\n\n")
    p = GeminiCLIProvider()
    resp = p.create_message([Message(role="user", content="x")], model="m")
    assert resp.text == "hello world"
    assert resp.tool_calls == []
    assert resp.finish_reason == "stop"


def test_create_message_warns_and_ignores_tools(monkeypatch, capsys) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout="ok")
    p = GeminiCLIProvider()
    resp = p.create_message(
        [Message(role="user", content="x")],
        tools=[{"type": "function", "function": {"name": "fake"}}],
        model="m",
    )
    assert resp.tool_calls == []
    err = capsys.readouterr().err
    assert "gemini-cli does not support custom tools" in err


def test_create_message_raises_on_nonzero_exit(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        return _FakeProc(returncode=2, stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/gemini")
    p = GeminiCLIProvider()
    with pytest.raises(RuntimeError, match=r"exited 2.*boom"):
        p.create_message([Message(role="user", content="x")], model="m")


def test_create_message_includes_extra_args(monkeypatch) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout="ok")
    p = GeminiCLIProvider(extra_args=("--quiet", "--no-emoji"))
    p.create_message([Message(role="user", content="x")], model="m")
    assert "--quiet" in captured["cmd"]
    assert "--no-emoji" in captured["cmd"]


def test_stream_message_emits_text_deltas_and_stream_end(monkeypatch) -> None:
    events_lines = [
        '{"type":"init","session_id":"s1","model":"m"}\n',
        '{"type":"message","role":"user","content":"hi"}\n',
        '{"type":"message","role":"assistant","content":"hello ","delta":true}\n',
        '{"type":"message","role":"assistant","content":"world","delta":true}\n',
    ]
    _patch_streaming_popen(monkeypatch, events_lines)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/gemini")
    p = GeminiCLIProvider()
    out = list(p.stream_message([Message(role="user", content="x")], model="m"))
    deltas = [e for e in out if isinstance(e, TextDelta)]
    ends = [e for e in out if isinstance(e, StreamEnd)]
    assert [d.text for d in deltas] == ["hello ", "world"]
    assert len(ends) == 1
    assert ends[0].response.text == "hello world"


def test_stream_message_passes_stream_json_format_flag(monkeypatch) -> None:
    captured: dict = {}
    _patch_streaming_popen(monkeypatch, [], capture=captured)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/gemini")
    p = GeminiCLIProvider()
    list(p.stream_message([Message(role="user", content="x")], model="m"))
    assert "--output-format" in captured["cmd"]
    fmt_idx = captured["cmd"].index("--output-format")
    assert captured["cmd"][fmt_idx + 1] == "stream-json"


def test_stream_message_uses_cwd_when_mcp_settings_dir_given(monkeypatch, tmp_path) -> None:
    captured: dict = {}
    _patch_streaming_popen(monkeypatch, [], capture=captured)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/gemini")
    p = GeminiCLIProvider(mcp_settings_dir=tmp_path)
    list(p.stream_message([Message(role="user", content="x")], model="m"))
    assert captured["kwargs"].get("cwd") == str(tmp_path)


def _patch_streaming_popen(
    monkeypatch,
    lines: list[str],
    *,
    returncode: int = 0,
    capture: dict | None = None,
) -> None:
    import io

    class _FakePopen:
        def __init__(self, cmd, **kwargs) -> None:
            if capture is not None:
                capture["cmd"] = list(cmd)
                capture["kwargs"] = kwargs
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

    monkeypatch.setattr(subprocess, "Popen", _FakePopen)


def test_supports_tools_property_reflects_mcp_settings(tmp_path) -> None:
    p_no = GeminiCLIProvider()
    assert p_no.supports_tools is False
    p_yes = GeminiCLIProvider(mcp_settings_dir=tmp_path)
    assert p_yes.supports_tools is True


def test_create_message_runs_with_cwd_when_mcp_settings_dir_given(monkeypatch, tmp_path) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout="ok")
    p = GeminiCLIProvider(mcp_settings_dir=tmp_path)
    p.create_message([Message(role="user", content="x")], model="m")
    assert captured["kwargs"].get("cwd") == str(tmp_path)


def test_create_message_passes_mcp_flags_when_mcp_wired(monkeypatch, tmp_path) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout="ok")
    p = GeminiCLIProvider(mcp_settings_dir=tmp_path)
    p.create_message([Message(role="user", content="x")], model="m")
    cmd = captured["cmd"]
    assert "--allowed-mcp-server-names" in cmd
    idx = cmd.index("--allowed-mcp-server-names")
    assert cmd[idx + 1] == "veles"
    assert "--yolo" in cmd


def test_create_message_omits_mcp_flags_when_no_mcp(monkeypatch) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout="ok")
    p = GeminiCLIProvider()
    p.create_message([Message(role="user", content="x")], model="m")
    cmd = captured["cmd"]
    assert "--allowed-mcp-server-names" not in cmd
    assert "--yolo" not in cmd


def test_stream_message_passes_mcp_flags_when_mcp_wired(monkeypatch, tmp_path) -> None:
    captured: dict = {}
    _patch_streaming_popen(monkeypatch, [], capture=captured)
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/gemini")
    p = GeminiCLIProvider(mcp_settings_dir=tmp_path)
    list(p.stream_message([Message(role="user", content="x")], model="m"))
    cmd = captured["cmd"]
    assert "--allowed-mcp-server-names" in cmd
    assert "--yolo" in cmd


def test_tools_warning_suppressed_when_mcp_settings_dir_present(
    monkeypatch, tmp_path, capsys
) -> None:
    captured: dict = {}
    _patch_run(monkeypatch, captured, stdout="ok")
    p = GeminiCLIProvider(mcp_settings_dir=tmp_path)
    p.create_message(
        [Message(role="user", content="x")],
        tools=[{"type": "function", "function": {"name": "fake"}}],
        model="m",
    )
    err = capsys.readouterr().err
    assert "does not support custom tools" not in err
