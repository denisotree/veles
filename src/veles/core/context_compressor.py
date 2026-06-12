"""Sliding-window context compressor — drops the middle, keeps head/tail.

Mandatory per PLAN.md §3.3: without it, long sessions hit the provider's
context limit. When the in-memory turn history grows past
`threshold_tokens`, the middle range is summarised by a cheap-model
sub-agent and the result is persisted under
`.veles/memory/sessions/<...>.md` (M160 — compactions are the agent's
own memory, not user content). The conversation passed to the next LLM
call is `head` + `tail`, with the first system message extended by a
short `[CONTEXT-COMPRESSION]` note pointing the agent at the summary.

Why augment the system prompt rather than insert a placeholder turn:
Anthropic and most other providers strictly require alternating
user/assistant roles in `messages`. Splicing a synthetic turn in the
middle would risk doubled-role violations. Extending the system message
sidesteps role-alternation entirely while still surfacing the summary
pointer to the model.

`SessionStore` keeps every original turn — compression mutates only the
in-memory list passed to the provider. `--resume` therefore loads full
history and the compressor re-runs idempotently (paying for one extra
summary). Caching summaries across resumes is M30+.

Two surfaces:
- Pure utilities (`estimate_tokens`, `needs_compression`,
  `find_safe_boundaries`, `render_middle_for_summary`,
  `apply_compression`) deterministic and testable in isolation.
- `make_default_compressor(...)` returns a `HistoryCompressor` callable
  that wraps the utilities with a sub-Agent summariser + memory-artefact
  write.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from veles.core.provider import Message

if TYPE_CHECKING:
    from veles.core.project import Project
    from veles.core.provider import Provider


_CHARS_PER_TOKEN = 4  # rough heuristic; tiktoken is ~3.5-4.5 across English/code

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CompressionConfig:
    """Trigger + slicing policy for sliding-window compression."""

    head_keep: int = 4
    tail_keep: int = 8
    threshold_tokens: int = 50_000
    max_summary_tokens: int = 1024
    # Hard ceiling on the rendered middle handed to the summariser. If
    # exceeded we trim oldest middle turns until under, preventing the
    # sub-agent from itself blowing the provider's context window
    # (e.g., 200k Bedrock limit on claude-haiku-4.5).
    max_summariser_input_tokens: int = 150_000
    # Hard ceiling enforced by Agent AFTER the compressor returns. The
    # last line of defence: if the compressed history is still over,
    # drop oldest non-system turns until under. Keeps the main
    # provider from a "prompt is too long" runtime error even when the
    # compressor itself silently no-ops.
    hard_ceiling_tokens: int = 180_000


HistoryCompressor = Callable[[list[Message], "str | None"], list[Message]]


def estimate_tokens(history: list[Message]) -> int:
    """Approximate token count via 4-chars-per-token heuristic.

    Cheap enough to call before every provider request. We'd rather
    compress slightly early than miss a context-limit hit, so the
    threshold is set conservatively below the real model limit.
    """
    n = 0
    for m in history:
        if m.content:
            n += len(m.content)
        for tc in m.tool_calls:
            n += len(json.dumps(tc.arguments, separators=(",", ":")))
            n += len(tc.name)
        if m.tool_call_id:
            n += len(m.tool_call_id)
    return n // _CHARS_PER_TOKEN


def needs_compression(history: list[Message], cfg: CompressionConfig) -> bool:
    """True when the history is over budget AND has middle turns to drop."""
    if len(history) <= cfg.head_keep + cfg.tail_keep + 1:
        return False
    return estimate_tokens(history) >= cfg.threshold_tokens


def find_safe_boundaries(history: list[Message], cfg: CompressionConfig) -> tuple[int, int] | None:
    """Pick (head_end, tail_start) so head ends on assistant/system AND tail
    starts on user.

    Returns None when no alternation-safe split exists (e.g. a single-prompt
    session with no second user turn) — the caller should leave history
    untouched in that case.
    """
    head_end = min(cfg.head_keep, len(history))
    while head_end > 0 and history[head_end - 1].role not in {"assistant", "system"}:
        head_end -= 1
    if head_end == 0:
        return None
    tail_start_lo = max(head_end, len(history) - cfg.tail_keep)
    tail_start = tail_start_lo
    while tail_start < len(history) and history[tail_start].role != "user":
        tail_start += 1
    if tail_start >= len(history):
        return None
    if tail_start - head_end <= 0:
        return None
    return head_end, tail_start


def render_middle_for_summary(middle: list[Message]) -> str:
    """Serialise dropped turns as plain text for the summariser prompt."""
    blocks: list[str] = []
    for m in middle:
        tag = m.role
        if m.role == "tool" and m.tool_call_id:
            tag = f"tool[{m.tool_call_id}]"
        body = m.content or ""
        if m.tool_calls:
            calls = ", ".join(
                f"{tc.name}({json.dumps(tc.arguments, separators=(',', ':'))})"
                for tc in m.tool_calls
            )
            body = (body + "\n" if body else "") + f"<calls: {calls}>"
        blocks.append(f"# {tag}\n{body}")
    return "\n\n".join(blocks)


def _build_compression_note(
    *, summary_path: str, n_turns_dropped: int, active_plan_refs: list[str] | None
) -> str:
    """Render the `[CONTEXT-COMPRESSION]` (+ optional `[ACTIVE-PLAN-REFS]`) banner.

    Lives in the head's system message so the model sees it before any history.
    """
    note = (
        f"\n\n[CONTEXT-COMPRESSION] {n_turns_dropped} earlier turns of this "
        f"session were summarised into {summary_path}; use wiki_read_page "
        f"to retrieve when needed."
    )
    if active_plan_refs:
        joined = ", ".join(active_plan_refs)
        note += (
            f"\n[ACTIVE-PLAN-REFS] preserved across compaction: {joined}. "
            f"These plans remain authoritative; consult them before "
            f"continuing the work."
        )
    return note


def _splice_note_into_head(head: list[Message], note: str) -> list[Message]:
    """Append `note` to head's first system message, or prepend one if absent."""
    if head and head[0].role == "system":
        first = head[0]
        head[0] = Message(
            role="system",
            content=(first.content or "") + note,
            tool_calls=list(first.tool_calls),
            tool_call_id=first.tool_call_id,
        )
    else:
        head.insert(0, Message(role="system", content=note.lstrip()))
    return head


