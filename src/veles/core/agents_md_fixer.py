"""Interactive LLM-driven wizard to add missing AGENTS.md sections.

When `veles schema validate` reports missing recommended sections
(Layout, Conventions, Workflows), this module provides an interactive
fix path: for each missing section it generates context-aware questions
via a cheap LLM sub-agent, asks the user (via a supplied callback), and
then generates section content from the answers.

UI is completely decoupled — the caller supplies an `ask_question`
callback, so CLI and TUI can use their own prompting mechanisms while
sharing this orchestration logic.

On any LLM failure the wizard falls back to the default template section
so the user still ends up with a valid AGENTS.md even without API access.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Question:
    text: str
    choices: list[str]  # empty = free-text input


_QUESTION_SYSTEM = """\
You are a project-setup assistant. The user is creating a new Veles project
and needs to fill in a section of their AGENTS.md context file.

Generate 2–4 questions to ask the user in order to write the "{section}"
section of AGENTS.md for the project named "{project_name}".

Respond ONLY with valid JSON (no markdown fences, no prose):
{{"questions": [{{"text": "...", "choices": ["option1", "option2", "option3"]}}]}}

"choices" must contain 2–4 representative options. Leave "choices" as an
empty list only if the question is inherently open-ended and no reasonable
defaults exist. Questions should be concise and specific.
"""

_CONTENT_SYSTEM = """\
You are a technical writer creating a section of an AGENTS.md context file.
AGENTS.md is the primary context file for a Veles AI agent project.

Write the "{section}" section for the project named "{project_name}".
Base the content on these user answers:
{answers_block}

Requirements:
- Start the output with exactly: ## {section}
- Write 3–8 concise bullet points or short paragraphs
- Be specific and actionable, not generic
- Use markdown formatting appropriate for AGENTS.md
- Do NOT wrap output in code fences
"""


def _run_sub_agent(
    system_prompt: str, user_prompt: str, *, provider: str, model: str, max_tokens: int
) -> str:
    """Spawn a tool-less, max-iter-1 Agent and return its text response.

    Module-level so tests can monkeypatch it without patching the Agent class.
    Returns empty string on any failure (callers handle the fallback).
    """
    from veles.core.agent import Agent
    from veles.core.tools.registry import Registry

    sub = Agent(
        provider=_make_provider(provider),
        registry=Registry(),
        model=model,
        max_iterations=1,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )
    try:
        result = sub.run(user_prompt)
    except Exception:
        return ""
    return result.text or ""


def generate_section_questions(
    section: str,
    project_name: str,
    *,
    provider: str,
    model: str,
) -> list[Question]:
    """Return 2–4 Questions for `section`. Falls back to [] on any error."""
    prompt = _QUESTION_SYSTEM.format(section=section, project_name=project_name)
    raw = _run_sub_agent(
        prompt,
        f"Generate questions for the {section} section.",
        provider=provider,
        model=model,
        max_tokens=512,
    )
    return _parse_questions(raw)


def generate_section_content(
    section: str,
    project_name: str,
    answers: dict[str, str],
    *,
    provider: str,
    model: str,
) -> str:
    """Return markdown starting with `## section`. Falls back to default on error."""
    answers_block = "\n".join(f"- {q}: {a}" for q, a in answers.items())
    prompt = _CONTENT_SYSTEM.format(
        section=section,
        project_name=project_name,
        answers_block=answers_block or "(no answers provided)",
    )
    text = _run_sub_agent(
        prompt,
        f"Write the {section} section.",
        provider=provider,
        model=model,
        max_tokens=1024,
    ).strip()
    if not text:
        return _default_section_content(section)
    if not re.match(rf"^##\s+{re.escape(section)}", text, re.IGNORECASE):
        text = f"## {section}\n\n{text}"
    return text


def fix_agents_md(
    path: Path,
    project_name: str,
    *,
    provider: str,
    model: str,
    ask_question: Callable[[Question], str],
    on_section_start: Callable[[str], None] = lambda _: None,
    on_section_done: Callable[[str], None] = lambda _: None,
) -> list[str]:
    """Add missing recommended sections to AGENTS.md interactively.

    Returns the list of section names that were added.
    """
    from veles.core.agents_md_schema import validate

    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    result = validate(text)
    if result.ok:
        return []

    added: list[str] = []
    for section in result.missing:
        on_section_start(section)
        questions = generate_section_questions(
            section, project_name, provider=provider, model=model
        )
        answers: dict[str, str] = {}
        for q in questions:
            try:
                answer = ask_question(q)
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer:
                answers[q.text] = answer

        content = generate_section_content(
            section, project_name, answers, provider=provider, model=model
        )
        _append_section(path, content)
        added.append(section)
        on_section_done(section)

    return added


def _append_section(path: Path, content: str) -> None:
    existing = path.read_text(encoding="utf-8")
    path.write_text(existing.rstrip("\n") + "\n\n" + content.strip() + "\n", encoding="utf-8")


def _default_section_content(section: str) -> str:
    # Layout-neutral placeholders. These are the fallback used only when the
    # LLM sub-agent produces nothing; the real content is layout-specific and
    # belongs to the active layout pack's AGENTS.md template
    # ([layout.scaffold].agents_md_template), so core must not bake in a
    # particular layout (e.g. the wiki's sources/ + wiki/ + INDEX) here.
    defaults: dict[str, str] = {
        "Layout": (
            "## Layout\n\n"
            "- Describe the project's top-level directories and what each holds.\n"
            "- `.veles/` is Veles' own state (memory, sessions) — leave it alone.\n"
        ),
        "Conventions": (
            "## Conventions\n\n"
            "- TODO: naming, formatting, and file-organisation rules for this project.\n"
        ),
        "Workflows": (
            "## Workflows\n\n"
            '- `veles run "<prompt>"` / `veles tui` — drive the agent.\n'
            "- `veles curate` — distil sessions into project memory.\n"
        ),
    }
    return defaults.get(section, f"## {section}\n\n- TODO: describe {section}.\n")


def _parse_questions(raw: str) -> list[Question]:
    """Parse sub-agent JSON output into Questions. Returns [] on any failure."""
    text = raw.strip()
    # Strip optional markdown fences
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = text.strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list):
        return []
    result: list[Question] = []
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        q_text = item.get("text", "")
        q_choices = item.get("choices", [])
        if not isinstance(q_text, str) or not q_text.strip():
            continue
        if not isinstance(q_choices, list):
            q_choices = []
        choices = [str(c) for c in q_choices if isinstance(c, str) and c.strip()]
        result.append(Question(text=q_text.strip(), choices=choices))
    return result


def _make_provider(provider_name: str):
    from veles.core.provider_factory import make_provider

    return make_provider(provider_name)
