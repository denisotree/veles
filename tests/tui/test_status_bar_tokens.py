"""M79: token counter + context window % in the status bar."""

from __future__ import annotations

from veles.tui.state import AppState
from veles.tui.widgets.status_bar import StatusBar


def _state(**overrides) -> AppState:
    base = dict(session_id=None, provider_name="openrouter", model="anthropic/claude-sonnet-4.6")
    base.update(overrides)
    return AppState(**base)  # type: ignore[arg-type]


def test_no_token_segment_until_first_turn() -> None:
    bar = StatusBar()
    bar.render_state(_state())
    assert "tok " not in bar.last_text
    assert "ctx " not in bar.last_text


def test_token_in_out_renders_after_turn() -> None:
    bar = StatusBar()
    bar.render_state(_state(tokens_in=1234, tokens_out=567))
    assert "tok " in bar.last_text
    assert "1k" in bar.last_text


def test_ctx_percent_against_claude_window() -> None:
    bar = StatusBar()
    bar.render_state(_state(last_turn_total_tokens=20_000))
    # 20k / 200k = 10%
    assert "ctx " in bar.last_text
    assert "10%" in bar.last_text


def test_ctx_warning_color_at_70_percent() -> None:
    bar = StatusBar()
    bar.render_state(_state(last_turn_total_tokens=140_000))
    # 140k/200k = 70% → yellow band (>=60)
    assert "[yellow]" in bar.last_text or "yellow" in bar.last_text


def test_ctx_critical_color_at_90_percent() -> None:
    bar = StatusBar()
    bar.render_state(_state(last_turn_total_tokens=180_000))
    # 180k/200k = 90% → red band (>=80)
    assert "red" in bar.last_text


def test_provider_prefix_stripped_when_mismatched() -> None:
    """M107: if the user picked OpenAI in the wizard but the stored
    model id still carries an `openrouter/` prefix, the status bar must
    render `openai/<model>` — not `openai/openrouter/<model>`."""
    bar = StatusBar()
    bar.render_state(_state(provider_name="openai", model="openrouter/gpt-5.4-mini"))
    assert "openai/gpt-5.4-mini" in bar.last_text
    assert "openrouter" not in bar.last_text


def test_provider_prefix_stripped_for_anthropic_qualified_model() -> None:
    bar = StatusBar()
    bar.render_state(
        _state(provider_name="openrouter", model="openrouter/anthropic/claude-sonnet-4.6")
    )
    # Only ONE level peeled — the inner `anthropic/` is an OpenRouter
    # route name the user cares about.
    assert "openrouter/anthropic/claude-sonnet-4.6" in bar.last_text


def test_bare_model_id_unchanged() -> None:
    bar = StatusBar()
    bar.render_state(_state(provider_name="openai", model="gpt-4o"))
    assert "openai/gpt-4o" in bar.last_text


def test_known_model_picks_right_context_window() -> None:
    """Claude defaults to 200k, GPT-4o to 128k. Make sure the % flips
    when the model id changes for the same token count."""
    bar1 = StatusBar()
    bar1.render_state(
        _state(model="anthropic/claude-sonnet-4.6", last_turn_total_tokens=64_000)
    )
    pct_claude = "32%"  # 64k/200k
    assert pct_claude in bar1.last_text

    bar2 = StatusBar()
    bar2.render_state(_state(model="openai/gpt-4o", last_turn_total_tokens=64_000))
    pct_gpt = "50%"  # 64k/128k
    assert pct_gpt in bar2.last_text
