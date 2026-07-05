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
def ask_user(question: str, options: list[str] | None = None) -> str:
    """Ask the user a short clarifying question and return their answer.

    Use this ONLY when you genuinely cannot proceed without a decision or
    detail that only the user can provide — an ambiguous requirement, a missing
    preference, a choice between real alternatives. Ask one focused question,
    not a list.

    When you are offering a CHOICE between concrete alternatives, ALWAYS pass
    them as `options` (e.g. `options=["Rename now", "Archive instead", "Skip"]`)
    instead of listing them in the question prose — the UI then presents them as
    an interactive picker (arrow-select, with a free-text "other" entry), which
    is far better than the user retyping an answer. The user may still type a
    free-text reply, so handle an answer that isn't one of your options.

    If no interactive user is available the tool returns a notice telling you to
    proceed on your best assumption instead of blocking.
    """
    answer = ask_user_question(question, options or None)
    if answer is None or not answer.strip():
        return _NO_HUMAN
    return answer
