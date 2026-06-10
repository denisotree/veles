"""WritingMode — the current TUI behaviour, wrapped in the Strategy API.

One `agent.run(prompt)` per user prompt, with streamed text and typed
events funnelled through the context's callbacks. Returns control to the
bridge with a single `TurnDone`. PreviousSession_id is mirrored back into
`AppState` so the next turn resumes the same SessionStore row.
"""

from __future__ import annotations

from veles.core.modes.base import Mode, ModeContext
from veles.tui.messages import TurnDone


class WritingMode:
    name: str = "writing"
    label: str = "write"
    system_block: str = ""  # current default agent prompt is the writing prompt

    def run_turn(self, prompt: str, ctx: ModeContext) -> None:
        agent = ctx.factory(ctx.state)
        result = agent.run(
            prompt,
            on_text_delta=ctx.on_text,
            event_listener=ctx.on_event,
        )
        if ctx.state.session_id is None and result.session_id is not None:
            ctx.state.session_id = result.session_id
        # Record the *effective* mode that drove this turn, so the next
        # turn's mode-switch-observation check sees the truth (matters
        # for AutoMode's sub-dispatch into Writing).
        ctx.state.last_mode_in_session = self.name  # type: ignore[assignment]
        ctx.post(TurnDone(result))


_: Mode = WritingMode()  # static protocol check
