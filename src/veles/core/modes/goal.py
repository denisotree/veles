"""GoalMode — the ultimate FSM-driven task-execution mode.

Phases (stored on the `Goal` artifact, so a TUI restart picks up where
the previous session left off):

    INTERVIEW → CONFIRM → PLAN → EXECUTE → CHECK → DONE
                              ↓        ↑       │
                              └────────┼───────┘ (off_track → re-plan)
                                       │
                                       └ step_ok_continue

Per-turn dispatch (one user prompt = one phase transition):

    INTERVIEW: model asks ONE clarifying question; when it has enough,
               it emits `<ready>summary</ready>`. Parser → CONFIRM.
    CONFIRM:   direct provider call (no agent.run, no SessionStore
               write) emits the localized "let me check I got this
               right: …" confirmation line.
               User's NEXT prompt is read as ack ("yes" → PLAN) or
               edits ("no, …" → INTERVIEW, summary cleared).
    PLAN:      `agent.run` in planning configuration. Model emits a
               `create_plan` tool call (→ EXECUTE) or `<infeasible>`
               (→ goal cancelled, mode → auto).
    EXECUTE:   model runs one step in writing configuration, then
               returns. FSM advances to CHECK.
    CHECK:     direct call to routed advisor returning strict JSON
               `{"verdict": "goal_reached"|"step_ok_continue"|
                            "step_off_track", "reason": "..."}`.
               Branch → DONE / EXECUTE / PLAN.
    DONE:      mark plan completed, mark goal completed, mode → auto.

Cooperative interrupt point: after CHECK, the FSM posts a system line
and waits for the user. They type `continue` to advance the next
step, or any other prompt (which the model will see in INTERVIEW/PLAN
context depending on phase). No Ctrl+C plumbing needed.
"""

from __future__ import annotations

import contextlib
import json
import re
from typing import Literal

from veles.core.modes.base import Mode, ModeContext
from veles.tui.messages import SystemLine, TurnDone

# ---- system prompts per phase ----

_INTERVIEW_SYSTEM = """\
<mode name="goal" phase="interview">
You are in GOAL mode, INTERVIEW phase. The user gave you a high-level
task. Your job: ask short clarifying questions, ONE per turn, until you
have a precise picture of:

  - the objective (what the user wants accomplished)
  - the done condition (how we'll know it's complete)
  - non-obvious constraints (deadlines, tools, files to leave alone)

When you believe you have enough, instead of asking another question
emit on a single line:

    <ready>One short paragraph summarising the objective + done condition + key constraints.</ready>

Until then, ask ONE question per turn and stop. Don't number, don't
batch, don't preface with chit-chat.
</mode>
"""

_PLAN_SYSTEM = """\
<mode name="goal" phase="plan">
The user confirmed the following objective summary:

  {summary}

You are in GOAL mode, PLAN phase. Read context (read_file, wiki_*,
web_search, fetch_url). When you have enough, call `create_plan`
with a structured plan covering objective + steps + assumptions +
risks + done_condition. The Permission Engine blocks mutations in
this phase except DRAFT_ONLY tools (which `create_plan` is).

If the task is infeasible given the constraints you've learned, emit
on a single line instead:

    <infeasible>One sentence explaining why.</infeasible>

Do not retry mutation tools after a refusal — the engine will deny
them and you'll burn turns. Plan first; the EXECUTE phase will run
the steps with full tool access.
</mode>
"""

_EXECUTE_SYSTEM_TEMPLATE = """\
<mode name="goal" phase="execute">
You are executing step {step_idx} of the plan:

    {step_text}

Plan context:
{plan_summary}

Tool access is unrestricted in this phase. Run the step, then STOP —
do not start the next step. The orchestrator will route to a CHECK
phase after this turn, then back here for the next step.
</mode>
"""

_CHECK_SYSTEM = """\
You are reviewing a single step that was just executed against a
larger goal. Respond with EXACTLY one line of strict JSON:

    {"verdict": "goal_reached|step_ok_continue|step_off_track", "reason": "<one short sentence>"}

- `goal_reached`     — the goal's done_condition is now satisfied.
- `step_ok_continue` — the step succeeded; more steps are needed.
- `step_off_track`   — the step misaligned with the plan or the goal;
                        the plan needs revision.

Output ONLY the JSON line. No prose, no fences, no leading/trailing
whitespace.
"""


# ---- regex helpers ----

_READY_RE = re.compile(r"<ready>(.*?)</ready>", re.DOTALL | re.IGNORECASE)
_INFEASIBLE_RE = re.compile(r"<infeasible>(.*?)</infeasible>", re.DOTALL | re.IGNORECASE)

