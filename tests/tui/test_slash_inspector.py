"""M115.1: dedicated `/tokens`, `/context`, `/status` slash commands.

VISION §7.2 requires inspector commands beyond the StatusBar chip —
they return detailed per-session / per-turn / per-model breakdowns that
don't fit in a one-line chip. Pure-handler tests (no UI), in the
existing slash-command style.
"""

from __future__ import annotations

from veles.tui.slash import build_default_registry


def _reg():
    return build_default_registry()


# ---------------- /tokens ----------------


def test_tokens_no_usage_yet(slash_ctx):
    """Empty session: command still works, reports zeros explicitly."""
    res = _reg().dispatch("/tokens", slash_ctx)
    assert res is not None and not res.is_error
    assert "0" in res.text  # zeros are visible, not omitted


def test_tokens_with_usage_shows_in_out_total(slash_ctx):
    slash_ctx.state.tokens_in = 1234
    slash_ctx.state.tokens_out = 567
    slash_ctx.state.last_turn_total_tokens = 1801
    res = _reg().dispatch("/tokens", slash_ctx)
    assert res is not None and not res.is_error
    # Numbers visible (formatted or raw — both fine)
    text = res.text
    assert "1234" in text or "1.2k" in text or "1k" in text
    assert "567" in text
    assert "last turn" in text.lower() or "turn" in text.lower()


def test_tokens_includes_in_out_labels(slash_ctx):
    slash_ctx.state.tokens_in = 100
    slash_ctx.state.tokens_out = 50
    res = _reg().dispatch("/tokens", slash_ctx)
    assert res is not None
    text = res.text.lower()
    assert "in" in text and "out" in text


# ---------------- /context ----------------


def test_context_with_zero_tokens_still_responds(slash_ctx):
    """No turn done yet — command still returns sensible info, not error."""
    slash_ctx.state.model = "anthropic/claude-sonnet-4.6"
    res = _reg().dispatch("/context", slash_ctx)
    assert res is not None and not res.is_error
    assert "200" in res.text  # Claude limit visible somewhere


def test_context_shows_size_limit_and_percentage(slash_ctx):
    slash_ctx.state.model = "anthropic/claude-sonnet-4.6"
    slash_ctx.state.last_turn_total_tokens = 20_000
    res = _reg().dispatch("/context", slash_ctx)
    assert res is not None and not res.is_error
    text = res.text
    # 20k / 200k = 10%
    assert "10" in text  # percentage
    assert "200" in text  # limit (200k for Claude)


def test_context_model_specific_limit_for_gpt(slash_ctx):
    slash_ctx.state.model = "openai/gpt-4o"
    res = _reg().dispatch("/context", slash_ctx)
    assert res is not None
    # gpt-4o has 128k limit per _context_limit_for
    assert "128" in res.text


def test_context_model_specific_limit_for_gemini(slash_ctx):
    slash_ctx.state.model = "google/gemini-1.5-pro"
    res = _reg().dispatch("/context", slash_ctx)
    assert res is not None
    # gemini-1.5 has 1M limit
    text = res.text.lower()
    assert "1m" in text or "1000" in text or "1,000" in text


# ---------------- /status ----------------


def test_status_lists_core_fields(slash_ctx):
    """Status summary should include model, mode, session, provider."""
    slash_ctx.state.model = "anthropic/claude-sonnet-4.6"
    slash_ctx.state.provider_name = "openrouter"
    slash_ctx.state.mode = "writing"
    res = _reg().dispatch("/status", slash_ctx)
    assert res is not None and not res.is_error
    text = res.text.lower()
    assert "model" in text
    assert "mode" in text
    assert "session" in text
    assert "provider" in text
    assert "writing" in text  # active mode echoed
    assert "openrouter" in text  # provider echoed


def test_status_shows_busy_flag(slash_ctx):
    slash_ctx.state.busy = True
    res = _reg().dispatch("/status", slash_ctx)
    assert res is not None
    assert "busy" in res.text.lower()


def test_status_shows_queue_depth(slash_ctx):
    slash_ctx.state.queue.extend(["one", "two", "three"])
    res = _reg().dispatch("/status", slash_ctx)
    assert res is not None
    assert "3" in res.text  # queue depth visible


def test_status_with_session_id(slash_ctx):
    slash_ctx.state.session_id = "sess_abc123"
    res = _reg().dispatch("/status", slash_ctx)
    assert res is not None
    assert "sess_abc123" in res.text


# ---------------- registry exposure ----------------


def test_help_lists_inspector_commands(slash_ctx):
    """All three new commands must appear in /help."""
    res = _reg().dispatch("/help", slash_ctx)
    assert res is not None
    for cmd in ("/tokens", "/context", "/status"):
        assert cmd in res.text, cmd


def test_inspector_commands_registered():
    """Sanity: they're discoverable by completer."""
    names = _reg().names()
    assert "/tokens" in names
    assert "/context" in names
    assert "/status" in names
