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
from typing import Any, Literal

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
    TokenBudget,
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
from veles.core.history_repair import (
    call_key,
    repair_tool_pairing,
    supersede_fenced,
    supersede_loaded_history,
    supersede_native,
)
from veles.core.memory import SessionStore
from veles.core.model_budgets import default_max_tokens_for
from veles.core.modules import fire_hook
from veles.core.provider import (
    Message,
    Provider,
    ProviderResponse,
    TokenUsage,
    ToolCall,
)
from veles.core.stall_guard import STALL_NUDGE, TOKEN_WARN_NUDGE, StallGuard
from veles.core.stream_consumer import consume_stream
from veles.core.timeutil import utc_iso
from veles.core.tool_dispatch import _dispatch, _emit
from veles.core.tools.registry import Registry
from veles.core.trace import (
    TraceRecord,
    TraceWriter,
    hash_text,
    hash_tools,
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

# M254: how many tool-free rounds an EMPTY final answer may cost before the run
# ends blank. Was a hard 1 (M214), which the original report said is not enough
# for a model that finishes and says nothing. Bounded the same way and for the
# same reason as `_PARSE_NUDGE_LIMIT` — a model that will never speak must not
# be able to spend the whole iteration budget being asked to.
_EMPTY_ANSWER_NUDGE_LIMIT = 3


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
    # M254: the slice of `completion_tokens` spent thinking (M250 harvests it
    # per call). Run-level, because the question it answers is run-level: when a
    # turn ends with no text, was the budget eaten by reasoning?
    reasoning_tokens: int = 0

    def add(self, usage: TokenUsage) -> None:
        prompt = getattr(usage, "prompt_tokens", 0)
        self.prompt_tokens += prompt
        self.completion_tokens += getattr(usage, "completion_tokens", 0)
        self.total_tokens += getattr(usage, "total_tokens", 0)
        self.cache_read_tokens += getattr(usage, "cache_read_tokens", 0)
        self.cache_creation_tokens += getattr(usage, "cache_creation_tokens", 0)
        self.reasoning_tokens += getattr(usage, "reasoning_tokens", 0)
        # Latest request's prompt size = current resident-context estimate.
        if prompt:
            self.last_prompt_tokens = prompt


# Why a run ended. `truncated`: the answer hit the completion-token cap (M254).
# `synthetic`: a mode (GoalMode) reporting a step that ran no agent turn.
StopReason = Literal[
    "completed",
    "max_iterations",
    "empty",
    "truncated",
    "cancelled",
    "budget_exhausted",
    "synthetic",
]


@dataclass(slots=True)
class RunResult:
    text: str
    iterations: int
    history: list[Message] = field(default_factory=list)
    stopped_reason: StopReason = "completed"
    session_id: str | None = None
    usage: UsageSnapshot = field(default_factory=UsageSnapshot)
    # Names of every tool the run dispatched. Lets callers judge success by
    # "did the work actually happen" instead of by non-empty final prose — a
    # thinking local model routinely ends with empty content after doing all
    # the tool work (seen live 2026-07-08, ollama qwen3.5:9b).
    invoked_tools: frozenset[str] = frozenset()


@dataclass(slots=True)
class _Turn:
    """Mutable state of one `Agent.run` — what the loop's phases share."""

    history: list[Message]
    fenced: bool  # tools presented as `veles-tool` text blocks (M143)
    tools: list[dict[str, Any]] | None  # native schemas for the provider; None when fenced
    stall_guard: StallGuard
    usage: UsageSnapshot = field(default_factory=UsageSnapshot)
    invoked: set[str] = field(default_factory=set)
    force_answer: bool = False  # withhold tools for the next round only
    token_warned: bool = False
    parse_nudges: int = 0
    empty_nudges: int = 0


def _scrubbed(sink: Callable[[str], None], scrubber: FencedToolScrubber) -> Callable[[str], None]:
    """Wrap a display callback so `veles-tool` fences never reach it."""

    def feed(chunk: str) -> None:
        if cleaned := scrubber.feed(chunk):
            sink(cleaned)

    return feed


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
        # M247: `None` resolves per model instead of a flat 4096. A reasoning
        # model spends the completion budget on a hidden thinking channel first,
        # so 4096 can be consumed entirely before it writes one visible
        # character — measured on glm-5.3-flash, which returned
        # `completion == max_tokens` with empty content. Callers that pass an
        # explicit number still win.
        max_tokens: int | None = None,
        verbose: bool = False,
        store: SessionStore | None = None,
        session_id: str | None = None,
        compressor: Callable[[list[Message], str | None], list[Message]] | None = None,
        hard_ceiling_tokens: int | None = None,
        trace_writer: TraceWriter | None = None,
        event_writer: EventWriter | None = None,
        plan_mode: bool = False,
        role: Literal["manager"] | None = None,
        stall_repeat_limit: int | None = 3,
        token_warn_threshold: int | None = 500_000,
        fenced_tools: bool = True,
    ) -> None:
        # Public: modes that need a direct provider call (AutoMode classifier,
        # GoalMode advisor / CONFIRM message) use it without running the loop.
        self.provider = provider
        self._registry = registry
        self._model = model
        # M122c: orchestration role (VISION §5.3). Default None = a normal
        # agent. role="manager" makes `run()` refuse to produce an answer
        # (managers decompose + spawn; they never write).
        self._role = role
        self._max_iterations = max_iterations
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens if max_tokens is not None else default_max_tokens_for(model)
        self._verbose = verbose
        self._store = store
        self._session_id = session_id
        self._compressor = compressor
        # Last-line truncation ceiling. After compressor returns, Agent
        # checks estimate_tokens(history) and, if still above this
        # threshold, drops oldest non-system turns until under. Set
        # `None` to disable (legacy callers without a configured limit).
        self._hard_ceiling_tokens = hard_ceiling_tokens
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
                    ts=utc_iso(),
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
        """The turn loop, one iteration per provider round:
        fit history → request → record → answer-or-nudge / run tools."""
        turn = self._start_turn(user_msg)
        cancel = current_cancel_token()
        for iteration in range(1, self._max_iterations + 1):
            # Cancellation checkpoint between rounds, so a stop requested during
            # tool dispatch is honoured before the next provider call.
            if cancel is not None:
                cancel.check()
            budget = current_budget()
            if budget is not None and budget.exhausted:
                text = f"<budget exhausted: {budget.consumed}/{budget.limit} tokens>"
                return self._result(turn, text, iteration - 1, "budget_exhausted")

            self._fit_history(turn)
            fire_hook(
                "pre_turn",
                turn=iteration,
                session_id=self._session_id,
                user_msg=user_msg,
                history_len=len(turn.history),
            )
            self._log(f"-> turn {iteration}: requesting completion")
            response = self._request_round(turn, on_text_delta, budget)
            calls, parse_errors = self._record_round(turn, response)
            fire_hook(
                "post_turn",
                turn=iteration,
                response_text=response.text or "",
                tool_call_count=len(calls),
                tokens_used=response.usage.total_tokens,
            )
            if not calls:
                result = self._answer_or_nudge(turn, response, parse_errors, iteration)
                if result is not None:
                    return result
                continue
            self._run_tools(turn, calls, parse_errors)

        self._log("-> max_iterations reached")
        last_text = next(
            (m.content for m in reversed(turn.history) if m.role == "assistant" and m.content),
            "",
        )
        return self._result(turn, last_text, self._max_iterations, "max_iterations")

    def _start_turn(self, user_msg: str) -> _Turn:
        schemas = self._registry.list_schemas()
        # M143: when the provider can't call tools natively, present them as
        # fenced `veles-tool` text blocks and parse calls back out of prose.
        # Decided before `_open_session` so the augmented system prompt is the
        # one persisted (and the sentinel guard keeps resume from doubling it).
        fenced = (
            self._fenced_tools
            and fenced_tools_enabled_by_env()
            and bool(schemas)
            and not getattr(self.provider, "supports_tools", True)
        )
        if fenced and FENCED_SENTINEL not in (self._system_prompt or ""):
            addendum = render_tools_prompt(schemas)
            self._system_prompt = (
                f"{self._system_prompt}\n\n{addendum}" if self._system_prompt else addendum
            )
        return _Turn(
            history=self._open_session(user_msg),
            fenced=fenced,
            # Fenced: the provider never receives native schemas (it would
            # ignore them); the tool surface lives in the system prompt.
            tools=None if fenced else (schemas or None),
            # M144: the only stall the loop can fall into is the same tool call
            # repeated round after round. The per-call guard (re-reading one
            # file all turn) rides the same on/off knob.
            stall_guard=StallGuard(
                repeat_limit=self._stall_repeat_limit,
                call_repeat_limit=7 if self._stall_repeat_limit else None,
            ),
        )

    def _fit_history(self, turn: _Turn) -> None:
        """Compress, then — if the compressor still left too much (silent skip,
        summariser failure, missing API key) — drop the oldest non-system turns
        until the history fits, so the provider never rejects the prompt as too
        long. The ceiling check is O(chars) per round, deliberately uncached
        (audited M149–M157)."""
        if self._compressor is not None:
            turn.history = self._compressor(turn.history, self._session_id)
        if self._hard_ceiling_tokens is None:
            return
        from veles.core.context_compressor import emergency_truncate, estimate_tokens

        current = estimate_tokens(turn.history)
        if current <= self._hard_ceiling_tokens:
            return
        turn.history, dropped = emergency_truncate(
            turn.history, target_tokens=self._hard_ceiling_tokens
        )
        if dropped:
            logger.warning(
                "emergency-truncated session=%s tokens_before=%d "
                "tokens_after=%d dropped_turns=%d ceiling=%d",
                self._session_id,
                current,
                estimate_tokens(turn.history),
                dropped,
                self._hard_ceiling_tokens,
            )

    def _request_round(
        self,
        turn: _Turn,
        on_text_delta: Callable[[str], None] | None,
        budget: TokenBudget | None,
    ) -> ProviderResponse:
        """One provider round: pick the tools, repair the history, stream or
        call, and account the usage."""
        # A tripped guard or an empty-answer nudge withholds tools for exactly
        # this round. (Fenced mode already sends none; the nudge text forces it.)
        tools = None if turn.force_answer else turn.tools
        turn.force_answer = False
        # Compression / truncation / resume / an adapter quirk can split a
        # tool_call from its result, which providers reject. Synthesize a
        # placeholder for an unanswered call and drop an orphaned result.
        turn.history = repair_tool_pairing(turn.history)

        # M143: in fenced mode the raw stream IS the tool-call channel — scrub
        # ```veles-tool blocks from the DISPLAY deltas so the chat shows prose
        # only (the full text is still parsed). Fences never span rounds.
        delta = on_text_delta
        scrubber: FencedToolScrubber | None = None
        if turn.fenced and on_text_delta is not None:
            scrubber = FencedToolScrubber()
            delta = _scrubbed(on_text_delta, scrubber)
        response = self._request_completion(
            history=turn.history, tools=tools, on_text_delta=delta, budget=budget
        )
        if scrubber is not None and on_text_delta is not None and (tail := scrubber.finalize()):
            on_text_delta(tail)
        turn.usage.add(response.usage)
        # Real per-round usage for live HUDs: a tool-call-only round streams no
        # text, so a chars/4 estimate over text deltas would read 0.
        usage = response.usage
        self._emit_event(
            RoundUsageEvent(
                ts=utc_iso(),
                session_id=self._session_id,
                prompt_tokens=getattr(usage, "prompt_tokens", 0),
                completion_tokens=getattr(usage, "completion_tokens", 0),
                total_tokens=getattr(usage, "total_tokens", 0),
                cumulative_completion=turn.usage.completion_tokens,
                cumulative_total=turn.usage.total_tokens,
                cache_read_tokens=getattr(usage, "cache_read_tokens", 0),
                cache_creation_tokens=getattr(usage, "cache_creation_tokens", 0),
            )
        )
        return response

    def _record_round(
        self, turn: _Turn, response: ProviderResponse
    ) -> tuple[list[ToolCall], list[str]]:
        """Record the assistant turn; return the calls to run and, in fenced
        mode, the blocks that failed to parse.

        Fenced (M143): calls are parsed out of the text and the turn is stored
        WITHOUT native tool_calls, so it resends as plain text to a non-tool
        server and resume can't leak a native tool-call shape."""
        if turn.fenced:
            calls, errors = parse_tool_calls_with_errors(response.text or "")
            stored: list[ToolCall] = []
        else:
            calls, errors = list(response.tool_calls), []
            stored = calls
        self._append(
            turn.history, Message(role="assistant", content=response.text, tool_calls=stored)
        )
        self._emit_event(
            AssistantMessageEvent(
                ts=utc_iso(),
                session_id=self._session_id,
                text=response.text,
                tool_call_count=len(calls),
                finish_reason=response.finish_reason,
            )
        )
        return calls, errors

    def _answer_or_nudge(
        self,
        turn: _Turn,
        response: ProviderResponse,
        parse_errors: list[str],
        iteration: int,
    ) -> RunResult | None:
        """A round with no tool calls: the final answer, or None after a nudge
        that gives the model another round."""
        # Fenced garbage round: the model TRIED to call tools but nothing parsed
        # (small local models emit broken JSON constantly). Ending the turn here
        # silently killed it mid-task — feed the errors back, bounded.
        if parse_errors and turn.parse_nudges < _PARSE_NUDGE_LIMIT:
            turn.parse_nudges += 1
            self._log(
                f"-> fenced block parsed to 0 calls "
                f"(nudge {turn.parse_nudges}/{_PARSE_NUDGE_LIMIT}); feeding errors back"
            )
            self._append(
                turn.history, Message(role="user", content=render_parse_errors(parse_errors))
            )
            return None
        text = response.text or ""
        if text:
            return self._result(turn, text, iteration, "completed")
        # M254: an empty answer has two causes that need opposite handling.
        #   finish_reason="length" — the completion budget ran out, and for a
        #     reasoning model the visible answer is the part that gets cut.
        #     Re-asking with the SAME budget hits the same wall, so report it
        #     and let the cap be raised.
        #   anything else — the model finished and said nothing. Nudge it with
        #     a tool-free round (M214), bounded like the parse nudge.
        if response.finish_reason == "length":
            self._log(
                f"-> empty answer: response hit the token cap "
                f"({turn.usage.completion_tokens} completion tokens, "
                f"{turn.usage.reasoning_tokens} of them reasoning) — "
                "raise --max-tokens or the model's budget"
            )
            return self._result(turn, "", iteration, "truncated")
        if turn.empty_nudges < _EMPTY_ANSWER_NUDGE_LIMIT:
            turn.empty_nudges += 1
            turn.force_answer = True
            self._log(
                f"-> empty answer: forcing a tool-free answer round "
                f"(nudge {turn.empty_nudges}/{_EMPTY_ANSWER_NUDGE_LIMIT})"
            )
            self._append(turn.history, Message(role="user", content=EMPTY_ANSWER_NUDGE))
            return None
        return self._result(turn, "", iteration, "empty")

    def _run_tools(self, turn: _Turn, calls: list[ToolCall], parse_errors: list[str]) -> None:
        """Dispatch the round's calls, then the two guards that watch the turn."""
        if turn.fenced:
            self._dispatch_fenced_calls(calls, turn.history, parse_errors=parse_errors)
        else:
            self._dispatch_tool_calls(calls, turn.history)
        turn.invoked.update(call.name for call in calls)

        # M144: with the results in history (so the call→result pairing stays
        # valid), a repeated call trips the stall guard: nudge, and force the
        # next round tool-free so the model must answer.
        if turn.stall_guard.record(calls):
            self._log("-> stall detected: forcing a tool-free answer round")
            turn.force_answer = True
            self._append(turn.history, Message(role="user", content=STALL_NUDGE))

        # A one-time heads-up once the turn has burned a lot of tokens, so a
        # looping turn stops. Unlike the stall guard it does NOT withhold tools
        # — a genuinely progressing long turn keeps going.
        total = turn.usage.total_tokens
        threshold = self._token_warn_threshold
        if not turn.token_warned and threshold is not None and total >= threshold:
            turn.token_warned = True
            self._log(f"-> turn crossed {total} tokens; nudging")
            self._append(
                turn.history,
                Message(role="user", content=TOKEN_WARN_NUDGE.format(tokens=total)),
            )

    def _result(self, turn: _Turn, text: str, iterations: int, reason: StopReason) -> RunResult:
        return self._finalize(
            RunResult(
                text=text,
                iterations=iterations,
                history=turn.history,
                stopped_reason=reason,
                session_id=self._session_id,
                usage=turn.usage,
                invoked_tools=frozenset(turn.invoked),
            )
        )

    def _append(self, history: list[Message], message: Message) -> None:
        history.append(message)
        self._persist(message)

    def _open_session(self, user_msg: str) -> list[Message]:
        """Bootstrap history, append + persist the user turn, fire session hooks."""
        was_resume = self._session_id is not None
        history = self._bootstrap_history()
        fire_hook("on_session_start", session_id=self._session_id, is_resume=was_resume)
        self._append(history, Message(role="user", content=user_msg))
        self._emit_event(UserMessageEvent(ts=utc_iso(), session_id=self._session_id, text=user_msg))
        return history

    def _request_completion(
        self,
        *,
        history: list[Message],
        tools: list[dict[str, Any]] | None,
        on_text_delta: Callable[[str], None] | None,
        budget: TokenBudget | None,
    ) -> ProviderResponse:
        """One LLM round-trip: stream or one-shot, with trace + budget bookkeeping."""
        call_started = time.monotonic()
        ttft_ms = 0
        if on_text_delta is not None:
            response, ttft_ms = consume_stream(
                self.provider,
                history=history,
                tools=tools,
                model=self._model,
                max_tokens=self._max_tokens,
                on_text_delta=on_text_delta,
                emit_event=self._emit_event,
                session_id=self._session_id,
            )
        else:
            # Run the blocking provider call so a cancel (Ctrl+C / Esc) unwinds
            # within one poll interval instead of waiting out the 120s HTTP
            # timeout — the between-iterations checkpoint alone can't interrupt a
            # call already in flight. Workers inherit the token (copy_context),
            # so this makes parallel delegation cancellable too.
            response = run_cancellable(
                lambda: self.provider.create_message(
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

    def _dispatch_one(self, call: ToolCall) -> Message:
        project = current_project()
        state_dir = project.state_dir if project is not None else None
        return _dispatch(
            self._registry,
            call,
            log=self._log,
            event_writer=self._event_writer,
            event_listener=self._event_listener,
            session_id=self._session_id,
            artifact_dir=state_dir,
            approval_dir=state_dir,
        )

    def _dispatch_tool_calls(self, calls: list[ToolCall], history: list[Message]) -> None:
        """Dispatch every tool the model asked for, appending tool-role messages."""
        for call in calls:
            tool_message = self._dispatch_one(call)
            # M238: blank the earlier result of an identical deterministic read
            # before appending the fresh one, so the stale copy stops competing
            # with it for attention. In-session only — see the note in
            # `_dispatch_fenced_calls`.
            supersede_native(history, call.name, call.arguments)
            self._append(history, tool_message)

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
        chunks: list[str] = []
        for call in calls:
            tool_message = self._dispatch_one(call)
            # M238: the tag makes this chunk findable later — fenced mode keeps
            # no arguments in the history, so without it a repeated identical
            # read cannot be matched to the chunk it supersedes.
            #
            # ponytail: supersession is in-memory only. `_persist` has already
            # written the full earlier result to the SessionStore, which is
            # append-only, so `--resume` rehydrates the stale copy. Fixing that
            # needs an update path on the store; the win here is the live turn's
            # context, which is where the contradiction actually bites.
            tag = call_key(call.name, call.arguments)
            supersede_fenced(history, call.name, tag, FENCED_RESULT_HEADER)
            chunks.append(f"[{call.name} {tag}]\n{tool_message.content or ''}")
        if parse_errors:
            chunks.append(render_parse_errors(parse_errors))
        combined = f"{FENCED_RESULT_HEADER}\n\n" + "\n\n".join(chunks)
        self._append(history, Message(role="user", content=combined))

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
            loaded = self._store.load_messages(self._session_id)
            # M245: the store is a complete archive (curator/insights mine it),
            # so duplicate reads come back verbatim and re-introduce exactly the
            # contradictions M238 removed at dispatch time. Prune the view, not
            # the record.
            supersede_loaded_history(loaded, FENCED_RESULT_HEADER)
            if self._system_prompt:
                fresh = Message(role="system", content=self._system_prompt)
                if loaded and loaded[0].role == "system":
                    loaded[0] = fresh
                else:
                    loaded.insert(0, fresh)
            return loaded

        # Fresh path with persistence: create a session and persist system prompt.
        if self._store is not None and self._session_id is None:
            self._session_id = self._store.create_session()
            # M224: refresh the sticky-routing key now that the id exists, so the
            # very first provider call of a fresh session already pins a provider.
            set_current_session_id(self._session_id)

        history: list[Message] = []
        if self._system_prompt:
            self._append(history, Message(role="system", content=self._system_prompt))
        return history

    def _persist(self, message: Message) -> None:
        if self._store is not None and self._session_id is not None:
            self._store.append_turn(self._session_id, message)

    def _emit_event(self, event: Event) -> None:
        """Self-side companion to module-level `_emit` — uses our writer and
        the per-run listener (if any) installed by `run()`."""
        _emit(self._event_writer, event, self._event_listener)

    def _request_extra(self) -> dict[str, Any]:
        """The `[engine.request.<provider>]` passthrough in force for this call
        (M250), for the trace. Best-effort: a provider that doesn't speak the
        OpenAI wire format has no such section, and tracing must never break a
        run."""
        try:
            from veles.core.openai_wire import request_body_overrides

            name = getattr(self.provider, "name", "")
            return request_body_overrides(name) if name else {}
        except Exception:  # pragma: no cover - trace enrichment is never load-bearing
            return {}

    def _emit_trace(
        self,
        *,
        response: ProviderResponse,
        tools: list[dict[str, Any]] | None,
        ttft_ms: int,
        total_latency_ms: int,
    ) -> None:
        if self._trace_writer is None:
            return
        usage = response.usage
        record = TraceRecord(
            request_id=uuid.uuid4().hex[:12],
            session_id=self._session_id,
            ts=utc_iso(),
            provider=getattr(self.provider, "name", type(self.provider).__name__),
            model=self._model,
            system_prompt_hash=hash_text(self._system_prompt),
            tool_bundle_hash=hash_tools(tools),
            input_tokens_new=max(0, usage.prompt_tokens - usage.cache_read_tokens),
            cache_read_tokens=usage.cache_read_tokens,
            cache_creation_tokens=usage.cache_creation_tokens,
            output_tokens=usage.completion_tokens,
            ttft_ms=ttft_ms,
            total_latency_ms=total_latency_ms,
            # M250: the upstream's own billed cost when it reports one
            # (OpenRouter's `usage.cost`); still 0.0 for backends that don't.
            est_cost_usd=usage.cost_usd,
            tool_calls_count=len(response.tool_calls),
            permission_decisions=[],
            final_status="ok",
            reasoning_tokens=usage.reasoning_tokens,
            upstream_provider=response.upstream_provider,
            request_extra=self._request_extra(),
        )
        try:
            self._trace_writer.write(record)
        except Exception as exc:
            # Tracing must never break a run. Log to stderr if verbose.
            self._log(f"   trace write failed: {exc}")

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(msg, file=sys.stderr, flush=True)


def run_oneshot(
    provider: Provider,
    model: str,
    system_prompt: str,
    text: str,
    *,
    max_tokens: int | None = None,
) -> RunResult:
    """One tool-less, single-round sub-agent call: summarise, classify, judge.

    Exceptions propagate — each caller decides what a failed side call means."""
    agent = Agent(
        provider=provider,
        registry=Registry(),
        model=model,
        max_iterations=1,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )
    return agent.run(text)
