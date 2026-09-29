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
    assert "line one" in out
    assert "line two" in out  # the \n between the two content lines survived


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
