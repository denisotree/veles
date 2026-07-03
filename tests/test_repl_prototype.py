"""`veles repl` — inline streaming REPL (Phase 1: slash + modes + status).

Covers the testable seams: message-routing callbacks, post-turn state
carry, slash dispatch through the *real* registry, and parser wiring. The
interactive prompt_toolkit loop and the live mode FSM are exercised by a
manual smoke run, not unit-driven here.
"""

from __future__ import annotations

import argparse
import typing

import pytest

from veles.cli.commands.repl import (
    _handle_slash,
    _make_turn_callbacks,
    _render_answer,
    _update_state_after_turn,
)
from veles.core.agent import RunResult, UsageSnapshot
from veles.tui.slash import build_default_registry
from veles.tui.state import AppState


def _state() -> AppState:
    return AppState(session_id=None, provider_name="openrouter", model="m")


def _console():
    from rich.console import Console

    return Console()


def _project_and_store(tmp_path):
    from veles.core.memory import SessionStore
    from veles.core.project import init_project

    project = init_project(tmp_path, name="repltest")
    return project, SessionStore(project.memory_db_path)


def test_turn_callbacks_stream_and_capture_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from veles.cli.commands.repl import _resolve_theme
    from veles.tui.messages import ChatDelta, SystemLine, TurnDone

    errors: list[str] = []
    theme = _resolve_theme(_state())
    post, on_text, _on_event, holder, flush = _make_turn_callbacks(_console(), theme, errors)
    post(SystemLine(text="[auto -> writing]"))  # dim mode line
    on_text("hello ")  # buffered (no block boundary yet)
    post(ChatDelta(text="world"))
    rr = RunResult(text="hello world", iterations=1, stopped_reason="completed", session_id="s1")
    post(TurnDone(result=rr))
    flush()  # renders the trailing block

    out = capsys.readouterr().out
    assert "[auto -> writing]" in out  # mode line printed
    assert "hello world" in out  # answer rendered
    assert holder["result"] is rr


def test_settled_status_shows_mode_tokens_cache_only() -> None:
    """The quiet bottom bar: mode + settled token/cache stats ONLY. Session id
    and provider/model are deliberately dropped (banner + /status carry those),
    per the user's "bottom bar = mode + tokens + cache" split."""
    from veles.cli.commands.repl import _settled_status

    state = _state()
    state.session_id = "sess1234"
    state.tokens_in = 1500
    state.tokens_out = 800
    state.last_prompt_tokens = 60000
    state.last_turn_cache_read = 42000
    line = _settled_status(state)
    assert "[auto]" in line  # mode chip
    assert "tok 1k/800" in line  # settled token totals
    assert "ctx 60k/" in line and "%" in line  # context meter
    assert "cache 42k" in line  # cache-read chip
    # Quiet bar — no session id, no provider/model churn.
    assert "sess1234" not in line
    assert "openrouter" not in line


def test_behaviour_block_forbids_deferred_work() -> None:
    """The REPL persistence block must kill the "announce a plan, promise to
    report back, then stop with no tool calls" failure mode — the turn ends the
    instant the model returns no tool calls, so there is no "later". Keep the
    ask_user carve-out intact (pausing to ask is still allowed)."""
    from veles.cli.commands.repl import _REPL_BEHAVIOUR_BLOCK

    low = _REPL_BEHAVIOUR_BLOCK.lower()
    assert "there is no 'later'" in low  # names the failure mode
    assert "tool calls" in low and "in this same reply" in low  # act now, here
    assert "ask_user" in _REPL_BEHAVIOUR_BLOCK  # carve-out preserved


def test_turn_callbacks_route_meta_to_sink() -> None:
    """With an on_meta sink, stream chunks / mode switches / tool calls flow to
    the live HUD instead of printing inline."""
    from veles.cli.commands.repl import _make_turn_callbacks, _resolve_theme
    from veles.tui.messages import SystemLine

    meta: list[tuple[str, str]] = []
    theme = _resolve_theme(_state())
    _post, on_text, on_event, _holder, _flush = _make_turn_callbacks(
        _console(), theme, [], on_meta=lambda k, t: meta.append((k, t))
    )
    on_text("hello")  # → ("stream", "hello")
    _post(SystemLine(text="[auto -> writing]"))  # → ("mode", ...)

    class _Evt:
        type = "tool_call"
        name = "edit_file"
        arguments: typing.ClassVar = {"path": "foo.py", "old_string": "a", "new_string": "b"}

    on_event(_Evt())  # → ("tool", "edit_file foo.py")
    kinds = {k for k, _ in meta}
    assert {"stream", "mode", "tool"} <= kinds
    assert ("mode", "[auto -> writing]") in meta
    assert any(k == "tool" and "edit_file" in t and "foo.py" in t for k, t in meta)


