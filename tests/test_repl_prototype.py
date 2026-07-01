"""`veles repl` — inline streaming REPL (Phase 1: slash + modes + status).

Covers the testable seams: message-routing callbacks, post-turn state
carry, slash dispatch through the *real* registry, and parser wiring. The
interactive prompt_toolkit loop and the live mode FSM are exercised by a
manual smoke run, not unit-driven here.
"""

from __future__ import annotations

import argparse

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
        usage=UsageSnapshot(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    _update_state_after_turn(state, rr)
    assert state.session_id == "s9"
    assert state.last_assistant_text == "answer"
    assert state.tokens_in == 10
    assert state.tokens_out == 5
    assert state.last_turn_total_tokens == 15


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
