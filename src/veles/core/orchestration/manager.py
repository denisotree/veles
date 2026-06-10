"""M122c: manager orchestrator — production wrapper around `spawn`.

The M122 spawn API ships as a primitive (`spawn(role, prompt, ...)`
returning a `WorkerHandle`). What VISION §5.3 actually requires on
top of the primitive:

1. **Decompose** — given a user prompt, decide how many workers and
   of what role, build a `WorkerPlan`.
2. **Manager-never-writes** — the manager role should not produce
   the final answer itself; it must spawn a writer. The plan's
   structure enforces it: a plan with no writer step is rejected
   by `dispatch_plan`.
3. **No-telephone-game** — when a writer worker fires, it receives
   the explorer's *raw* output (via `WorkerHandle.result`) in its
   prompt, not a manager-paraphrased summary.

This module is the production seam. `decompose_and_run(prompt,
agent_factory)` is the public entry point; the actual decomposition
heuristic ships as a small rule-based classifier (long prompts /
"and" connectives / explicit "research" keywords → multi-worker
plan; short single-step prompts → direct-answer).

The heuristic stays simple on purpose — M122c is the *runtime
wiring*, not the LLM-driven planning. Once M122d wires a planner-
LLM call, this module becomes its host without API churn.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from veles.core.orchestration.workers import (
    AgentFactory,
    WorkerHandle,
    WorkerPlan,
    WorkerSpec,
    WorkerStep,
    spawn,
    spawn_parallel,
)

logger = logging.getLogger(__name__)


# ---------- decomposition heuristic ----------


# Keywords that hint at "this is a multi-step research task" — trigger
# the multi-worker path. Conservative: anything mismatched falls into
# the direct-answer path so we don't over-spawn.
_RESEARCH_KEYWORDS = (
    "research",
    "investigate",
    "compare",
    "analyse",
    "analyze",
    "summarise",
    "summarize",
    "explore",
    "find and",
    "look up",
)

# Length threshold above which we assume the prompt has enough scope
# to warrant decomposition. Below this, single-shot is more efficient.
_DECOMPOSITION_MIN_CHARS = 80


def needs_decomposition(prompt: str) -> bool:
    """Heuristic: does this prompt benefit from manager-spawn?

    Two signals:
    - **Length**: prompts shorter than 80 chars are usually "what is
      X" / "fix this bug" — single-shot is better.
    - **Keyword**: explicit "research / investigate / compare" pulls
      the multi-worker path regardless of length.
    """
    text = prompt.strip().lower()
    if any(kw in text for kw in _RESEARCH_KEYWORDS):
        return True
    return len(text) >= _DECOMPOSITION_MIN_CHARS


def build_default_plan(prompt: str) -> WorkerPlan:
    """Build the canonical 2-worker plan (one explorer, one writer).
    The explorer gathers evidence under the user's prompt; the writer
    synthesises the explorer's output (passed verbatim) into the
    final reply. This is the minimum that satisfies VISION §5.3:
    manager doesn't write, writer sees explorer raw."""
    plan = WorkerPlan(objective=prompt[:120])
    plan.add(
        WorkerStep(
            role="explorer",
            prompt=(
                "Investigate the following request and gather every "
                "piece of evidence the writer will need to compose a "
                "complete answer. Quote sources verbatim; cite file "
                "paths. Do NOT compose the final answer.\n\n"
                f"User request: {prompt}"
            ),
            rationale="Gather evidence before synthesis",
        )
    )
    plan.add(
        WorkerStep(
            role="writer",
            prompt="<filled in after the explorer returns>",
            rationale="Synthesise explorer output into the user-facing reply",
        )
    )
    return plan


# ---------- enforcement ----------


class PlanContractError(ValueError):
    """Raised when a plan violates VISION §5.3 invariants — e.g. no
    writer step, manager-step present, …"""


def assert_plan_valid(plan: WorkerPlan) -> None:
    """Enforce VISION §5.3 contract on `plan`. Currently:

    - **Must have at least one writer step.** Otherwise the final
      answer would have to come from the manager, violating
      "manager-never-writes".
    - **Must NOT have a manager step.** The manager isn't a worker
      it spawns — it *is* the dispatcher.

    Raises `PlanContractError` on violation. Tests assert both
    branches.
    """
    roles = [s.role for s in plan.steps]
    if "writer" not in roles:
        raise PlanContractError(
            "plan has no writer step — manager would have to write the "
            "final answer, violating VISION §5.3 'manager-never-writes'"
        )
    if "manager" in roles:
        raise PlanContractError(
            "plan contains a manager step — manager is the dispatcher, "
            "not a spawnable worker (VISION §5.3)"
        )


