"""M147: deep research — a thin specialization of the core orchestrator.

Deep research is **plan → parallel explore → synthesize**, built entirely on
`decompose_and_run` (manager/worker, no-telephone-game). It is NOT a new core
subsystem: a planner turns the question into N focused angles, one explorer
worker investigates each in parallel (`web_search` + `fetch_url`), and a writer
synthesises a cited report from their verbatim evidence.

Design decisions:
  - The planner is injectable (`planner: Callable[[str], list[str]]`) so the
    pipeline is testable without an LLM; `make_llm_planner` is the default
    LLM-driven query generation.
  - Evidence reaches the writer through each explorer's *final message* (path
    b): explorers are told to quote passages + URLs verbatim there. No
    SessionStore / `make_session_digest_loader` wiring needed for the MVP.
  - The writer's report instruction is passed through `decompose_and_run`'s
    `writer_instruction` (the per-step writer prompt is composed by the
    manager and would otherwise ignore ours).

Follow-ups (M147b): iterative deepening (synthesize → decide → more queries),
transcript hand-off via `make_session_digest_loader`, saving the report to the
project wiki, an HTML report.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from veles.core.orchestration.manager import ManagerRunResult, decompose_and_run
from veles.core.orchestration.workers import AgentFactory, WorkerPlan, WorkerStep

_DEFAULT_MAX_SUBQUESTIONS = 4

# Read + network + wiki-read only. Research explorers gather evidence; they
# never write files or run shell, so the only sensitive class in this set is
# network (`web_search`/`fetch_url`), which the `veles research` command
# pre-authorises — the user opted into web research by running it.
RESEARCH_EXPLORER_TOOLS = (
    "read_file",
    "search_files",
    "list_files",
    "stat_file",
    "wiki_list_pages",
    "wiki_read_page",
    "wiki_search",
    "fetch_url",
    "web_search",
    "pdf_read",
)

_EXPLORER_TEMPLATE = (
    "You are researching one angle of this question:\n\n  {question}\n\n"
    "Investigate THIS specific sub-question and gather evidence:\n\n  {sub}\n\n"
    "Use `web_search` to find sources and `fetch_url` to read the most "
    "promising ones. Report the actual evidence in your final answer: quote "
    "the relevant passages verbatim and give the source URL for each. Do NOT "
    "write the overall report or draw the final conclusion — that is the "
    "writer's job. If you find nothing useful, say so explicitly."
)

_WRITER_INSTRUCTION = (
    "Write a thorough, well-structured research report answering the original "
    "question, using ONLY the evidence the explorers gathered above. Integrate "
    "their findings — do not paraphrase away or drop the specifics. Cite every "
    "claim with the source URL the explorer provided. Call out disagreements "
    "or gaps between sources. Open with a 2-3 sentence summary, then the "
    "detail. Do not invent facts that are not present in the evidence above."
)

_PLANNER_SYSTEM = (
    "You are a research planner. Given a research question, break it into a "
    "few focused, non-overlapping sub-questions or angles that, investigated "
    "in parallel, would together answer it well. Reply with ONLY a JSON array "
    "of short strings — no prose, no markdown fence. "
    'Example: ["first angle", "second angle", "third angle"].'
)


def build_research_plan(question: str, sub_questions: list[str]) -> WorkerPlan:
    """One explorer step per sub-question + one writer step. The writer step's
    prompt is a placeholder — `decompose_and_run` composes the real writer
    prompt from explorer outputs + the `writer_instruction` we pass it."""
    plan = WorkerPlan(objective=question[:120])
    for sub in sub_questions:
        plan.add(
            WorkerStep(
                role="explorer",
                prompt=_EXPLORER_TEMPLATE.format(question=question, sub=sub),
                rationale=f"Investigate: {sub[:80]}",
            )
        )
    plan.add(
        WorkerStep(
            role="writer",
            prompt="<composed by decompose_and_run from explorer evidence>",
            rationale="Synthesise the cited research report",
        )
    )
    return plan


def run_deep_research(
    question: str,
    *,
    agent_factory: AgentFactory,
    planner: Callable[[str], list[str]],
    max_subquestions: int = _DEFAULT_MAX_SUBQUESTIONS,
    factory_kwargs: dict | None = None,
) -> ManagerRunResult:
    """Plan → parallel explore → synthesize.

    `planner(question)` returns the research angles; an empty result or a
    raising planner falls back to a single explorer on the original question
    (research still runs, just un-decomposed). Returns the manager result whose
    `final_text` is the synthesised report.
    """
    try:
        subs = [s.strip() for s in planner(question) if s and s.strip()]
    except Exception:  # noqa: BLE001 — a broken planner must not abort research
        subs = []
    subs = subs[:max_subquestions] or [question]
    plan = build_research_plan(question, subs)
    return decompose_and_run(
        question,
        agent_factory=agent_factory,
        plan_builder=lambda _: plan,
        factory_kwargs=factory_kwargs,
        writer_instruction=_WRITER_INSTRUCTION,
    )


def make_llm_planner(
    provider, model: str, *, max_subquestions: int = _DEFAULT_MAX_SUBQUESTIONS
) -> Callable[[str], list[str]]:
    """Default planner: a tool-less sub-agent that returns research angles as a
    JSON array. Parses defensively; returns [] on total failure so
    `run_deep_research` falls back to a single explorer."""

    def _plan(question: str) -> list[str]:
        from veles.core.agent import Agent
        from veles.core.tools.registry import Registry

        agent = Agent(
            provider=provider,
            registry=Registry(),  # tool-less planner
            model=model,
            max_iterations=1,
            system_prompt=_PLANNER_SYSTEM,
        )
        result = agent.run(f"Research question: {question}")
        return parse_subquestions(result.text, max_subquestions)

    return _plan


def parse_subquestions(text: str | None, cap: int) -> list[str]:
    """Pull research angles out of a planner response: a JSON array if present,
    else non-empty lines with list bullets/numbers stripped. Capped at `cap`."""
    if not text:
        return []
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            arr = json.loads(match.group(0))
        except (ValueError, TypeError):
            arr = None
        if isinstance(arr, list):
            subs = [str(x).strip() for x in arr if str(x).strip()]
            if subs:
                return subs[:cap]
    out: list[str] = []
    for raw in text.splitlines():
        s = raw.strip().lstrip("-*0123456789.) ").strip()
        if s and s[0] not in "[]{}":
            out.append(s)
    return out[:cap]


__all__ = [
    "RESEARCH_EXPLORER_TOOLS",
    "build_research_plan",
    "make_llm_planner",
    "parse_subquestions",
    "run_deep_research",
]
