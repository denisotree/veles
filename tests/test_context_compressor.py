"""M29 — sliding-window context compressor.

Tests the deterministic surfaces (`estimate_tokens`,
`needs_compression`, `find_safe_boundaries`,
`render_middle_for_summary`, `apply_compression`) plus an Agent
integration with a stub compressor that confirms the callable is
invoked before each provider request and the truncated history
reaches the provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from veles.core.agent import Agent
from veles.core.context_compressor import (
    CompressionConfig,
    apply_compression,
    estimate_tokens,
    find_safe_boundaries,
    needs_compression,
    render_middle_for_summary,
)
from veles.core.provider import (
    Message,
    ProviderResponse,
    TokenUsage,
    ToolCall,
)
from veles.core.tools.registry import Registry


def _msg(role: str, content: str | None = None, **kw) -> Message:
    return Message(role=role, content=content, **kw)


def _conv(*roles: str) -> list[Message]:
    """Build a synthetic alternating history with deterministic content."""
    return [_msg(r, f"{r}-{i}-" + ("x" * 40)) for i, r in enumerate(roles)]


# ---- estimate_tokens ----


def test_estimate_tokens_counts_content() -> None:
    h = [_msg("user", "x" * 400)]
    assert estimate_tokens(h) == 100


def test_estimate_tokens_counts_tool_calls() -> None:
    tc = ToolCall(id="c1", name="echo", arguments={"text": "hi" * 50})
    h = [_msg("assistant", "", tool_calls=[tc])]
    # Body 0 + json args ~110 chars + name 4 ≈ 114 chars / 4 ≈ 28 tokens.
    assert estimate_tokens(h) > 0


# ---- needs_compression ----


def test_needs_compression_false_when_history_too_short() -> None:
    cfg = CompressionConfig(head_keep=2, tail_keep=2, threshold_tokens=10)
    h = _conv("system", "user", "assistant", "user", "assistant")  # 5 msgs
    # head+tail+1 == 5 → equal, returns False
    assert needs_compression(h, cfg) is False


def test_needs_compression_false_when_under_threshold() -> None:
    cfg = CompressionConfig(head_keep=2, tail_keep=2, threshold_tokens=10_000_000)
    h = _conv("system", "user", "assistant", "user", "assistant", "user", "assistant")
    assert needs_compression(h, cfg) is False


def test_needs_compression_true_when_over_threshold_and_long_enough() -> None:
    cfg = CompressionConfig(head_keep=1, tail_keep=1, threshold_tokens=10)
    h = _conv("system", "user", "assistant", "user", "assistant")
    assert needs_compression(h, cfg) is True


# ---- find_safe_boundaries ----


def test_find_safe_boundaries_normal_alternation() -> None:
    cfg = CompressionConfig(head_keep=2, tail_keep=2)
    h = _conv("system", "user", "assistant", "user", "assistant", "user", "assistant")
    bounds = find_safe_boundaries(h, cfg)
    assert bounds is not None
    head_end, tail_start = bounds
    # head_keep=2 → indices 0..1 → "system","user". Last is "user" → trim to 1.
    assert head_end == 1
    # tail_keep=2 → tail_start_lo = max(1, 7-2) = 5. h[5]="user" → start at 5.
    assert tail_start == 5


def test_find_safe_boundaries_returns_none_when_no_user_in_tail() -> None:
    cfg = CompressionConfig(head_keep=1, tail_keep=2)
    # Only one user message, at index 1 (inside head).
    h = _conv("system", "user", "assistant", "assistant")
    assert find_safe_boundaries(h, cfg) is None


def test_find_safe_boundaries_returns_none_when_head_collapses_to_zero() -> None:
    cfg = CompressionConfig(head_keep=1, tail_keep=2)
    # head_keep=1 → "user". Trim because not in {assistant,system} → head_end=0 → None.
    h = _conv("user", "assistant", "user", "assistant")
    assert find_safe_boundaries(h, cfg) is None


def test_find_safe_boundaries_skips_tool_messages_in_tail() -> None:
    cfg = CompressionConfig(head_keep=2, tail_keep=3)
    # tool right at tail_start_lo → must skip forward to user.
    h = [
        _msg("system", "s"),
        _msg("user", "u1"),
        _msg("assistant", "a1"),
        _msg("tool", "t1", tool_call_id="c1"),
        _msg("assistant", "a2"),
        _msg("user", "u2"),
        _msg("assistant", "a3"),
    ]
    bounds = find_safe_boundaries(h, cfg)
    assert bounds is not None
    head_end, tail_start = bounds
    assert head_end == 1  # trim away "user" at index 1 → end at index 1 (system)
    # tail_start_lo = max(1, 7-3) = 4. h[4]="assistant" → skip to user at 5.
    assert tail_start == 5


# ---- render_middle_for_summary ----


def test_render_middle_includes_role_and_content() -> None:
    middle = [_msg("user", "hello"), _msg("assistant", "hi there")]
    rendered = render_middle_for_summary(middle)
    assert "# user" in rendered
    assert "hello" in rendered
    assert "# assistant" in rendered
    assert "hi there" in rendered


def test_render_middle_serialises_tool_calls() -> None:
    tc = ToolCall(id="c1", name="echo", arguments={"text": "hi"})
    middle = [_msg("assistant", "", tool_calls=[tc])]
    rendered = render_middle_for_summary(middle)
    assert "echo(" in rendered
    assert "hi" in rendered


def test_render_middle_marks_tool_role_with_call_id() -> None:
    middle = [_msg("tool", "result", tool_call_id="c42")]
    rendered = render_middle_for_summary(middle)
    assert "# tool[c42]" in rendered


# ---- apply_compression ----


def test_apply_compression_augments_first_system_message() -> None:
    cfg = CompressionConfig(head_keep=2, tail_keep=2)
    h = _conv("system", "user", "assistant", "user", "assistant", "user", "assistant")
    out = apply_compression(h, cfg, summary_path="wiki/sessions/abc.md", n_turns_dropped=4)
    assert out[0].role == "system"
    assert "[CONTEXT-COMPRESSION]" in (out[0].content or "")
    assert "wiki/sessions/abc.md" in (out[0].content or "")


def test_apply_compression_drops_middle_and_keeps_tail_intact() -> None:
    cfg = CompressionConfig(head_keep=2, tail_keep=2)
    h = _conv("system", "user", "assistant", "user", "assistant", "user", "assistant")
    out = apply_compression(h, cfg, summary_path="wiki/sessions/x.md", n_turns_dropped=4)
    # head_end=1, tail_start=5 → out = [aug_system] + h[5:] = 1 + 2 = 3 msgs.
    assert len(out) == 3
    assert out[1].role == "user"
    assert out[2].role == "assistant"


def test_apply_compression_returns_history_unchanged_when_no_safe_split() -> None:
    cfg = CompressionConfig(head_keep=1, tail_keep=2)
    h = _conv("user", "assistant", "user", "assistant")
    out = apply_compression(h, cfg, summary_path="x.md", n_turns_dropped=2)
    assert out == h


def test_apply_compression_prepends_system_when_head_lacks_one() -> None:
    cfg = CompressionConfig(head_keep=2, tail_keep=2)
    h = [
        _msg("user", "u1"),
        _msg("assistant", "a1"),  # head_end falls here (assistant is safe)
        _msg("user", "u2"),
        _msg("assistant", "a2"),
        _msg("user", "u3"),
        _msg("assistant", "a3"),
    ]
    out = apply_compression(h, cfg, summary_path="z.md", n_turns_dropped=2)
    # head_keep=2 → "user","assistant" → ends on assistant (safe). No system in head → prepend.
    assert out[0].role == "system"
    assert "z.md" in (out[0].content or "")


# ---- Agent integration with a stub compressor ----


@dataclass
class _CapturingProvider:
    name: str = "stub"
    supports_tools: bool = True
    responses: list[ProviderResponse] = field(default_factory=list)
    seen_histories: list[list[Message]] = field(default_factory=list)
    _idx: int = 0

    def create_message(self, messages, tools=None, *, model: str, max_tokens: int = 4096):
        # Snapshot the list at call time; the agent doesn't mutate Messages after
        # passing them, so referencing the same instances is safe.
        self.seen_histories.append(list(messages))
        resp = self.responses[self._idx]
        self._idx += 1
        return resp


def _ok(text: str = "done") -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        finish_reason="stop",
    )


def test_agent_calls_compressor_before_each_provider_request() -> None:
    """The compressor sees the current history and may shorten it."""
    invoked = []

    def fake_compressor(history, session_id):
        invoked.append((session_id, len(history)))
        # Return a slimmer copy: drop everything but system + last 2.
        if len(history) > 3:
            return [history[0], history[-2], history[-1]]
        return history

    provider = _CapturingProvider(responses=[_ok("hi")])
    agent = Agent(
        provider=provider,
        registry=Registry(),
        model="m",
        system_prompt="sys",
        compressor=fake_compressor,
    )
    result = agent.run("hello")

    assert result.stopped_reason == "completed"
    assert len(invoked) == 1
    seen = provider.seen_histories[0]
    # System + user — fake_compressor returns input unchanged for short history.
    assert [m.role for m in seen] == ["system", "user"]


def test_agent_compressor_truncation_visible_to_next_provider_call() -> None:
    """When compressor returns a shorter list, that's what the provider sees."""
    fake = [
        _msg("system", "sys"),
        _msg("user", "u1"),
        _msg("assistant", "a1"),
        _msg("user", "u2"),
        _msg("assistant", "a2"),
        _msg("user", "u3"),
        _msg("assistant", "a3"),
    ]

    def truncate(history, session_id):
        # Always return a fixed shorter conversation, ignoring input.
        return list(fake)

    provider = _CapturingProvider(responses=[_ok("answer")])
    agent = Agent(
        provider=provider,
        registry=Registry(),
        model="m",
        compressor=truncate,
    )
    agent.run("real prompt")

    seen = provider.seen_histories[0]
    assert [m.role for m in seen] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
        "assistant",
    ]


