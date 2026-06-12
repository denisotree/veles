"""M148: `ask_user` — the agent asks the human a free-text clarifying question.

Non-sensitive (no action, just asks). Routes through a ContextVar prompter
(M71 pattern) so the TUI/channels install their own surface; the default skips
when no interactive human is available (non-TTY, autopilot) so headless and
unattended runs never block.

Invariants:
  1. The tool returns the user's answer when a prompter supplies one.
  2. No prompter answer (None) → a "proceed on your best assumption" notice,
     never a block.
  3. The tool is registered, non-sensitive, and in the run toolset.
  4. End-to-end: an agent calling ask_user gets the installed prompter's answer
     back as the tool result and continues.
"""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.tools.builtin.ask_user import _NO_HUMAN, ask_user
from veles.core.tools.registry import registry
from veles.core.tools.toolsets import TOOLSETS
from veles.core.user_prompt import (
    reset_question_prompter,
    set_question_prompter,
)

# --- unit: the tool --------------------------------------------------------


def test_returns_prompter_answer() -> None:
    token = set_question_prompter(lambda q: f"answer to: {q}")
    try:
        assert ask_user("which env?") == "answer to: which env?"
    finally:
        reset_question_prompter(token)


def test_no_human_returns_assumption_notice() -> None:
    token = set_question_prompter(lambda _q: None)
    try:
        assert ask_user("anything?") == _NO_HUMAN
    finally:
        reset_question_prompter(token)


def test_blank_answer_treated_as_no_human() -> None:
    token = set_question_prompter(lambda _q: "   ")
    try:
        assert ask_user("?") == _NO_HUMAN
    finally:
        reset_question_prompter(token)


def test_default_prompter_skips_without_tty() -> None:
    # The load-bearing safety gate: under pytest stdin is not a TTY, so the
    # default prompter returns None (no block on input()) and the tool degrades
    # to the assumption notice. A headless/daemon run hits this same path.
    from veles.core.user_prompt import ask_user_question

    assert ask_user_question("anything?") is None
    assert ask_user("anything?") == _NO_HUMAN


def test_registered_non_sensitive_and_in_run_toolset() -> None:
    entry = registry.get("ask_user")
    assert entry is not None
    assert entry.sensitive is False  # never trust-gated
    assert "ask_user" in TOOLSETS["run"]


# --- e2e: agent calls ask_user --------------------------------------------


@dataclass
class _OneAskProvider:
    """Calls ask_user once, then answers using whatever came back."""

    name: str = "stub"
    supports_tools: bool = True
    supports_streaming: bool = False
    n: int = 0

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        del tools, model, max_tokens
        self.n += 1
        if self.n == 1:
            return ProviderResponse(
                text=None,
                tool_calls=[
                    ToolCall(id="c1", name="ask_user", arguments={"question": "prod or dev?"})
                ],
                usage=TokenUsage(total_tokens=1),
                finish_reason="tool_use",
            )
        # Echo the tool result so the test can assert it flowed back.
        last_tool = next((m for m in reversed(messages) if m.role == "tool"), None)
        return ProviderResponse(
            text=f"using {last_tool.content if last_tool else '?'}",
            tool_calls=[],
            usage=TokenUsage(total_tokens=1),
            finish_reason="stop",
        )


def test_agent_receives_user_answer_as_tool_result() -> None:
    from veles.core.agent import Agent

    token = set_question_prompter(lambda _q: "prod")
    try:
        agent = Agent(_OneAskProvider(), registry.subset(["ask_user"]), model="m")
        result = agent.run("deploy it")
    finally:
        reset_question_prompter(token)

    assert result.stopped_reason == "completed"
    assert result.text == "using prod"
