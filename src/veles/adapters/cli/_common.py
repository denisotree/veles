"""Shared helpers for CLI-delegation adapters."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Iterable, Iterator
from typing import Any, ClassVar, Protocol

from veles.adapters.cli._streaming import popen_jsonl
from veles.core.provider import Message, ProviderResponse, StreamEnd, StreamEvent, TextDelta


def format_messages_as_prompt(messages: list[Message]) -> str:
    """Render a Veles message list into a markdown-ish flat prompt.

    System/User/Assistant turns each become an H1-headed block. Tool messages
    are skipped — CLI delegates don't carry our tool_call_id chain, and there
    is no canonical place for them in a single-shot prompt.
    """
    parts: list[str] = []
    for m in messages:
        if m.role == "system":
            parts.append(f"# System\n\n{m.content or ''}\n")
        elif m.role == "user":
            parts.append(f"# User\n\n{m.content or ''}\n")
        elif m.role == "assistant":
            parts.append(f"# Assistant\n\n{m.content or ''}\n")
    return "\n".join(parts)


def iter_jsonl(text: str) -> Iterator[dict[str, Any]]:
    """Each JSON object line of `text`; blank and malformed lines are skipped."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            yield json.loads(stripped)
        except json.JSONDecodeError:
            continue


class StreamState(Protocol):
    """Accumulates a CLI's JSON event stream into a final response."""

    error: str | None

    def absorb(self, event: dict[str, Any]) -> str: ...

    def to_response(self, *, raw: Any) -> ProviderResponse: ...


class CLIProvider:
    """A provider that runs a local agent CLI (`claude`, `gemini`) as a subprocess.

    Subclasses say how to build the command line (`_build_cmd`), where to run it
    (`_cwd`) and how to read its event stream (`_new_state`); running, error
    reporting and streaming are shared."""

    name: str = "cli"
    supports_streaming: bool = True
    INSTALL_HINT: ClassVar[str] = ""

    def __init__(
        self,
        *,
        binary: str,
        timeout: float,
        extra_args: Iterable[str],
        tools_config: object | None,
    ) -> None:
        self._binary = binary
        self._timeout = timeout
        self._extra_args = tuple(extra_args)
        self._tools_config = tools_config

    @property
    def supports_tools(self) -> bool:
        return self._tools_config is not None

    def _build_cmd(self, messages: list[Message], model: str, *, stream: bool) -> list[str]:
        raise NotImplementedError

    def _new_state(self) -> StreamState:
        raise NotImplementedError

    def _cwd(self) -> str | None:
        return None

    def _prepare(self, tools: list[dict] | None) -> None:
        if shutil.which(self._binary) is None:
            raise RuntimeError(
                f"{self._binary!r} CLI not found in PATH; install {self.INSTALL_HINT}"
                " or pass --provider openrouter"
            )
        if tools and self._tools_config is None:
            print(
                f"warning: {self.name} does not support custom tools; "
                f"ignoring {len(tools)} tool schema(s)",
                file=sys.stderr,
            )

    def _run(self, cmd: list[str]) -> str:
        """Run `cmd` to completion and return its stdout; a non-zero exit raises."""
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self._timeout, check=False, cwd=self._cwd()
        )
        if proc.returncode != 0:
            stderr = proc.stderr.strip() or "<no stderr>"
            raise RuntimeError(f"{self._binary} exited {proc.returncode}: {stderr}")
        return proc.stdout

    def stream_message(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> Iterator[StreamEvent]:
        del max_tokens  # agent CLIs expose no max_tokens knob
        self._prepare(tools)
        cmd = self._build_cmd(messages, model, stream=True)
        state = self._new_state()
        try:
            for event in popen_jsonl(cmd, timeout=self._timeout, cwd=self._cwd()):
                chunk = state.absorb(event)
                if chunk:
                    yield TextDelta(text=chunk)
        except RuntimeError as exc:
            state.error = str(exc)
        yield StreamEnd(response=state.to_response(raw=None))