def _build_app(tmp_path):
    from veles.cli.commands.repl import _console, _ReplApp, _resolve_theme

    project, store = _project_and_store(tmp_path)
    state = _state()
    app = _ReplApp(
        argparse.Namespace(),
        project,
        state,
        lambda *_a, **_k: None,
        store,
        build_default_registry(project=project),
        _console(),
        _resolve_theme(state),
        [],
    )
    return app, store


def test_repl_ui_strings_localized_not_hardcoded_russian(tmp_path) -> None:
    """Regression: the REPL used to hardcode Russian UI strings, so an English
    user saw e.g. '(Ctrl+O раскрыть)'. All picker/HUD strings must route through
    i18n and render English by default — no Cyrillic leaks."""
    import re

    from veles.core.i18n import set_active_locale

    set_active_locale("en")
    cyrillic = re.compile("[Ѐ-ӿ]")  # Cyrillic block
    try:
        app, store = _build_app(tmp_path)
        try:
            app.busy = True
            hud = "".join(f[1] for f in app._meta_fragments())
            assert "(Ctrl+O expand)" in hud and not cyrillic.search(hud)

            app.q_active = True
            app.q_question = "Pick one"
            app.q_options = ["A", "B"]
            app.q_allow_free = True
            picker = "".join(f[1] for f in app._picker_fragments())
            assert not cyrillic.search(picker)  # no Russian in the English picker

            app.mp_loading = False
            app.mp_models = ["m1", "m2"]
            mp = "".join(f[1] for f in app._mp_fragments())
            assert not cyrillic.search(mp)
        finally:
            store.close()
    finally:
        set_active_locale("en")


def test_meta_fragments_working_idle_and_expand_in_both(tmp_path) -> None:
    app, store = _build_app(tmp_path)
    try:
        app.turn_start = 0.0  # falsy → elapsed renders as 0s
        app._push_meta("stream", "x" * 40)  # ≈10 tok
        app._push_meta("tool", "edit_file foo.py")
        app._push_meta("mode", "[auto -> writing]")

        # During generation: "working…" label, collapsed by default.
        app.busy = True
        text = "".join(f[1] for f in app._meta_fragments())
        assert "working" in text and "1 tool(s)" in text and "≈10 tok" in text
        assert "foo.py" not in text  # collapsed → no event list
        app.meta_expanded = True
        text2 = "".join(f[1] for f in app._meta_fragments())
        assert "foo.py" in text2 and "auto -> writing" in text2

        # Idle (turn finished): "done" label, and the SAME toggle still expands —
        # the unified behaviour the block stays visible for.
        app.busy = False
        idle = "".join(f[1] for f in app._meta_fragments())
        assert "done" in idle and "foo.py" in idle  # still expanded while idle
        app.meta_expanded = False
        idle2 = "".join(f[1] for f in app._meta_fragments())
        assert "foo.py" not in idle2  # collapse works while idle too
    finally:
        store.close()


def test_meta_timer_frozen_when_idle(tmp_path) -> None:
    """Once a turn is done the elapsed seconds must be FROZEN, not recomputed
    from turn_start on every idle re-render (the bug: "done · … · 294s")."""
    app, store = _build_app(tmp_path)
    try:
        app._push_meta("stream", "x" * 20)
        app.turn_elapsed = 42.0
        app.turn_start = 100.0  # a live compute would yield a huge, growing number
        app.busy = False
        text = "".join(f[1] for f in app._meta_fragments())
        assert "done" in text and "42s" in text  # frozen duration, not now - turn_start
    finally:
        store.close()


