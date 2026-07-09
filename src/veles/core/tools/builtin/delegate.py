"""`delegate` — hand a small, well-scoped subtask to a fresh light sub-agent.

The base working pattern (VISION §5.3): a capable root decomposes a task and
delegates each small subtask to a context-isolated worker with a NARROW toolset,
then accepts the result or delegates a correction. The worker shares no history
with the caller — everything it needs goes in `subtask` + `context`.
"""

from __future__ import annotations

from veles.core.orchestration.delegation import (
    MAX_DELEGATE_DEPTH,
    current_delegate_depth,
    current_subagent_factory,
    enter_delegate,
    exit_delegate,
)
from veles.core.risk import RiskClass
from veles.core.tools.registry import registry, tool

# A worker with no explicit toolset is read-only — the root must grant mutation
# tools deliberately. wiki_* resolve only when the wiki engine registered them.
_DEFAULT_READONLY_TOOLS = ("read_file", "list_files", "wiki_read_page", "wiki_search")

_WORKER_FRAME = (
    "You are a focused sub-agent handling ONE small subtask delegated by a "
    "coordinator. Do ONLY this subtask, using the limited tools you were given — "
    "do not expand scope or start unrelated work. You share NO history with the "
    "coordinator, so everything you need is in this prompt. When finished, reply "
    "with a concise report: what you did, what you produced (file paths / ids), "
    "and anything the coordinator needs to continue. Never ask the user a "
    "question; if you are blocked, report the blocker and stop."
)


@tool(risk_class=RiskClass.COMPUTE_ONLY, side_effects=[])
def delegate(subtask: str, tools: list[str] | None = None, context: str = "") -> str:
    """Delegate a small, self-contained subtask to a fresh light sub-agent with a
    NARROW toolset and isolated context, and return its report.

    Prefer this as the default way to tackle non-trivial work: break the task
    into small subtasks and delegate each. The sub-agent has a fresh context and
    shares no history with you — put EVERYTHING it needs into `subtask` and
    `context` (relevant paths, the target structure, constraints). `tools` is the
    exact list of tool names it may use, chosen from the tools available in this
    project (omit it for a read-only worker; grant write/edit/move/wiki tools
    only when the subtask needs them). Any files the worker changes persist; read
    its report and either accept and move on, or delegate a correction.
    """
    factory = current_subagent_factory()
    if factory is None:
        return "<error: delegation is not available in this context>"
    if current_delegate_depth() >= MAX_DELEGATE_DEPTH:
        return (
            f"<refused: max delegation depth {MAX_DELEGATE_DEPTH} reached — do this "
            "subtask directly instead of delegating further>"
        )
    if not subtask.strip():
        return "<error: subtask is empty>"

    requested = list(tools) if tools else list(_DEFAULT_READONLY_TOOLS)
    # S1 (2026-07-07 audit): a worker may never exceed the delegating agent's
    # own scope. Intersect with the running agent's toolset (`current_toolset`)
    # so a scoped run — e.g. `veles add`, whose `[ingest]` toolset omits
    # `run_shell`/`fetch_url` — can't `delegate(tools=["run_shell"])` to smuggle
    # a wider capability into a worker. Outside a scoped agent run (empty set)
    # fall back to the global registry (historic behaviour, e.g. direct tests).
    from veles.core.agent_state import current_toolset

    known = current_toolset() or frozenset(registry.list_names())
    resolved = [t for t in requested if t in known]
    dropped = [t for t in requested if t not in known]
    if not resolved:
        return (
            f"<error: none of the requested tools are available here: {requested}. "
            f"Available include: {sorted(known)[:20]}…>"
        )

    system_prompt = _WORKER_FRAME
    if context.strip():
        system_prompt = f"{_WORKER_FRAME}\n\n<context>\n{context.strip()}\n</context>"

    from veles.core.orchestration.workers import spawn

    tok = enter_delegate()
    try:
        handle = spawn(
            "worker",
            subtask,
            agent_factory=factory,
            system_prompt=system_prompt,
            factory_kwargs={"tools": resolved},
        )
    finally:
        exit_delegate(tok)

    if handle.error:
        return f"<delegate failed: {handle.error}>"
    report = handle.result or "(worker returned no report)"
    if dropped:
        report = f"{report}\n(note: these requested tools were unavailable and dropped: {dropped})"
    return report
