"""`ask_user` — the agent asks the human a free-text clarifying question (M148).

Non-sensitive: it performs no action, it just asks — so it is not trust-gated.
When no interactive human is available (non-TTY, autopilot, daemon, or a UI
that opted out of blocking), the tool tells the agent to proceed on its best
assumption rather than blocking, so it is safe in headless and unattended runs.
"""

from __future__ import annotations

from veles.core.risk import RiskClass
from veles.core.tools.registry import tool
from veles.core.user_prompt import ask_user_question

_NO_HUMAN = (
    "(No interactive user is available to answer right now. Proceed with your "
    "best assumption and state the assumption you made, so it can be corrected "
    "later.)"
)


@tool(risk_class=RiskClass.READ_ONLY, side_effects=[])
def ask_user(question: str) -> str:
    """Ask the user a short clarifying question and return their answer.

    Use this ONLY when you genuinely cannot proceed without a decision or
    detail that only the user can provide — an ambiguous requirement, a missing
    preference, a choice between real alternatives. Ask one focused question,
    not a list. If no interactive user is available the tool returns a notice
    telling you to proceed on your best assumption instead of blocking.
    """
    answer = ask_user_question(question)
    if answer is None or not answer.strip():
        return _NO_HUMAN
    return answer