def test_picker_fragments_list_options_and_free_entry(tmp_path) -> None:
    app, store = _build_app(tmp_path)
    try:
        app.q_active = True
        app.q_question = "Apply the plan?"
        app.q_options = ["Apply fully", "Exclude sources/"]
        app.q_allow_free = True  # ask_user offers a free-text row
        app.q_sel = 0
        text = "".join(f[1] for f in app._picker_fragments())
        assert "Apply the plan?" in text
        assert "Apply fully" in text and "Exclude sources/" in text
        assert "✎" in text  # free-text sentinel row present (locale-independent marker)
        app.q_free = True
        assert "Enter" in "".join(f[1] for f in app._picker_fragments())  # free-input hint
    finally:
        store.close()


def test_permission_prompt_trust_maps_decision(tmp_path, monkeypatch) -> None:
    """The trust-ladder permission prompt is answered inside the app picker (no
    nested Application), and the chosen row maps to the right PromptDecision."""
    import threading
    import time as _t

    from veles.cli.commands import repl as repl_mod
    from veles.core.permission.prompt import PromptRequest

    app, store = _build_app(tmp_path)
    try:
        monkeypatch.setattr(repl_mod.sys.stdin, "isatty", lambda: True)
        req = PromptRequest(
            tool_name="write_file", arguments={"path": "x"}, reason="trust", kind="trust"
        )
        result: dict = {}

        def _run():
            result["ans"] = app._permission_prompt(req)

        th = threading.Thread(target=_run)
        th.start()
        for _ in range(400):  # wait until the picker publishes (executor thread)
            if app.q_active:
                break
            _t.sleep(0.005)
        assert app.q_active
        assert app.q_values == ["allow_once", "allow_project", "allow_global", "deny"]
        assert app.q_allow_free is False  # no free-text row for a permission prompt
        app.q_sel = 1  # "Always for this project"
        app._picker_enter()
        th.join(timeout=2)
        assert result["ans"].decision == "allow_project"
    finally:
        store.close()


def test_permission_prompt_denies_without_tty(tmp_path) -> None:
    from veles.core.permission.prompt import PromptRequest

    app, store = _build_app(tmp_path)
    try:
        # pytest stdin is non-interactive → deny, never block.
        req = PromptRequest(tool_name="run_shell", arguments={}, reason="", kind="trust")
        assert app._permission_prompt(req).decision == "deny"
    finally:
        store.close()


def test_confirm_critical_picker_yes(tmp_path, monkeypatch) -> None:
    """DESTRUCTIVE hard-confirm (delete_file) is answered in-app as a yes/no
    picker — the default confirmer reads input() and hangs the running app."""
    import threading
    import time as _t

    from veles.cli.commands import repl as repl_mod

    app, store = _build_app(tmp_path)
    try:
        monkeypatch.setattr(repl_mod.sys.stdin, "isatty", lambda: True)
        result: dict = {}

        def _run():
            result["ok"] = app._confirm_critical("dispatch delete_file", "destructive action")

        th = threading.Thread(target=_run)
        th.start()
        for _ in range(400):
            if app.q_active:
                break
            _t.sleep(0.005)
        assert app.q_active
        assert app.q_values == ["yes", "no"]
        assert app.q_sel == 1  # highlight defaults to Cancel (safe)
        app.q_sel = 0  # choose "Да, выполнить"
        app._picker_enter()
        th.join(timeout=2)
        assert result["ok"] is True
    finally:
        store.close()


def test_confirm_critical_cancel_denies(tmp_path, monkeypatch) -> None:
    import threading
    import time as _t

    from veles.cli.commands import repl as repl_mod

    app, store = _build_app(tmp_path)
    try:
        monkeypatch.setattr(repl_mod.sys.stdin, "isatty", lambda: True)
        result: dict = {}

        def _run():
            result["ok"] = app._confirm_critical("dispatch delete_file", "")

        th = threading.Thread(target=_run)
        th.start()
        for _ in range(400):
            if app.q_active:
                break
            _t.sleep(0.005)
        app._answer(None)  # Esc / cancel
        th.join(timeout=2)
        assert result["ok"] is False
    finally:
        store.close()


def test_confirm_critical_no_tty_refuses(tmp_path) -> None:
    app, store = _build_app(tmp_path)
    try:
        # pytest stdin is non-interactive → refuse without blocking.
        assert app._confirm_critical("dispatch delete_file", "x") is False
    finally:
        store.close()


def test_picker_fragments_permission_has_no_free_row(tmp_path) -> None:
    app, store = _build_app(tmp_path)
    try:
        app.q_active = True
        app.q_question = "Allow write_file?"
        app.q_options = ["Once (this call only)", "Refuse"]
        app.q_allow_free = False
        text = "".join(f[1] for f in app._picker_fragments())
        assert "Once (this call only)" in text and "Refuse" in text
        assert "✎" not in text  # permission prompt → no free-text row
    finally:
        store.close()


