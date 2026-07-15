"""Discovery half of proactive delivery (M214): pull *definite dated events*
out of memory so the dream loop can materialise them as reminders.

Deliberately conservative — the user asked to be notified "only about things
that will definitely happen". The LLM is instructed to emit an event ONLY when
it has a concrete date/time and is certain to occur; anything speculative,
vague, undated, or already past is dropped. A round that finds nothing returns
`[]` and the dream step is a no-op.

Compose-once: the notification text (title + optional body) is finalised HERE,
at discovery. The delivery loop later sends it verbatim with no second LLM call
— so retries are idempotent and there is no delivery-time hallucination.

`dedup_key` is derived from the normalised title alone (not the time), so a
rescheduled event re-arms the SAME reminder row (`upsert_dream_event`) instead
of spawning a duplicate. This is the pure extractor; the dream wiring assembles
the corpus and writes the rows.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from veles.core.provider import Message, Provider

_MAX_CORPUS_CHARS = 8000

_SYSTEM = (
    "You extract definite, dated future events from a person's notes so an "
    "assistant can remind them. You are conservative: you would rather miss a "
    "vague event than invent one."
)

_PROMPT = """Read the NOTES below and list events that meet ALL of these:
- has a CONCRETE date and time (or a clearly-resolvable one like "today 20:00");
- WILL DEFINITELY happen (a scheduled/committed event, not a maybe, a wish, or a habit);
- is in the FUTURE relative to the current time.

EXCLUDE anything speculative ("maybe", "should", "sometime"), undated, purely
recurring with no concrete next occurrence, or already past.

Output ONLY a JSON array. Each item has keys:
  "title": short imperative reminder
  "when": ISO-8601 datetime with timezone
  "note": optional extra context
If nothing qualifies, output exactly: []

Current time (ISO-8601): {now_iso}

NOTES:
{corpus}
"""


@dataclass(slots=True)
class ProactiveEvent:
    """A definite dated event, ready to materialise as a reminder."""

    dedup_key: str
    title: str
    body: str | None
    due_at: float  # unix seconds


def _dedup_key(title: str) -> str:
    norm = re.sub(r"\s+", " ", title.strip().lower())
    return "dream-" + hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def _parse_iso(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = _dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.UTC)
    return parsed.timestamp()


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    """Best-effort: pull the first JSON array out of an LLM reply, tolerating
    ```json fences and surrounding prose."""
    if not text:
        return []
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    blob = fenced.group(1) if fenced else None
    if blob is None:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end < start:
            return []
        blob = text[start : end + 1]
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return []
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def extract_definite_events(
    *,
    corpus: str,
    now: float,
    provider: Provider,
    model: str,
    max_tokens: int = 1024,
) -> list[ProactiveEvent]:
    """Ask the model for definite dated future events in `corpus`. Returns an
    empty list on an empty corpus, a parse failure, or nothing qualifying."""
    if not corpus.strip():
        return []
    now_iso = _dt.datetime.fromtimestamp(now, tz=_dt.UTC).isoformat()
    prompt = _PROMPT.format(now_iso=now_iso, corpus=corpus[:_MAX_CORPUS_CHARS])
    response = provider.create_message(
        [Message(role="system", content=_SYSTEM), Message(role="user", content=prompt)],
        model=model,
        max_tokens=max_tokens,
    )
    events: list[ProactiveEvent] = []
    seen: set[str] = set()
    for item in _extract_json_array(response.text or ""):
        title = str(item.get("title", "")).strip()
        due_at = _parse_iso(item.get("when"))
        if not title or due_at is None or due_at <= now:
            continue  # definite FUTURE dated events only
        key = _dedup_key(title)
        if key in seen:
            continue  # collapse same-title dupes within one round
        seen.add(key)
        note = item.get("note")
        body = str(note).strip() if note and str(note).strip() else None
        events.append(ProactiveEvent(dedup_key=key, title=title, body=body, due_at=due_at))
    return events


__all__ = ["ProactiveEvent", "extract_definite_events"]
