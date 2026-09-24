"""Curator core types and pure helpers (VISION §5.1).

The curator's orchestration — the post-turn `maybe_run_*` triggers and the
curator pass — lives in `runtime/learning.py`, shared by the CLI and the
daemon. This module holds what has no dependencies: the pass result type,
the curate toolset and limits, and the transcript rendering."""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.provider import Message

CURATE_TOOLS = (
    "wiki_write_page",
    "wiki_append_log",
    # M125: curator mirrors its distilled output into SQL memory tables
    # so `/insights`, `/rules`, and the recall pipeline can find it
    # without scanning the wiki filesystem.
    "memory_save_insight",
    "memory_save_rule",
)

CURATE_DEFAULT_LIMIT = 20
CURATE_TURN_LIMIT = 80
CURATE_CHARS_LIMIT = 64_000
CURATE_QUIET_WINDOW_SEC = 60.0
# The curator's own cumulative token budget, NOT the caller's per-run
# `--max-tokens-total` (default 100k — a cost guard for the USER'S task).
# The curate prompt carries the serialized session (up to CURATE_CHARS_LIMIT
# chars ≈ 16-25k tokens) and re-counts against the budget every round, so a
# normal 4-6-round curation needs ~150k; 100k killed it mid-run (live
# 2026-07-08, ollama qwen3.5:9b). 250k covers ~10 rounds of a worst-case
# prompt while still bounding a runaway pass on a paid provider.
CURATE_TOKEN_BUDGET = 250_000

# M28: idle curator fires at 24h gap
CURATOR_IDLE_THRESHOLD_SEC = 24 * 3600
CURATOR_IDLE_LIMIT = 5
CURATOR_POSTRUN_LIMIT = 1


@dataclass(frozen=True, slots=True)
class CuratorPassResult:
    """Outcome of one curator pass — used by `_cmd_curate` and the
    M28 continuous triggers to drive their respective stderr output."""

    successes: int
    had_candidates: bool
    advanced_to: float
    starting_cursor: float


def _render_message(m: Message) -> str:
    parts: list[str] = [f"[{m.role}]"]
    if m.content:
        parts.append(m.content)
    if m.tool_calls:
        calls = ", ".join(f"{tc.name}({tc.arguments!r})" for tc in m.tool_calls)
        parts.append(f"<calls: {calls}>")
    if m.tool_call_id:
        parts.append(f"<tool_call_id={m.tool_call_id}>")
    return " ".join(parts)


def truncate_session_messages(messages: list[Message], max_turns: int, max_chars: int) -> str:
    """Render messages as plain text with first/last truncation if too large."""
    rendered = [_render_message(m) for m in messages]
    head_keep = 4
    if len(rendered) > max_turns:
        cut = len(rendered) - max_turns
        head = rendered[:head_keep]
        tail = rendered[head_keep + cut :]
        body = (
            "\n\n".join(head)
            + f"\n\n<...truncated {cut} turns to fit budget...>\n\n"
            + "\n\n".join(tail)
        )
    else:
        body = "\n\n".join(rendered)
    if len(body) > max_chars:
        keep_each = max_chars // 2
        body = (
            body[:keep_each]
            + f"\n\n<...truncated mid-content to fit {max_chars} chars...>\n\n"
            + body[-keep_each:]
        )
    return body
