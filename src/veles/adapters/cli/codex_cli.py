"""Codex CLI adapter — `codex exec --json` as a CLI delegate (release G).

codex is only the model. It runs in `delegate_workspace(project, "codex")`, outside
the project, with the user's codex config ignored (`--ignore-user-config`), no session
files (`--ephemeral`), a read-only sandbox and its own tools switched off by feature
flags — shell, exec, images, subagents, browser, plugins, web search. The feature
names are checked once per process (`lockdown_flags`): a renamed critical one stops
the provider instead of leaving that tool on. Code mode stays only with the bridge:
codex reaches MCP tools through it (its JavaScript has no file, network or process
access); without the bridge it is off too, so codex answers in Veles' fenced blocks.

The tool-aware build passes Veles' MCP server in `-c` arguments only — no config file
for the agent to rewrite — approves just that server's tools, and forwards the env it
needs by name (codex hands MCP servers a 12-variable environment).
"""

from __future__ import annotations

import functools
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veles.adapters.cli._common import CLIProvider, format_messages_as_prompt
from veles.adapters.cli._tool_namespace import claude_mcp_prefix
from veles.core.fenced_tools import FENCED_SENTINEL
from veles.core.provider import Message, ProviderResponse, TokenUsage

# Disabled on every run; the first three would let codex read or run outside Veles.
_CRITICAL = ("shell_tool", "unified_exec", "view_image")
_LOCKDOWN = (
    *_CRITICAL,
    "multi_agent",
    "goals",
    "plugins",
    "apps",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "image_generation",
    "tool_suggest",
    "skill_search",
    "sleep_tool",
    "skill_mcp_dependency_install",
)
_UNKNOWN = "Unknown feature flag: "
# Without it codex reaches for its own (disabled) exec instead of writing Veles'
# fenced blocks — live: 0/3 without, 3/5 with (2026-10-06).
_FENCED_PREAMBLE = (
    "Your `exec` tool and every other built-in tool are disabled in this session — do "
    "not call them, they fail. Tools are listed in the system section below: call one by "
    "writing a ```veles-tool block in your reply and stop; the caller runs it and sends "
    "you the result in the next message.\n\n"
)
# Forwarded to Veles' MCP child by name (codex filters its env); never auto-allow.
_FORWARDED_ENV = (
    "VELES_USER_HOME",
    "BRAVE_SEARCH_API_KEY",
    "TAVILY_API_KEY",
    "VELES_WEB_SEARCH_BACKEND",
    "VELES_FETCH_ALLOW_PRIVATE",
    "VELES_SANDBOX_ROOTS",
    "VELES_LOCALE",
    "VELES_LOG_LEVEL",
    "VELES_LOCAL_TOOLS",
    "VELES_LOCAL_JSON_MODE",
    "OLLAMA_HOST",
)


@functools.cache
def lockdown_flags(binary: str, *, chat: bool) -> tuple[str, ...]:
    """`--disable` for every lockdown feature this codex knows, checked with `codex
    features list` (no model call). A critical name it doesn't know raises — fail
    closed; another is dropped with one warning. `chat` (no MCP bridge) also drops
    code mode: with it, codex reaches for its own exec instead of answering in Veles'
    fenced `veles-tool` blocks; the bridge needs it to call MCP tools."""
    names: list[str] = [*_LOCKDOWN, "code_mode_host"] if chat else list(_LOCKDOWN)
    while True:
        disable = [arg for name in names for arg in ("--disable", name)]
        try:
            proc = subprocess.run(
                [binary, "features", "list", *disable],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"codex features check failed: {exc}") from exc
        if proc.returncode == 0:
            return (*disable, "-c", 'web_search="disabled"', "-s", "read-only")
        unknown = proc.stderr.partition(_UNKNOWN)[2].split()[:1]
        if not unknown or unknown[0] not in names:
            raise RuntimeError(f"codex features check failed: {proc.stderr.strip()}")
        if unknown[0] in _CRITICAL:
            raise RuntimeError(
                f"this codex no longer has the feature flag {unknown[0]!r}, so Veles can't "
                "switch that tool off — update Veles, or use another provider"
            )
        print(
            f"warning: codex has no feature flag {unknown[0]!r}; not disabling it",
            file=sys.stderr,
        )
        names.remove(unknown[0])


def forwarded_env_names() -> list[str]:
    """Env names Veles' MCP child needs: its own settings plus every catalogue
    provider's key and base-URL variables (skills run there)."""
    from veles.core.providers import catalog

    names: dict[str, None] = dict.fromkeys(_FORWARDED_ENV)
    for spec in catalog().values():
        names.update(dict.fromkeys(spec.key_env))
        if spec.base_url_env:
            names[spec.base_url_env] = None
    return list(names)


