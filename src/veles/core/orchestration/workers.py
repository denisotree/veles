"""M122 MVP + M122b: spawn helpers (sync and parallel), worker roles,
plan-with-checkboxes, mini-report persistence.

`spawn(role, prompt, agent_factory)` builds an isolated sub-Agent
that runs the worker prompt with a role-specific system prompt and
returns the text result. The factory is injected so this module
stays decoupled from `cli/_runtime.py::make_agent` (so tests can
hand in a stub factory).

M122b adds `spawn_parallel(specs, agent_factory)` — given a list of
`(role, prompt[, kwargs])` tuples, dispatches each worker on its own
thread (via `concurrent.futures.ThreadPoolExecutor`) and returns the
handles in input order. Threads (not asyncio) because the underlying
`Agent.run` is synchronous and blocks on provider HTTP — the simplest
way to overlap that is a worker pool, not an event loop.
"""

from __future__ import annotations

import enum
import json
import logging
import sqlite3
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from veles.core.agent import Agent

logger = logging.getLogger(__name__)


class WorkerRole(str, enum.Enum):
    """The four shipped roles. New roles can be plugged in by passing
    a role string not in the enum — `spawn` accepts either; the enum
    just gives discoverability."""

    EXPLORER = "explorer"
    WRITER = "writer"
    ADVISOR = "advisor"
    MANAGER = "manager"


# Default system prompts per role. Tuned for the four canonical
# decomposition workers from VISION §5.3. Callers can pass an explicit
# `system_prompt` to `spawn` to override.
ROLE_PROMPTS: dict[str, str] = {
    WorkerRole.EXPLORER.value: (
        "You are an explorer worker. Your job is to investigate the user's "
        "files, the project memory, or external sources to gather evidence "
        "relevant to the manager's prompt. Be exhaustive on the requested "
        "scope; do not synthesise final answers — that's the writer's job. "
        "Cite file paths and quote relevant text verbatim when you can."
    ),
    WorkerRole.WRITER.value: (
        "You are a writer worker. Your job is to synthesise the manager's "
        "input (which may include verbatim explorer outputs) into a clear, "
        "final answer for the user. Do not paraphrase the inputs; integrate "
        "them. Cite sources by file path or worker reference."
    ),
    WorkerRole.ADVISOR.value: (
        "You are an advisor worker. Your job is to review the manager's "
        "plan or a writer's draft for correctness, missing steps, or "
        "risks. Reply with concrete issues (one per line) or 'ACK: no "
        "issues' when the input passes review. Do not rewrite — that's "
        "the writer's job."
    ),
    WorkerRole.MANAGER.value: (
        "You are the manager. Decompose the user's task into worker steps "
        "and emit a plan as a checkbox list (see `WorkerPlan`). Do not "
        "produce the final answer yourself — spawn a writer worker. End "
        "every task with a mini-report capturing what was done, why this "
        "decomposition, and what was hard."
    ),
}


@dataclass(frozen=True, slots=True)
class WorkerHandle:
    """Result envelope from a `spawn` call.

    - `role`: which role ran (string for forward-compat with custom roles)
    - `result`: the worker's final text output, or None on error
    - `session_id`: the sub-agent's session id (so writers can reference
      explorers' raw output via the session log, not a manager paraphrase
      — the no-telephone-game rule from VISION §5.3)
    - `error`: error message if the worker failed
    - `tokens_in` / `tokens_out`: usage from the last turn (when available)
    """

    role: str
    prompt: str
    result: str | None = None
    session_id: str | None = None
    error: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0


# `AgentFactory` here matches the shape used by `cli/_runtime.py`,
# which takes a state-like object and returns an Agent. For the
# orchestration MVP we accept anything callable that returns an Agent
# instance and let tests inject stubs.
AgentFactory = Callable[..., "Agent"]


