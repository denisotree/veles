"""M170 — generalized verify→escalate seam.

Lifts the GoalMode CHECK pattern (an advisor judges; the FSM re-plans on
off-track) into a reusable, mode-agnostic decision usable from plain
`veles run` and, next, the daemon turn path. A cheap/local base model
answers; an advisor-tier model (routed `advisor`, which may be a
`claude-cli`) judges whether the answer is sound and grounded in the
evidence; on a confident FAIL the prompt is re-run on the stronger model —
the "fallback в умную CLI-модель при галлюцинациях" of the work bot.

**Three-state verdict, deliberately.** PASS → keep the answer, FAIL →
escalate, UNKNOWN → keep the answer. UNKNOWN covers BOTH an unavailable
advisor AND an unparseable judge response: a flaky judge must never trigger
an expensive tier-1 re-run it didn't actually call for. `parse_verdict`
(advisor.py) collapses parse-failure to `ok=False`, which would mean
"escalate" here — so this module parses the judge output itself
(`_parse_judge`) to keep parse-failure in UNKNOWN, not FAIL.

`verify_and_maybe_escalate` is pure and injection-based (verifier +
escalator passed in), so the same decision drives the CLI and the daemon
without duplicated logic; only the escalator's concrete return type differs
(a CLI `RunResult`, a daemon turn outcome, or a plain string in tests).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from veles.core.tools.builtin.advisor import call_advisor

# Verifier: (prompt, answer) -> (verdict, concerns). Concerns are only
# meaningful for FAIL; PASS/UNKNOWN return an empty list.
Verifier = Callable[[str, str], "tuple[VerifyVerdict, list[str]]"]
# Escalator: (prompt) -> stronger model's result (any type the caller wants
# back — a RunResult, a string, ...). None disables escalation (flag only).
Escalator = Callable[[str], Any]


class VerifyVerdict(Enum):
    PASS = "pass"  # answer is sound/grounded — keep it
    FAIL = "fail"  # confident, parseable rejection — escalate
    UNKNOWN = "unknown"  # advisor unavailable or judge unparseable — keep it


@dataclass(slots=True)
class VerifyOutcome:
    verdict: VerifyVerdict
    escalated: bool = False
    concerns: list[str] = field(default_factory=list)
    # The escalator's return value when `escalated` is True, else None.
    escalated_result: Any | None = None


def verify_and_maybe_escalate(
    prompt: str,
    answer: str,
    *,
    verifier: Verifier,
    escalator: Escalator | None = None,
) -> VerifyOutcome:
    """Judge `answer`; on a confident FAIL re-run `prompt` via `escalator`.

    PASS / UNKNOWN keep the original answer and never call the escalator.
    Only FAIL with an escalator wired produces `escalated=True` and an
    `escalated_result`.
    """
    verdict, concerns = verifier(prompt, answer)
    if verdict is not VerifyVerdict.FAIL or escalator is None:
        return VerifyOutcome(verdict=verdict, escalated=False, concerns=concerns)
    escalated_result = escalator(prompt)
    return VerifyOutcome(
        verdict=verdict,
        escalated=True,
        concerns=concerns,
        escalated_result=escalated_result,
    )


_VERIFY_SYSTEM = (
    "You are a verification judge. You are given a user QUESTION, the agent's "
    "ANSWER, and (when available) the EVIDENCE the agent actually gathered — "
    "its tool calls and their results. Judge whether the answer is correct and "
    "GROUNDED in that evidence: flag hallucinated facts, unsupported claims, or "
    "numbers/values that do not appear in the evidence.\n\n"
    "Respond with a JSON object on a single line:\n\n"
    '{"ok": true|false, "concerns": ["..."]}\n\n'
    '- "ok" is true ONLY if the answer is sound and supported by the evidence.\n'
    '- "ok" is false if you find any hallucination or unsupported claim.\n'
    '- "concerns" lists the specific problems (one short sentence each).\n\n'
    "Return JSON only — no prose, no code fences."
)


def _parse_judge(raw: str) -> tuple[VerifyVerdict, list[str]]:
    """Map a judge response to a 3-state verdict.

    Unparseable / wrong-shape / empty → UNKNOWN (NOT FAIL): we must not
    escalate on the judge's own malfunction. `ok=true` → PASS, `ok=false`
    → FAIL with concerns.
    """
    text = raw.strip()
    if text.startswith("```"):
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: -len("```")]
        text = text.strip()
    if not text:
        return VerifyVerdict.UNKNOWN, []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return VerifyVerdict.UNKNOWN, []
    if not isinstance(data, dict) or "ok" not in data:
        return VerifyVerdict.UNKNOWN, []
    concerns = [str(c) for c in (data.get("concerns") or []) if isinstance(c, str) and c.strip()]
    return (VerifyVerdict.PASS, []) if bool(data.get("ok")) else (VerifyVerdict.FAIL, concerns)


def advisor_verifier(
    prompt: str, answer: str, *, evidence: str = ""
) -> tuple[VerifyVerdict, list[str]]:
    """Default verifier: ask the routed advisor model to judge the answer.

    Feeds the gathered `evidence` (tool-call trace) alongside the answer so
    the judge can catch grounding errors, not just incoherent prose. An
    unavailable/failed advisor maps to UNKNOWN (keep the answer).
    """
    body = f"QUESTION:\n{prompt}\n\nANSWER:\n{answer}\n"
    if evidence:
        body += f"\nEVIDENCE (tool calls + results the agent used):\n{evidence}\n"
    raw = call_advisor(body, system_prompt=_VERIFY_SYSTEM)
    if raw.startswith("<advisor unavailable") or raw.startswith("<advisor failed"):
        return VerifyVerdict.UNKNOWN, []
    return _parse_judge(raw)


__all__ = [
    "Escalator",
    "Verifier",
    "VerifyOutcome",
    "VerifyVerdict",
    "advisor_verifier",
    "verify_and_maybe_escalate",
]
