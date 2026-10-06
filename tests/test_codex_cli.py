"""codex as a CLI delegate: a locked-down model, Veles' tools over MCP (spike:
docs/superpowers/specs/2026-10-06-codex-spike.md)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

from veles.adapters.cli import codex_cli
from veles.adapters.cli.codex_cli import CodexCLIProvider
from veles.core.provider import Message

_FIX = Path(__file__).parent / "fixtures" / "codex"


@dataclass
class _Proc:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@pytest.fixture(autouse=True)
def _fresh_probe(monkeypatch: pytest.MonkeyPatch):
    codex_cli.lockdown_flags.cache_clear()
    monkeypatch.setattr(shutil, "which", lambda _n: "/usr/local/bin/codex")
    yield
    codex_cli.lockdown_flags.cache_clear()


def _codex(monkeypatch, *, run_out: str = "", rc: int = 0, unknown: tuple[str, ...] = ()):
    """subprocess.run: `codex features list` rejects names in `unknown`; `exec` answers
    `run_out`; records every command."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        if cmd[1:3] == ["features", "list"]:
            bad = [f for f in unknown if f in cmd]
            if bad:
                return _Proc(1, "", f"Error: Unknown feature flag: {bad[0]}")
            return _Proc(0, "shell_tool  stable  false\n", "")
        return _Proc(rc, run_out, "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def _ask(prov: CodexCLIProvider, text: str = "hi"):
    return prov.create_message([Message(role="user", content=text)], model="gpt-6-luna")


def test_the_command_is_headless_and_locked_down(monkeypatch, tmp_path: Path) -> None:
    calls = _codex(monkeypatch, run_out=(_FIX / "answer.jsonl").read_text())
    reply = _ask(CodexCLIProvider(workspace=tmp_path), "--looks like a flag")
    cmd = calls[-1]
    assert cmd[:2] == ["codex", "exec"]
    for flag in ("--json", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check"):
        assert flag in cmd
    assert cmd[cmd.index("-s") + 1] == "read-only"
    disabled = {cmd[i + 1] for i, a in enumerate(cmd) if a == "--disable"}
    assert {"shell_tool", "unified_exec", "view_image", "multi_agent"} <= disabled
    assert 'web_search="disabled"' in cmd
    assert cmd[cmd.index("-m") + 1] == "gpt-6-luna"
    assert cmd[-2] == "--" and "--looks like a flag" in cmd[-1]  # prompt after `--`
    assert reply.text == "Hi there, friend." and reply.finish_reason == "stop"
    assert reply.usage.prompt_tokens == 12843 and reply.usage.cache_read_tokens == 11008
    assert reply.usage.completion_tokens == 9


def _disabled(cmd: list[str]) -> set[str]:
    return {cmd[i + 1] for i, a in enumerate(cmd) if a == "--disable"}


def test_code_mode_only_where_the_bridge_needs_it(monkeypatch, tmp_path: Path) -> None:
    """Chat: no code mode, so codex answers in Veles' fenced `veles-tool` blocks instead
    of reaching for its own exec (live smoke, 2026-10-06). Bridge: code mode stays —
    codex calls MCP tools through it."""
    calls = _codex(monkeypatch, run_out=(_FIX / "answer.jsonl").read_text())
    _ask(CodexCLIProvider(workspace=tmp_path))
    assert "code_mode_host" in _disabled(calls[-1])
    _ask(CodexCLIProvider(workspace=tmp_path, mcp_server={"command": "/py", "args": []}))
    assert "code_mode_host" not in _disabled(calls[-1])


def test_the_fenced_protocol_gets_a_preamble_in_chat_only(monkeypatch, tmp_path: Path) -> None:
    """codex reaches for its own (disabled) exec instead of writing a `veles-tool` block
    unless told plainly — live: 0/3 without, 3/5 with (2026-10-06)."""
    from veles.core.fenced_tools import FENCED_SENTINEL

    calls = _codex(monkeypatch, run_out=(_FIX / "answer.jsonl").read_text())
    fenced = [
        Message(role="system", content=f"{FENCED_SENTINEL}\nuse ```veles-tool blocks"),
        Message(role="user", content="read NOTES.txt"),
    ]
    CodexCLIProvider(workspace=tmp_path).create_message(fenced, model="m")
    assert calls[-1][-1].startswith("Your `exec` tool and every other built-in tool")
    _ask(CodexCLIProvider(workspace=tmp_path))  # no fenced protocol in the prompt
    assert not calls[-1][-1].startswith("Your `exec`")
    bridge = CodexCLIProvider(workspace=tmp_path, mcp_server={"command": "/py", "args": []})
    bridge.create_message(fenced, model="m")
    assert not calls[-1][-1].startswith("Your `exec`")


def test_a_renamed_critical_feature_refuses(monkeypatch, tmp_path: Path) -> None:
    _codex(monkeypatch, unknown=("shell_tool",))
    with pytest.raises(RuntimeError, match="shell_tool"):
        _ask(CodexCLIProvider(workspace=tmp_path))


def test_a_renamed_minor_feature_is_dropped_with_a_warning(monkeypatch, tmp_path, capsys) -> None:
    calls = _codex(monkeypatch, run_out=(_FIX / "answer.jsonl").read_text(), unknown=("goals",))
    _ask(CodexCLIProvider(workspace=tmp_path))
    run = calls[-1]
    assert "goals" not in run and "shell_tool" in run
    assert "goals" in capsys.readouterr().err


def test_every_message_is_kept(monkeypatch, tmp_path: Path) -> None:
    _codex(monkeypatch, run_out=(_FIX / "bridge.jsonl").read_text())
    reply = _ask(CodexCLIProvider(workspace=tmp_path))
    assert "locate the Veles MCP read_file tool" in reply.text.split("\n\n")[0]
    assert reply.text.endswith("secret-line\n```")


def test_not_logged_in_says_codex_login(monkeypatch, tmp_path: Path) -> None:
    _codex(monkeypatch, run_out=(_FIX / "not_logged_in.jsonl").read_text(), rc=1)
    reply = _ask(CodexCLIProvider(workspace=tmp_path))
    assert reply.finish_reason == "error"
    assert "401" in reply.text and "codex login" in reply.text


def test_a_bad_model_is_an_error(monkeypatch, tmp_path: Path) -> None:
    _codex(monkeypatch, run_out=(_FIX / "bad_model.jsonl").read_text(), rc=1)
    reply = _ask(CodexCLIProvider(workspace=tmp_path))
    assert reply.finish_reason == "error" and "nope-model" in reply.text
    assert "codex login" not in reply.text


def _mcp_values(cmd: list[str]) -> dict[str, object]:
    out: dict[str, object] = {}
    for i, a in enumerate(cmd):
        if a == "-c" and cmd[i + 1].startswith("mcp_servers.veles."):
            key, _, value = cmd[i + 1].partition("=")
            out[key.removeprefix("mcp_servers.veles.")] = tomllib.loads(f"v = {value}")["v"]
    return out


def test_the_bridge_is_in_arguments_only(monkeypatch, tmp_path: Path) -> None:
    calls = _codex(monkeypatch, run_out=(_FIX / "answer.jsonl").read_text())
    server = {"command": "/py", "args": ["-m", "veles.adapters.cli.mcp_server"]}
    prov = CodexCLIProvider(workspace=tmp_path, mcp_server=server)
    assert prov.supports_tools
    _ask(prov)
    values = _mcp_values(calls[-1])
    assert values["command"] == "/py" and values["args"] == server["args"]
    assert values["default_tools_approval_mode"] == "approve"
    assert values["tool_timeout_sec"] == 300
    assert prov.qualify_prompt("use read_file", ("read_file",)) == "use mcp__veles__read_file"


def test_mcp_args_survive_spaces_and_quotes(monkeypatch, tmp_path: Path) -> None:
    calls = _codex(monkeypatch, run_out=(_FIX / "answer.jsonl").read_text())
    odd = ["--project-root", '/p/my "proj" dir', "--budget-file", "/p/b\\x.json"]
    _ask(CodexCLIProvider(workspace=tmp_path, mcp_server={"command": "/py", "args": odd}))
    assert _mcp_values(calls[-1])["args"] == odd


def test_the_bridge_forwards_env_by_name_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret")
    monkeypatch.setenv("VELES_TRUST_AUTO_ALLOW", "1")
    calls = _codex(monkeypatch, run_out=(_FIX / "answer.jsonl").read_text())
    _ask(CodexCLIProvider(workspace=tmp_path, mcp_server={"command": "/py", "args": []}))
    names = _mcp_values(calls[-1])["env_vars"]
    assert isinstance(names, list)
    wanted = {"VELES_USER_HOME", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "TAVILY_API_KEY"}
    assert wanted <= set(names)
    assert "VELES_TRUST_AUTO_ALLOW" not in names and "VELES_DAEMON_TOKEN" not in names
    assert not any("sk-or-secret" in a for a in calls[-1])


def test_no_bridge_without_a_server(monkeypatch, tmp_path: Path) -> None:
    calls = _codex(monkeypatch, run_out=(_FIX / "answer.jsonl").read_text())
    prov = CodexCLIProvider(workspace=tmp_path)
    _ask(prov)
    assert not prov.supports_tools and not _mcp_values(calls[-1])


def test_runs_in_its_workspace(monkeypatch, tmp_path: Path) -> None:
    seen: dict = {}
    _codex(monkeypatch, run_out=(_FIX / "answer.jsonl").read_text())
    original = subprocess.run

    def spy(cmd, **kw):
        seen["cwd"] = kw.get("cwd")
        return original(cmd, **kw)

    monkeypatch.setattr(subprocess, "run", spy)
    _ask(CodexCLIProvider(workspace=tmp_path / "ws"))
    assert seen["cwd"] == str(tmp_path / "ws")


def test_models_come_from_codex_debug_models(monkeypatch, tmp_path: Path) -> None:
    catalog = {
        "models": [
            {"slug": "gpt-6-luna", "visibility": "list"},
            {"slug": "gpt-reserve", "visibility": "hide"},
            {"slug": "gpt-5.6-terra", "visibility": "list"},
        ]
    }

    def fake_run(cmd, **kw):
        assert cmd[1:] == ["debug", "models"] and kw["cwd"] == str(tmp_path)
        return _Proc(0, json.dumps(catalog), "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert CodexCLIProvider(workspace=tmp_path).list_models() == ["gpt-6-luna", "gpt-5.6-terra"]


def test_models_fail_soft(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Proc(1, "", "boom"))
    assert CodexCLIProvider(workspace=tmp_path).list_models() == []


def test_the_catalogue_builds_codex_outside_the_project(tmp_path: Path, isolated_user_home) -> None:
    from veles.core.delegate_dir import delegate_workspace
    from veles.core.project import init_project
    from veles.core.provider_factory import make_provider
    from veles.core.providers import find_provider
    from veles.runtime.registry import make_tool_aware_provider

    project = init_project(tmp_path / "p", name="p")
    spec = find_provider("codex")
    assert spec is not None and spec.wire == "cli" and not spec.needs_key
    chat = make_provider("codex")
    tooled = make_tool_aware_provider("codex", project)
    assert not chat.supports_tools and tooled.supports_tools
    assert Path(tooled._cwd()) == delegate_workspace(project, "codex")
    assert not Path(tooled._cwd()).is_relative_to(project.root)
