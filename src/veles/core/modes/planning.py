"""PlanningMode — read-only research that ends with a plan artifact.

Two enforcement layers, both intentional:

  * Permission Engine (`core/permission/engine.py:_planning_mode_rule`)
    — the source of truth. When the Agent is built with
    `plan_mode=True`, the engine sets `AgentState.PLANNING` and denies
    every mutation-class tool call (write_file, run_shell, …).
    DRAFT_ONLY is intentionally outside the mutation set, so the
    `create_plan` tool keeps working.

  * `[planning]` toolset — UX layer. The model never sees `write_file`
    or `run_shell` schemas, so it doesn't burn a turn discovering they're
    denied. The factory in `veles.tui:run_tui` reads the active mode and
    picks this toolset's registry.

Mid-session mode switches inject a `<mode-switch-observation>` block
into the next user prompt (see `wrap_mode_switch_observation`). Fresh
sessions get the same text appended to the constructor system prompt.

A planning turn ends one of three ways:
  1. The model asks a clarifying question (no tool call, no plan yet) —
     `agent.run` returns naturally, user answers next turn.
  2. The model calls `create_plan(...)` — plan artifact persisted; the
     model's closing message quotes the plan id + path.
  3. The model calls a forbidden tool — engine denies it, the typed
     observation lands in the loop, the model adapts.
"""

from __future__ import annotations

from veles.core.modes.base import Mode, ModeContext, wrap_mode_switch_observation
from veles.tui.messages import TurnDone

_SYSTEM_BLOCK = """\
<mode name="planning">
You are in PLANNING mode. No mutations are allowed — `write_file`,
`run_shell`, and any tool that changes external state will be denied
by the Permission Engine. If you see a `planning_mode` refusal,
adapt; do not retry the same call.

Workflow for every user prompt in this mode:
  1. If essential information is missing to write a useful plan,
     ask EXACTLY ONE clarifying question, then stop. The user will
     answer in the next turn and you can continue.
  2. Otherwise: gather context with the read-only tools available
     (read_file, wiki_*, web_search, fetch_url, pdf_read,
     image_describe). Optionally call `advisor_review` on a draft
     of your thinking for a second opinion.
  3. When you have enough, call the `create_plan` tool with a
     structured plan (objective + steps + assumptions + risks +
     done_condition + tools_required). The tool returns
     `{plan_id, path}` — quote the id and path in your closing
     message. Do not paste the full plan body; the artifact file is
     the deliverable.

Output style:
  - Be concise. The user reads the plan file, not the chat.
  - One clarifying question per turn — never a batch.
  - When done, a one-line confirmation like
    `plan p-3f4b9a created at .veles/plans/active/p-3f4b9a.md`.
</mode>
"""


class PlanningMode:
    name: str = "planning"
    label: str = "plan"
    system_block: str = _SYSTEM_BLOCK

    def run_turn(self, prompt: str, ctx: ModeContext) -> None:
        # On a mid-session mode change, the Agent won't re-emit the
        # constructor system prompt (agent.py:336-339). The wrapper
        # prepends a one-shot observation block to the user prompt so
        # the model sees the new mode's rules without rebuilding the
        # session.
        effective_prompt = prompt
        if (
            ctx.state.session_id is not None
            and ctx.state.last_mode_in_session is not None
            and ctx.state.last_mode_in_session != self.name
        ):
            effective_prompt = wrap_mode_switch_observation(
                prompt, self.name, self.system_block
            )

        agent = ctx.factory(ctx.state, mode_override=self.name)
        result = agent.run(
            effective_prompt,
            on_text_delta=ctx.on_text,
            event_listener=ctx.on_event,
        )
        if ctx.state.session_id is None and result.session_id is not None:
            ctx.state.session_id = result.session_id
        ctx.state.last_mode_in_session = self.name  # type: ignore[assignment]
        ctx.post(TurnDone(result))


_: Mode = PlanningMode()  # static protocol check
