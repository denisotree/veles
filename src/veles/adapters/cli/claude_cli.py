"""Claude CLI adapter — delegate generation to a local `claude` subprocess.

We invoke `claude --output-format stream-json --verbose -p <prompt>` and parse
the line-delimited JSON event stream. The `result` event is canonical for the
final answer; `assistant` events are kept as a fallback when `result` is
missing and are also where streaming TextDeltas are sourced from.

Tool bridging works only when an MCP-config bridges Veles tools into the
spawned `claude` subprocess (M13). Otherwise tool schemas are ignored with
a stderr warning.

The spawned claude runs isolated (`_isolation_flags`): its code-running tools,
the project's `.claude/settings.json` hooks and `.mcp.json` servers never apply,
so everything it does goes through Veles' own trust ladder.
"""

from __future__ import annotations

import functools
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veles.adapters.cli._common import CLIProvider, format_messages_as_prompt, iter_jsonl
from veles.core.provider import Message, ProviderResponse, TokenUsage


class ClaudeCLIProvider(CLIProvider):
    name: str = "claude-cli"
    INSTALL_HINT = "Claude Code"

    def __init__(
        self,
        *,
        binary: str = "claude",
        timeout: float = 300.0,
        extra_args: Iterable[str] = (),
        mcp_config_path: Path | None = None,
    ) -> None:
        super().__init__(
            binary=binary, timeout=timeout, extra_args=extra_args, tools_config=mcp_config_path
        )
        self._mcp_config_path = mcp_config_path

    def _new_state(self) -> _ClaudeStreamState:
        return _ClaudeStreamState()

    def _build_cmd(self, messages: list[Message], model: str, *, stream: bool = True) -> list[str]:
        del stream  # the claude CLI always speaks stream-json here
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
        cmd += _isolation_flags(self._binary)
        if self._mcp_config_path is not None:
            # Veles gates its own tools (trust ladder, sandbox); allowing the
            # server here only stops headless claude denying them as unprompted.
            cmd += ["--mcp-config", str(self._mcp_config_path), "--allowedTools", "mcp__veles"]
        cmd += list(self._extra_args)
        return cmd

    def create_message(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        del max_tokens  # claude CLI does not expose a max_tokens knob
        self._prepare(tools)
        stdout = self._run(self._build_cmd(messages, model))
        state = _ClaudeStreamState()
        for event in iter_jsonl(stdout):
            state.absorb(event)
        return state.to_response(raw=stdout)


@functools.cache
def _isolation_flags(binary: str) -> tuple[str, ...]:
    """Flags that keep the delegated claude a model, not a second agent: no
    code-running tools, no project settings/hooks, no MCP servers but Veles'.
    `--restricted` does it all where the CLI has it (headless claude then also
    denies its own Edit/Write, which would prompt); older CLIs get the
    equivalent by hand. Probed from `--help` once per process, not pinned to a
    version."""
    try:
        help_text = subprocess.run(
            [binary, "--help"], capture_output=True, text=True, timeout=30, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        help_text = ""
    if "--restricted" in help_text:
        return ("--restricted", "--strict-mcp-config")
    return ("--setting-sources", "user", "--strict-mcp-config", "--tools", "")


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
    for event in iter_jsonl(stdout):
        state.absorb(event)
    return (state.final_text or state.fallback_text), state.usage
