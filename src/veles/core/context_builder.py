"""Stable-prefix / volatile-suffix context assembly (Tier ε, M67).

The prompt cache rewards exact-prefix reuse, so the rule is: stable
content first, volatile content late, with one cache breakpoint between.

Callers (CLI commands, channel daemons, ingest/query/lint flows) used to
build the system prompt with ad-hoc `"\n\n---\n\n".join(parts)` and an
inline `inject_breakpoint(...)` call. That worked, but every new caller
re-implemented the same shape, and forgetting the sentinel silently
fragments the cache. M67 centralises the contract here.

What goes where:

  stable_parts (cached, byte-stable per session):
    - tool definitions (sorted by name — done in Registry.list_schemas)
    - system / developer instructions
    - AGENTS.md, INDEX.md, scoped instructions
    - skill index, stable reference material
    - prior turn history (append-only — provider takes care of this)

  volatile_parts (never cached, appended last):
    - `<memory-context>` blocks per-turn
    - `<subproject-proposals>` blocks
    - current todo / progress log
    - dynamic runtime (cwd, timestamps, request_id)
    - the new user message (carried separately, not in system prompt)

`assemble_system_prompt` returns `(prompt, stable_text)` so the trace
writer (M68) can hash the stable portion only and the cache-fragmentation
alert (§19.1) catches real drift, not new user input.
"""

from __future__ import annotations

from veles.core.cache_hints import CACHE_BREAKPOINT_SENTINEL, inject_breakpoint

DEFAULT_SEPARATOR = "\n\n---\n\n"


def assemble_system_prompt(
    stable_parts: list[str],
    volatile_parts: list[str] | None = None,
    *,
    separator: str = DEFAULT_SEPARATOR,
) -> tuple[str | None, str]:
    """Assemble a cache-friendly system prompt.

    Returns `(full_prompt, stable_text)`:
      full_prompt — what goes into Agent(system_prompt=...). None when both
                    `stable_parts` and `volatile_parts` are empty / falsy.
      stable_text — just the stable portion, for hashing and cache telemetry.
                    Returned even when full_prompt is None so callers can
                    pass it to `hash_text` without a conditional.

    Empty / None entries in either list are filtered out before joining.
    """
    stable = separator.join(p for p in stable_parts if p)
    volatile_parts = volatile_parts or []
    volatile = separator.join(p for p in volatile_parts if p)
    if not stable and not volatile:
        return None, ""
    if not volatile:
        return stable, stable
    if not stable:
        # No stable portion — nothing to cache. Volatile-only prompt is rare
        # (a query that bypasses AGENTS.md) but the contract has to handle it.
        return volatile, ""
    return inject_breakpoint(stable, separator + volatile), stable


def stable_text(stable_parts: list[str], *, separator: str = DEFAULT_SEPARATOR) -> str:
    """Return only the stable portion. Useful when callers already split."""
    return separator.join(p for p in stable_parts if p)


__all__ = [
    "CACHE_BREAKPOINT_SENTINEL",
    "DEFAULT_SEPARATOR",
    "assemble_system_prompt",
    "stable_text",
]
