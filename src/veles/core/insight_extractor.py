"""Per-session insight extraction — pulls durable lessons from history.

Closes TASK.md #2.2 ("memory + learning loop"): M22 added per-turn
recall and M28 added a continuous curator that condenses sessions,
but neither pulls *atomic* lessons out — the user saying "remember X"
or a tool error followed by a successful correction. M31 extracts
those; M161 made the `insights` SQL row the canonical store (recall,
aging, and dream dedup operate on it), with a markdown view rendered
to `.veles/memory/insights/` as a regenerable human-readable mirror.

Two heuristic triggers, both detected on the completed `Agent.run`
history (no per-turn LLM cost):

1. **Remember-intent** — the user message starts with `remember`,
   `note that`, `don't forget`, `запомни`, `помни`, `не забудь`,
   `не делай`. Each match is one extraction.

2. **Tool-error recovery** — a tool message whose content begins with
   `<error` (the M27 error format) gets paired with a context window
   of ±3 surrounding turns. The lesson is "what went wrong + how it
   was fixed (or attempted)".

Both run a single sub-Agent call on a cheap model (default
`anthropic/claude-haiku-4.5`) with no tools; the model is asked for a
short markdown body and a kebab-case slug. Each extraction is
persisted via `save_insight_row` (SQL write required — a db failure
means the insight is not persisted), then journalled to the
system-ops log (`op="insight"`).

A trigger that yields an empty summary or fails LLM-side is silently
skipped — the parent run already succeeded and we'd rather lose a
lesson than crash on a follow-up.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from veles.core.provider import Message
from veles.core.slug import normalize_slug as _normalize_slug

if TYPE_CHECKING:
    from veles.core.project import Project
    from veles.core.provider import Provider


_REMEMBER_RE = re.compile(
    r"\b(remember|note that|don'?t forget|never|always)\b"
    r"|(^|\s)(запомни|помни|не\s+забудь|не\s+делай|никогда|всегда)\b",
    re.IGNORECASE,
)
_ERROR_PREFIX = "<error"
_RECOVERY_CONTEXT_WINDOW = 3
_MAX_INSIGHTS_PER_RUN = 5  # safety cap — no runaway extraction


InsightExtractor = Callable[[list[Message], "str | None"], int]


@dataclass(frozen=True, slots=True)
class _RememberTrigger:
    user_idx: int


@dataclass(frozen=True, slots=True)
class _RecoveryTrigger:
    error_idx: int
    window_start: int
    window_end: int  # exclusive


def find_remember_triggers(history: list[Message]) -> list[_RememberTrigger]:
    """Return user-message indices that look like an explicit remember-instruction.

    The match is intentionally conservative: keyword inside the body, not
    a substring of an unrelated word. Hits in non-user messages are
    ignored — the model's own remember-self-talk should not feed back as
    a learned lesson.
    """
    out: list[_RememberTrigger] = []
    for i, m in enumerate(history):
        if m.role != "user" or not m.content:
            continue
        if _REMEMBER_RE.search(m.content):
            out.append(_RememberTrigger(user_idx=i))
    return out


def find_recovery_triggers(history: list[Message]) -> list[_RecoveryTrigger]:
    """Return tool-error indices with their surrounding ±N-turn window.

    The window captures the assistant turn that issued the failing
    tool_call AND the next assistant turns that recovered (or failed
    again). De-duplicated when consecutive tool errors arise within
    one assistant retry — only the first error of a contiguous run is
    reported.
    """
    out: list[_RecoveryTrigger] = []
    last_emitted = -2
    for i, m in enumerate(history):
        if m.role != "tool" or not m.content or not m.content.startswith(_ERROR_PREFIX):
            continue
        if i - last_emitted == 1:
            # Tail of a contiguous error run; the previous trigger's window
            # already covers this one.
            last_emitted = i
            continue
        start = max(0, i - _RECOVERY_CONTEXT_WINDOW)
        end = min(len(history), i + _RECOVERY_CONTEXT_WINDOW + 1)
        out.append(_RecoveryTrigger(error_idx=i, window_start=start, window_end=end))
        last_emitted = i
    return out


def _render_window(history: list[Message], start: int, end: int) -> str:
    blocks: list[str] = []
    for m in history[start:end]:
        tag = m.role
        if m.role == "tool" and m.tool_call_id:
            tag = f"tool[{m.tool_call_id}]"
        body = m.content or ""
        if m.tool_calls:
            calls = ", ".join(f"{tc.name}({tc.arguments})" for tc in m.tool_calls)
            body = (body + "\n" if body else "") + f"<calls: {calls}>"
        blocks.append(f"# {tag}\n{body}")
    return "\n\n".join(blocks)


_REMEMBER_PROMPT = (
    "You are extracting a durable lesson the user explicitly asked to "
    "remember. Read the conversation snippet and produce:\n\n"
    "Line 1: a short kebab-case slug (3-6 words, lowercase, hyphens).\n"
    "Line 2: blank.\n"
    "Line 3+: a markdown body — H1 title, then 1-3 sentences capturing "
    "exactly what should be remembered. No preamble, no apologies, no "
    "meta-commentary. If nothing actionable is in the snippet, output "
    "the single line `SKIP` and nothing else."
)

_RECOVERY_PROMPT = (
    "You are extracting a durable lesson from a tool error and its "
    "recovery. Read the conversation window and produce:\n\n"
    "Line 1: a short kebab-case slug (3-6 words, lowercase, hyphens).\n"
    "Line 2: blank.\n"
    "Line 3+: a markdown body — H1 title, then 1-3 sentences naming "
    "what failed, why, and what the corrected approach was. If the "
    "snippet shows no recovery (the agent gave up), output the single "
    "line `SKIP` and nothing else."
)


def _parse_extractor_output(text: str) -> tuple[str, str] | None:
    """Split sub-agent output into (slug, body) or None if it said SKIP."""
    stripped = text.strip()
    if not stripped or stripped.upper().startswith("SKIP"):
        return None
    lines = stripped.splitlines()
    if len(lines) < 2:
        return None
    slug = _normalize_slug(lines[0].strip()) or ""
    if not slug:
        return None
    body_start = 1
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1
    body = "\n".join(lines[body_start:]).strip()
    if not body:
        return None
    return slug, body


_BATCH_PROMPT = (
    "You are scanning a Veles conversation for insights worth keeping in"
    " the project wiki. Inspect the dialog and propose up to 5 candidate"
    " insights — facts, decisions, gotchas, or reusable patterns the user"
    " or the agent surfaced that would help on a future turn.\n\n"
    "Output one candidate per block, separated by blank lines. Each block"
    " must use this exact shape:\n\n"
    "slug: <kebab-case>\n"
    "title: <human-readable>\n"
    "body:\n"
    "<markdown body, 2-6 lines>\n\n"
    "Skip anything trivial, repetitive, or already obvious from the"
    " current code. If nothing is worth keeping, reply with the single"
    " line 'NONE'."
)


@dataclass(slots=True, frozen=True)
class InsightCandidate:
    slug: str
    title: str
    body: str


def _parse_batch_output(text: str) -> list[InsightCandidate]:
    """Parse the LLM's `slug:/title:/body:` blocks into candidates."""
    text = (text or "").strip()
    if not text or text.upper() == "NONE":
        return []
    candidates: list[InsightCandidate] = []
    current: dict[str, str] = {}
    body_lines: list[str] = []
    in_body = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() and (current or body_lines):
            if in_body:
                current["body"] = "\n".join(body_lines).strip()
            if {"slug", "title", "body"}.issubset(current):
                candidates.append(
                    InsightCandidate(
                        slug=current["slug"].strip(),
                        title=current["title"].strip(),
                        body=current["body"].strip(),
                    )
                )
            current = {}
            body_lines = []
            in_body = False
            continue
        lowered = line.lstrip().lower()
        if lowered.startswith("slug:"):
            if in_body and current:
                current["body"] = "\n".join(body_lines).strip()
                if {"slug", "title", "body"}.issubset(current):
                    candidates.append(
                        InsightCandidate(
                            slug=current["slug"].strip(),
                            title=current["title"].strip(),
                            body=current["body"].strip(),
                        )
                    )
                current = {}
                body_lines = []
                in_body = False
            current["slug"] = line.split(":", 1)[1].strip()
            continue
        if lowered.startswith("title:"):
            current["title"] = line.split(":", 1)[1].strip()
            continue
        if lowered.startswith("body:"):
            in_body = True
            tail = line.split(":", 1)[1].strip()
            if tail:
                body_lines.append(tail)
            continue
        if in_body:
            body_lines.append(line)
    if in_body and current:
        current["body"] = "\n".join(body_lines).strip()
    if {"slug", "title", "body"}.issubset(current):
        candidates.append(
            InsightCandidate(
                slug=current["slug"].strip(),
                title=current["title"].strip(),
                body=current["body"].strip(),
            )
        )
    return candidates