# ---- observability: every compressor decision is logged ----


def _project(tmp_path):
    """Lightweight Project fixture for tests that build the real
    compressor closure (need wiki + state_dir paths)."""
    from veles.core.project import init_project

    return init_project(tmp_path, name="compressor-test")


def _make_compressor(project, cfg, *, sub_provider=None):
    from veles.core.context_compressor import make_default_compressor

    return make_default_compressor(
        provider=sub_provider or _CapturingProvider(responses=[_ok("summary")]),
        model="m",
        cfg=cfg,
        project=project,
    )


def test_compressor_logs_skip_below_threshold(tmp_path, caplog) -> None:
    project = _project(tmp_path)
    cfg = CompressionConfig(threshold_tokens=1_000_000)
    compressor = _make_compressor(project, cfg)
    h = _conv("system", "user", "assistant")
    with caplog.at_level("INFO", logger="veles.core.context_compressor"):
        compressor(h, "sess-low")
    assert any(
        "compressor skip" in r.message
        and "below-threshold" in r.message
        and "sess-low" in r.message
        for r in caplog.records
    )


def test_compressor_logs_skip_when_no_safe_boundaries(tmp_path, caplog) -> None:
    """History that's over threshold but lacks a user-message in the
    last `tail_keep` positions can't be split — must log explicitly."""
    project = _project(tmp_path)
    cfg = CompressionConfig(threshold_tokens=10, head_keep=1, tail_keep=4)
    compressor = _make_compressor(project, cfg)
    # Long enough to trigger needs_compression but tail has no user role.
    h = [_msg("system", "s" + "x" * 200)] + [_msg("assistant", "a" + "x" * 200) for _ in range(10)]
    with caplog.at_level("INFO", logger="veles.core.context_compressor"):
        compressor(h, "sess-no-bounds")
    assert any(
        "compressor skip" in r.message and "no-safe-boundaries" in r.message for r in caplog.records
    )


