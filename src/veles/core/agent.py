"""Agent turn-loop — request → response → tool dispatch → repeat until terminal.

M1 adds optional persistence via `SessionStore`: every appended Message is
written through to SQLite, and an existing session can be resumed by passing
`session_id`. With store=None the agent stays stateless (M0 behaviour).

Surface deliberately minimal: no streaming, no callbacks, no interrupts,
no fallback models, no checkpoints, and no behavioural flags on the loop
itself.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from veles.core.agent_state import (
    AgentState,
    clear_invoked_tools,
    clear_untrusted,
    reset_current_toolset,
    reset_invoked_tools,
    reset_state,
    reset_untrusted,
    set_current_toolset,
    set_state,
)
from veles.core.cancel import TurnCancelled, current_cancel_token, run_cancellable
from veles.core.context import (
    current_budget,
    current_project,
    reset_current_session_id,
    set_current_session_id,
)
from veles.core.context_scrubber import scrub_text
from veles.core.events import (
    AssistantMessage as AssistantMessageEvent,
)
from veles.core.events import (
    ErrorEvent,
    Event,
    EventWriter,
    events_path_for_project,
)
from veles.core.events import (
    RoundUsage as RoundUsageEvent,
)
from veles.core.events import (
    UserMessage as UserMessageEvent,
)
from veles.core.fenced_tools import (
    FENCED_RESULT_HEADER,
    FENCED_SENTINEL,
    FencedToolScrubber,
    fenced_tools_enabled_by_env,
    parse_tool_calls_with_errors,
    render_parse_errors,
    render_tools_prompt,
)
from veles.core.history_repair import repair_tool_pairing
from veles.core.memory import SessionStore
from veles.core.modules import fire_hook
from veles.core.provider import (
    Message,
    Provider,
    ProviderResponse,
    ToolCall,
)
from veles.core.stall_guard import STALL_NUDGE, TOKEN_WARN_NUDGE, StallGuard

# M156: streaming response consumer extracted to `stream_consumer.py`.
from veles.core.stream_consumer import consume_stream

# M156: tool dispatch + permission/approval pipeline extracted to
# `tool_dispatch.py`. Re-imported here both for the Agent loop's own use
# (`_dispatch`, `_emit`) and as back-compat re-exports — tests import these
# names from `veles.core.agent` and may patch them on this module; the loop
# resolves them via this module's globals, so such patches keep working.
from veles.core.tool_dispatch import (  # noqa: F401
    _audit_autopilot_dispatch,
    _dispatch,
    _emit,
    _emit_tool_refusal,
    _invoke_tool_safely,
    _persist_approval_if_grant,
    _run_approval_prompt,
)
from veles.core.tools.registry import Registry
from veles.core.trace import (
    TraceRecord,
    TraceWriter,
    hash_text,
    hash_tools,
    now_iso,
    trace_path_for_project,
)

logger = logging.getLogger(__name__)

# M214 (B2): injected when a turn would end with no tool calls AND no text, to
# force the model to actually answer instead of leaving the turn blank.
EMPTY_ANSWER_NUDGE = (
    "Your last response was empty. Reply now with your answer to the user based "
    "on what you already have. Do not call any tools — just write the answer."
)

# Fenced mode: how many times per run a zero-calls parse failure is fed back
# to the model before the garbage round is allowed to end the turn. Bounded so
# a model stuck emitting broken JSON can't loop to max_iterations on nudges.
_PARSE_NUDGE_LIMIT = 3


@dataclass(slots=True)
class UsageSnapshot:
    """M79: per-run token totals summed across iterations. Exposed on
    RunResult so the TUI can render `tok in/out` in the status bar."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    # M177: the *last* request's prompt-token count (overwritten, not summed).
    # Approximates the live context occupancy — what's resident in the window
    # for the next turn — so the status chip can show a sane % instead of
    # cumulative run usage.
    last_prompt_tokens: int = 0

    def add(self, usage) -> None:
        prompt = getattr(usage, "prompt_tokens", 0)
        self.prompt_tokens += prompt
        self.completion_tokens += getattr(usage, "completion_tokens", 0)
        self.total_tokens += getattr(usage, "total_tokens", 0)
        self.cache_read_tokens += getattr(usage, "cache_read_tokens", 0)
        self.cache_creation_tokens += getattr(usage, "cache_creation_tokens", 0)
        # Latest request's prompt size = current resident-context estimate.
        if prompt:
            self.last_prompt_tokens = prompt