class CodexCLIProvider(CLIProvider):
    name: str = "codex"
    INSTALL_HINT = "the Codex CLI (`brew install --cask codex` or `npm i -g @openai/codex`)"

    def __init__(
        self,
        *,
        workspace: Path | None,
        mcp_server: dict[str, Any] | None = None,
        binary: str = "codex",
        timeout: float = 300.0,
    ) -> None:
        super().__init__(binary=binary, timeout=timeout, extra_args=(), tools_config=mcp_server)
        self._workspace = workspace
        self._mcp_server = mcp_server

    def mcp_tool_name(self, name: str) -> str:
        return claude_mcp_prefix(name)  # codex shows them as mcp__veles__<name>

    def _cwd(self) -> str | None:
        if self._workspace is None:
            return None
        self._workspace.mkdir(parents=True, exist_ok=True)
        return str(self._workspace)

    def _new_state(self) -> _CodexStreamState:
        return _CodexStreamState()

    def _build_cmd(self, messages: list[Message], model: str, *, stream: bool = True) -> list[str]:
        del stream  # always JSONL
        cmd = [self._binary, "exec", "--json", "--ephemeral", "--ignore-user-config"]
        chat = self._mcp_server is None
        cmd += ["--skip-git-repo-check", *lockdown_flags(self._binary, chat=chat)]
        if model:
            cmd += ["-m", model]
        if self._mcp_server is not None:
            cmd += self._bridge_flags(self._mcp_server)
        prompt = format_messages_as_prompt(messages)
        if chat and FENCED_SENTINEL in prompt:
            prompt = _FENCED_PREAMBLE + prompt
        return [*cmd, "--", prompt]

    def _bridge_flags(self, server: dict[str, Any]) -> list[str]:
        values = {
            "command": json.dumps(server["command"]),
            "args": json.dumps(list(server["args"])),
            # Only this server's tools; each call still goes through Veles' trust ladder.
            "default_tools_approval_mode": '"approve"',
            "env_vars": json.dumps(forwarded_env_names()),
            "tool_timeout_sec": str(int(self._timeout)),
        }
        return [
            arg
            for key, value in values.items()
            for arg in ("-c", f"mcp_servers.veles.{key}={value}")
        ]

    def list_models(self) -> list[str]:
        """`codex debug models` slugs that codex lists; [] on any failure."""
        try:
            proc = subprocess.run(
                [self._binary, "debug", "models"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                cwd=self._cwd(),
                stdin=subprocess.DEVNULL,
            )
            models = json.loads(proc.stdout).get("models", []) if proc.returncode == 0 else []
        except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
            return []
        return [m["slug"] for m in models if isinstance(m, dict) and m.get("visibility") == "list"]


@dataclass(slots=True)
class _CodexStreamState:
    messages: list[str] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: str | None = None

    def absorb(self, event: dict[str, Any]) -> str:
        etype = event.get("type")
        if etype == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message" and item.get("text"):
                text = str(item["text"])
                chunk = ("\n\n" if self.messages else "") + text
                self.messages.append(text)
                return chunk
        elif etype == "turn.completed":
            u = event.get("usage") or {}
            prompt = int(u.get("input_tokens") or 0)
            out = int(u.get("output_tokens") or 0)
            self.usage = TokenUsage(
                prompt_tokens=prompt,
                completion_tokens=out,
                total_tokens=prompt + out,
                cache_read_tokens=int(u.get("cached_input_tokens") or 0),
                cache_creation_tokens=int(u.get("cache_write_input_tokens") or 0),
                reasoning_tokens=int(u.get("reasoning_output_tokens") or 0),
            )
        elif etype == "turn.failed":
            self.error = str((event.get("error") or {}).get("message") or "codex turn failed")
        # `{"type":"error"}` events and error items are retries/fallbacks, not the outcome.
        return ""

    def to_response(self, *, raw: Any) -> ProviderResponse:
        text = "\n\n".join(self.messages)
        if self.error and not text:
            login = "401" in self.error or "Unauthorized" in self.error
            hint = " — log in: `codex login`" if login else ""
            text = f"<codex error: {self.error}{hint}>"
        return ProviderResponse(
            text=text or None,
            tool_calls=[],
            usage=self.usage,
            finish_reason="error" if self.error else "stop",
            raw=raw,
        )
