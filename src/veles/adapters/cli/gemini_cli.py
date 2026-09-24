"""Gemini CLI adapter — delegate generation to a local `gemini` subprocess.

Symmetric to ClaudeCLIProvider: spawn the `gemini` binary in one-shot mode
(`gemini -p <prompt> --model <m>`), capture stdout as the response text.
M16 enables real subprocess streaming via `--output-format stream-json` —
gemini emits line-delimited JSON events of the form
`{"type":"message","role":"assistant","content":"<chunk>","delta":true}`,
which we map onto TextDelta events.

Tool bridging works only when an MCP-config has been planted at
`<mcp_settings_dir>/.gemini/settings.json` (M14). Note: as of gemini-cli
0.40.x, headless `-p` mode does NOT load MCP servers from any settings.json,
so `supports_tools=True` is structurally accurate but practically inert
until upstream gemini supports headless MCP (Veles M17 territory).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veles.adapters.cli._common import CLIProvider, format_messages_as_prompt
from veles.core.provider import Message, ProviderResponse, TokenUsage


class GeminiCLIProvider(CLIProvider):
    name: str = "gemini-cli"
    INSTALL_HINT = "Gemini CLI"

    def __init__(
        self,
        *,
        binary: str = "gemini",
        timeout: float = 300.0,
        extra_args: Iterable[str] = (),
        mcp_settings_dir: Path | None = None,
    ) -> None:
        super().__init__(
            binary=binary, timeout=timeout, extra_args=extra_args, tools_config=mcp_settings_dir
        )
        self._mcp_settings_dir = mcp_settings_dir

    def _new_state(self) -> _GeminiStreamState:
        return _GeminiStreamState()

    def _build_cmd(self, messages: list[Message], model: str, *, stream: bool) -> list[str]:
        prompt = format_messages_as_prompt(messages)
        cmd = [self._binary, "-p", prompt]
        if model:
            cmd += ["--model", model]
        if stream:
            cmd += ["--output-format", "stream-json"]
        if self._mcp_settings_dir is not None:
            # gemini -p ignores workspace mcpServers unless explicitly allow-listed,
            # and tool calls would block on interactive permission prompts.
            cmd += ["--allowed-mcp-server-names", "veles", "--yolo"]
        cmd += list(self._extra_args)
        return cmd

    def _cwd(self) -> str | None:
        return str(self._mcp_settings_dir) if self._mcp_settings_dir else None

    def create_message(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        del max_tokens  # gemini CLI does not expose a max_tokens knob
        self._prepare(tools)
        stdout = self._run(self._build_cmd(messages, model, stream=False))
        return ProviderResponse(
            text=stdout.strip() or None,
            tool_calls=[],
            usage=TokenUsage(),
            finish_reason="stop",
            raw=stdout,
        )


@dataclass(slots=True)
class _GeminiStreamState:
    accumulated: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: str | None = None

    def absorb(self, event: dict[str, Any]) -> str:
        if event.get("type") != "message":
            return ""
        if event.get("role") != "assistant":
            return ""
        content = event.get("content")
        if not isinstance(content, str) or not content:
            return ""
        self.accumulated += content
        return content

    def to_response(self, *, raw: Any = None) -> ProviderResponse:
        text = self.accumulated
        if self.error and not text:
            text = f"<gemini-cli error: {self.error}>"
        return ProviderResponse(
            text=text or None,
            tool_calls=[],
            usage=self.usage,
            finish_reason="error" if self.error else "stop",
            raw=None,
        )
