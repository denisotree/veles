"""M122: Hierarchical multi-agent orchestration (VISION §5.3).

A *manager* agent decomposes a task, spawns specialised *worker*
agents (explorer, writer, advisor, custom roles), and synthesises
the final answer through a separate writer worker — never first
person, never summarising worker outputs through itself. The
no-telephone-game rule means a writer worker receives the explorer's
output verbatim, not the manager's paraphrase.

This MVP provides:
- `WorkerRole` enum + `ROLE_PROMPTS` mapping for the four builtin roles.
- `WorkerHandle` dataclass — the result envelope returned by `spawn`.
- `spawn(role, prompt, agent_factory)` — synchronous helper that
  builds an isolated sub-Agent, runs one turn, returns the result.
- `WorkerPlan` — the agent's plan with checkbox-tracked workers
  (VISION §5.3 step 3).
- `mini_report(...)` — persists the manager's post-run mini-report
  (VISION §5.3 step 5) as an insight row.

Deferred to M122b: parallel worker dispatch (asyncio gather over
multiple `spawn`s), strict "manager-never-writes" enforcement in
`Agent.run`, deep integration with the existing GoalMode FSM,
worker-to-worker hand-off via session_id references (the
no-telephone-game payload-passing).
"""

from veles.core.orchestration.integration import (
    MANAGER_ENV,
    env_manager_mode,
    run_with_manager_if_eligible,
    should_use_manager,
)
from veles.core.orchestration.manager import (
    ManagerRunResult,
    PlanContractError,
    assert_plan_valid,
    build_default_plan,
    decompose_and_run,
    needs_decomposition,
)
from veles.core.orchestration.workers import (
    ROLE_PROMPTS,
    WorkerHandle,
    WorkerPlan,
    WorkerRole,
    WorkerSpec,
    WorkerStep,
    make_session_digest_loader,
    mini_report,
    spawn,
    spawn_parallel,
)

__all__ = [
    "MANAGER_ENV",
    "ROLE_PROMPTS",
    "ManagerRunResult",
    "PlanContractError",
    "WorkerHandle",
    "WorkerPlan",
    "WorkerRole",
    "WorkerSpec",
    "WorkerStep",
    "assert_plan_valid",
    "build_default_plan",
    "decompose_and_run",
    "env_manager_mode",
    "make_session_digest_loader",
    "mini_report",
    "needs_decomposition",
    "run_with_manager_if_eligible",
    "should_use_manager",
    "spawn",
    "spawn_parallel",
]