def apply_compression(
    history: list[Message],
    cfg: CompressionConfig,
    *,
    summary_path: str,
    n_turns_dropped: int,
    active_plan_refs: list[str] | None = None,
) -> list[Message]:
    """Build the post-compression history.

    Strategy: trim the middle, augment the first `system` message in head
    with a `[CONTEXT-COMPRESSION]` note pointing at `summary_path`. If
    head has no system message, prepend one — that is alternation-safe
    because system messages sit outside the user/assistant alternation
    invariant on every supported provider.

    `active_plan_refs` carries plan URIs (`artifact://veles/plans/<id>`)
    that survive across the compaction boundary — the rehydrated agent
    needs to know which plans were active so it doesn't drop them on the
    floor when an old turn referencing them gets summarised away. This
    is the storage half of the M70 `test_compaction_preserves_active_plan`
    contract.
    """
    bounds = find_safe_boundaries(history, cfg)
    if bounds is None:
        return history
    head_end, tail_start = bounds
    note = _build_compression_note(
        summary_path=summary_path,
        n_turns_dropped=n_turns_dropped,
        active_plan_refs=active_plan_refs,
    )
    head = _splice_note_into_head(list(history[:head_end]), note)
    return head + list(history[tail_start:])


def _now_slug() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def make_default_compressor(
    *,
    provider: Provider,
    model: str,
    cfg: CompressionConfig,
    project: Project,
) -> HistoryCompressor:
    """Build a `HistoryCompressor` that summarises with a sub-Agent and
    writes the result to `.veles/memory/sessions/`.

    The sub-Agent shares the parent's `TokenBudget` (ContextVar) and
    runs with no tools and no nested compressor — recursion is therefore
    impossible. An exhausted budget yields an empty summary; we still
    drop the middle (the agent will know less, which is preferable to
    crashing the parent on a context overflow).
    """
    # Late import — Agent is core but importing it at module top would
    # couple every importer of compression utilities to that heavy
    # module, and Agent annotates its compressor parameter, so a cycle
    # is one careless import away.
    from veles.core.agent import Agent
    from veles.core.memory.artefacts import append_memory_log, write_session_summary
    from veles.core.tools.registry import Registry

    def _compress(history: list[Message], session_id: str | None) -> list[Message]:
        sid = session_id or "session"
        tokens_before = estimate_tokens(history)
        if not needs_compression(history, cfg):
            logger.info(
                "compressor skip session=%s reason=below-threshold tokens=%d threshold=%d turns=%d",
                sid,
                tokens_before,
                cfg.threshold_tokens,
                len(history),
            )
            return history
        bounds = find_safe_boundaries(history, cfg)
        if bounds is None:
            logger.info(
                "compressor skip session=%s reason=no-safe-boundaries "
                "tokens=%d turns=%d head_keep=%d tail_keep=%d",
                sid,
                tokens_before,
                len(history),
                cfg.head_keep,
                cfg.tail_keep,
            )
            return history
        head_end, tail_start = bounds
        middle = history[head_end:tail_start]
        if not middle:
            logger.info(
                "compressor skip session=%s reason=empty-middle tokens=%d",
                sid,
                tokens_before,
            )
            return history
        # Trim middle from the front until rendered input fits the
        # summariser's context window. Without this guard a 200k-token
        # session has a 200k-token middle, the sub-agent posts that to
        # the same provider, and the run dies with the same "prompt is
        # too long" error the compressor was meant to prevent.
        rendered = render_middle_for_summary(middle)
        rendered_tokens = len(rendered) // _CHARS_PER_TOKEN
        if rendered_tokens > cfg.max_summariser_input_tokens:
            original_len = len(middle)
            while middle and rendered_tokens > cfg.max_summariser_input_tokens:
                middle = middle[1:]
                rendered = render_middle_for_summary(middle)
                rendered_tokens = len(rendered) // _CHARS_PER_TOKEN
            logger.info(
                "compressor summariser-input-truncated session=%s "
                "dropped_from_front=%d kept_middle=%d input_tokens=%d "
                "limit=%d",
                sid,
                original_len - len(middle),
                len(middle),
                rendered_tokens,
                cfg.max_summariser_input_tokens,
            )
            if not middle:
                # Truncated middle to empty — nothing meaningful to
                # summarise, but apply_compression still drops the
                # original middle range from the live history (the
                # bytes never reach the main provider).
                rendered = "(middle too large to summarise — dropped without summary)"
        sub_prompt = (
            "You are a summariser. Compress the following Veles agent turns "
            "into a tight markdown brief that a future agent can use to recall "
            "context: list user goals, tool calls + outcomes, decisions made, "
            "and unresolved questions. Drop pleasantries. Keep ≤500 words."
        )
        sub_agent = Agent(
            provider=provider,
            registry=Registry(),
            model=model,
            max_iterations=1,
            system_prompt=sub_prompt,
            max_tokens=cfg.max_summary_tokens,
        )
        # If the summariser blows up (rate-limit, network, an unforeseen
        # context-limit), don't let it take down the main run — fall
        # back to a placeholder summary and still drop the middle from
        # the live history. The main provider getting a small history
        # is strictly better than crashing.
        try:
            result = sub_agent.run(rendered)
            summary = (result.text or "").strip() or "_(empty summary)_"
            if getattr(result, "stopped_reason", None) == "budget_exhausted":
                logger.info(
                    "compressor summariser-budget-exhausted session=%s — using partial summary",
                    sid,
                )
        except Exception as exc:
            logger.warning(
                "compressor summariser-failed session=%s exc=%s: %s",
                sid,
                type(exc).__name__,
                exc,
            )
            summary = f"(summary failed: {type(exc).__name__}; see daemon log)"
        slug_id = sid
        slug = f"{slug_id}-c-{_now_slug()}"
        title = f"Compressed segment of session {slug_id}"
        summary_abs = write_session_summary(project, slug=slug, title=title, content=summary)
        try:
            rel_path = summary_abs.relative_to(project.root).as_posix()
        except ValueError:
            rel_path = str(summary_abs)
        append_memory_log(
            project,
            op="compress",
            summary=f"compressed {len(middle)} turns of session {slug_id} -> {rel_path}",
        )
        # M70: pull active plan URIs and embed them in the compaction note
        # so they survive the rehydration cycle.
        from veles.core.plan_artifact import collect_active_refs

        plan_refs = collect_active_refs(project.state_dir)
        result_history = apply_compression(
            history,
            cfg,
            summary_path=rel_path,
            n_turns_dropped=len(middle),
            active_plan_refs=plan_refs,
        )
        logger.info(
            "compressor applied session=%s tokens_before=%d tokens_after=%d "
            "n_middle_dropped=%d summary_path=%s",
            sid,
            tokens_before,
            estimate_tokens(result_history),
            len(middle),
            rel_path,
        )
        return result_history

    return _compress