def test_compressor_truncates_middle_when_too_large(tmp_path, caplog) -> None:
    """Middle that exceeds max_summariser_input_tokens is trimmed from
    the front before being handed to the sub-agent."""
    project = _project(tmp_path)
    cfg = CompressionConfig(
        threshold_tokens=10,
        head_keep=1,
        tail_keep=1,
        max_summariser_input_tokens=20,
    )

    captured_input: list[int] = []

    @dataclass
    class _SizeCapturingProvider:
        name: str = "stub"
        supports_tools: bool = True

        def create_message(self, messages, tools=None, *, model, max_tokens=4096):
            # First message is sub-agent system; second is the rendered
            # middle as user content. Record its length to assert
            # truncation happened.
            for m in messages:
                if m.role == "user":
                    captured_input.append(len(m.content or ""))
                    break
            return _ok("summary")

    compressor = _make_compressor(project, cfg, sub_provider=_SizeCapturingProvider())
    # 6 middle messages each ~200 chars → ~300 tokens of rendered, well
    # above the 20-token cap; we expect trimming to leave a much
    # smaller payload.
    h = (
        [_msg("system", "sys")]
        + [_msg("user" if i % 2 == 0 else "assistant", ("c" + str(i)) * 50) for i in range(6)]
        + [_msg("user", "u-final")]
    )
    with caplog.at_level("INFO", logger="veles.core.context_compressor"):
        compressor(h, "sess-trunc")
    assert any("summariser-input-truncated" in r.message for r in caplog.records), (
        "expected truncation log line"
    )


