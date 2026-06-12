"""M147: deep research — plan → parallel explore → synthesize.

A thin specialization of the core orchestrator: a planner turns the question
into N angles, one explorer per angle runs in parallel (web tools), a writer
synthesises a cited report from their verbatim evidence. The planner is
injected so the pipeline is testable without an LLM.

Invariants:
  1. `build_research_plan` makes one explorer step per sub-question + one
     writer step; explorer prompts carry the sub-question + web-tool guidance.
  2. `parse_subquestions` reads a JSON array, falls back to lines, and caps.
  3. `run_deep_research` runs every explorer and returns the writer's report;
     an empty/failing planner falls back to a single explorer.
  4. `make_llm_planner` parses a stub provider's listing into angles.
"""

from __future__ import annotations

from veles.core.orchestration.research import (
    build_research_plan,
    make_llm_planner,
    parse_subquestions,
    run_deep_research,
)
from veles.core.provider import ProviderResponse, TokenUsage

# --- unit: build_research_plan --------------------------------------------


def test_plan_has_one_explorer_per_subquestion_plus_writer() -> None:
    plan = build_research_plan("Q?", ["angle a", "angle b", "angle c"])
    roles = [s.role for s in plan.steps]
    assert roles == ["explorer", "explorer", "explorer", "writer"]
    explorers = [s for s in plan.steps if s.role == "explorer"]
    assert "angle a" in explorers[0].prompt
    assert "web_search" in explorers[0].prompt  # told how to gather
    assert "Q?" in explorers[0].prompt


# --- unit: parse_subquestions ---------------------------------------------


def test_parse_json_array() -> None:
    out = parse_subquestions('Here you go: ["one", "two", "three"]', cap=5)
    assert out == ["one", "two", "three"]


def test_parse_line_fallback_and_cap() -> None:
    out = parse_subquestions("1. first\n2. second\n3. third\n4. fourth", cap=2)
    assert out == ["first", "second"]


def test_parse_empty() -> None:
    assert parse_subquestions("", cap=5) == []
    assert parse_subquestions(None, cap=5) == []


# --- stub agent + factory --------------------------------------------------


class _ScriptedAgent:
    """A fake worker Agent: its reply depends on the role embedded in its
    system prompt, so the test can tell explorers from the writer."""

    def __init__(self, system_prompt: str, calls: list) -> None:
        self._system = system_prompt or ""
        self._calls = calls

    def run(self, prompt: str, **_):
        from veles.core.agent import RunResult

        self._calls.append(prompt)
        # Role markers are distinctive prefixes of ROLE_PROMPTS; check writer
        # first because the writer's role prompt also mentions "explorer".
        if "writer worker" in self._system:
            # The writer's prompt embeds every explorer's verbatim output.
            n = prompt.count("EVIDENCE:")
            text = f"REPORT synthesised from {n} explorer(s)"
        elif "explorer worker" in self._system:
            text = "EVIDENCE: quoted passage [https://src.test/x]"
        else:
            text = "?"
        return RunResult(text=text, iterations=1, stopped_reason="completed")


def _factory_with(calls: list):
    def factory(**kwargs):
        return _ScriptedAgent(kwargs.get("system_prompt", ""), calls)

    return factory


# --- run_deep_research -----------------------------------------------------


def test_run_deep_research_explores_each_angle_and_synthesises() -> None:
    calls: list = []
    result = run_deep_research(
        "How does X work?",
        agent_factory=_factory_with(calls),
        planner=lambda q: ["angle 1", "angle 2", "angle 3"],
    )
    assert result.error is None
    # Writer saw all three explorers' verbatim evidence (no-telephone-game).
    assert result.final_text == "REPORT synthesised from 3 explorer(s)"
    # Three explorer prompts + one writer prompt ran.
    explorer_runs = [c for c in calls if "angle" in c]
    assert len(explorer_runs) == 3
    # The research writer_instruction (M147 → decompose_and_run override)
    # actually reached the writer, not the generic manager synthesis prompt.
    writer_prompt = next(c for c in calls if "EVIDENCE:" in c and "research report" in c)
    assert "Cite every claim with the source URL" in writer_prompt


def test_planner_failure_falls_back_to_single_explorer() -> None:
    calls: list = []

    def boom(_q):
        raise RuntimeError("planner down")

    result = run_deep_research(
        "fallback question",
        agent_factory=_factory_with(calls),
        planner=boom,
    )
    assert result.error is None
    assert result.final_text == "REPORT synthesised from 1 explorer(s)"


def test_empty_planner_falls_back_to_single_explorer() -> None:
    calls: list = []
    result = run_deep_research("q", agent_factory=_factory_with(calls), planner=lambda _q: [])
    assert result.final_text == "REPORT synthesised from 1 explorer(s)"


def test_max_subquestions_caps_explorers() -> None:
    calls: list = []
    run_deep_research(
        "q",
        agent_factory=_factory_with(calls),
        planner=lambda _q: ["a", "b", "c", "d", "e"],
        max_subquestions=2,
    )
    assert len([c for c in calls if c.strip().startswith("You are researching") is False]) >= 0
    # Exactly 2 explorers ran (+1 writer).
    explorer_runs = [c for c in calls if "Investigate THIS specific" in c]
    assert len(explorer_runs) == 2


# --- make_llm_planner ------------------------------------------------------


class _ListProvider:
    name = "stub"
    supports_tools = True
    supports_streaming = False

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        del messages, tools, model, max_tokens
        return ProviderResponse(
            text='["angle one", "angle two", "angle three", "angle four"]',
            tool_calls=[],
            usage=TokenUsage(total_tokens=1),
            finish_reason="stop",
        )


def test_make_llm_planner_parses_and_caps() -> None:
    planner = make_llm_planner(_ListProvider(), "m", max_subquestions=3)
    out = planner("some question")
    assert out == ["angle one", "angle two", "angle three"]


# --- CLI smoke: cmd_research wiring ----------------------------------------


def test_cmd_research_prints_report_and_manages_trust_env(tmp_path, monkeypatch, capsys) -> None:
    import argparse
    import os

    from veles.core.orchestration.manager import ManagerRunResult
    from veles.core.orchestration.workers import WorkerPlan
    from veles.core.project import init_project

    project = init_project(tmp_path / "demo", name="demo")

    seen_env: dict = {}

    def fake_run(question, *, agent_factory, planner, max_subquestions, **_):
        # The command must pre-authorise trust while research runs.
        seen_env["during"] = os.environ.get("VELES_TRUST_AUTO_ALLOW")
        return ManagerRunResult(
            final_text="THE REPORT", handles=(), plan=WorkerPlan(objective=question)
        )

    monkeypatch.setattr("veles.cli.build_run_system_prompt", lambda *a, **k: "base")
    monkeypatch.setattr("veles.core.orchestration.research.run_deep_research", fake_run)
    # ollama isn't in the API-key env set, so _ensure_api_key isn't consulted.
    monkeypatch.setattr("veles.cli._make_provider", lambda name: _ListProvider())
    monkeypatch.delenv("VELES_TRUST_AUTO_ALLOW", raising=False)

    from veles.cli.commands.research import cmd_research

    args = argparse.Namespace(
        question="how does X work?",
        provider="ollama",
        model="m",
        max_iterations=10,
        verbose=False,
        max_subquestions=3,
    )
    rc = cmd_research(args, project)

    assert rc == 0
    assert "THE REPORT" in capsys.readouterr().out
    assert seen_env["during"] == "1"  # trust pre-authorised during the run
    assert "VELES_TRUST_AUTO_ALLOW" not in os.environ  # restored (was unset) after
