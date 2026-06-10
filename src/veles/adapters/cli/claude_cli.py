"""Claude CLI adapter — delegate generation to a local `claude` subprocess.

We invoke `claude --output-format stream-json --verbose -p <prompt>` and parse
the line-delimited JSON event stream. The `result` event is canonical for the
final answer; `assistant` events are kept as a fallback when `result` is
missing and are also where streaming TextDeltas are sourced from.

Tool bridging works only when an MCP-config bridges Veles tools into the
spawned `claude` subprocess (M13). Otherwise tool schemas are ignored with
a stderr warning.
"""

from __future__ import annotations

import json
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

# Re-export under the legacy private name for downstream callers (notably
# tests written before the helper moved to `_common`).
_format_messages_as_prompt = format_messages_as_prompt


class ClaudeCLIProvider:
    name: str = "claude-cli"
    supports_streaming: bool = True

    def __init__(
        self,
        *,
        binary: str = "claude",
        timeout: float = 300.0,
        extra_args: Iterable[str] = (),
        mcp_config_path: Path | None = None,
    ) -> None:
        self._binary = binary
        self._timeout = timeout
        self._extra_args = tuple(extra_args)
        self._mcp_config_path = mcp_config_path

    @property
    def supports_tools(self) -> bool:
        return self._mcp_config_path is not None

    def _build_cmd(self, messages: list[Message], model: str) -> list[str]:
        prompt = format_messages_as_prompt(messages)
        cmd = [
            self._binary,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if model:
            cmd += ["--model", model]
        if self._mcp_config_path is not None:
            cmd += ["--mcp-config", str(self._mcp_config_path)]
        cmd += list(self._extra_args)
        return cmd

    def _maybe_warn_about_tools(self, tools: list[dict] | None) -> None:
        if tools and self._mcp_config_path is None:
            print(
                f"warning: {self.name} does not support custom tools; "
                f"ignoring {len(tools)} tool schema(s)",
                file=sys.stderr,
            )

    def _ensure_binary(self) -> None:
        if shutil.which(self._binary) is None:
            raise RuntimeError(
                f"{self._binary!r} CLI not found in PATH; install Claude Code"
                " or pass --provider openrouter"
            )

    def create_message(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        del max_tokens  # claude CLI does not expose a max_tokens knob
        self._ensure_binary()
        self._maybe_warn_about_tools(tools)
        cmd = self._build_cmd(messages, model)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self._timeout,
            check=False,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.strip() or "<no stderr>"
            raise RuntimeError(f"{self._binary} exited {proc.returncode}: {stderr}")
        state = _ClaudeStreamState()
        for line in proc.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            state.absorb(event)
        return state.to_response(raw=proc.stdout)

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
        cmd = self._build_cmd(messages, model)
        state = _ClaudeStreamState()
        try:
            for event in popen_jsonl(cmd, timeout=self._timeout):
                chunk = state.absorb(event)
                if chunk:
                    yield TextDelta(text=chunk)
        except RuntimeError as exc:
            state.error = str(exc)
        yield StreamEnd(response=state.to_response(raw=None))


@dataclass(slots=True)
class _ClaudeStreamState:
    final_text: str = ""
    fallback_text: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: str | None = None

    def absorb(self, event: dict[str, Any]) -> str:
        """Update state; return the text chunk to emit (empty string if none)."""
        etype = event.get("type")
        if etype == "result":
            self.final_text = str(event.get("result") or "")
            u = event.get("usage") or {}
            in_t = int(u.get("input_tokens", 0) or 0)
            out_t = int(u.get("output_tokens", 0) or 0)
            self.usage = TokenUsage(
                prompt_tokens=in_t,
                completion_tokens=out_t,
                total_tokens=in_t + out_t,
            )
            return ""
        if etype == "assistant":
            msg = event.get("message") or {}
            chunk = ""
            for block in msg.get("content") or []:
                if block.get("type") == "text":
                    chunk += block.get("text", "") or ""
            if chunk:
                self.fallback_text += chunk
            return chunk
        return ""

    def to_response(self, *, raw: Any) -> ProviderResponse:
        text = self.final_text or self.fallback_text
        if self.error and not text:
            text = f"<claude-cli error: {self.error}>"
        return ProviderResponse(
            text=text or None,
            tool_calls=[],
            usage=self.usage,
            finish_reason="error" if self.error else "stop",
            raw=raw,
        )


def _parse_stream(stdout: str) -> tuple[str, TokenUsage]:
    """Pull final text + token usage out of `claude --output-format stream-json`."""
    state = _ClaudeStreamState()
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        state.absorb(event)
    return (state.final_text or state.fallback_text), state.usage