Verdict = Literal["goal_reached", "step_ok_continue", "step_off_track"]


def parse_ready_marker(text: str) -> str | None:
    """Return the summary inside `<ready>…</ready>` or None."""
    m = _READY_RE.search(text or "")
    return m.group(1).strip() if m else None


def parse_infeasible_marker(text: str) -> str | None:
    m = _INFEASIBLE_RE.search(text or "")
    return m.group(1).strip() if m else None


def parse_check_verdict(raw: str) -> tuple[Verdict, str]:
    """Decode the advisor's JSON verdict. Defaults to `step_off_track`
    on any parse failure so a malformed advisor reply triggers a
    re-plan rather than silently advancing or completing."""
    text = (raw or "").strip()
    if text.startswith("```"):
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: -len("```")]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ("step_off_track", f"advisor JSON parse failed: {raw[:80]}")
    if not isinstance(data, dict):
        return ("step_off_track", "advisor returned non-object")
    verdict = str(data.get("verdict") or "")
    if verdict not in ("goal_reached", "step_ok_continue", "step_off_track"):
        return ("step_off_track", f"advisor verdict unknown: {verdict!r}")
    reason = str(data.get("reason") or "")
    return (verdict, reason)  # type: ignore[return-value]


# ---- yes/no parsing ----


def _classify_confirm_reply(prompt: str) -> Literal["yes", "no", "cancel"]:
    """Permissive: any prompt starting with 'yes'/'да'/'ok' → yes;
    starting with 'cancel'/'отмен' → cancel; anything else → no
    (treated as edits, returns to INTERVIEW). Case-insensitive."""
    p = (prompt or "").strip().lower()
    if p.startswith(("cancel", "отмен")):
        return "cancel"
    if p.startswith(("yes", "y ", "y\n", "да", "ok", "ага")) or p in {"y", "yes!"}:  # noqa: RUF001 — Russian replies are parsed bilingually
        return "yes"
    return "no"


# ---- goal mode ----