def test_ask_returns_none_without_tty(tmp_path, monkeypatch) -> None:
    from veles.cli.commands import repl as repl_mod

    app, store = _build_app(tmp_path)
    try:
        monkeypatch.setattr(repl_mod.sys.stdin, "isatty", lambda: False)
        assert app._ask("pick?", ["a", "b"]) is None  # headless → never blocks
    finally:
        store.close()


def test_picker_enter_selects_option_and_wakes_waiter(tmp_path) -> None:
    import threading

    app, store = _build_app(tmp_path)
    try:
        app.q_active = True
        app.q_question = "q?"
        app.q_options = ["a", "b"]
        app.q_sel = 1
        app.q_event = threading.Event()
        app._picker_enter()  # picks "b"
        assert app.q_answer == "b"
        assert app.q_active is False
        assert app.q_event is None  # cleared after answering
    finally:
        store.close()


def test_picker_enter_on_sentinel_switches_to_free_text(tmp_path) -> None:
    app, store = _build_app(tmp_path)
    try:
        app.q_active = True
        app.q_options = ["a", "b"]
        app.q_allow_free = True
        app.q_sel = 2  # the free-text sentinel (index == len(options))
        app._picker_enter()
        assert app.q_free is True  # now capturing a typed answer
        assert app.q_active is True  # still waiting
    finally:
        store.close()


def test_on_enter_records_input_history(tmp_path) -> None:
    """Submitting a command must append it to the input history so Up recalls
    the just-typed command — not a stale entry from an earlier run."""
    app, store = _build_app(tmp_path)
    try:
        app._spawn = lambda coro: coro.close()  # no event loop needed here
        app.input.text = "реализуй планы один за другим"
        app._on_enter()
        assert app.input.text == ""  # box cleared after submit
        assert app._hist[-1] == "реализуй планы один за другим"

        app.input.text = "второй запрос"
        app._on_enter()
        assert app._hist[-1] == "второй запрос"  # newest is last → first Up recalls it
        # Persisted for cross-run recall (a fresh store reads the same file).
        from prompt_toolkit.history import FileHistory

        reread = list(
            FileHistory(str(app.project.state_dir / "repl_history")).load_history_strings()
        )
        assert "второй запрос" in reread
    finally:
        store.close()


def test_history_up_down_recall_newest_first(tmp_path) -> None:
    app, store = _build_app(tmp_path)
    try:
        app._hist = ["alpha one", "bravo two"]
        app._hist_pos = None
        app.input.text = "draft"  # in-progress line
        app._history_up()
        assert app.input.text == "bravo two"  # newest first
        app._history_up()
        assert app.input.text == "alpha one"
        app._history_up()
        assert app.input.text == "alpha one"  # clamps at the oldest
        app._history_down()
        assert app.input.text == "bravo two"
        app._history_down()
        assert app.input.text == "draft"  # past the newest → restore the draft
    finally:
        store.close()


def test_on_enter_empty_input_is_ignored(tmp_path) -> None:
    app, store = _build_app(tmp_path)
    try:
        spawned: list = []

        def _fake_spawn(coro):
            spawned.append(1)
            coro.close()

        app._spawn = _fake_spawn
        app.input.text = "   "
        app._on_enter()
        assert spawned == []  # blank input dispatches nothing
        assert app.input.text == ""
    finally:
        store.close()


def test_input_box_sizes_to_content(tmp_path) -> None:
    """The input Window must size to its content (1 line when empty), not extend
    toward its max height — the box-bloat fix."""
    app, store = _build_app(tmp_path)
    try:
        # dont_extend_height is a Filter; truthy → the window sizes to content.
        assert app.input.window.dont_extend_height()
    finally:
        store.close()