# ---------- run a plan ----------


@dataclass(frozen=True, slots=True)
class ManagerRunResult:
    """What `decompose_and_run` returns. `final_text` is the user-
    facing reply (from the writer); `handles` are all worker handles
    in dispatch order; `plan` is the executed WorkerPlan."""

    final_text: str | None
    handles: tuple[WorkerHandle, ...]
    plan: WorkerPlan
    error: str | None = None


def decompose_and_run(
    prompt: str,
    *,
    agent_factory: AgentFactory,
    plan_builder: Callable[[str], WorkerPlan] | None = None,
    factory_kwargs: dict[str, Any] | None = None,
    session_loader: Callable[[str | None], str | None] | None = None,
    writer_instruction: str | None = None,
) -> ManagerRunResult:
    """Run a manager-spawn workflow for `prompt`. Returns the writer's
    output as `final_text` (or None on error). Plan execution order:

    1. Build the plan via `plan_builder` (defaults to the 2-worker
       explorer→writer plan).
    2. Validate it via `assert_plan_valid` — fails fast on contract
       violations (no writer / manager-as-worker).
    3. Run all non-writer steps (concurrently when possible via
       `spawn_parallel`).
    4. Substitute the writer step's prompt with the *raw* outputs of
       the prior steps (the no-telephone-game property), then run
       it via `spawn`.
    5. Return the writer's text as `final_text`.

    `factory_kwargs` flows through to each `spawn` call.
    """
    builder = plan_builder or build_default_plan
    plan = builder(prompt)
    try:
        assert_plan_valid(plan)
    except PlanContractError as exc:
        return ManagerRunResult(
            final_text=None, handles=(), plan=plan, error=str(exc)
        )

    pre_writer = [s for s in plan.steps if s.role != "writer"]
    writer_step = next(s for s in plan.steps if s.role == "writer")

    pre_handles: list[WorkerHandle] = []
    if pre_writer:
        specs = [
            WorkerSpec(
                role=s.role, prompt=s.prompt, factory_kwargs=factory_kwargs
            )
            for s in pre_writer
        ]
        pre_handles = spawn_parallel(specs, agent_factory=agent_factory)
        # Reflect handle status back onto the plan so a downstream
        # render can show what completed and what failed.
        for step, handle in zip(pre_writer, pre_handles, strict=True):
            step.session_id = handle.session_id
            step.status = "failed" if handle.error else "done"
            if handle.result:
                step.result_summary = handle.result[:200]

    # Build the writer's prompt: original request + every pre-worker's
    # raw output verbatim, fenced with role labels. This is the
    # no-telephone-game guarantee.
    writer_step.status = "in_progress"
    composed = [f"# Original request\n\n{prompt}", ""]
    for step, handle in zip(pre_writer, pre_handles, strict=True):
        composed.append(f"## Output from {step.role} (session {handle.session_id or '?'})")
        composed.append("")
        if handle.error:
            composed.append(f"_(this worker failed: {handle.error})_")
        else:
            # M122c worker-to-worker hand-off: when a session_loader is wired,
            # give the writer the worker's full session transcript (tool calls
            # + intermediate findings) read by id — not just its final text.
            digest = session_loader(handle.session_id) if session_loader else None
            if digest:
                composed.append("### Session transcript")
                composed.append(digest)
                composed.append("")
                composed.append("### Final output")
            composed.append(handle.result or "_(no output)_")
        composed.append("")
    composed.append("# Your task")
    composed.append("")
    composed.append(
        writer_instruction
        or (
            "Synthesise the user-facing reply from the inputs above. "
            "Do not paraphrase worker outputs — integrate them. Cite "
            "sources by file path or worker reference when they came from "
            "an explorer. Reply directly without preamble."
        )
    )
    writer_prompt = "\n".join(composed)
    writer_handle = spawn(
        "writer",
        writer_prompt,
        agent_factory=agent_factory,
        factory_kwargs=factory_kwargs,
    )
    writer_step.session_id = writer_handle.session_id
    writer_step.status = "failed" if writer_handle.error else "done"
    if writer_handle.result:
        writer_step.result_summary = writer_handle.result[:200]

    all_handles = tuple(pre_handles) + (writer_handle,)
    return ManagerRunResult(
        final_text=writer_handle.result,
        handles=all_handles,
        plan=plan,
        error=writer_handle.error,
    )


__all__ = [
    "ManagerRunResult",
    "PlanContractError",
    "assert_plan_valid",
    "build_default_plan",
    "decompose_and_run",
    "needs_decomposition",
]
