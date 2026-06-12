"""Curator core types and pure helpers (VISION §5.1).

The curator's *orchestration* lives in `cli/_curator.py` for now — its
public surface is the argparse-driven `_maybe_run_*` triggers, and the
existing test suite intentionally monkey-patches CLI-level lookup paths
(`veles.cli._run_curator_pass`) for isolation. Moving that orchestration
here would force every test in `tests/test_curator_*.py` and friends to
re-patch, with no behavioural payoff.

What *can* live in core cleanly:

- `_CuratorPassResult` — value type, no dependencies.
- `_CURATE_TOOLS`, `_CURATE_*_LIMIT` — domain constants the CLI layer
  reaches for during configuration; equally useful to any future
  daemon-side curator or test fixture without paying for the CLI
  import chain.
- `_render_message`, `_truncate_session_messages` — pure rendering
  helpers used during prompt construction.

`cli/_curator.py` re-imports these names so existing
`from veles.cli._curator import _CURATE_TOOLS` paths keep working
unchanged."""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.provider import Message

_CURATE_TOOLS = (
    "wiki_write_page",
    "wiki_append_log",
    # M125: curator mirrors its distilled output into SQL memory tables
    # so `/insights`, `/rules`, and the recall pipeline can find it
    # without scanning the wiki filesystem.
    "memory_save_insight",
    "memory_save_rule",
)

_CURATE_DEFAULT_LIMIT = 20
_CURATE_TURN_LIMIT = 80
_CURATE_CHARS_LIMIT = 64_000
_CURATE_QUIET_WINDOW_SEC = 60.0

# M28: idle curator fires at 24h gap
_CURATOR_IDLE_THRESHOLD_SEC = 24 * 3600
_CURATOR_IDLE_LIMIT = 5
_CURATOR_POSTRUN_LIMIT = 1


@dataclass(frozen=True, slots=True)
class _CuratorPassResult:
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


def _truncate_session_messages(messages: list[Message], max_turns: int, max_chars: int) -> str:
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