@dataclass(slots=True)
class RunResult:
    text: str
    iterations: int
    history: list[Message] = field(default_factory=list)
    stopped_reason: str = "completed"  # completed | max_iterations | empty
    session_id: str | None = None
    usage: UsageSnapshot = field(default_factory=UsageSnapshot)
    # Names of every tool the run dispatched. Lets callers judge success by
    # "did the work actually happen" instead of by non-empty final prose — a
    # thinking local model routinely ends with empty content after doing all
    # the tool work (seen live 2026-07-08, ollama qwen3.5:9b).
    invoked_tools: frozenset[str] = frozenset()


class ManagerNeverWritesError(RuntimeError):
    """A manager-role agent must decompose the task and spawn workers — it must
    never run to produce the final answer itself (VISION §5.3
    'manager-never-writes'). Raised by `Agent.run` when the agent was built with
    `role="manager"`. The plan-level guard (`orchestration.manager.
    assert_plan_valid`) catches this at decomposition time; this is the runtime
    backstop for code paths that construct a manager agent directly."""


class Agent:
    def __init__(
        self,
        provider: Provider,
        registry: Registry,
        *,
        model: str,
        # Runaway backstop, not a task budget — the StallGuard is the real stop.
        max_iterations: int = 1000,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        verbose: bool = False,
        store: SessionStore | None = None,
        session_id: str | None = None,
        compressor: Callable[[list[Message], str | None], list[Message]] | None = None,
        hard_ceiling_tokens: int | None = None,
        trace_writer: TraceWriter | None = None,
        event_writer: EventWriter | None = None,
        plan_mode: bool = False,
        role: str | None = None,
        stall_repeat_limit: int | None = 3,
        token_warn_threshold: int | None = 500_000,
        fenced_tools: bool = True,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._model = model
        # M122c: orchestration role (VISION §5.3). Default None = a normal
        # agent. role="manager" makes `run()` refuse to produce an answer
        # (managers decompose + spawn; they never write).
        self._role = role
        self._max_iterations = max_iterations
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._verbose = verbose
        self._store = store
        self._session_id = session_id
        self._compressor = compressor
        # Last-line truncation ceiling. After compressor returns, Agent
        # checks estimate_tokens(history) and, if still above this
        # threshold, drops oldest non-system turns until under. Set
        # `None` to disable (legacy callers without a configured limit).
        self._hard_ceiling_tokens = hard_ceiling_tokens
        # Public handle for Modes that need a direct provider call
        # (AutoMode classifier, GoalMode advisor / CONFIRM message)
        # without running the full agent loop and polluting SessionStore.
        self.provider = provider
        # M68 / M69: per-call trace + typed event log. Caller-provided writers
        # take precedence; otherwise we auto-attach when an active project is
        # set so plain `veles run` emits both files without extra wiring.
        # None means the corresponding output is fully disabled (current
        # behaviour for unit tests that pass no project context).
        project = current_project()
        if trace_writer is not None:
            self._trace_writer: TraceWriter | None = trace_writer
        else:
            self._trace_writer = (
                TraceWriter(trace_path_for_project(project.state_dir))
                if project is not None
                else None
            )
        if event_writer is not None:
            self._event_writer: EventWriter | None = event_writer
        else:
            self._event_writer = (
                EventWriter(events_path_for_project(project.state_dir))
                if project is not None
                else None
            )
        self._plan_mode = plan_mode
        # M144: stall guard threshold. After the same tool-call signature
        # recurs this many times in a turn, the agent forces one tool-free
        # round so the model answers instead of looping a dead call. None/0
        # disables.
        self._stall_repeat_limit = stall_repeat_limit
        # Soft one-time nudge once a single turn's cumulative tokens cross this,
        # so a looping turn is told to stop before it burns millions. None disables.
        self._token_warn_threshold = token_warn_threshold
        # M143: present tools as fenced `veles-tool` text blocks (and parse
        # calls back out of prose) when the provider lacks native function
        # calling. Default on — it's what makes local models usable with
        # tools. Set False to restore the old "non-tool provider gets no
        # tools" behaviour.
        self._fenced_tools = fenced_tools
        # Per-run side-channel for live UI subscribers (TUI inspector, daemon
        # WebSocket push). Set in `run()`, cleared in `finally`. Distinct from
        # `_event_writer`: writer persists to disk for audit, listener is an
        # in-memory firehose. Both fire from the same `_emit` site.
        self._event_listener: Callable[[Event], None] | None = None

    def run(
        self,
        user_msg: str,
        *,
        on_text_delta: Callable[[str], None] | None = None,
        event_listener: Callable[[Event], None] | None = None,
    ) -> RunResult:
        # M122c: a manager never writes. Refuse to run a manager-role agent for
        # an answer — it must decompose and spawn workers via the orchestration
        # manager (`decompose_and_run`). Runtime backstop for the plan-level
        # `assert_plan_valid` guard.
        if self._role == "manager":
            raise ManagerNeverWritesError(
                "agent role='manager' must not run to produce an answer; "
                "decompose the task and spawn workers (VISION §5.3)"
            )
        state_token = set_state(AgentState.PLANNING if self._plan_mode else AgentState.IDLE)
        invoked_token = clear_invoked_tools()
        untrusted_token = clear_untrusted()  # M198: fresh untrusted corpus per run
        # S1: publish this run's scoped toolset so `delegate` can't grant a
        # worker more than the running agent itself holds.
        toolset_token = set_current_toolset(frozenset(self._registry.list_names()))
        # M224: expose the session id so the OpenRouter adapter can forward it as
        # a sticky-routing key. Seeded here (may be None on a fresh persisted run)
        # and refreshed in `_build_history` once the session is created.
        session_token = set_current_session_id(self._session_id)
        self._event_listener = event_listener
        try:
            return self._run_inner(user_msg, on_text_delta=on_text_delta)
        except TurnCancelled:
            # User-initiated stop (e.g. Ctrl+C in the TUI). Not an error:
            # return a clean cancelled result so the UI clears `busy` and
            # the worker thread unwinds promptly instead of hanging the
            # process at shutdown. Any user/assistant turns streamed so far
            # are already persisted by `_persist`.
            self._log("-> turn cancelled by user")
            return self._finalize(
                RunResult(
                    text="",
                    iterations=0,
                    stopped_reason="cancelled",
                    session_id=self._session_id,
                )
            )
        except Exception as exc:
            # M132: a failed turn (provider timeout, adapter error, tool
            # framework bug) is recorded as a typed ErrorEvent before it
            # propagates. `_emit_event` fans to the persistent events.jsonl
            # (survives restarts) AND the live listener (TUI inspector), so
            # errors stop vanishing into a scrolled-away chat line. The
            # exception still re-raises — callers (bridge, CLI) keep their
            # existing handling.
            self._emit_event(
                ErrorEvent(
                    ts=now_iso(),
                    session_id=self._session_id,
                    where="agent.run",
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            raise
        finally:
            self._event_listener = None
            reset_invoked_tools(invoked_token)
            reset_untrusted(untrusted_token)
            reset_current_toolset(toolset_token)
            reset_current_session_id(session_token)
            reset_state(state_token)

    def _run_inner(
        self,
        user_msg: str,
        *,
        on_text_delta: Callable[[str], None] | None = None,
    ) -> RunResult:
        schemas = self._registry.list_schemas()
        # M143: when the provider can't call tools natively, present them as
        # fenced `veles-tool` text blocks and parse calls back out of prose.
        # Decided before `_open_session` so the augmented system prompt is the
        # one persisted (and the sentinel guard keeps resume from doubling it).
        fenced = (
            self._fenced_tools
            and fenced_tools_enabled_by_env()
            and bool(schemas)
            and not getattr(self._provider, "supports_tools", True)
        )
        if fenced and FENCED_SENTINEL not in (self._system_prompt or ""):
            addendum = render_tools_prompt(schemas)
            self._system_prompt = (
                f"{self._system_prompt}\n\n{addendum}" if self._system_prompt else addendum
            )

        history = self._open_session(user_msg)
        tools = schemas or None
        # In fenced mode the provider never receives native schemas (it would
        # ignore them); the tool surface lives in the system prompt instead.
        tools_for_provider = None if fenced else tools
        # M79: accumulate token usage across the iterations of one run so
        # the TUI can render it on the status bar.
        usage_acc = UsageSnapshot()

        cancel = current_cancel_token()

        # M144: detect the only stall the Veles loop can fall into — the same
        # tool call repeated round after round — and force a single tool-free
        # answer round when it trips. `force_answer` withholds tools for the
        # next provider call only.
        stall_guard = StallGuard(
            repeat_limit=self._stall_repeat_limit,
            # Per-call guard (re-reading the same file all turn) rides the same
            # on/off knob — disabling the stall guard disables both signals.
            call_repeat_limit=7 if self._stall_repeat_limit else None,
        )
        force_answer = False
        token_warned = False
        invoked: set[str] = set()
        # Live 2026-07-08 (ollama qwen3.5:9b): small local models emit broken
        # JSON in veles-tool fences constantly. A round whose block parses to
        # ZERO calls used to be treated as the final answer — the turn died
        # silently mid-task. Feed the parse errors back (bounded, so a model
        # stuck on garbage can't loop forever).
        parse_nudges = 0
        # M214 (B2): a turn that would end with NO tool calls and EMPTY text
        # (e.g. a tool-only round the model didn't close with an answer) leaves
        # the channel placeholder stuck at "...". Force ONE tool-free answer
        # round before giving up, once per turn.
        empty_retry_used = False

        for iteration in range(1, self._max_iterations + 1):
            # Cooperative cancellation checkpoint #1: between iterations,
            # so a stop requested during tool dispatch (or a non-streaming
            # `create_message`) is honoured before the next provider call.
            if cancel is not None:
                cancel.check()

            budget = current_budget()
            if budget is not None and budget.exhausted:
                return self._finalize(
                    RunResult(
                        text=f"<budget exhausted: {budget.consumed}/{budget.limit} tokens>",
                        iterations=iteration - 1,
                        history=history,
                        stopped_reason="budget_exhausted",
                        session_id=self._session_id,
                        usage=usage_acc,
                        invoked_tools=frozenset(invoked),
                    )
                )

            if self._compressor is not None:
                history = self._compressor(history, self._session_id)

            # Last-line defence: if the compressor returned a still-
            # too-large history (silent skip, summariser failure,
            # missing API key), drop oldest non-system turns until we
            # fit under the model's context window. Prevents the
            # provider from raising "prompt is too long" at runtime.
            # NOTE: the estimate_tokens ceiling check below is O(chars) over
            # the whole history each iteration — deliberately uncached
            # (audited M149-M157, decided no cache).
            if self._hard_ceiling_tokens is not None:
                from veles.core.context_compressor import (
                    emergency_truncate,
                    estimate_tokens,
                )

                current = estimate_tokens(history)
                if current > self._hard_ceiling_tokens:
                    new_history, dropped = emergency_truncate(
                        history, target_tokens=self._hard_ceiling_tokens
                    )
                    if dropped:
                        import logging as _logging

                        _logging.getLogger(__name__).warning(
                            "emergency-truncated session=%s tokens_before=%d "
                            "tokens_after=%d dropped_turns=%d ceiling=%d",
                            self._session_id,
                            current,
                            estimate_tokens(new_history),
                            dropped,
                            self._hard_ceiling_tokens,
                        )
                    history = new_history

            fire_hook(
                "pre_turn",
                turn=iteration,
                session_id=self._session_id,
                user_msg=user_msg,
                history_len=len(history),
            )
            self._log(f"-> turn {iteration}: requesting completion")

            # M144: a tripped stall guard withholds tools for exactly one
            # round, forcing the model to answer instead of looping the same
            # dead call. The flag is consumed here. (In fenced mode the
            # provider already sees tools=None; the nudge message does the
            # forcing there.)
            round_tools = None if force_answer else tools_for_provider
            force_answer = False

            # Last-line consistency guard before the wire: compression /
            # truncation / a resumed session / a provider translation quirk can
            # split a tool_call from its result, which providers reject with
            # "No tool output found for function call ...". Synthesize a
            # placeholder for any unanswered call and drop any orphaned result.
            history = repair_tool_pairing(history)

            # M143 follow-up: in fenced mode the raw stream IS the tool-call
            # channel — scrub ```veles-tool blocks out of the DISPLAY deltas so
            # the chat shows prose only (the full raw text is still parsed for
            # calls below). Fresh scrubber per round; fences never span rounds.
            round_delta = on_text_delta
            round_scrubber = None
            if fenced and on_text_delta is not None:
                round_scrubber = FencedToolScrubber()

                def round_delta(chunk: str, _cb=on_text_delta, _scrub=round_scrubber) -> None:  # type: ignore[misc]
                    cleaned = _scrub.feed(chunk)
                    if cleaned:
                        _cb(cleaned)

            response = self._request_completion(
                history=history,
                tools=round_tools,
                on_text_delta=round_delta,
                budget=budget,
            )
            if round_scrubber is not None and on_text_delta is not None:
                tail = round_scrubber.finalize()
                if tail:
                    on_text_delta(tail)
            usage_acc.add(response.usage)
            # Real per-round usage for live HUDs: a tool-call-only round streams
            # no text, so a chars/4 estimate over text deltas would read 0.
            self._emit_event(
                RoundUsageEvent(
                    ts=now_iso(),
                    session_id=self._session_id,
                    prompt_tokens=getattr(response.usage, "prompt_tokens", 0),
                    completion_tokens=getattr(response.usage, "completion_tokens", 0),
                    total_tokens=getattr(response.usage, "total_tokens", 0),
                    cumulative_completion=usage_acc.completion_tokens,
                    cumulative_total=usage_acc.total_tokens,
                )
            )

            # M143: in fenced mode the model expresses tool calls as text, so
            # parse them out of the response and record the assistant turn
            # WITHOUT native tool_calls (keeps the wire plain on resend). The
            # native path is unchanged.
            parse_errors: list[str] = []
            if fenced:
                effective_calls, parse_errors = parse_tool_calls_with_errors(response.text or "")
                self._record_fenced_assistant(response, effective_calls, history)
            else:
                self._record_assistant_response(response, history)
                effective_calls = response.tool_calls

            fire_hook(
                "post_turn",
                turn=iteration,
                response_text=response.text or "",
                tool_call_count=len(effective_calls),
                tokens_used=response.usage.total_tokens,
            )

            if not effective_calls:
                # Fenced garbage round: the model TRIED to call tools but
                # nothing parsed. Ending the turn here (the pre-fix behaviour)
                # silently killed it mid-task — feed the parse errors back and
                # let the model re-emit, up to _PARSE_NUDGE_LIMIT per run.
                if parse_errors and parse_nudges < _PARSE_NUDGE_LIMIT:
                    parse_nudges += 1
                    self._log(
                        f"-> fenced block parsed to 0 calls "
                        f"(nudge {parse_nudges}/{_PARSE_NUDGE_LIMIT}); feeding errors back"
                    )
                    nudge = Message(role="user", content=render_parse_errors(parse_errors))
                    history.append(nudge)
                    self._persist(nudge)
                    continue
                final_text = response.text or ""
                # M214 (B2): don't finalize an EMPTY answer on the first try —
                # force one tool-free round so the model actually speaks, rather
                # than leaving a channel turn blank. Bounded to one retry.
                if not final_text and not empty_retry_used:
                    empty_retry_used = True
                    force_answer = True
                    self._log("-> empty answer: forcing one tool-free answer round")
                    nudge = Message(role="user", content=EMPTY_ANSWER_NUDGE)
                    history.append(nudge)
                    self._persist(nudge)
                    continue
                return self._finalize(
                    RunResult(
                        text=final_text,
                        iterations=iteration,
                        history=history,
                        stopped_reason="completed" if final_text else "empty",
                        session_id=self._session_id,
                        usage=usage_acc,
                        invoked_tools=frozenset(invoked),
                    )
                )

            if fenced:
                self._dispatch_fenced_calls(effective_calls, history, parse_errors=parse_errors)
            else:
                self._dispatch_tool_calls(response, history)
            invoked.update(call.name for call in effective_calls)

            # M144: with the repeated tool's results now in history (so the
            # assistant→tool message pairing stays valid for the next call),
            # check for a stall. If tripped, inject a nudge and force the next
            # round to run tool-free so the model must answer.
            if stall_guard.record(effective_calls):
                self._log("-> stall detected: forcing a tool-free answer round")
                force_answer = True
                nudge = Message(role="user", content=STALL_NUDGE)
                history.append(nudge)
                self._persist(nudge)

            # Soft token-budget heads-up: once the turn crosses the threshold,
            # tell the model ONCE it has burned a lot of tokens so it stops if it
            # is looping. Unlike the stall guard this does NOT withhold tools — a
            # genuinely progressing long turn keeps going.
            if (
                not token_warned
                and self._token_warn_threshold is not None
                and usage_acc.total_tokens >= self._token_warn_threshold
            ):
                token_warned = True
                self._log(f"-> turn crossed {usage_acc.total_tokens} tokens; nudging")
                warn = Message(
                    role="user",
                    content=TOKEN_WARN_NUDGE.format(tokens=usage_acc.total_tokens),
                )
                history.append(warn)
                self._persist(warn)

        self._log("-> max_iterations reached")
        last_text = next(
            (m.content for m in reversed(history) if m.role == "assistant" and m.content),
            "",
        )
        return self._finalize(
            RunResult(
                text=last_text or "",
                iterations=self._max_iterations,
                history=history,
                stopped_reason="max_iterations",
                session_id=self._session_id,
                usage=usage_acc,
                invoked_tools=frozenset(invoked),
            )
        )

    def _open_session(self, user_msg: str) -> list[Message]:
        """Bootstrap history, append + persist the user turn, fire session hooks."""
        was_resume = self._session_id is not None
        history = self._bootstrap_history()
        fire_hook("on_session_start", session_id=self._session_id, is_resume=was_resume)
        user_message = Message(role="user", content=user_msg)
        history.append(user_message)
        self._persist(user_message)
        self._emit_event(UserMessageEvent(ts=now_iso(), session_id=self._session_id, text=user_msg))
        return history

    def _request_completion(
        self,
        *,
        history: list[Message],
        tools: list[dict] | None,
        on_text_delta: Callable[[str], None] | None,
        budget,
    ) -> ProviderResponse:
        """One LLM round-trip: stream or one-shot, with trace + budget bookkeeping."""
        call_started = time.monotonic()
        ttft_ms = 0
        if on_text_delta is not None:
            response, ttft_ms = self._consume_stream_timed(
                history=history, tools=tools, on_text_delta=on_text_delta
            )
        else:
            # Run the blocking provider call so a cancel (Ctrl+C / Esc) unwinds
            # within one poll interval instead of waiting out the 120s HTTP
            # timeout — the between-iterations checkpoint alone can't interrupt a
            # call already in flight. Workers inherit the token (copy_context),
            # so this makes parallel delegation cancellable too.
            response = run_cancellable(
                lambda: self._provider.create_message(
                    history,
                    tools=tools,
                    model=self._model,
                    max_tokens=self._max_tokens,
                ),
                current_cancel_token(),
            )
        total_latency_ms = int((time.monotonic() - call_started) * 1000)
        self._emit_trace(
            response=response,
            tools=tools,
            ttft_ms=ttft_ms,
            total_latency_ms=total_latency_ms,
        )
        if budget is not None:
            budget.consumed += response.usage.total_tokens
        if response.text:
            response.text = scrub_text(response.text)
        return response

    def _record_assistant_response(
        self, response: ProviderResponse, history: list[Message]
    ) -> None:
        """Append the assistant turn, persist it, emit AssistantMessage."""
        assistant_message = Message(
            role="assistant",
            content=response.text,
            tool_calls=list(response.tool_calls),
        )
        history.append(assistant_message)
        self._persist(assistant_message)
        self._emit_event(
            AssistantMessageEvent(
                ts=now_iso(),
                session_id=self._session_id,
                text=response.text,
                tool_call_count=len(response.tool_calls),
                finish_reason=response.finish_reason,
            )
        )

    def _dispatch_tool_calls(self, response: ProviderResponse, history: list[Message]) -> None:
        """Dispatch every tool the model asked for, appending tool-role messages."""
        project = current_project()
        artifact_dir = project.state_dir if project is not None else None
        approval_dir = project.state_dir if project is not None else None
        for call in response.tool_calls:
            tool_message = _dispatch(
                self._registry,
                call,
                log=self._log,
                event_writer=self._event_writer,
                event_listener=self._event_listener,
                session_id=self._session_id,
                artifact_dir=artifact_dir,
                approval_dir=approval_dir,
            )
            history.append(tool_message)
            self._persist(tool_message)

    def _record_fenced_assistant(
        self,
        response: ProviderResponse,
        parsed_calls: list[ToolCall],
        history: list[Message],
    ) -> None:
        """M143: record the assistant turn for the fenced path. Keeps the raw
        text (which contains the `veles-tool` blocks) but stores NO native
        tool_calls — so the message serialises as plain text when resent to a
        non-tool server, and resume can't leak a native tool-call shape."""
        assistant_message = Message(role="assistant", content=response.text, tool_calls=[])
        history.append(assistant_message)
        self._persist(assistant_message)
        self._emit_event(
            AssistantMessageEvent(
                ts=now_iso(),
                session_id=self._session_id,
                text=response.text,
                tool_call_count=len(parsed_calls),
                finish_reason=response.finish_reason,
            )
        )

    def _dispatch_fenced_calls(
        self,
        calls: list[ToolCall],
        history: list[Message],
        parse_errors: list[str] | None = None,
    ) -> None:
        """M143: execute fenced tool calls and feed every result back as ONE
        user-role message. Reuses `_dispatch` (permission / veto / event
        machinery) but discards its `role=tool` Message — that shape would
        serialise to the native tool-call wire form a non-tool server may
        reject. Results return as plain text instead, clearly framed as data.

        `parse_errors`: junk that was dropped from the same veles-tool block
        (live 2026-07-08, ollama qwen3.5:9b — broken JSON among valid calls).
        Reported alongside the results so the model can re-emit the dropped
        calls instead of silently losing them."""
        project = current_project()
        artifact_dir = project.state_dir if project is not None else None
        approval_dir = project.state_dir if project is not None else None
        chunks: list[str] = []
        for call in calls:
            tool_message = _dispatch(
                self._registry,
                call,
                log=self._log,
                event_writer=self._event_writer,
                event_listener=self._event_listener,
                session_id=self._session_id,
                artifact_dir=artifact_dir,
                approval_dir=approval_dir,
            )
            chunks.append(f"[{call.name}]\n{tool_message.content or ''}")
        if parse_errors:
            chunks.append(render_parse_errors(parse_errors))
        combined = Message(
            role="user",
            content=f"{FENCED_RESULT_HEADER}\n\n" + "\n\n".join(chunks),
        )
        history.append(combined)
        self._persist(combined)

    def _finalize(self, result: RunResult) -> RunResult:
        fire_hook(
            "on_session_end",
            session_id=self._session_id,
            stopped_reason=result.stopped_reason,
            iterations=result.iterations,
        )
        return result

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def _bootstrap_history(self) -> list[Message]:
        # Resume path: known session_id loads its full history. M114:
        # callers that explicitly pass a `system_prompt` on every Agent
        # build (the daemon does this since M-R2.3 to keep AGENTS.md +
        # recall fresh for each Telegram turn) want it applied on
        # resume too — otherwise the model sees the system message
        # frozen at the first turn and forgets the project context.
        # If the caller passed None we honour the saved system message
        # — that's the `veles run --resume` flow where the user wants
        # the original context back verbatim.
        if self._session_id is not None and self._store is not None:
            history = self._store.load_messages(self._session_id)
            if self._system_prompt:
                fresh = Message(role="system", content=self._system_prompt)
                if history and history[0].role == "system":
                    history[0] = fresh
                else:
                    history.insert(0, fresh)
            return history

        # Fresh path with persistence: create a session and persist system prompt.
        if self._store is not None and self._session_id is None:
            self._session_id = self._store.create_session()
            # M224: refresh the sticky-routing key now that the id exists, so the
            # very first provider call of a fresh session already pins a provider.
            set_current_session_id(self._session_id)

        history: list[Message] = []
        if self._system_prompt:
            sys_msg = Message(role="system", content=self._system_prompt)
            history.append(sys_msg)
            self._persist(sys_msg)
        return history

    def _persist(self, message: Message) -> None:
        if self._store is not None and self._session_id is not None:
            self._store.append_turn(self._session_id, message)

    def _consume_stream(
        self,
        *,
        history: list[Message],
        tools: list[dict] | None,
        on_text_delta: Callable[[str], None],
    ) -> ProviderResponse:
        response, _ = self._consume_stream_timed(
            history=history, tools=tools, on_text_delta=on_text_delta
        )
        return response

    def _consume_stream_timed(
        self,
        *,
        history: list[Message],
        tools: list[dict] | None,
        on_text_delta: Callable[[str], None],
    ) -> tuple[ProviderResponse, int]:
        """Thin delegate — body extracted to `stream_consumer.consume_stream`
        (M156). Returns (response, time-to-first-token in ms)."""
        return consume_stream(
            self._provider,
            history=history,
            tools=tools,
            model=self._model,
            max_tokens=self._max_tokens,
            on_text_delta=on_text_delta,
            emit_event=self._emit_event,
            session_id=self._session_id,
        )

    def _emit_event(self, event) -> None:
        """Self-side companion to module-level `_emit` — uses our writer and
        the per-run listener (if any) installed by `run()`."""
        _emit(self._event_writer, event, self._event_listener)

    def _emit_trace(
        self,
        *,
        response: ProviderResponse,
        tools: list[dict] | None,
        ttft_ms: int,
        total_latency_ms: int,
    ) -> None:
        if self._trace_writer is None:
            return
        usage = response.usage
        record = TraceRecord(
            request_id=uuid.uuid4().hex[:12],
            session_id=self._session_id,
            ts=now_iso(),
            provider=getattr(self._provider, "name", type(self._provider).__name__),
            model=self._model,
            system_prompt_hash=hash_text(self._system_prompt),
            tool_bundle_hash=hash_tools(tools),
            input_tokens_new=max(0, usage.prompt_tokens - usage.cache_read_tokens),
            cache_read_tokens=usage.cache_read_tokens,
            cache_creation_tokens=usage.cache_creation_tokens,
            output_tokens=usage.completion_tokens,
            ttft_ms=ttft_ms,
            total_latency_ms=total_latency_ms,
            est_cost_usd=0.0,
            tool_calls_count=len(response.tool_calls),
            permission_decisions=[],
            final_status="ok",
        )
        try:
            self._trace_writer.write(record)
        except Exception as exc:
            # Tracing must never break a run. Log to stderr if verbose.
            self._log(f"   trace write failed: {exc}")

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(msg, file=sys.stderr, flush=True)