def test_kitty_sequences_remap_and_binding(tmp_path) -> None:
    """With the kitty protocol enabled, Shift+Enter arrives as a distinct CSI-u
    sequence → the F24 carrier (bound to insert newline); Enter still submits.
    The control-key CSI-u forms map to the SAME Keys.* as legacy, so pt's line
    editing and our Ctrl+C/D/J/O keep working under the protocol."""
    from prompt_toolkit.input import ansi_escape_sequences as aes
    from prompt_toolkit.keys import Keys

    from veles.cli.commands.repl import _register_kitty_sequences

    _register_kitty_sequences()
    assert aes.ANSI_SEQUENCES["\x1b[27;2;13~"] == Keys.F24  # xterm modifyOtherKeys
    assert aes.ANSI_SEQUENCES["\x1b[13;2u"] == Keys.F24  # kitty Shift+Enter
    assert aes.ANSI_SEQUENCES["\x1b[13;3u"] == Keys.F24  # kitty Alt+Enter
    assert aes.ANSI_SEQUENCES["\x1b[27u"] == Keys.Escape  # Esc (disambiguated)
    assert aes.ANSI_SEQUENCES["\x1b[9;2u"] == Keys.BackTab  # Shift+Tab → mode cycle
    assert aes.ANSI_SEQUENCES["\x1b[99;5u"] == Keys.ControlC  # Ctrl+C (== legacy)
    assert aes.ANSI_SEQUENCES["\x1b[97;5u"] == Keys.ControlA  # Ctrl+A → line-home
    assert aes.ANSI_SEQUENCES["\x1b[106;5u"] == Keys.ControlJ  # Ctrl+J → newline

    app, store = _build_app(tmp_path)
    try:
        bound = {k for b in app.app.key_bindings.bindings for k in b.keys}
        assert Keys.F24 in bound  # Shift+Enter carrier
        assert Keys.ControlJ in bound
    finally:
        store.close()


def test_filter_models_substring_case_insensitive() -> None:
    from veles.cli.commands.repl import _filter_models

    models = ["openrouter/anthropic/claude", "openai/gpt-4o", "google/gemini"]
    assert _filter_models(models, "") == models  # empty → all
    assert _filter_models(models, "CLAUDE") == ["openrouter/anthropic/claude"]
    assert _filter_models(models, "gpt") == ["openai/gpt-4o"]
    assert _filter_models(models, "zzz") == []


def test_fetch_models_wraps_fetcher(tmp_path, monkeypatch) -> None:
    from veles.tui.screens import _model_fetcher

    class _ML:
        models: typing.ClassVar = ["a/x", "a/y"]
        source = "cache"

    monkeypatch.setattr(_model_fetcher, "fetch_models", lambda *_a, **_k: _ML())
    app, store = _build_app(tmp_path)
    try:
        assert app._fetch_models(False) == (["a/x", "a/y"], "cache")
    finally:
        store.close()


def test_fetch_models_swallows_errors(tmp_path, monkeypatch) -> None:
    from veles.tui.screens import _model_fetcher

    def _boom(*_a, **_k):
        raise RuntimeError("no key")

    monkeypatch.setattr(_model_fetcher, "fetch_models", _boom)
    app, store = _build_app(tmp_path)
    try:
        assert app._fetch_models(True) == ([], "error")  # never propagates
    finally:
        store.close()


def test_model_picker_filter_and_pick_persists(tmp_path, monkeypatch) -> None:
    from veles.core import tui_state

    persisted: dict = {}
    monkeypatch.setattr(
        tui_state, "persist_model_choice", lambda project, model: persisted.update(m=model)
    )
    app, store = _build_app(tmp_path)
    try:
        app.mp_active = True
        app.mp_models = ["openai/gpt-4o", "anthropic/claude", "anthropic/claude-haiku"]
        app.input.text = "haiku"  # filters to one; on_text_changed resets sel→0
        assert app._mp_filtered() == ["anthropic/claude-haiku"]
        app._mp_pick()
        assert app.state.model == "anthropic/claude-haiku"
        assert persisted["m"] == "anthropic/claude-haiku"  # persisted the choice
        assert app.mp_active is False  # picker closed
        assert app.input.text == ""  # filter cleared
    finally:
        store.close()


def test_model_picker_move_wraps_and_cancel_closes(tmp_path) -> None:
    app, store = _build_app(tmp_path)
    try:
        app.mp_active = True
        app.mp_models = ["a", "b", "c"]
        app.mp_sel = 0
        app._mp_move(-1)  # wrap to the last
        assert app.mp_sel == 2
        app._mp_move(1)  # wrap back to the first
        assert app.mp_sel == 0
        app._mp_cancel()
        assert app.mp_active is False and app.mp_models == []
    finally:
        store.close()


