"""CLI-delegation adapters: spawn external LLM CLIs as Veles providers. The base
class and its helpers are public — module delegates build on them (`veles.sdk.providers`)."""

from veles.adapters.cli._common import (
    CLIProvider,
    StreamState,
    format_messages_as_prompt,
    iter_jsonl,
)
from veles.adapters.cli._streaming import popen_jsonl

__all__ = ["CLIProvider", "StreamState", "format_messages_as_prompt", "iter_jsonl", "popen_jsonl"]
