"""`AgentBridge` installs the unified PromptRequest prompter
(`_handle_prompt`) in the worker thread's ContextVar scope and routes
it to the inline `ComposerPrompt` via
`app.call_from_thread(app.composer_prompt, …)`.

We don't spin up a real Textual App here — `call_from_thread` is the
sole seam we need to mock. The tests assert two things:

  1. `_handle_prompt` forwards the right options + default to
     `composer_prompt` (trust → 4-way ladder, approval → yes/no) and
     propagates the returned decision back as a `PromptAnswer`.
  2. None / unexpected return values degrade to a safe default
     (deny) — a runtime glitch in the prompt must never silently
     elevate a sensitive call.
"""

from __future__ import annotations

from veles.core.permission.prompt import PromptAnswer, PromptRequest
from veles.tui.bridge import AgentBridge
from veles.tui.state import AppState
from veles.tui.widgets.composer_prompt import PromptOption


class _FakeApp:
    """Captures `call_from_thread` arguments and returns a canned
    value. Stands in for the live Textual App without dragging the
    event loop into the test."""

    def __init__(self, *, return_value: object) -> None:
        self._return_value = return_value
        self.recorded_calls: list[tuple[object, tuple, dict]] = []

    def call_from_thread(self, callable_, *args, **kwargs):
        self.recorded_calls.append((callable_, args, kwargs))
        return self._return_value

    def composer_prompt(self, **kwargs):
        raise AssertionError("not invoked in fake path")


def _bridge(return_value: object) -> tuple[_FakeApp, AgentBridge]:
    fake = _FakeApp(return_value=return_value)
    state = AppState(session_id=None, provider_name="stub", model="m")
    bridge = AgentBridge(app=fake, state=state, factory=lambda s: None)  # type: ignore[arg-type]
    return fake, bridge


def _kwargs_of(fake: _FakeApp) -> dict:
    callable_, _args, kwargs = fake.recorded_calls[0]
    assert callable_ == fake.composer_prompt
    return kwargs


def _trust_req(tool: str = "run_shell") -> PromptRequest:
    return PromptRequest(tool_name=tool, arguments={"cmd": "ls"}, kind="trust")


def _approval_req() -> PromptRequest:
    return PromptRequest(
        tool_name="write_external",
        arguments={"path": "/x"},
        reason="wrote outside",
        kind="approval",
    )


def test_trust_prompt_passes_four_option_ladder_and_propagates_choice() -> None:
    fake, bridge = _bridge("allow_project")
    answer = bridge._handle_prompt(_trust_req("run_shell"))
    assert answer == PromptAnswer("allow_project")
    kwargs = _kwargs_of(fake)
    assert "run_shell" in kwargs["question"]
    assert kwargs["default_key"] == "deny"
    options: list[PromptOption] = kwargs["options"]
    keys = [o.key for o in options]
    assert keys == ["allow_once", "allow_project", "allow_global", "deny"]
    hotkeys = [o.hotkey for o in options]
    assert hotkeys == ["1", "2", "3", "4"]


def test_trust_prompt_body_shows_arguments() -> None:
    fake, bridge = _bridge("deny")
    bridge._handle_prompt(_trust_req("run_shell"))
    kwargs = _kwargs_of(fake)
    assert "cmd" in kwargs["body"]
    assert "ls" in kwargs["body"]


def test_trust_prompt_defaults_to_deny_on_none() -> None:
    fake, bridge = _bridge(None)
    assert bridge._handle_prompt(_trust_req()) == PromptAnswer("deny")
    del fake


def test_trust_prompt_defaults_to_deny_on_wrong_value() -> None:
    """A misbehaving prompt that dismisses with anything other than a
    valid decision key must not be allowed to upgrade a sensitive call."""
    fake, bridge = _bridge("yes please")
    assert bridge._handle_prompt(_trust_req()) == PromptAnswer("deny")
    del fake


def test_approval_prompt_passes_yes_no_options_and_propagates_decision() -> None:
    fake, bridge = _bridge("allow_once")
    answer = bridge._handle_prompt(_approval_req())
    assert answer == PromptAnswer("allow_once")
    assert answer.approved is True
    kwargs = _kwargs_of(fake)
    assert kwargs["question"] == "Approval required"
    assert "write_external" in kwargs["body"]
    assert "wrote outside" in kwargs["body"]
    assert kwargs["default_key"] == "deny"
    options: list[PromptOption] = kwargs["options"]
    assert [o.key for o in options] == ["allow_once", "deny"]
    assert [o.hotkey for o in options] == ["y", "n"]


def test_approval_prompt_defaults_to_deny_on_none() -> None:
    fake, bridge = _bridge(None)
    answer = bridge._handle_prompt(_approval_req())
    assert answer == PromptAnswer("deny")
    assert answer.approved is False
    del fake
