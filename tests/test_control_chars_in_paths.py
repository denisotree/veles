"""Task 3 (Stage 1b): control characters in agent-controlled strings must not
forge a confirmation prompt or a diff preview.

`resolve_safe` refuses a control character in the raw path before any
filesystem work; `_default_confirmer`, the REPL's `_confirm_critical`, and
the write/edit diff preview all escape through `veles.core.text.shown` /
`shown_multiline` before printing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.path_guard import SandboxViolation, resolve_safe
from veles.core.tools.builtin.write_file import write_file


def _set_env_roots(monkeypatch: pytest.MonkeyPatch, *roots: Path) -> None:
    monkeypatch.setenv("VELES_SANDBOX_ROOTS", ":".join(str(r) for r in roots))


# ---------------- resolve_safe: control characters refused ----------------


def test_resolve_safe_refuses_esc_in_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env_roots(monkeypatch, tmp_path)
    with pytest.raises(SandboxViolation, match="control characters"):
        resolve_safe("a\x1b[2Kb.md")


def test_resolve_safe_refuses_bidi_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_env_roots(monkeypatch, tmp_path)
    # U+202E RIGHT-TO-LEFT OVERRIDE — makes the displayed name read backwards
    # relative to the bytes on disk.
    with pytest.raises(SandboxViolation, match="control characters"):
        resolve_safe("evil‮gnp.exe")


def test_resolve_safe_refuses_c1_control(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env_roots(monkeypatch, tmp_path)
    with pytest.raises(SandboxViolation, match="control characters"):
        resolve_safe("note\x85name.md")


def test_resolve_safe_allows_non_ascii_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A normal non-ASCII (Cyrillic) filename is not a control character and
    stays allowed — the refusal targets control chars, not non-ASCII text."""
    _set_env_roots(monkeypatch, tmp_path)
    assert resolve_safe("заметка.md") == (tmp_path / "заметка.md").resolve()


# ---------------- write_file: refused before any file is created ----------------


