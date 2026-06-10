"""`/mode` slash command — list, set, validate, persist.

The slash is the explicit / scriptable counterpart to Shift+Tab. Same
state mutation, same persistence path. Asserting both keeps the cycle
and the slash in sync.
"""

from __future__ import annotations

from veles.core.tui_state import load_tui_state
from veles.tui.slash.builtin import build_default_registry


def test_slash_mode_no_args_lists_modes_and_marks_current(slash_ctx) -> None:
    reg = build_default_registry()
    slash_ctx.state.mode = "writing"
    result = reg.dispatch("/mode", slash_ctx)
    assert result is not None
    assert not result.is_error
    body = result.text or ""
    # All four mode names appear; the active one is starred.
    for name in ("auto", "planning", "writing", "goal"):
        assert name in body
    assert " *writing" in body


def test_slash_mode_set_updates_state_and_persists(slash_ctx) -> None:
    reg = build_default_registry()
    result = reg.dispatch("/mode goal", slash_ctx)
    assert result is not None
    assert not result.is_error
    assert slash_ctx.state.mode == "goal"
    # Persistence file written to <project>/.veles/tui_state.json.
    assert load_tui_state(slash_ctx.project.state_dir).mode == "goal"


def test_slash_mode_unknown_value_returns_error(slash_ctx) -> None:
    reg = build_default_registry()
    result = reg.dispatch("/mode bogus", slash_ctx)
    assert result is not None
    assert result.is_error
    assert "bogus" in (result.text or "")
    # State must not change on error.
    assert slash_ctx.state.mode == "auto"


def test_slash_mode_extra_args_ignored(slash_ctx) -> None:
    """`/mode planning anything else` — only the first token matters."""
    reg = build_default_registry()
    result = reg.dispatch("/mode planning some other words", slash_ctx)
    assert result is not None
    assert not result.is_error
    assert slash_ctx.state.mode == "planning"
