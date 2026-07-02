"""WritingMode — the current TUI behaviour, wrapped in the Strategy API.

One `agent.run(prompt)` per user prompt, with streamed text and typed
events funnelled through the context's callbacks. Returns control to the
bridge with a single `TurnDone`. PreviousSession_id is mirrored back into
`AppState` so the next turn resumes the same SessionStore row.
"""

from __future__ import annotations

from veles.core.modes.base import Mode, ModeContext, wrap_mode_switch_observation
from veles.tui.messages import TurnDone

# Injected once, into the first prompt after switching TO writing from another
# mode. WritingMode's `system_block` is empty (the base prompt IS the writing
# prompt), so `wrap_mode_switch_observation` would short-circuit — we pass this
# note as the block instead. It must be assertive: a model resumed mid-session
# still sees its own earlier planning-mode refusals ("switch to writing first")
# in history and, without this, keeps parroting them even though the switch
# already happened.
_SWITCH_NOTE = (
    "You are NOT in planning anymore. Any planning-mode restriction on modifying "
    "files or running tools is LIFTED — write_file, edit_file, move_file, "
    "delete_file, make_dir, run_shell and the wiki tools are all available now. "
    "If an earlier turn told the user to switch to writing before acting, that "
    "switch has ALREADY happened: do not ask them to switch again — carry out the "
    "requested changes now."
)


class WritingMode:
    name: str = "writing"
    label: str = "write"
    system_block: str = ""  # current default agent prompt is the writing prompt

    def run_turn(self, prompt: str, ctx: ModeContext) -> None:
        # When the mode just changed to writing (e.g. planning → writing via
        # Shift+Tab), tell the model — otherwise the switch is invisible to it
        # and it keeps refusing on stale planning-mode grounds.
        effective_prompt = prompt
        if (
            ctx.state.last_mode_in_session is not None
            and ctx.state.last_mode_in_session != self.name
        ):
            effective_prompt = wrap_mode_switch_observation(prompt, self.name, _SWITCH_NOTE)
        agent = ctx.factory(ctx.state)
        result = agent.run(
            effective_prompt,
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