def emergency_truncate(
    history: list[Message],
    *,
    target_tokens: int,
) -> tuple[list[Message], int]:
    """Last-line truncation when the compressor failed to bring history
    under the model's hard ceiling.

    Keeps the first system message (or all system messages if multiple
    come first) and as many recent non-system turns as fit under
    `target_tokens`. Splices a `[CONTEXT-EMERGENCY-TRUNCATED]` banner
    into the head's first system message so the model knows context
    was discarded without a summary.

    Returns `(new_history, n_dropped)`. `n_dropped` is 0 when no
    truncation was needed (estimate ≤ target).
    """
    if estimate_tokens(history) <= target_tokens:
        return history, 0
    # Identify leading system block.
    lead = 0
    while lead < len(history) and history[lead].role == "system":
        lead += 1
    head = list(history[:lead])
    body = list(history[lead:])
    # Drop oldest body turns until under target.
    n_dropped = 0
    while body and estimate_tokens(head + body) > target_tokens:
        body.pop(0)
        n_dropped += 1
    note = (
        f"\n\n[CONTEXT-EMERGENCY-TRUNCATED] {n_dropped} earlier turns "
        f"dropped without summary to fit the model's context window. "
        f"Earlier context is lost; ask the user to re-state if needed."
    )
    head = _splice_note_into_head(head, note)
    return head + body, n_dropped
