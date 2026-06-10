"""M39 — always-confirm gate for critical operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import (
    reset_active_project,
    set_active_project,
)
from veles.core.critical_ops import (
    _LITERAL_YES,
    confirm_critical,
    reset_critical_confirmer,
    set_critical_confirmer,
)
from veles.core.project import init_project
from veles.core.tools.builtin.write_file import write_file

# ---------- harness ----------


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with no contextvar prompter override and no leaked project."""
    monkeypatch.delenv("VELES_TRUST_AUTO_ALLOW", raising=False)
    set_active_project(None)


# ---------- confirm_critical contextvar plumbing ----------


def test_overridden_confirmer_intercepts_prompt() -> None:
    seen: list[tuple[str, str]] = []

    def fake(op: str, summary: str) -> bool:
        seen.append((op, summary))
        return True

    token = set_critical_confirmer(fake)
    try:
        result = confirm_critical("install skill x", "summary text")
    finally:
        reset_critical_confirmer(token)
    assert result is True
    assert seen == [("install skill x", "summary text")]


def test_overridden_confirmer_can_refuse() -> None:
    token = set_critical_confirmer(lambda _o, _s: False)
    try:
        assert confirm_critical("op", "summary") is False
    finally:
        reset_critical_confirmer(token)


def test_reset_confirmer_restores_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """After reset, the default (TTY-or-refuse) confirmer is back in effect."""
    token = set_critical_confirmer(lambda _o, _s: True)
    reset_critical_confirmer(token)
    # Force non-TTY → default refuses without prompting.
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert confirm_critical("op", "summary") is False


# ---------- default_confirmer ----------


def test_default_confirmer_refuses_without_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert confirm_critical("op", "summary") is False


def test_default_confirmer_accepts_literal_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: _LITERAL_YES)
    assert confirm_critical("op", "summary") is True


def test_default_confirmer_strips_whitespace_around_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "  yes  ")
    assert confirm_critical("op", "summary") is True


def test_default_confirmer_rejects_uppercase_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "YES")
    assert confirm_critical("op", "summary") is False


def test_default_confirmer_rejects_y_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")
    assert confirm_critical("op", "summary") is False


def test_default_confirmer_rejects_no(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "no")
    assert confirm_critical("op", "summary") is False


def test_default_confirmer_rejects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    assert confirm_critical("op", "summary") is False


def test_default_confirmer_rejects_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert confirm_critical("op", "summary") is False


# ---------- write_file integration ----------


def _setup_writable_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point sandbox `~/.veles/` at tmp_path/home so writes there land in tmp."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".veles").mkdir()
    monkeypatch.setattr(
        "veles.core.path_guard.Path.home",
        classmethod(lambda cls: fake_home),
    )
    monkeypatch.delenv("VELES_SANDBOX_ROOTS", raising=False)
    return fake_home


def test_write_file_inside_project_no_critical_confirm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Writes inside the active project root never call confirm_critical.

    M117d: the target must also be inside the active layout-pack's
    writable zones (`wiki/` or `.veles/` for the default llm-wiki pack).
    A naked top-level file was permitted pre-M117d; now writable-zones
    enforcement requires a zone-rooted path."""
    _setup_writable_user_home(monkeypatch, tmp_path)
    project = init_project(tmp_path / "proj", name="proj")
    invocations: list[tuple[str, str]] = []

    def boom(op: str, summary: str) -> bool:
        invocations.append((op, summary))
        return True

    proj_token = set_active_project(project)
    conf_token = set_critical_confirmer(boom)
    try:
        # Use a wiki/ target — the llm-wiki layout-pack declares it
        # writable so M117d's is_writable check passes.
        target = project.root / "wiki" / "inside.md"
        msg = write_file(str(target), "hello")
    finally:
        reset_critical_confirmer(conf_token)
        reset_active_project(proj_token)
    assert "wrote" in msg
    assert target.read_text(encoding="utf-8") == "hello"
    assert invocations == []


def test_write_file_outside_project_to_user_veles_calls_confirm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_home = _setup_writable_user_home(monkeypatch, tmp_path)
    project = init_project(tmp_path / "proj", name="proj")
    invocations: list[tuple[str, str]] = []

    def fake(op: str, summary: str) -> bool:
        invocations.append((op, summary))
        return True

    proj_token = set_active_project(project)
    conf_token = set_critical_confirmer(fake)
    try:
        target = fake_home / ".veles" / "skills" / "foo.py"
        msg = write_file(str(target), "print('hi')")
    finally:
        reset_critical_confirmer(conf_token)
        reset_active_project(proj_token)
    assert "wrote" in msg
    assert target.read_text(encoding="utf-8") == "print('hi')"
    assert len(invocations) == 1
    op, summary = invocations[0]
    assert "outside active project" in op
    assert str(target) in op
    assert "user-global" in summary


def test_write_file_outside_project_refused_returns_error_msg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_home = _setup_writable_user_home(monkeypatch, tmp_path)
    project = init_project(tmp_path / "proj", name="proj")
    proj_token = set_active_project(project)
    conf_token = set_critical_confirmer(lambda _o, _s: False)
    target = fake_home / ".veles" / "skills" / "evil.py"
    try:
        result = write_file(str(target), "print('hi')")
    finally:
        reset_critical_confirmer(conf_token)
        reset_active_project(proj_token)
    assert "<refused" in result
    assert "outside active project" in result
    assert not target.exists()


def test_write_file_no_active_project_skips_critical_confirm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With no active project there is no `outside-of-project` notion."""
    monkeypatch.setenv("VELES_SANDBOX_ROOTS", str(tmp_path))
    invocations: list[tuple[str, str]] = []
    conf_token = set_critical_confirmer(
        lambda op, summary: bool(invocations.append((op, summary))) or True
    )
    try:
        target = tmp_path / "nofproject.txt"
        msg = write_file(str(target), "hello")
    finally:
        reset_critical_confirmer(conf_token)
    assert "wrote" in msg
    assert invocations == []
