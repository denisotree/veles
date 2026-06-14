"""Advisor pattern (M44) — independent-reviewer tool for the agent.

VISION §5.3.1 advisor: a parent agent should be able to call out to a
second LLM at "checkpoint" moments (a finalised plan, an architectural
decision, a final answer) for an independent review. The reviewer has
no tools, no persistence, no continuation — its job is to flag concerns
and suggest improvements without doing the work itself.

This tool spawns a tool-less, single-iteration sub-agent on the routed
`advisor` task (default in `routing.DEFAULT_TASKS`). The sub-agent is
prompted to return strict JSON of shape:

    {"ok": true|false, "concerns": ["..."], "suggestions": ["..."]}

The handler parses that JSON, falls back to a "concerns: parse failed"
verdict on bad output, and renders a human-readable string for the
parent agent to incorporate into its next turn.

The sub-agent uses the parent's `current_budget` ContextVar (token
budget propagates naturally) and `current_project` ContextVar to look
up routing. If no project is active, or the routed provider has no
API key set, the tool returns a one-line `<advisor unavailable: ...>`
message — the parent agent can decide whether to proceed without
review.

The advisor tool is **not** marked sensitive (M38) — invoking it is an
explicit user-flow choice, the network call is to the same class of
backend the user already authorised when launching `veles run`, and
re-prompting on every advisor call would defeat the pattern.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

_ADVISOR_SYSTEM_PROMPT = (
    "You are an independent reviewer. The user will present a plan, "
    "design decision, or final answer. Your job is to flag concerns and "
    "suggest improvements without doing the work yourself.\n\n"
    "Respond with a JSON object on a single line:\n\n"
    '{"ok": true|false, "concerns": ["..."], "suggestions": ["..."]}\n\n'
    '- "ok" is false if you found any blocking concern.\n'
    '- "concerns" lists problems that should be addressed before proceeding.\n'
    '- "suggestions" lists improvements the user should consider.\n\n'
    "Keep each item to one short sentence. Return JSON only — no prose, "
    "no code fences."
)


@dataclass(slots=True)
class Verdict:
    ok: bool = True
    concerns: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def call_advisor(input_text: str, *, system_prompt: str | None = None) -> str:
    """Direct provider call to the routed advisor model.

    Lower-level than the `advisor_review` tool: callers (GoalMode's CHECK
    phase) get the raw model output without the structured-verdict
    rendering. Returns a `<advisor unavailable: ...>` / `<advisor failed: ...>`
    sentinel string on any error so the caller can decide how to handle
    it (treat as off-track, abort the FSM, etc.).
    """
    from veles.core.agent import Agent
    from veles.core.context import current_project
    from veles.core.provider_factory import has_api_key, make_provider
    from veles.core.routing import route
    from veles.core.tools.registry import Registry

    project = current_project()
    if project is None:
        return "<advisor unavailable: no active project>"
    from veles.core.model_resolver import ConfigurationError

    try:
        provider_name, model = route("advisor", project)
    except ConfigurationError as exc:
        return f"<advisor unavailable: {exc}>"
    if not has_api_key(provider_name):
        return f"<advisor unavailable: no API key for routed provider {provider_name!r}>"
    try:
        provider = make_provider(provider_name, model=model)
    except Exception as exc:
        return f"<advisor unavailable: failed to build {provider_name!r}: {exc}>"

    sub_agent = Agent(
        provider=provider,
        registry=Registry(),
        model=model,
        max_iterations=1,
        system_prompt=system_prompt or _ADVISOR_SYSTEM_PROMPT,
    )
    try:
        result = sub_agent.run(input_text)
    except Exception as exc:
        return f"<advisor failed: {type(exc).__name__}: {exc}>"
    return result.text or ""


@tool(risk_class=RiskClass.COMPUTE_ONLY)
def advisor_review(plan_or_decision: str) -> str:
    """Run a second-opinion sub-agent over `plan_or_decision`.

    Use this when committing to a plan, finalising an architectural
    decision, or before delivering a substantive answer. Pass the full
    text being reviewed; the tool returns a structured verdict
    (``ADVISOR VERDICT: OK`` or ``CONCERNS`` plus bullets) that should
    inform — but not replace — your own judgement.
    """
    raw = call_advisor(plan_or_decision)
    if raw.startswith("<advisor unavailable") or raw.startswith("<advisor failed"):
        return raw
    return render_verdict(parse_verdict(raw))


def parse_verdict(raw: str) -> Verdict:
    """Decode the advisor's JSON output into a `Verdict`.

    Tolerates ```code-fenced JSON, returns a "parse failure" verdict on
    invalid input rather than raising — the parent agent should always
    receive a usable signal.
    """
    text = raw.strip()
    if text.startswith("```"):
        # Strip an opening fence (```json or ```) and a closing one if present.
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: -len("```")]
        text = text.strip()
    if not text:
        return Verdict(ok=False, concerns=["advisor returned an empty response"])
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        snippet = raw[:200].replace("\n", " ")
        return Verdict(
            ok=False,
            concerns=[f"advisor returned non-JSON output: {snippet}"],
        )
    if not isinstance(data, dict):
        return Verdict(ok=False, concerns=["advisor returned non-object JSON"])
    ok = bool(data.get("ok", False))
    raw_concerns = data.get("concerns") or []
    raw_suggestions = data.get("suggestions") or []
    concerns = [str(c) for c in raw_concerns if isinstance(c, str) and c.strip()]
    suggestions = [str(s) for s in raw_suggestions if isinstance(s, str) and s.strip()]
    return Verdict(ok=ok, concerns=concerns, suggestions=suggestions)


def render_verdict(verdict: Verdict) -> str:
    """Format a `Verdict` as a parent-agent-readable text block."""
    label = "OK" if verdict.ok and not verdict.concerns else "CONCERNS"
    lines = [f"ADVISOR VERDICT: {label}"]
    if verdict.concerns:
        lines.append("Concerns:")
        for c in verdict.concerns:
            lines.append(f"- {c}")
    if verdict.suggestions:
        lines.append("Suggestions:")
        for s in verdict.suggestions:
            lines.append(f"- {s}")
    if not verdict.concerns and not verdict.suggestions:
        lines.append("(no concerns, no suggestions)")
    return "\n".join(lines)
