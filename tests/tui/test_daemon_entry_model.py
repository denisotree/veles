"""`_entry_model`: which model the daemon picker shows for a registry entry."""

from __future__ import annotations

from pathlib import Path

import veles.tui.screens._daemon_picker_data as picker
from veles.daemon.registry import DaemonEntry
from veles.tui.screens._daemon_picker_data import _entry_model


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
    """No config.toml → `None` (rendered as `-`). A brand-new project
    starts without one."""
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