def spawn(
    role: str,
    prompt: str,
    *,
    agent_factory: AgentFactory,
    system_prompt: str | None = None,
    factory_kwargs: dict[str, Any] | None = None,
) -> WorkerHandle:
    """Build a sub-Agent, run one turn on `prompt`, return the result.

    `agent_factory(system_prompt=<resolved>, **factory_kwargs)` is the
    contract — exact signature is up to the caller. For role-aware
    behaviour we resolve the system prompt from `ROLE_PROMPTS[role]`
    when one wasn't passed explicitly.

    Errors during agent construction or `run()` are caught and surfaced
    on the handle as `error=...`. We never raise out of here — the
    manager loop wants a `WorkerHandle` either way so it can decide
    whether to retry / skip / abort.
    """
    # M122c: the manager dispatches workers — it is not itself a spawnable
    # worker. Refuse before constructing/running so "manager-never-writes" holds
    # even if a caller bypasses the plan-level `assert_plan_valid` guard.
    if role == WorkerRole.MANAGER.value:
        return WorkerHandle(
            role=role,
            prompt=prompt,
            error=(
                "manager-never-writes: the manager dispatches workers, it is "
                "not a spawnable worker (VISION §5.3)"
            ),
        )
    sys_prompt = system_prompt or ROLE_PROMPTS.get(role)
    factory_kwargs = dict(factory_kwargs or {})
    if sys_prompt is not None and "system_prompt" not in factory_kwargs:
        factory_kwargs["system_prompt"] = sys_prompt

    try:
        agent = agent_factory(**factory_kwargs)
    except Exception as exc:  # noqa: BLE001 — orchestration layer is the boundary
        logger.warning("spawn(%s): factory raised %s", role, exc)
        return WorkerHandle(role=role, prompt=prompt, error=f"factory: {exc}")

    try:
        result = agent.run(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning("spawn(%s): run() raised %s", role, exc)
        return WorkerHandle(role=role, prompt=prompt, error=f"run: {exc}")

    # Extract whatever the agent returned. `Agent.run` returns a
    # `RunResult` (dataclass with `text`/`session_id`/`usage`); we
    # duck-type so this module doesn't import Agent at runtime.
    text = getattr(result, "text", None)
    session_id = getattr(result, "session_id", None)
    usage = getattr(result, "usage", None)
    tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0)
    tokens_out = int(getattr(usage, "completion_tokens", 0) or 0)

    return WorkerHandle(
        role=role,
        prompt=prompt,
        result=text,
        session_id=session_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


# ---------- parallel spawn (M122b) ----------


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    """One worker to dispatch in a parallel batch. `role` and `prompt`
    are the only required fields; `system_prompt` overrides the role
    default, and `factory_kwargs` flows through to `agent_factory`
    untouched (so callers can pin `model=` / `max_iterations=` /
    other per-worker knobs)."""

    role: str
    prompt: str
    system_prompt: str | None = None
    factory_kwargs: dict[str, Any] | None = None


def spawn_parallel(
    specs: Sequence[WorkerSpec | tuple],
    *,
    agent_factory: AgentFactory,
    max_concurrent: int | None = None,
) -> list[WorkerHandle]:
    """Dispatch every spec concurrently and return handles in the
    same order as `specs`.

    Each worker runs in its own thread because the underlying
    `Agent.run` is synchronous and blocks on provider I/O — threads
    overlap that I/O cheaply. `max_concurrent` caps the pool size;
    `None` defaults to `len(specs)` so up to N workers run at once.

    `specs` accepts both `WorkerSpec` objects and bare 2/3/4-tuples
    `(role, prompt[, system_prompt[, factory_kwargs]])` so callers
    can keep the dispatch site tight. Errors from any worker are
    captured on their `WorkerHandle.error` field — `spawn_parallel`
    never raises out, mirroring the sync `spawn` contract.
    """
    normalised = [_to_spec(s) for s in specs]
    if not normalised:
        return []
    pool_size = max_concurrent if max_concurrent and max_concurrent > 0 else len(normalised)
    with ThreadPoolExecutor(max_workers=pool_size) as ex:
        # ThreadPoolExecutor threads start with a *fresh* context, so without
        # this the workers would not see ContextVars set on the caller —
        # `current_budget()` (cumulative `--max-tokens-total` cap),
        # `current_project()` (sandbox root for read/fetch tools), and the
        # cancel token. Run each worker inside its own snapshot of the caller's
        # context so they inherit all three. The budget is a shared mutable
        # object, so the cap stays cumulative across workers.
        futures = [
            ex.submit(
                copy_context().run,
                spawn,
                spec.role,
                spec.prompt,
                agent_factory=agent_factory,
                system_prompt=spec.system_prompt,
                factory_kwargs=spec.factory_kwargs,
            )
            for spec in normalised
        ]
        return [f.result() for f in futures]


def _to_spec(item: WorkerSpec | tuple | Iterable) -> WorkerSpec:
    if isinstance(item, WorkerSpec):
        return item
    seq = tuple(item)
    if len(seq) == 2:
        role, prompt = seq
        return WorkerSpec(role=role, prompt=prompt)
    if len(seq) == 3:
        role, prompt, sysp = seq
        return WorkerSpec(role=role, prompt=prompt, system_prompt=sysp)
    if len(seq) == 4:
        role, prompt, sysp, fkw = seq
        return WorkerSpec(role=role, prompt=prompt, system_prompt=sysp, factory_kwargs=fkw)
    raise ValueError(
        f"spawn_parallel: tuple specs must be length 2, 3, or 4; got {len(seq)}"
    )


# ---------- worker-to-worker session hand-off (M122c) ----------


def make_session_digest_loader(
    store: Any, *, max_chars: int = 4000
) -> Callable[[str | None], str | None]:
    """Build a `(session_id) -> str | None` that renders a worker's full
    session transcript (VISION §5.3 worker-to-worker hand-off).

    The no-telephone-game rule says the writer should see an explorer's *raw*
    output. The base manager pastes the explorer's final text; this loader goes
    further — it lets the writer read the explorer's **session log by id** (its
    tool calls + intermediate findings), not just the conclusion. `store` is any
    object exposing `session_exists` + `load_messages` (i.e. `SessionStore`);
    the loader returns None for a missing / empty session so the caller falls
    back to the pasted result. Decoupled by injection so this module never
    imports SessionStore."""

    def loader(session_id: str | None) -> str | None:
        if not session_id:
            return None
        try:
            if not store.session_exists(session_id):
                return None
            messages = store.load_messages(session_id)
        except Exception:  # noqa: BLE001 — hand-off is best-effort enrichment
            return None
        lines: list[str] = []
        for m in messages:
            if getattr(m, "role", None) == "system":
                continue
            content = (getattr(m, "content", None) or "").strip()
            tool_calls = getattr(m, "tool_calls", None) or []
            if tool_calls and not content:
                names = ", ".join(getattr(c, "name", "?") for c in tool_calls)
                content = f"(tool calls: {names})"
            if not content:
                continue
            lines.append(f"[{m.role}] {content}")
        if not lines:
            return None
        digest = "\n".join(lines)
        if len(digest) > max_chars:
            digest = digest[:max_chars] + "\n… (transcript truncated)"
        return digest

    return loader


# ---------- plan with checkboxes (VISION §5.3 step 3) ----------


@dataclass(slots=True)
class WorkerStep:
    """One row of the manager's plan."""

    role: str
    prompt: str
    rationale: str = ""
    status: str = "pending"  # 'pending' | 'in_progress' | 'done' | 'failed'
    session_id: str | None = None
    result_summary: str | None = None

    def to_checkbox_line(self) -> str:
        mark = "[ ]"
        if self.status == "in_progress":
            mark = "[~]"
        elif self.status == "done":
            mark = "[x]"
        elif self.status == "failed":
            mark = "[!]"
        return f"- {mark} {self.role}: {self.prompt[:80]}"


@dataclass(slots=True)
class WorkerPlan:
    """The manager's decomposition. Persisted via `plan_artifact.py`
    in M122b; here we just hold it in memory with a render method
    the manager prints back to the user."""

    objective: str
    steps: list[WorkerStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def add(self, step: WorkerStep) -> None:
        self.steps.append(step)

    def render(self) -> str:
        rows = [f"# Plan: {self.objective}", ""]
        for step in self.steps:
            rows.append(step.to_checkbox_line())
        return "\n".join(rows)

    def to_json(self) -> str:
        return json.dumps(
            {
                "objective": self.objective,
                "created_at": self.created_at,
                "steps": [
                    {
                        "role": s.role,
                        "prompt": s.prompt,
                        "rationale": s.rationale,
                        "status": s.status,
                        "session_id": s.session_id,
                        "result_summary": s.result_summary,
                    }
                    for s in self.steps
                ],
            }
        )


# ---------- mini-report (VISION §5.3 step 5) ----------


def mini_report(
    conn: sqlite3.Connection,
    *,
    objective: str,
    what_was_done: str,
    why_this_decomposition: str,
    challenges: str = "",
    category: str = "manager-report",
    now: float | None = None,
) -> int:
    """Persist the manager's post-run report into `insights`. Returns
    the inserted row id (or 0 if the connection rejected the write).

    The report shape is documented per VISION §5.3 step 5: what was
    done, why this decomposition, and what was hard. We collapse that
    into a markdown body so it shows up as a normal insight to recall
    and `/insights` consumers, retrievable fast by category.
    """
    wall = time.time() if now is None else now
    title = f"manager: {objective[:80]}"
    body_parts = [
        "## What was done",
        what_was_done.strip(),
        "",
        "## Why this decomposition",
        why_this_decomposition.strip(),
    ]
    if challenges.strip():
        body_parts.extend(["", "## Challenges", challenges.strip()])
    body = "\n".join(body_parts)
    cur = conn.execute(
        "INSERT INTO insights(title, body, category, created_at)"
        " VALUES (?, ?, ?, ?)",
        (title, body, category, wall),
    )
    return int(cur.lastrowid or 0)


__all__ = [
    "ROLE_PROMPTS",
    "WorkerHandle",
    "WorkerPlan",
    "WorkerRole",
    "WorkerSpec",
    "WorkerStep",
    "make_session_digest_loader",
    "mini_report",
    "spawn",
    "spawn_parallel",
]
