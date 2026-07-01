"""AutoMode — smart default that picks between planning and writing.

A short prompt that's basically a chat reply ("what's in README?",
"rename X to Y") shouldn't pay the planning tax. A complex one
("design a migration", "refactor the trust ladder") usually benefits
from a written plan first.

AutoMode classifies the prompt with one direct provider call — NOT a
sub-Agent. Sub-Agents persist synthetic user/assistant messages to
SessionStore and emit trace records, neither of which belongs in a
routing decision. On `plan` it dispatches to `PlanningMode`; on
`direct` (or any unparseable response) to `WritingMode`. The routing
verdict is logged to chat as a system line so the user sees what auto
chose before the assistant starts streaming.

The sub-Mode is the one that writes `state.last_mode_in_session`, so
mid-session mode detection sees the *effective* mode (writing/
planning), not the user-selected `"auto"`.
"""

from __future__ import annotations

from typing import Literal

from veles.core.modes.base import Mode, ModeContext
from veles.core.modes.planning import PlanningMode
from veles.core.modes.writing import WritingMode
from veles.core.provider import Message

Verdict = Literal["direct", "plan"]

_CLASSIFIER_SYSTEM = (
    "Route the user request to one execution mode. Answer with exactly one\n"
    "lowercase word.\n"
    "  - `direct`: DO the work now — answer, read, edit, run commands, or\n"
    "    carry out a task, EVEN IF it takes several steps or tool calls.\n"
    "    This is the default; prefer it.\n"
    "  - `plan`: ONLY when the user explicitly asks you to plan / design /\n"
    "    research an approach FIRST, or the task is genuinely large and\n"
    "    ambiguous enough that writing a plan before touching anything is\n"
    "    clearly warranted. A request to carry out or EXECUTE work (e.g.\n"
    "    'do it', 'implement the plan', 'выполни', 'реализуй') is `direct`,\n"
    "    never `plan`.\n"
    "When unsure, answer `direct`.\n"
    "Respond with the single word, no punctuation, no prose."
)


def classify(prompt: str, provider, model: str) -> Verdict:
    """One round-trip to `provider.create_message`. Returns `"plan"` iff
    the model emits a token starting with `plan` (case-insensitive);
    everything else (including parse failures and provider errors) →
    `"direct"`. The default is intentionally permissive: forcing the
    user through planning on an ambiguous response is more annoying
    than the inverse, and PlanningMode is a strict read-only sandbox
    so a miss there can't damage anything."""
    try:
        resp = provider.create_message(
            [
                Message(role="system", content=_CLASSIFIER_SYSTEM),
                Message(role="user", content=prompt),
            ],
            tools=None,
            model=model,
            max_tokens=8,
        )
    except Exception:
        return "direct"
    text = (resp.text or "").strip().lower()
    return "plan" if text.startswith("plan") else "direct"


class AutoMode:
    name: str = "auto"
    label: str = "auto"
    # AutoMode itself doesn't tune model behaviour — its sub-Mode does.
    system_block: str = ""

    def run_turn(self, prompt: str, ctx: ModeContext) -> None:
        from veles.tui.messages import SystemLine

        # Build a throwaway Agent in writing-mode config to harvest its
        # `provider` reference. Agent.__init__ is cheap (no SessionStore
        # writes, no network); the classifier call below uses `.provider`
        # directly so SessionStore stays clean of synthetic routing turns.
        scratch = ctx.factory(ctx.state, mode_override="writing")
        verdict = classify(prompt, scratch.provider, ctx.state.model)
        ctx.post(SystemLine(text=f"[auto → {verdict}]"))

        sub: Mode = PlanningMode() if verdict == "plan" else WritingMode()
        sub.run_turn(prompt, ctx)


_: Mode = AutoMode()  # static protocol check