def test_write_file_esc_in_path_refused_no_file_created(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_env_roots(monkeypatch, tmp_path)
    with pytest.raises(SandboxViolation, match="control characters"):
        write_file("a\x1b[2Kb.md", "pwned")
    assert list(tmp_path.iterdir()) == []


# ---------------- _default_confirmer: escapes op/summary ----------------


def test_default_confirmer_escapes_control_chars(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from veles.core.critical_ops import _default_confirmer

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")

    op = "delete file\x1b[2K evil"
    summary = "line one\x07bell\x1b[31mred"
    assert _default_confirmer(op, summary) is True

    err = capsys.readouterr().err
    assert "\x1b" not in err  # no raw ESC reaches the terminal
    assert "\x07" not in err  # no raw BEL either
    assert "\\x1b" in err  # escaped, visible form is present instead
    assert "\\x07" in err
    assert "delete file" in err
    assert "evil" in err


def test_default_confirmer_keeps_newlines_in_multiline_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A legitimate multi-line summary (e.g. an MCP recipe review body built
    by `mcp/approvals.py::describe_recipe`, or an install summary's
    `Source:`/`Target:` lines) must still print on separate lines — escaping
    is about control characters, not about collapsing real structure."""
    from veles.core.critical_ops import _default_confirmer

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")

    summary = "Source: pkg\x1b[2K\nTarget: /dest\nReview before confirming."
    assert _default_confirmer("op", summary) is True

    err = capsys.readouterr().err
    assert "\x1b" not in err  # the injected ESC is still escaped
    assert "\\x1b" in err
    lines = err.splitlines()
    assert "  │ Source: pkg\\x1b[2K" in lines
    assert "  │ Target: /dest" in lines


# ---------------- diff preview: control chars in content escaped ----------------


def _theme():
    from veles.cli.commands.repl import _resolve_theme
    from veles.core.session_state import AppState

    return _resolve_theme(AppState(session_id=None, provider_name="openrouter", model="m"))


def test_diff_preview_escapes_esc_but_keeps_newlines(capsys: pytest.CaptureFixture[str]) -> None:
    from rich.console import Console

    from veles.cli.repl.render import _render_edit_diff

    _render_edit_diff(
        Console(),
        _theme(),
        "edit_file",
        {
            "path": "notes.md",
            "old_string": "before",
            "new_string": "line one\x1b[31mred\x1b[0m\nline two",
        },
    )
    out = capsys.readouterr().out
    assert "\x1b" not in out  # no raw ANSI escape leaks into the diff
    assert "\\x1b" in out  # escaped form shown instead
    assert "\\n" not in out  # the real newline was NOT itself escaped away
    lines = out.splitlines()
    # "line one"/"line two" landed as two separate `+` diff lines, not one
    # line joined by a literal "\n" — proves shown_multiline() kept the
    # structural newline while still escaping the ANSI escape inside it.
    assert any(line.lstrip().startswith("+line one") for line in lines)
    assert any(line.lstrip() == "+line two" for line in lines)


def test_diff_preview_escapes_control_chars_in_path(capsys: pytest.CaptureFixture[str]) -> None:
    from rich.console import Console

    from veles.cli.repl.render import _render_edit_diff

    _render_edit_diff(
        Console(),
        _theme(),
        "edit_file",
        {"path": "a\x1b[2Kb.md", "old_string": "x", "new_string": "y"},
    )
    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert "\\x1b" in out


# ---------------- permission prompt body: agent-controlled fields escaped ----------------


def test_shown_multiline_escapes_carriage_return() -> None:
    """`\\r` is not `\\n`/`\\t`, so `shown_multiline` still escapes it — a raw
    CR is a terminal-line-overwrite vector (VISION-style spoofing), same
    class as ESC."""
    from veles.core.text import shown_multiline

    assert shown_multiline("a\rb") == "a\\rb"


def test_permission_prompt_body_escapes_control_chars_in_arguments() -> None:
    from veles.core.permission.prompt import PromptRequest, format_prompt_body

    req = PromptRequest(
        tool_name="run_shell",
        arguments={"command": "ls\x1b[2K\r; rm -rf /"},
        reason="process_execution requires trust ladder",
        kind="trust",
    )
    body = format_prompt_body(req)
    assert "\x1b" not in body  # no raw ESC
    assert "\r" not in body  # no raw CR (line-overwrite spoofing)
    assert "\\x1b" in body  # escaped forms present instead
    assert "\\r" in body
    assert "run_shell" in body


def test_repl_confirm_critical_escapes_control_chars_in_op_and_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The REPL's in-app M39 picker (`_confirm_critical`) prints `op`/`summary`
    escaped, same as the default confirmer — separate code path, same
    property."""
    import argparse
    import threading
    import time as _t

    from rich.console import Console

    from veles.cli.commands import repl as repl_mod
    from veles.cli.commands.repl import _ReplApp, _resolve_theme
    from veles.cli.repl.slash import build_default_registry
    from veles.core.memory import SessionStore
    from veles.core.project import init_project
    from veles.core.session_state import AppState

    project = init_project(tmp_path, name="repltest")
    store = SessionStore(project.memory_db_path)
    state = AppState(session_id=None, provider_name="openrouter", model="m")
    # Plain Console (not the REPL's force_terminal=True one): under pytest
    # capture, rich then emits no ANSI style codes of its own, so the only
    # ESC bytes in `out` — if any — come from our escaping bug, not from
    # styling. The `_render_edit_diff` tests above use the same approach.
    app = _ReplApp(
        argparse.Namespace(),
        project,
        state,
        lambda *_a, **_k: None,
        store,
        build_default_registry(project=project),
        Console(),
        _resolve_theme(state),
        [],
    )
    try:
        monkeypatch.setattr(repl_mod.sys.stdin, "isatty", lambda: True)
        result: dict = {}
        op = "dispatch delete_file\x1b[2K evil"
        summary = "line one\rCR-injected"

        def _run():
            result["ok"] = app._confirm_critical(op, summary)

        th = threading.Thread(target=_run)
        th.start()
        for _ in range(400):
            if app.q_active:
                break
            _t.sleep(0.005)
        assert app.q_active
        app.q_sel = 1  # highlight defaults to Cancel (safe)
        app._picker_enter()
        th.join(timeout=2)
        assert result["ok"] is False
    finally:
        store.close()

    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert "\r" not in out
    assert "\\x1b" in out
    assert "\\r" in out
    assert "dispatch delete_file" in out
    assert "line one" in out
