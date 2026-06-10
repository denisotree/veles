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

import shutil
import subprocess
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veles.adapters.cli._common import format_messages_as_prompt
from veles.adapters.cli._streaming import popen_jsonl
from veles.core.provider import (
    Message,
    ProviderResponse,
    StreamEnd,
    StreamEvent,
    TextDelta,
    TokenUsage,
)


class GeminiCLIProvider:
    name: str = "gemini-cli"
    supports_streaming: bool = True

    def __init__(
        self,
        *,
        binary: str = "gemini",
        timeout: float = 300.0,
        extra_args: Iterable[str] = (),
        mcp_settings_dir: Path | None = None,
    ) -> None:
        self._binary = binary
        self._timeout = timeout
        self._extra_args = tuple(extra_args)
        self._mcp_settings_dir = mcp_settings_dir

    @property
    def supports_tools(self) -> bool:
        return self._mcp_settings_dir is not None

    def _ensure_binary(self) -> None:
        if shutil.which(self._binary) is None:
            raise RuntimeError(
                f"{self._binary!r} CLI not found in PATH; install Gemini CLI"
                " or pass --provider openrouter"
            )

    def _maybe_warn_about_tools(self, tools: list[dict] | None) -> None:
        if tools and self._mcp_settings_dir is None:
            print(
                f"warning: {self.name} does not support custom tools; "
                f"ignoring {len(tools)} tool schema(s)",
                file=sys.stderr,
            )

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
        self._ensure_binary()
        self._maybe_warn_about_tools(tools)
        cmd = self._build_cmd(messages, model, stream=False)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self._timeout,
            check=False,
            cwd=self._cwd(),
        )
        if proc.returncode != 0:
            stderr = proc.stderr.strip() or "<no stderr>"
            raise RuntimeError(f"{self._binary} exited {proc.returncode}: {stderr}")
        text = proc.stdout.strip()
        return ProviderResponse(
            text=text or None,
            tool_calls=[],
            usage=TokenUsage(),
            finish_reason="stop",
            raw=proc.stdout,
        )

    def stream_message(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> Iterator[StreamEvent]:
        del max_tokens
        self._ensure_binary()
        self._maybe_warn_about_tools(tools)
        cmd = self._build_cmd(messages, model, stream=True)
        state = _GeminiStreamState()
        try:
            for event in popen_jsonl(cmd, timeout=self._timeout, cwd=self._cwd()):
                chunk = state.absorb(event)
                if chunk:
                    yield TextDelta(text=chunk)
        except RuntimeError as exc:
            state.error = str(exc)
        yield StreamEnd(response=state.to_response())


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

    def to_response(self) -> ProviderResponse:
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
