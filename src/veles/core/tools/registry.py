"""Tool registry — single source of truth for which tools the agent can call.

Tools self-register via the `@tool` decorator at import time. The registry can
emit OpenAI-style tool schemas (universally accepted by OpenRouter, OpenAI,
Anthropic-via-translation) and dispatch a call by name.

The registry stays deliberately small — it owns the name→entry mapping and
schema emission, nothing else.

M65 extends the contract: tools may declare a `risk_class` (taxonomy in
`core/risk.py`) and a `max_result_chars` cap; results may be returned as a
`ToolResult` dataclass for structured observations. Legacy tools that return
`str` keep working — `dispatch` auto-wraps them and applies truncation.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veles.core.risk import RiskClass, is_sensitive_class
from veles.core.tool_result import (
    DEFAULT_MAX_RESULT_CHARS,
    ToolResult,
    serialize_for_dispatch,
    truncate_with_artifact,
)
from veles.core.tools.schema import python_function_to_schema


@dataclass(slots=True)
class ToolEntry:
    name: str
    description: str
    parameter_schema: dict[str, Any]
    handler: Callable[..., Any]
    is_async: bool
    sensitive: bool = False
    risk_class: RiskClass | None = None
    side_effects: list[str] = field(default_factory=list)
    timeout_s: float | None = None
    max_result_chars: int = DEFAULT_MAX_RESULT_CHARS
    # M72: when set, this tool is the commit half of a draft/commit pair.
    # `commit_of="draft_email"` means the Permission Engine will deny this
    # tool unless `draft_email` has already been invoked earlier in the
    # session (verified via the typed event log).
    commit_of: str | None = None


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    def register(self, entry: ToolEntry) -> None:
        if entry.name in self._tools:
            raise ValueError(f"tool {entry.name!r} already registered")
        self._tools[entry.name] = entry

    def get(self, name: str) -> ToolEntry:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool {name!r}") from exc

    def list_names(self) -> list[str]:
        return list(self._tools)

    def subset(self, names: Iterable[str]) -> Registry:
        """Return a new registry exposing only `names` (silently skips unknowns)."""
        out = Registry()
        for name in names:
            entry = self._tools.get(name)
            if entry is not None:
                out._tools[name] = entry
        return out

    def list_schemas(self) -> list[dict[str, Any]]:
        """Return tool schemas in OpenAI Chat Completions format.

        Tools are emitted sorted by `name` (M67 cache-aware invariant): the
        tool-bundle is part of the stable prompt prefix, so any non-
        deterministic ordering (e.g. dict-insertion order shifting with
        import order) silently fragments the prompt cache.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": e.name,
                    "description": e.description,
                    "parameters": e.parameter_schema,
                },
            }
            for e in sorted(self._tools.values(), key=lambda t: t.name)
        ]

    def dispatch(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        artifact_dir: Path | None = None,
    ) -> str:
        """Call tool `name` and return the wire-format string for the LLM.

        Three return modes from a tool handler:
          1. `ToolResult` — serialized as JSON via `serialize_for_dispatch`,
             so the model sees `status`, `next_valid_actions`, etc.
          2. `str` — passed through unchanged when it fits `max_result_chars`.
             Modern legacy tools (markdown blobs, code dumps) keep their
             readable shape — wrapping them in JSON only adds noise.
          3. `str` over budget — serialized as JSON with an `evidence_ref`
             pointing at the offloaded artifact and a head/tail preview.

        Anything that isn't `ToolResult` or `str` is coerced via `str(...)`
        first, then re-enters the path-2 / path-3 decision.
        """
        entry = self.get(name)
        if entry.is_async:
            raw = asyncio.run(entry.handler(**arguments))
        else:
            raw = entry.handler(**arguments)

        if isinstance(raw, ToolResult):
            return serialize_for_dispatch(raw)

        text = raw if isinstance(raw, str) else str(raw)
        if len(text) <= entry.max_result_chars:
            # Backward-compatible passthrough: legacy tools keep their raw
            # wire shape and existing tests / model-side expectations hold.
            return text
        visible, evidence_ref = truncate_with_artifact(
            text,
            max_chars=entry.max_result_chars,
            state_dir=artifact_dir,
        )
        result = ToolResult(
            status="success",
            summary=visible,
            evidence_ref=evidence_ref,
        )
        return serialize_for_dispatch(result)


registry = Registry()


def tool(
    *,
    name: str | None = None,
    description: str | None = None,
    sensitive: bool | None = None,
    risk_class: RiskClass | None = None,
    side_effects: list[str] | None = None,
    timeout_s: float | None = None,
    max_result_chars: int = DEFAULT_MAX_RESULT_CHARS,
    commit_of: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register `fn` as a tool.

    M65 metadata (all optional, additive):
      risk_class       — `RiskClass` from `core/risk.py`. When provided and
                         `sensitive` is left unset, `sensitive` is derived
                         from the class (`is_sensitive_class`).
      side_effects     — free-form labels: e.g. ["filesystem", "network"].
      timeout_s        — advisory per-call budget. NOT enforced for builtin
                         tools (audit 2026-07-08: no dispatch-site reader
                         exists); only the MCP client applies its own call
                         budgets. A deliberately long tool (e.g. `wiki_add`
                         batch ingest) is therefore never timeout-killed.
      max_result_chars — visible-payload cap. Excess lands in an artifact.

    Legacy `sensitive=True` keeps working — it's still the gate for the
    M38 trust ladder until M64 unifies everything via the Permission Engine.
    """

    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        resolved_name = name or fn.__name__
        doc = inspect.getdoc(fn) or ""
        resolved_description = description or doc.split("\n\n", 1)[0].strip() or resolved_name
        if sensitive is not None:
            resolved_sensitive = sensitive
        elif risk_class is not None:
            resolved_sensitive = is_sensitive_class(risk_class)
        else:
            resolved_sensitive = False
        registry.register(
            ToolEntry(
                name=resolved_name,
                description=resolved_description,
                parameter_schema=python_function_to_schema(fn),
                handler=fn,
                is_async=inspect.iscoroutinefunction(fn),
                sensitive=resolved_sensitive,
                risk_class=risk_class,
                side_effects=list(side_effects) if side_effects else [],
                timeout_s=timeout_s,
                max_result_chars=max_result_chars,
                commit_of=commit_of,
            )
        )
        return fn

    return wrap