class GoalMode:
    name: str = "goal"
    label: str = "goal"
    # No system block — the per-phase prompts are injected by run_turn.
    system_block: str = ""

    def run_turn(self, prompt: str, ctx: ModeContext) -> None:
        # Lazy import to avoid pulling these into core.modes module load.
        from veles.core.agent import RunResult
        from veles.core.goal import (
            budget_exhausted,
            cancel,
            complete,
            create_goal,
            read_goal,
            update_fsm,
        )
        from veles.core.plan_artifact import mark_done as mark_plan_done
        from veles.core.plan_artifact import read_plan
        from veles.core.tools.builtin.advisor import call_advisor

        state_dir = ctx.project.state_dir
        goal_id = ctx.state.active_goal_id
        goal = read_goal(state_dir, goal_id) if goal_id else None
        if goal is None:
            # First entry into GoalMode — bootstrap a fresh Goal in
            # `interview` phase. Objective is a placeholder until the
            # model emits `<ready>...</ready>`; the artifact's purpose
            # here is to anchor the FSM across turns.
            goal = create_goal(
                state_dir,
                objective="(in interview; awaiting clarification)",
                done_condition="",
            )
            ctx.state.active_goal_id = goal.id
            ctx.post(SystemLine(text=f"[goal mode active — goal {goal.id} in interview]"))

        # Budget guard — fires between phases. If the user has burned
        # through max_steps via repeated re-plans, bail rather than loop.
        if goal.current_phase in ("plan", "execute", "check"):
            exhausted = budget_exhausted(goal)
            if exhausted:
                cancel(state_dir, goal.id, reason=f"budget: {exhausted}")
                ctx.state.active_goal_id = None
                ctx.state.mode = "auto"  # type: ignore[assignment]
                ctx.post(SystemLine(text=f"[goal {goal.id} cancelled — {exhausted}; mode → auto]"))
                ctx.post(
                    TurnDone(
                        result=RunResult(
                            text="",
                            iterations=0,
                            stopped_reason="synthetic",
                        )
                    )
                )
                ctx.state.last_mode_in_session = self.name  # type: ignore[assignment]
                return

        phase = goal.current_phase
        if phase == "interview":
            self._run_interview(prompt, ctx, goal)
        elif phase == "confirm":
            self._run_confirm(prompt, ctx, goal)
        elif phase == "plan":
            self._run_plan(prompt, ctx, goal)
        elif phase == "execute":
            self._run_execute(prompt, ctx, goal)
        elif phase == "check":
            self._run_check(prompt, ctx, goal, call_advisor=call_advisor)
        elif phase == "done":
            # Stale phase persisted while mode flipped back. Re-arm to
            # interview so the next turn starts a fresh goal.
            ctx.state.active_goal_id = None
            ctx.post(
                SystemLine(text="[goal already done; cycle Shift+Tab → goal to start a new one]")
            )
            ctx.post(TurnDone(result=RunResult(text="", iterations=0, stopped_reason="synthetic")))
        else:  # pragma: no cover - defensive
            ctx.post(SystemLine(text=f"[goal: unknown phase {phase!r}; abandoning]"))
            cancel(state_dir, goal.id, reason=f"unknown phase {phase!r}")
            ctx.state.active_goal_id = None
            ctx.post(TurnDone(result=RunResult(text="", iterations=0, stopped_reason="synthetic")))

        ctx.state.last_mode_in_session = self.name  # type: ignore[assignment]

        # Silence pyright unused-import warnings for symbols we conditionally use
        # in the per-phase handlers below; importing here at the dispatch site
        # keeps each handler from re-importing the same names.
        del mark_plan_done, read_plan, complete, update_fsm

    # ---- per-phase handlers ----

    def _run_interview(self, prompt: str, ctx: ModeContext, goal) -> None:
        from veles.core.goal import update_fsm

        # The model gets the INTERVIEW system prompt as an extra_system;
        # the factory bakes it into the constructor prompt for fresh
        # sessions, otherwise we inject via the mode-switch wrapper.
        agent = ctx.factory(
            ctx.state,
            mode_override="writing",
            extra_system=_INTERVIEW_SYSTEM,
        )
        result = agent.run(prompt, on_text_delta=ctx.on_text, event_listener=ctx.on_event)
        if ctx.state.session_id is None and result.session_id is not None:
            ctx.state.session_id = result.session_id

        summary = parse_ready_marker(result.text or "")
        if summary:
            update_fsm(
                ctx.project.state_dir,
                goal.id,
                phase="confirm",
                interview_summary=summary,
            )
            ctx.post(SystemLine(text="[goal: interview complete → confirm next]"))
        ctx.post(TurnDone(result))

    def _run_confirm(self, prompt: str, ctx: ModeContext, goal) -> None:
        """If `prompt` is non-empty, it's the user's reply to the
        previous CONFIRM line. Otherwise (first turn in CONFIRM), we
        emit the confirmation line and stop, waiting for the user to
        respond next turn.

        No SessionStore write happens for the synthetic confirmation
        line — the user's reply will land in the next turn's history
        normally.
        """
        from veles.core.agent import RunResult
        from veles.core.goal import cancel, update_fsm

        if not prompt.strip():
            # No user reply yet; emit the confirmation line.
            self._emit_confirmation(ctx, goal)
            return

        verdict = _classify_confirm_reply(prompt)
        if verdict == "yes":
            update_fsm(ctx.project.state_dir, goal.id, phase="plan")
            ctx.post(SystemLine(text="[goal: confirmed → plan]"))
            ctx.post(
                TurnDone(
                    result=RunResult(
                        text="",
                        iterations=0,
                        stopped_reason="synthetic",
                    )
                )
            )
            return
        if verdict == "cancel":
            cancel(ctx.project.state_dir, goal.id, reason="user cancelled at confirm")
            ctx.state.active_goal_id = None
            ctx.state.mode = "auto"  # type: ignore[assignment]
            ctx.post(SystemLine(text="[goal cancelled at confirm; mode → auto]"))
            ctx.post(TurnDone(result=RunResult(text="", iterations=0, stopped_reason="synthetic")))
            return
        # `no` — treat as edits. Append the prompt to the summary as
        # context, return to interview for another round of questions.
        new_summary = (goal.interview_summary + "\nEdits: " + prompt).strip()
        update_fsm(
            ctx.project.state_dir,
            goal.id,
            phase="interview",
            interview_summary=new_summary,
        )
        ctx.post(SystemLine(text="[goal: edits noted → interview]"))
        # Run one interview turn immediately on the edits so the model
        # can ask the next question.
        self._run_interview(prompt, ctx, goal)

    def _emit_confirmation(self, ctx: ModeContext, goal) -> None:
        """Print the localized confirmation line directly to the chat.
        No `agent.run` and no provider call — the summary text is
        already on the Goal artifact; we just want it surfaced to the
        user and stop. SessionStore stays clean of this synthetic
        assistant message; the user's next reply will land in history
        normally."""
        from veles.core.agent import RunResult
        from veles.core.i18n import t
        from veles.tui.messages import ChatDelta

        text = (
            t("goal.confirm_line", summary=goal.interview_summary)
            + "\n\n"
            + t("goal.confirm_actions")
        )
        ctx.post(ChatDelta(text=text))
        ctx.post(
            TurnDone(
                result=RunResult(
                    text=text,
                    iterations=0,
                    stopped_reason="synthetic",
                )
            )
        )

    def _run_plan(self, prompt: str, ctx: ModeContext, goal) -> None:
        from veles.core.goal import cancel, update_fsm

        sys_block = _PLAN_SYSTEM.format(summary=goal.interview_summary or "(no summary)")
        agent = ctx.factory(ctx.state, mode_override="planning", extra_system=sys_block)
        result = agent.run(
            prompt or "Continue with the plan.",
            on_text_delta=ctx.on_text,
            event_listener=ctx.on_event,
        )
        if ctx.state.session_id is None and result.session_id is not None:
            ctx.state.session_id = result.session_id

        infeasible = parse_infeasible_marker(result.text or "")
        if infeasible:
            cancel(ctx.project.state_dir, goal.id, reason=f"infeasible: {infeasible}")
            ctx.state.active_goal_id = None
            ctx.state.mode = "auto"  # type: ignore[assignment]
            ctx.post(SystemLine(text=f"[goal infeasible: {infeasible}; mode → auto]"))
        else:
            # The model called `create_plan`; the latest plan_id is in
            # the `active/` directory. Pick the most recent one — the
            # tool result already carried the id, but tracking it
            # through the agent loop is fragile, so we re-discover.
            from veles.core.plan_artifact import list_active

            plans = list_active(ctx.project.state_dir)
            if plans:
                update_fsm(
                    ctx.project.state_dir,
                    goal.id,
                    phase="execute",
                    plan_id=plans[0].id,
                )
                ctx.post(SystemLine(text=f"[goal: plan {plans[0].id} → execute]"))
            else:
                # Model claimed it would plan but didn't actually call
                # `create_plan`. Stay in `plan` for another turn.
                ctx.post(SystemLine(text="[goal: no plan persisted; staying in plan]"))
        ctx.post(TurnDone(result))

    def _run_execute(self, prompt: str, ctx: ModeContext, goal) -> None:
        from veles.core.goal import append_checkpoint, update_fsm
        from veles.core.plan_artifact import read_plan

        plan = read_plan(ctx.project.state_dir, goal.plan_id or "")
        if plan is None or not plan.steps:
            ctx.post(SystemLine(text="[goal: plan missing or stepless; back to plan]"))
            update_fsm(ctx.project.state_dir, goal.id, phase="plan")
            from veles.core.agent import RunResult

            ctx.post(TurnDone(result=RunResult(text="", iterations=0, stopped_reason="synthetic")))
            return

        step_idx = goal.steps_done  # we'll bump it via append_checkpoint
        if step_idx >= len(plan.steps):
            # All steps consumed but advisor never said goal_reached;
            # punt to CHECK so the advisor can verify, or back to plan.
            update_fsm(ctx.project.state_dir, goal.id, phase="check")
            from veles.core.agent import RunResult

            ctx.post(TurnDone(result=RunResult(text="", iterations=0, stopped_reason="synthetic")))
            return

        step_text = plan.steps[step_idx]
        plan_summary = "\n".join(f"  - {s}" for s in plan.steps)

        # M122c: deep GoalMode ↔ manager-spawn integration. When manager mode
        # is explicitly enabled (env `VELES_MANAGER_MODE`), the EXECUTE step is
        # decomposed into explorer→writer workers via the orchestration manager
        # instead of a single agent turn — the 6-phase FSM subsuming VISION
        # §5.3's hierarchical decomposition. Opt-in (`use_heuristic_default=
        # False`) so the default single-agent executor is byte-for-byte
        # unchanged.
        from veles.core.orchestration.integration import should_use_manager

        if should_use_manager(step_text, use_heuristic_default=False):
            result = self._execute_step_via_manager(step_text, plan_summary, ctx)
        else:
            sys_block = _EXECUTE_SYSTEM_TEMPLATE.format(
                step_idx=step_idx + 1,
                step_text=step_text,
                plan_summary=plan_summary,
            )
            agent = ctx.factory(ctx.state, mode_override="writing", extra_system=sys_block)
            result = agent.run(
                prompt or "Execute the next step.",
                on_text_delta=ctx.on_text,
                event_listener=ctx.on_event,
            )
        if ctx.state.session_id is None and result.session_id is not None:
            ctx.state.session_id = result.session_id

        append_checkpoint(
            ctx.project.state_dir,
            goal.id,
            description=f"step {step_idx + 1}/{len(plan.steps)}: {step_text}",
            evidence_ref=None,
        )
        update_fsm(ctx.project.state_dir, goal.id, phase="check")
        ctx.post(SystemLine(text=f"[goal: step {step_idx + 1} done → check]"))
        ctx.post(TurnDone(result))

    def _execute_step_via_manager(self, step_text: str, plan_summary: str, ctx: ModeContext):
        """M122c: run one EXECUTE step through the orchestration manager
        (explorer→writer). The worker factory adapts `ctx.factory` to the
        `spawn` contract (`(**kwargs) -> Agent`), mapping the role's
        `system_prompt` onto `extra_system`. Returns a synthetic `RunResult`
        carrying the writer's final text."""
        from veles.core.agent import RunResult
        from veles.core.memory import SessionStore
        from veles.core.orchestration import make_session_digest_loader
        from veles.core.orchestration.manager import decompose_and_run

        def worker_factory(**kw):
            return ctx.factory(
                ctx.state,
                mode_override="writing",
                extra_system=kw.get("system_prompt"),
            )

        objective = (
            f"Execute this plan step and report the result.\n\n"
            f"Step: {step_text}\n\nFull plan:\n{plan_summary}"
        )
        # M122c part 3: give the writer the explorer's session transcript (read
        # by id from the project store), not just its pasted final text — the
        # worker-to-worker hand-off. Missing/empty session → loader returns None
        # → the manager falls back to the verbatim text-paste.
        store = SessionStore(ctx.project.memory_db_path)
        try:
            mr = decompose_and_run(
                objective,
                agent_factory=worker_factory,
                session_loader=make_session_digest_loader(store),
            )
        finally:
            store.close()
        if mr.error and not mr.final_text:
            text = f"[manager-spawn failed: {mr.error}]"
        else:
            text = mr.final_text or ""
        ctx.post(SystemLine(text=f"[goal: step ran via manager-spawn ({len(mr.handles)} workers)]"))
        return RunResult(
            text=text,
            iterations=0,
            stopped_reason="completed",
            session_id=ctx.state.session_id,
        )

    def _run_check(
        self,
        prompt: str,
        ctx: ModeContext,
        goal,
        *,
        call_advisor,
    ) -> None:
        from veles.core.agent import RunResult
        from veles.core.goal import append_checkpoint, complete, update_fsm
        from veles.core.plan_artifact import mark_done as mark_plan_done
        from veles.core.plan_artifact import read_plan

        del prompt  # user "continue" was just the cue; CHECK runs synthetically

        plan = read_plan(ctx.project.state_dir, goal.plan_id or "")
        plan_body = plan.objective if plan else "(plan missing)"
        last_step = goal.progress[-1].description if goal.progress else "(no progress yet)"
        check_input = (
            f"Goal objective: {goal.objective}\n"
            f"Done condition: {goal.done_condition}\n"
            f"Plan: {plan_body}\n"
            f"Last executed step: {last_step}\n"
            f"Steps completed: {goal.steps_done}\n"
        )
        raw = call_advisor(check_input, system_prompt=_CHECK_SYSTEM)
        verdict, reason = parse_check_verdict(raw)
        append_checkpoint(
            ctx.project.state_dir,
            goal.id,
            description=f"advisor: {verdict} — {reason}",
            metrics={"advisor_verdict": verdict, "advisor_reason": reason},
            advance_step=False,
        )

        if verdict == "goal_reached":
            if goal.plan_id:
                # Plan may already be marked done; non-fatal.
                with contextlib.suppress(Exception):
                    mark_plan_done(ctx.project.state_dir, goal.plan_id)
            complete(ctx.project.state_dir, goal.id, evidence=reason)
            ctx.state.active_goal_id = None
            ctx.state.mode = "auto"  # type: ignore[assignment]
            ctx.post(SystemLine(text=f"[goal achieved — {reason}; mode → auto]"))
        elif verdict == "step_off_track":
            update_fsm(ctx.project.state_dir, goal.id, phase="plan")
            ctx.post(SystemLine(text=f"[goal: off-track ({reason}); re-planning]"))
        else:  # step_ok_continue
            update_fsm(ctx.project.state_dir, goal.id, phase="execute")
            ctx.post(SystemLine(text=f"[goal: step ok ({reason}); next step]"))

        ctx.post(TurnDone(result=RunResult(text=raw, iterations=0, stopped_reason="synthetic")))


_: Mode = GoalMode()  # static protocol check
