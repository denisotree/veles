"""Bridge between the synchronous `Agent.run` loop and the Textual UI.

`Agent.run` is blocking and runs synchronously: it owns the conversation
loop, the provider call, tool dispatch, and the per-run streaming
callback. Running it inline on the Textual main thread would freeze the
UI for the duration of every turn. Running it on the asyncio loop also
isn't safe — the provider SDKs (anthropic, openai, gemini) issue
blocking HTTP calls.

Solution: a dedicated worker thread per turn, driven by
`App.run_worker(..., thread=True)`. The agent's two side channels
(`on_text_delta` for streamed text, `event_listener` for typed events)
are thread-funnelled to the UI through `app.call_from_thread(
post_message, …)`, which is the supported way to enqueue work onto the
event loop from foreign threads.

`AgentBridge` is constructed by `TuiApp` and outlives every turn —
state.queue, the factory, the app reference are all immutable for the
session.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from textual.app import App

from veles.core.agent import Agent
from veles.core.agent_events import AgentError, AgentEvent, ChatDelta, SystemLine, TurnDone
from veles.core.events import Event
from veles.core.modules import ModuleRegistry
from veles.core.project import Project
from veles.core.session_state import AppState
from veles.tui import wire

# `core.agent_events` dataclasses carry no Textual base (core must not import
# textual — see that module's docstring); `App.post_message` requires a real
# `textual.message.Message` though. This maps each plain dataclass to its
# `tui.wire` counterpart (identical field names) so `post()` can convert
# right before handing the message to Textual.
_WIRE_TYPES: dict[type, type] = {
    ChatDelta: wire.ChatDelta,
    AgentEvent: wire.AgentEvent,
    TurnDone: wire.TurnDone,
    AgentError: wire.AgentError,
    SystemLine: wire.SystemLine,
}

AgentFactory = Callable[..., Agent]
"""Builds (or rebuilds) the Agent for the next turn from the current
state. Signature: `factory(state, *, mode_override: str | None = None, ...)`.
We rebuild per turn rather than cache so that `state.model` or
`state.session_id` switches via slash commands take effect immediately
without an explicit reset path. The optional `mode_override` lets a
Mode override which mode the factory should configure the Agent for
without flipping `state.mode` (used by GoalMode's PLAN-vs-EXECUTE
phases, which run on the same `state.mode == "goal"`)."""


class AgentBridge:
    def __init__(
        self,
        app: App,
        state: AppState,
        factory: AgentFactory,
        project: Project | None = None,
        module_registry: ModuleRegistry | None = None,
    ) -> None:
        self._app = app
        self._state = state
        self._factory = factory
        self._project = project
        # The active project + module registry live in main-thread
        # ContextVars (set by the CLI entry point). Textual runs each turn
        # on a ThreadPoolExecutor worker (`run_worker(thread=True)`), which
        # does NOT propagate ContextVars — so the agent loop and its tools
        # would see `current_project() == None` (wiki_* / memory_save then
        # hard-raise "no active Veles project"). We capture both here, on
        # the main thread where they're live, and re-install them inside
        # `_run_turn` (the worker thread). The daemon avoids this because
        # `asyncio.to_thread` copies the context for it.
        self._module_registry = module_registry
        # Set while a turn is in flight so the UI thread can stop it
        # cooperatively (Ctrl+C). Created per turn in `_run_turn`, cleared
        # in its `finally`. `CancelToken.cancel()` is thread-safe, so the
        # UI thread may call `cancel_turn()` against an agent running on the
        # worker thread without locking.
        self._cancel_token: Any = None

    # ---- public surface ----

    def cancel_turn(self) -> bool:
        """Request cooperative cancellation of the in-flight turn.

        Returns True iff a turn was running (a token was set). The agent
        loop checks the token between iterations and between streamed
        events and unwinds with a clean cancelled result, so the worker
        thread returns promptly instead of blocking process shutdown."""
        token = self._cancel_token
        if token is None:
            return False
        token.cancel()
        return True

    def submit(self, prompt: str) -> None:
        """Dispatch one prompt. If a turn is already in flight, queue it
        for FIFO drain on `TurnDone` (Phase 6 wires the editing UI; Phase
        1 just accumulates)."""
        if self._state.busy:
            self._state.queue.append(prompt)
            return
        self._state.busy = True
        self._app.run_worker(
            lambda: self._run_turn(prompt),
            thread=True,
            exclusive=True,
            group="agent",
        )

    def drain_one(self) -> bool:
        """If a queued prompt exists, dispatch it. Returns True iff one
        was popped. Called from `TuiApp.on_turn_done`."""
        if not self._state.queue:
            return False
        next_prompt = self._state.queue.popleft()
        self._state.busy = True
        self._app.run_worker(
            lambda: self._run_turn(next_prompt),
            thread=True,
            exclusive=True,
            group="agent",
        )
        return True

    def pop_last_for_edit(self) -> str | None:
        """Pop the *newest* queued prompt (deque's right end) for the
        composer to re-edit. Returns `None` when the queue is empty so
        the caller (Composer's Up handler) can fall through to history
        navigation."""
        if not self._state.queue:
            return None
        return self._state.queue.pop()

    # ---- worker body ----

    def _run_turn(self, prompt: str) -> None:
        """Runs on a worker thread. Funnels both side channels back to
        the UI thread via `call_from_thread`. Also installs the unified
        PromptRequest-based prompter (`_handle_prompt`) in this thread's
        ContextVar scope so the agent's gating logic surfaces an inline
        prompt instead of reading stdin."""
        # Local imports keep `bridge.py` cheap to import from `app.py`
        # at module-load time (Textual itself is the main cost).
        from veles.core.cancel import (
            CancelToken,
            reset_cancel_token,
            set_cancel_token,
        )
        from veles.core.context import (
            reset_active_project,
            set_active_project,
        )
        from veles.core.modules import (
            reset_module_registry,
            set_module_registry,
        )
        from veles.core.permission.prompt import (
            reset_prompter as reset_unified_prompter,
        )
        from veles.core.permission.prompt import (
            set_prompter as set_unified_prompter,
        )
        from veles.core.trust import begin_trust_turn, end_trust_turn
        from veles.core.user_prompt import (
            reset_question_prompter,
            set_question_prompter,
        )

        def post(msg: object) -> None:
            wire_cls = _WIRE_TYPES.get(type(msg))
            wired = wire_cls(**vars(msg)) if wire_cls is not None else msg
            self._app.call_from_thread(self._app.post_message, wired)

        def on_text(text: str) -> None:
            post(ChatDelta(text))

        def on_event(event: Event) -> None:
            post(AgentEvent(event))

        from veles.core.modes import ModeContext, get_mode

        cancel = CancelToken()
        self._cancel_token = cancel
        cancel_ctx_token = set_cancel_token(cancel)
        # Re-install the main-thread ContextVars Textual's worker thread
        # dropped (see __init__): without this the agent's tools resolve
        # `current_project()` to None and wiki_* / memory_save hard-raise.
        project_ctx_token = set_active_project(self._project)
        module_ctx_token = set_module_registry(self._module_registry)
        unified_token = set_unified_prompter(self._handle_prompt)
        # M148: ask_user must never reach the default stdin prompter under
        # Textual (input() would fight the TUI for the terminal). Install a
        # non-blocking skip prompter so ask_user degrades to "proceed on your
        # best assumption" in the TUI. A real modal is M148b.
        question_token = set_question_prompter(lambda _q, _opts=None: None)
        turn_token = begin_trust_turn()
        try:
            mode = get_mode(self._state.mode)
            ctx = ModeContext(
                state=self._state,
                project=self._project,  # type: ignore[arg-type]
                factory=self._factory,
                post=post,
                on_text=on_text,
                on_event=on_event,
            )
            mode.run_turn(prompt, ctx)
            # Each Mode writes `state.last_mode_in_session = self.name`
            # at the end of its own `run_turn`. The bridge does NOT
            # write it here — AutoMode sub-dispatches to Planning or
            # Writing and must record the *effective* mode, not `"auto"`.
        except BaseException as exc:
            post(AgentError(exc))
        finally:
            self._cancel_token = None
            reset_cancel_token(cancel_ctx_token)
            reset_active_project(project_ctx_token)
            reset_module_registry(module_ctx_token)
            end_trust_turn(turn_token)
            reset_unified_prompter(unified_token)
            reset_question_prompter(question_token)

    # ---- prompter side channels (worker thread) ----

    def _handle_prompt(self, req):
        """M124-perm-unify: single entry point for both trust and approval
        prompts. Shows the inline ComposerPrompt with `format_prompt_body`
        as the body — so users finally see the actual command / file path
        the agent is about to touch, not just the tool name.

        Returns a `PromptAnswer` with one of:
          - trust kind:    allow_once / allow_project / allow_global / deny
          - approval kind: allow_once / deny
        """
        from veles.core.permission.prompt import (
            PromptAnswer,
            PromptRequest,
            format_prompt_body,
        )
        from veles.tui.widgets.composer_prompt import PromptOption

        assert isinstance(req, PromptRequest)
        body = format_prompt_body(req, max_value_chars=1000)
        if req.kind == "trust":
            options = [
                PromptOption(key="allow_once", label="Once (this call only)", hotkey="1"),
                PromptOption(
                    key="allow_project",
                    label="Always for this project",
                    hotkey="2",
                ),
                PromptOption(
                    key="allow_global",
                    label="Always everywhere",
                    hotkey="3",
                ),
                PromptOption(key="deny", label="Refuse", hotkey="4"),
            ]
            question = f"Tool {req.tool_name!r} wants to execute"
            default_key = "deny"
        else:
            options = [
                PromptOption(key="allow_once", label="Approve", hotkey="y"),
                PromptOption(key="deny", label="Deny", hotkey="n"),
            ]
            question = "Approval required"
            default_key = "deny"
        choice = self._app.call_from_thread(
            self._app.composer_prompt,
            question=question,
            body=body,
            options=options,
            default_key=default_key,
        )
        if not isinstance(choice, str) or choice not in {
            "allow_once",
            "allow_session",
            "allow_project",
            "allow_global",
            "deny",
        }:
            return PromptAnswer("deny")
        return PromptAnswer(choice)  # type: ignore[arg-type]
