"""M115.3 (was M109): native text selection — now always-on, no toggle.

VISION §7.2 requires "native выделение, копирование, вставка … без
переключения режимов". The previous M109 design had a Ctrl+Shift+S
toggle (mouse capture on/off); M115.3 removes the toggle and turns
mouse capture off permanently. Trade-off: clicks no longer focus
widgets — keyboard navigation is the canonical way through the TUI.
The `[select]` status chip is gone (no longer meaningful when there's
no off-state).

Selectable chat messages (SelectableStatic with `allow_select=True`)
remain — Textual's in-app selection API (Shift+arrow keyboard select,
copy-on-selection on supported terminals) is unaffected by mouse-
capture state.
"""

from __future__ import annotations

from veles.tui.state import AppState
from veles.tui.widgets.status_bar import StatusBar


def _state(**overrides) -> AppState:
    base = dict(session_id=None, provider_name="openrouter", model="gpt-4o")
    base.update(overrides)
    return AppState(**base)  # type: ignore[arg-type]


def test_status_bar_never_renders_select_chip() -> None:
    """The chip is gone — there's no off-state to differentiate from."""
    bar = StatusBar()
    bar.render_state(_state())
    assert "[select]" not in bar.last_text


def test_chat_log_user_static_is_selectable() -> None:
    """Every message Static mounted by ChatLog is a SelectableStatic
    (allow_select=True), so Textual's selection API can target it
    (Shift+arrow selection, in-app copy-on-selection, etc.)."""
    from veles.tui.widgets.chat_log import SelectableStatic

    widget = SelectableStatic("hello", classes="veles-user")
    assert widget.allow_select is True


# ---- mouse capture is off from boot, no toggle action ----


async def test_mouse_capture_disabled_on_mount(
    agent_factory_for, text_response
) -> None:
    """Native terminal drag-select works from boot without any user
    action. M115.5: mouse reporting is now disabled driver-level via
    `app.run(mouse=False)` in `veles.tui.run_tui`; under Pilot the
    driver flag isn't applied, so `mouse_capture` may read as default-
    truthy. The load-bearing contract is that the `[select]` chip is
    gone (no mode toggle exists) — see `test_run_tui_passes_mouse_false`
    for the runtime path."""
    from veles.tui.app import TuiApp

    app = TuiApp(
        state=AppState(session_id=None, provider_name="stub", model="m"),
        agent_factory=agent_factory_for(text_response("hi")),
    )
    async with app.run_test() as pilot:
        status = pilot.app.query_one(StatusBar)
        assert "[select]" not in status.last_text


def test_status_bar_is_selectable() -> None:
    """StatusBar opts into Textual selection so Shift+arrow / drag-select
    can target chips like the model name (the M115.5 bug-fix scope)."""
    assert StatusBar().allow_select is True


def test_inspector_header_is_selectable() -> None:
    """Inspector header carries the active tool/state summary — has to
    be selectable for ⌘C-copy parity with chat messages."""
    from veles.tui.widgets.inspector import Inspector, _SelectableStatic

    inspector = Inspector()
    # `compose()` is a generator yielding widgets; the first yield is the
    # header. Inspector keeps the instance on `_header` for refresh().
    header = next(inspector.compose())
    assert isinstance(header, _SelectableStatic)
    assert header.allow_select is True


async def test_inspector_body_rows_are_selectable(
    agent_factory_for, text_response
) -> None:
    """Once the inspector is expanded and a tool call lands, body rows
    are SelectableStatics so a user can drag-copy any single line."""
    from veles.core.events import ToolCall
    from veles.tui.app import TuiApp
    from veles.tui.widgets.inspector import Inspector, _SelectableStatic

    app = TuiApp(
        state=AppState(session_id=None, provider_name="stub", model="m"),
        agent_factory=agent_factory_for(text_response("hi")),
    )
    async with app.run_test() as pilot:
        inspector = pilot.app.query_one(Inspector)
        inspector.set_expanded(True)
        inspector.notify_event(
            ToolCall(
                ts="2026-05-26T00:00:00Z",
                session_id=None,
                tool_call_id="t1",
                name="grep",
                arguments={"pattern": "foo"},
            )
        )
        await pilot.pause()
        rows = list(inspector._body.children)
        assert rows, "expected at least one body row after notify_event"
        for row in rows:
            assert isinstance(row, _SelectableStatic)
            assert row.allow_select is True


def test_super_c_binding_routes_to_screen_copy_text() -> None:
    """⌘C forwarded as `super+c` (some iTerm2/WezTerm/kitty profiles)
    triggers OSC52 copy via Textual's built-in screen action."""
    from textual.binding import Binding

    from veles.tui.app import TuiApp

    matches = [
        b
        for b in TuiApp.BINDINGS
        if isinstance(b, Binding) and b.key == "super+c"
    ]
    assert matches, "super+c binding missing"
    assert matches[0].action == "screen.copy_text"


def test_ctrl_shift_c_binding_routes_to_screen_copy_text() -> None:
    """Ctrl+Shift+C is the Linux/Windows canonical for in-app copy."""
    from textual.binding import Binding

    from veles.tui.app import TuiApp

    matches = [
        b
        for b in TuiApp.BINDINGS
        if isinstance(b, Binding) and b.key == "ctrl+shift+c"
    ]
    assert matches, "ctrl+shift+c binding missing"
    assert matches[0].action == "screen.copy_text"


def test_ctrl_c_still_routes_to_copy_or_exit() -> None:
    """Regression guard for M77 (Ctrl+C single-copy + double-tap exit).
    The OSC52 fallback binds super+c / ctrl+shift+c; ctrl+c must stay
    with copy_or_exit."""
    from textual.binding import Binding

    from veles.tui.app import TuiApp

    matches = [
        b for b in TuiApp.BINDINGS if isinstance(b, Binding) and b.key == "ctrl+c"
    ]
    assert matches and matches[0].action == "copy_or_exit"


def test_run_tui_passes_mouse_false() -> None:
    """The runtime `app.run()` must be invoked with `mouse=False` — this
    is the load-bearing piece that gives native terminal drag-select +
    system ⌘C in macOS Terminal.app (where OSC52 doesn't work).
    Source-level guard: stubbing the full `run_tui` boot path (provider
    factory, session store, skill registries) is too brittle, so we
    assert the literal call shape in the module source instead."""
    import inspect

    import veles.tui as tui_pkg

    source = inspect.getsource(tui_pkg.run_tui)
    assert "mouse=False" in source, (
        "run_tui must invoke app.run(..., mouse=False) to disable mouse "
        "reporting at the driver level"
    )


async def test_no_toggle_action_exists(agent_factory_for, text_response) -> None:
    """The Ctrl+Shift+S binding and `action_toggle_select_mode` are
    gone — VISION §7.2 forbids a select mode-toggle."""
    from veles.tui.app import TuiApp

    app = TuiApp(
        state=AppState(session_id=None, provider_name="stub", model="m"),
        agent_factory=agent_factory_for(text_response("hi")),
    )
    async with app.run_test() as pilot:
        assert not hasattr(pilot.app, "action_toggle_select_mode")


def test_select_mode_field_removed_from_state() -> None:
    """AppState no longer carries `select_mode` — it was only meaningful
    while the toggle existed."""
    fields = AppState.__dataclass_fields__  # type: ignore[attr-defined]
    assert "select_mode" not in fields
