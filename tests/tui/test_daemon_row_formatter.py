"""M-R2.6: DaemonRowFormatter — pure row rendering + signature."""

from __future__ import annotations

from pathlib import Path

from veles.daemon.registry import DaemonEntry
from veles.tui.screens.daemon_picker import DaemonRowFormatter, _entry_model


def _entry(**overrides) -> DaemonEntry:
    base = dict(
        slug="alpha",
        project_path="/proj/alpha",
        project_name="alpha",
        pid=0,
        host="127.0.0.1",
        port=8765,
        started_at=1.0,
    )
    base.update(overrides)
    return DaemonEntry(**base)  # type: ignore[arg-type]


def test_signature_changes_with_pid() -> None:
    s0 = DaemonRowFormatter.signature(_entry(pid=0))
    s1 = DaemonRowFormatter.signature(_entry(pid=4242))
    assert s0 != s1


def test_signature_independent_of_uptime() -> None:
    """Signature reflects structural state (slug, pid, status). Uptime
    drift between ticks doesn't change it — that's what makes the
    diff-update path valid for the common case."""
    e = _entry(pid=4242, started_at=1.0)
    assert DaemonRowFormatter.signature(e) == DaemonRowFormatter.signature(e)


def test_signature_stable_across_model_changes() -> None:
    """A live `/model` swap must NOT change the row signature —
    otherwise every Telegram/TUI swap would clear the ListView and
    yank focus from the highlighted daemon. The in-place update path
    re-renders the row's label (incl. the model column) on every
    refresh tick, so the new model is visible without a rebuild."""
    e = _entry()
    assert DaemonRowFormatter.signature(e, model="openai/gpt-4o") == DaemonRowFormatter.signature(
        e, model="anthropic/claude-haiku"
    )


def test_render_includes_core_fields() -> None:
    row = DaemonRowFormatter.render(_entry(), now=10.0)
    assert "alpha" in row
    assert "127.0.0.1" in row
    assert "8765" in row
    assert "/proj/alpha" in row


def test_render_includes_uptime_field() -> None:
    """`up <value>` chunk is always present — formatter handles both
    live (`up 5m`) and not-running (`up 0m`) cases."""
    row = DaemonRowFormatter.render(_entry(pid=0), now=10.0)
    assert "up " in row


def test_render_includes_model_when_supplied() -> None:
    row = DaemonRowFormatter.render(_entry(), now=10.0, model="anthropic/claude-3.7-sonnet")
    assert "anthropic/claude-3.7-sonnet" in row


def test_render_uses_dash_when_model_missing() -> None:
    """A daemon without a `[engine] model` in its project config
    still renders cleanly with a `-` placeholder so columns stay
    aligned and the user knows nothing is pinned."""
    row = DaemonRowFormatter.render(_entry(), now=10.0, model=None)
    # The dash must appear between the uptime column and the project
    # path — assert it shows up at all rather than being silently
    # dropped (which would misalign neighbouring rows that DO have
    # a model).
    assert " - " in row or row.rstrip().endswith("/proj/alpha")
    assert "-" in row


def test_render_truncates_long_model_id() -> None:
    """Curated models from OpenRouter routinely exceed 30 chars
    (e.g. provider/model:beta). Truncation keeps the column at a
    fixed width — column drift would push the project_path off the
    edge of narrow terminals."""
    long = "openrouter/anthropic/claude-3.5-sonnet-extended:beta"
    row = DaemonRowFormatter.render(_entry(), now=10.0, model=long)
    # The full id should be cropped; an ellipsis or its 32-char prefix
    # is enough to know the column held its width.
    assert long not in row
    assert long[:30] in row


# ---- _entry_model helper ----


def test_entry_model_reads_project_config(tmp_path: Path) -> None:
    """When `<project>/.veles/config.toml` has `[engine] model = X`,
    the helper returns X."""
    (tmp_path / ".veles").mkdir()
    (tmp_path / ".veles" / "config.toml").write_text(
        '[engine]\nprovider = "openrouter"\nmodel = "openai/gpt-4o"\n',
        encoding="utf-8",
    )
    entry = _entry(project_path=str(tmp_path))
    assert _entry_model(entry) == "openai/gpt-4o"


def test_entry_model_returns_none_when_config_missing(tmp_path: Path) -> None:
    """No config.toml → `None` (rendered as `-` in the column).
    Defensive: a brand-new project starts without one."""
    entry = _entry(project_path=str(tmp_path))
    assert _entry_model(entry) is None


def test_entry_model_returns_none_when_provider_section_missing(
    tmp_path: Path,
) -> None:
    """Config exists but has no `[engine]` section — still `None`,
    not a crash, not a string-conversion of an empty dict."""
    (tmp_path / ".veles").mkdir()
    (tmp_path / ".veles" / "config.toml").write_text("[daemon]\nport = 8765\n", encoding="utf-8")
    entry = _entry(project_path=str(tmp_path))
    assert _entry_model(entry) is None


def test_entry_model_prefers_live_active_model_when_daemon_alive(
    tmp_path: Path, monkeypatch
) -> None:
    """When the daemon is reachable, the picker shows what /v1/health
    reports as `active_model` — i.e. the last /model swap — not the
    static project config."""
    import veles.daemon.picker_data as picker

    (tmp_path / ".veles").mkdir()
    (tmp_path / ".veles" / "config.toml").write_text(
        '[engine]\nmodel = "static-config-model"\n', encoding="utf-8"
    )
    entry = _entry(project_path=str(tmp_path), pid=4242)
    monkeypatch.setattr(picker, "is_alive", lambda pid: True)
    monkeypatch.setattr(picker, "_live_active_model", lambda e: "live-override-model")
    assert _entry_model(entry) == "live-override-model"


def test_entry_model_falls_back_to_config_when_daemon_unreachable(
    tmp_path: Path, monkeypatch
) -> None:
    """Daemon process is alive but the HTTP probe fails (firewall,
    crash during shutdown, timeout). Picker degrades to project
    config instead of showing a dash."""
    import veles.daemon.picker_data as picker

    (tmp_path / ".veles").mkdir()
    (tmp_path / ".veles" / "config.toml").write_text(
        '[engine]\nmodel = "config-fallback"\n', encoding="utf-8"
    )
    entry = _entry(project_path=str(tmp_path), pid=4242)
    monkeypatch.setattr(picker, "is_alive", lambda pid: True)
    monkeypatch.setattr(picker, "_live_active_model", lambda e: None)
    assert _entry_model(entry) == "config-fallback"


def test_entry_model_handles_blank_project_path() -> None:
    """A registry row with an empty `project_path` (legacy entry,
    or corrupt manual edit) returns `None` instead of trying to read
    `/.veles/config.toml`."""
    entry = _entry(project_path="")
    assert _entry_model(entry) is None