def batch_extract_insights(
    history: list[Message],
    *,
    provider: Provider,
    model: str,
    max_candidates: int = 5,
) -> list[InsightCandidate]:
    """M87: scan the whole dialog and return insight candidates without
    persisting them. The TUI surfaces candidates as a `/save` picker;
    the user accepts one at a time, no implicit writes."""
    from veles.core.agent import Agent
    from veles.core.tools.registry import Registry

    if not history:
        return []
    snippet = _render_window(history, 0, len(history))
    sub = Agent(
        provider=provider,
        registry=Registry(),
        model=model,
        max_iterations=1,
        system_prompt=_BATCH_PROMPT,
        max_tokens=2048,
    )
    try:
        result = sub.run(snippet)
    except Exception:
        return []
    return _parse_batch_output(result.text or "")[:max_candidates]


def make_insight_extractor(
    *,
    provider: Provider,
    model: str,
    project: Project,
    max_insights: int = _MAX_INSIGHTS_PER_RUN,
) -> InsightExtractor:
    """Build an `InsightExtractor` that scans completed history and
    persists one `insights` row (+ rendered memory view) per detected
    trigger.

    The sub-Agent shares the parent's `TokenBudget` (ContextVar) and
    runs with no tools. An LLM failure on a single trigger is logged
    via stderr but doesn't abort the remaining triggers — partial
    extraction is better than total loss.
    """
    from veles.core.agent import Agent
    from veles.core.memory.artefacts import append_memory_log
    from veles.core.tools.builtin.memory_save import save_insight_row
    from veles.core.tools.registry import Registry

    def _extract_one(prompt: str, snippet: str) -> tuple[str, str] | None:
        sub = Agent(
            provider=provider,
            registry=Registry(),
            model=model,
            max_iterations=1,
            system_prompt=prompt,
            max_tokens=512,
        )
        try:
            result = sub.run(snippet)
        except Exception:
            return None
        return _parse_extractor_output(result.text or "")

    def _persist_one(*, prompt: str, snippet: str, slug_id: str, trigger_label: str) -> int:
        """Run one extractor pass and persist the result. Returns 1 on success, 0 otherwise."""
        parsed = _extract_one(prompt, snippet)
        if parsed is None:
            return 0
        slug, body = parsed
        title = slug.replace("-", " ").title()
        # SQL row is canonical — a db failure means the insight is NOT
        # persisted (no orphaned markdown that recall can't see).
        rid = save_insight_row(title=title, body=body, category=trigger_label, project=project)
        if rid == 0:
            return 0
        with contextlib.suppress(Exception):
            append_memory_log(
                project,
                op="insight",
                summary=f"{trigger_label}: session {slug_id} -> insight #{rid}",
            )
        return 1

    def _extract(history: list[Message], session_id: str | None) -> int:
        triggers_remember = find_remember_triggers(history)
        triggers_recovery = find_recovery_triggers(history)
        if not triggers_remember and not triggers_recovery:
            return 0
        # Cap to avoid runaway when the user has many "remember" prompts in
        # one session; most-recent wins.
        triggers_remember = triggers_remember[-max_insights:]
        budget_left = max_insights - len(triggers_remember)
        triggers_recovery = triggers_recovery[-max(0, budget_left) :]

        slug_id = session_id or "session"
        written = 0

        for trig in triggers_remember:
            window_start = max(0, trig.user_idx - 1)
            window_end = min(len(history), trig.user_idx + 2)
            written += _persist_one(
                prompt=_REMEMBER_PROMPT,
                snippet=_render_window(history, window_start, window_end),
                slug_id=slug_id,
                trigger_label="remember-trigger",
            )

        for rtrig in triggers_recovery:
            written += _persist_one(
                prompt=_RECOVERY_PROMPT,
                snippet=_render_window(history, rtrig.window_start, rtrig.window_end),
                slug_id=slug_id,
                trigger_label="recovery-trigger",
            )

        return written

    return _extract
