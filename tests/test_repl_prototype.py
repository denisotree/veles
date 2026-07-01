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


def test_meta_fragments_show_working_and_expand(tmp_path) -> None:
    app, store = _build_app(tmp_path)
    try:
        app.turn_start = 0.0  # falsy → elapsed renders as 0s
        app._push_meta("stream", "x" * 40)  # ≈10 tok
        app._push_meta("tool", "edit_file foo.py")
        app._push_meta("mode", "[auto -> writing]")
        text = "".join(f[1] for f in app._meta_fragments())
        assert "working" in text and "1 tool(s)" in text and "≈10 tok" in text
        assert "foo.py" not in text  # collapsed → no event list
        app.meta_expanded = True
        text2 = "".join(f[1] for f in app._meta_fragments())
        assert "foo.py" in text2 and "auto -> writing" in text2
    finally:
        store.close()


def test_picker_fragments_list_options_and_free_entry(tmp_path) -> None:
    app, store = _build_app(tmp_path)
    try:
        app.q_active = True
        app.q_question = "Apply the plan?"
        app.q_options = ["Apply fully", "Exclude sources/"]
        app.q_sel = 0
        text = "".join(f[1] for f in app._picker_fragments())
        assert "Apply the plan?" in text
        assert "Apply fully" in text and "Exclude sources/" in text
        assert app._FREE_LABEL in text  # free-text sentinel row present
        app.q_free = True
        assert "свой вариант" in "".join(f[1] for f in app._picker_fragments())
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
        app.q_sel = 2  # the free-text sentinel (index == len(options))
        app._picker_enter()
        assert app.q_free is True  # now capturing a typed answer
        assert app.q_active is True  # still waiting
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


def test_repl_command_registered() -> None:
    from veles.cli._parsers.agent_loop import register

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register(sub)
    assert "repl" in sub.choices
    ns = parser.parse_args(["repl", "--resume", "abc"])
    assert ns.command == "repl"
    assert ns.resume == "abc"