def test_print_model_list_fallback(monkeypatch, capsys: pytest.CaptureFixture[str]) -> None:
    from veles.cli.commands.repl import _print_model_list
    from veles.tui.screens import _model_fetcher

    class _ML:
        models: typing.ClassVar = ["openai/gpt-4o", "anthropic/claude"]
        source = "cache"

    monkeypatch.setattr(_model_fetcher, "fetch_models", lambda *_a, **_k: _ML())
    _print_model_list(_console(), "openrouter", "anthropic/claude", refresh=False)
    out = capsys.readouterr().out
    assert "openrouter" in out and "2 models" in out
    assert "anthropic/claude" in out and "← current" in out  # current marked


def test_cancel_generation_stops_and_restores_request(tmp_path) -> None:
    """Esc during generation cancels the turn, clears the queue, and drops the
    running request back into the input box for editing."""
    from veles.core.cancel import CancelToken

    app, store = _build_app(tmp_path)
    try:
        app.busy = True
        app._last_submitted = "реализуй план"
        app.cancel_token = CancelToken()
        app.queue.append("queued follow-up")
        app.input.text = "half-typed something"

        app._cancel_generation()

        assert app.cancel_token.cancelled  # running turn told to stop
        assert list(app.queue) == []  # a full stop — queue cleared
        assert app.input.text == "реализуй план"  # last request restored for editing
    finally:
        store.close()


def test_suspend_live_pauses_and_resumes_active_live() -> None:
    from veles.cli.commands import repl as repl_mod

    class _FakeLive:
        def __init__(self) -> None:
            self.events: list[str] = []

        def stop(self) -> None:
            self.events.append("stop")

        def start(self, refresh: bool = False) -> None:
            self.events.append("start")

    fake = _FakeLive()
    repl_mod._ACTIVE_LIVE = fake
    try:
        with repl_mod._suspend_live():
            assert fake.events == ["stop"]  # paused for the nested prompt
        assert fake.events == ["stop", "start"]  # resumed after
    finally:
        repl_mod._ACTIVE_LIVE = None


def test_ask_repl_skips_without_tty(monkeypatch) -> None:
    from veles.cli.commands import repl as repl_mod

    monkeypatch.setattr(repl_mod.sys.stdin, "isatty", lambda: False)
    theme = repl_mod._resolve_theme(_state())
    # No interactive TTY → None so the agent proceeds on its best assumption.
    assert repl_mod._ask_repl(_console(), theme, "pick?", ["a", "b"]) is None


def test_render_edit_diff(capsys: pytest.CaptureFixture[str]) -> None:
    from veles.cli.commands.repl import _render_edit_diff, _resolve_theme

    _render_edit_diff(
        _console(),
        _resolve_theme(_state()),
        "edit_file",
        {"path": "foo.py", "old_string": "return x + 1", "new_string": "return x * 2"},
    )
    out = capsys.readouterr().out
    assert "foo.py" in out
    assert "return x + 1" in out  # removed line present
    assert "return x * 2" in out  # added line present


def test_split_blocks() -> None:
    from veles.cli.commands.repl import _split_blocks

    # a completed paragraph flushes; the next (unterminated) one stays buffered
    blocks, rem = _split_blocks("para one\n\npara two")
    assert blocks == ["para one"]
    assert rem == "para two"

    # a fenced code block is atomic — blank lines inside it don't split it
    blocks, rem = _split_blocks("```py\ncode\n\nmore\n```\n\nafter")
    assert blocks == ["```py\ncode\n\nmore\n```"]
    assert rem == "after"

    # an unterminated fence stays entirely in the remainder
    blocks, rem = _split_blocks("text\n\n```py\nhalf")
    assert blocks == ["text"]
    assert rem == "```py\nhalf"

    # a lone newline is not a boundary — wait for a blank line
    blocks, rem = _split_blocks("line one\nline two")
    assert blocks == []
    assert rem == "line one\nline two"


def test_render_answer_formats_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    _render_answer(_console(), "# Heading\n\n- alpha\n- beta\n\n**bold** and `code`")
    out = capsys.readouterr().out
    # Markdown structure renders (text survives; rich may restyle/underline).
    assert "Heading" in out
    assert "alpha" in out and "beta" in out
    assert "bold" in out