def test_compressor_swallows_summariser_failure(tmp_path, caplog) -> None:
    """A sub-agent failure must not propagate — compressor still
    applies a placeholder summary so the main run can proceed."""
    project = _project(tmp_path)
    cfg = CompressionConfig(threshold_tokens=10, head_keep=1, tail_keep=1)

    @dataclass
    class _RaisingProvider:
        name: str = "stub"
        supports_tools: bool = True

        def create_message(self, messages, tools=None, *, model, max_tokens=4096):
            raise RuntimeError("simulated summariser failure")

    compressor = _make_compressor(project, cfg, sub_provider=_RaisingProvider())
    h = (
        [_msg("system", "sys")]
        + [_msg("user" if i % 2 == 0 else "assistant", f"turn-{i}") for i in range(6)]
        + [_msg("user", "u-final")]
    )
    with caplog.at_level("WARNING", logger="veles.core.context_compressor"):
        result = compressor(h, "sess-fail")
    # Compressor returned a shorter history despite the failure.
    assert len(result) < len(h)
    assert any(
        "summariser-failed" in r.message and "RuntimeError" in r.message for r in caplog.records
    )


def test_compressor_logs_applied_summary(tmp_path, caplog) -> None:
    project = _project(tmp_path)
    cfg = CompressionConfig(threshold_tokens=10, head_keep=1, tail_keep=1)
    compressor = _make_compressor(project, cfg)
    # Each turn ~80 chars → ~20 tokens; 6 turns = 120 tokens, well over
    # the 10-token threshold, so needs_compression fires.
    h = (
        [_msg("system", "sys")]
        + [
            _msg(
                "user" if i % 2 == 0 else "assistant",
                f"turn-{i}-" + ("x" * 80),
            )
            for i in range(6)
        ]
        + [_msg("user", "u-final")]
    )
    with caplog.at_level("INFO", logger="veles.core.context_compressor"):
        result = compressor(h, "sess-applied")
    assert any(
        "compressor applied" in r.message and "sess-applied" in r.message for r in caplog.records
    )
    assert len(result) < len(h)


# ---- M217: summary cache across --resume ----


def _compressible_history() -> list[Message]:
    return (
        [_msg("system", "sys")]
        + [_msg("user" if i % 2 == 0 else "assistant", f"turn-{i}-" + ("x" * 80)) for i in range(6)]
        + [_msg("user", "u-final")]
    )