def test_update_state_after_turn_carries_session_and_tokens() -> None:
    state = _state()
    rr = RunResult(
        text="answer",
        iterations=1,
        stopped_reason="completed",
        session_id="s9",
        usage=UsageSnapshot(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cache_read_tokens=7,
            last_prompt_tokens=12,
        ),
    )
    _update_state_after_turn(state, rr)
    assert state.session_id == "s9"
    assert state.last_assistant_text == "answer"
    assert state.tokens_in == 10
    assert state.tokens_out == 5
    assert state.last_turn_total_tokens == 15
    assert state.last_prompt_tokens == 12  # feeds the ctx chip
    assert state.last_turn_cache_read == 7  # feeds the cache chip


def test_update_state_after_turn_ignores_none() -> None:
    state = _state()
    _update_state_after_turn(state, None)
    assert state.session_id is None  # no crash, no change


def test_handle_slash_help_quit_unknown(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    project, store = _project_and_store(tmp_path)
    console = _console()
    errors: list[str] = []
    try:
        registry = build_default_registry(project=project)
        state = _state()

        quit_, submit = _handle_slash("/help", registry, state, project, store, console, errors)
        assert quit_ is False and submit is None
        assert capsys.readouterr().out  # repl help was printed

        quit_, submit = _handle_slash("/quit", registry, state, project, store, console, errors)
        assert quit_ is True

        quit_, submit = _handle_slash("/zzznope", registry, state, project, store, console, errors)
        assert quit_ is False
        assert "unknown" in capsys.readouterr().out.lower()
    finally:
        store.close()


def test_handle_slash_clear_resets_session(tmp_path) -> None:
    project, store = _project_and_store(tmp_path)
    console = _console()
    errors: list[str] = []
    try:
        registry = build_default_registry(project=project)
        state = _state()
        state.session_id = "s-old"
        state.last_assistant_text = "prev"

        _handle_slash("/clear", registry, state, project, store, console, errors)
        assert state.session_id is None
        assert state.last_assistant_text is None
    finally:
        store.close()


def test_replapp_constructs(tmp_path) -> None:
    """The inline prompt_toolkit Application builds its layout/widgets/style
    without error (run() itself needs a real TTY and is tested live)."""
    from veles.cli.commands.repl import _console, _ReplApp, _resolve_theme

    project, store = _project_and_store(tmp_path)
    try:
        state = _state()
        registry = build_default_registry(project=project)
        app = _ReplApp(
            argparse.Namespace(),
            project,
            state,
            lambda *_a, **_k: None,  # factory stub — not called at construction
            store,
            registry,
            _console(),
            _resolve_theme(state),
            [],
        )
        assert app.app is not None
        assert app._status_fragments()  # status bar renders
        assert app.busy is False
    finally:
        store.close()


def test_replapp_propagates_active_project_to_worker(tmp_path) -> None:
    """The captured parent context carries the active project into a worker
    thread — the fix for tools resolving ~/.veles/skills when run_in_executor
    dropped the context."""
    import contextvars
    from concurrent.futures import ThreadPoolExecutor

    from veles.cli.commands.repl import _console, _ReplApp, _resolve_theme
    from veles.core.context import current_project, reset_active_project, set_active_project

    project, store = _project_and_store(tmp_path)
    token = set_active_project(project)
    try:
        state = _state()
        app = _ReplApp(
            argparse.Namespace(),
            project,
            state,
            lambda *_a, **_k: None,
            store,
            build_default_registry(project=project),
            _console(),
            _resolve_theme(state),
            [],
        )
        turn_ctx = app._parent_ctx.run(contextvars.copy_context)
        seen: dict = {}

        def _work() -> None:
            seen["project"] = turn_ctx.run(current_project)

        with ThreadPoolExecutor(max_workers=1) as ex:
            ex.submit(_work).result()
        assert seen["project"] is project
    finally:
        reset_active_project(token)
        store.close()


def test_repl_is_the_default_no_subcommand() -> None:
    """The REPL has no subcommand — its flags live on the top-level parser and
    bare `veles` (command is None) dispatches to it. `repl`/`tui` are gone."""
    from veles.cli._parsers import build_parser

    parser = build_parser()
    ns = parser.parse_args(["--resume", "abc"])
    assert ns.command is None
    assert ns.resume == "abc"
    for gone in ("repl", "tui"):
        with pytest.raises(SystemExit):
            parser.parse_args([gone])