def test_summary_reused_across_resume(tmp_path) -> None:
    """A --resume reloads full history and re-runs the compressor over the
    same middle. The expensive summariser call must be served from cache the
    second time instead of billing another LLM round-trip."""
    project = _project(tmp_path)
    cfg = CompressionConfig(threshold_tokens=10, head_keep=1, tail_keep=1)
    h = _compressible_history()

    p1 = _CapturingProvider(responses=[_ok("SUMMARY-A")])
    compress1 = _make_compressor(project, cfg, sub_provider=p1)
    out1 = compress1(list(h), "sess-resume")
    assert len(p1.seen_histories) == 1  # summariser ran once (cold cache)
    assert len(out1) < len(h)

    # --resume: fresh compressor + fresh provider, identical history + model.
    p2 = _CapturingProvider(responses=[_ok("SUMMARY-B")])
    compress2 = _make_compressor(project, cfg, sub_provider=p2)
    out2 = compress2(list(h), "sess-resume")
    assert p2.seen_histories == []  # cache hit → summariser NOT re-run
    assert len(out2) < len(h)  # still compressed


def test_summary_cache_misses_on_different_model(tmp_path) -> None:
    """The cache is namespaced by model — a different summariser model must
    not replay a vector from another space."""
    from veles.core.context_compressor import make_default_compressor

    project = _project(tmp_path)
    cfg = CompressionConfig(threshold_tokens=10, head_keep=1, tail_keep=1)
    h = _compressible_history()

    compress1 = _make_compressor(
        project, cfg, sub_provider=_CapturingProvider(responses=[_ok("A")])
    )
    compress1(list(h), "sess-model")

    p2 = _CapturingProvider(responses=[_ok("B")])
    compress2 = make_default_compressor(provider=p2, model="other-model", cfg=cfg, project=project)
    compress2(list(h), "sess-model")
    assert len(p2.seen_histories) == 1  # different model → cache miss, summariser runs


# ---- emergency truncation ----


def test_emergency_truncate_drops_oldest_until_under_target() -> None:
    """Truncation drops oldest non-system turns until under target. The
    augmented system banner itself takes ~80 tokens, so the realistic
    target leaves room for it — production default is 180000, where
    that's noise."""
    from veles.core.context_compressor import emergency_truncate

    h = [_msg("system", "s")] + [_msg("user", "x" * 400) for _ in range(20)]
    before = estimate_tokens(h)
    new, dropped = emergency_truncate(h, target_tokens=600)
    assert dropped > 0
    after = estimate_tokens(new)
    # Hard ceiling is approximate (banner adds ~80 tokens), but the
    # result must be drastically smaller and roughly within target.
    assert after < before // 2
    assert after <= 700
    # System banner survived.
    assert new[0].role == "system"
    assert "[CONTEXT-EMERGENCY-TRUNCATED]" in (new[0].content or "")


def test_emergency_truncate_no_op_when_under_target() -> None:
    from veles.core.context_compressor import emergency_truncate

    h = [_msg("system", "s"), _msg("user", "small")]
    new, dropped = emergency_truncate(h, target_tokens=1_000_000)
    assert dropped == 0
    assert new is h


def test_agent_emergency_truncates_when_compressor_left_too_much(
    tmp_path,
) -> None:
    """If the compressor returns a still-too-large history, Agent runs
    emergency_truncate before sending to the provider."""

    def identity(history, session_id):
        return history  # compressor that does nothing

    big_history = [_msg("system", "sys")] + [
        _msg("user" if i % 2 == 0 else "assistant", "x" * 400) for i in range(20)
    ]

    # Pre-populate the store so Agent loads `big_history` as resumption.
    from veles.core.memory import SessionStore

    store = SessionStore(tmp_path / "memory.db")
    sid = store.create_session()
    for m in big_history:
        store.append_turn(sid, m)

    provider = _CapturingProvider(responses=[_ok("ok")])
    agent = Agent(
        provider=provider,
        registry=Registry(),
        model="m",
        compressor=identity,
        store=store,
        session_id=sid,
        hard_ceiling_tokens=500,
    )
    agent.run("next prompt")
    seen = provider.seen_histories[0]
    assert estimate_tokens(seen) <= 500
    # Emergency banner present.
    assert any(
        "[CONTEXT-EMERGENCY-TRUNCATED]" in (m.content or "") for m in seen if m.role == "system"
    )
