"""`_entry_channels` prefers the daemon's *live* channels over config
(M158-followup).

The picker must reflect what `state.channel_runners` actually started, not
re-derive from config: config can declare a channel the daemon skipped
(missing token at startup) or omit one added since the last restart. The
single source of truth is the running daemon (`/v1/health` `channels`); config
is only the fallback for a stopped/unreachable daemon.
"""

from __future__ import annotations

from veles.core.project import init_project
from veles.core.project_config import load_project_config, save_project_config
from veles.daemon.registry import DaemonEntry
from veles.daemon import picker_data as dpd


def _entry(project_root: str = "", *, pid: int = 0) -> DaemonEntry:
    return DaemonEntry(
        slug="d",
        project_path=project_root,
        project_name="d",
        pid=pid,
        host="127.0.0.1",
        port=8765,
        started_at=1.0,
    )


def _write_global_telegram(project) -> None:
    cfg = load_project_config(project)
    cfg.setdefault("channels", {}).setdefault("telegram", {})["enabled"] = True
    save_project_config(project, cfg)


def test_entry_channels_prefers_live_over_config(tmp_path, monkeypatch):
    """Config declares nothing, but the live daemon serves telegram → shown."""
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setattr(dpd, "is_alive", lambda pid: True)
    monkeypatch.setattr(dpd, "_fetch_health", lambda e: {"channels": ["telegram"]})
    assert dpd._entry_channels(_entry(str(project.root), pid=4321)) == ["telegram"]


def test_entry_channels_live_empty_is_authoritative(tmp_path, monkeypatch):
    """Config SAYS telegram, but the live daemon runs none (skipped: no token)
    → the picker shows none, matching reality. This is the false-positive the
    config-only path could not catch."""
    project = init_project(tmp_path / "p", name="p")
    _write_global_telegram(project)
    monkeypatch.setattr(dpd, "is_alive", lambda pid: True)
    monkeypatch.setattr(dpd, "_fetch_health", lambda e: {"channels": []})
    assert dpd._entry_channels(_entry(str(project.root), pid=4321)) == []


def test_entry_channels_falls_back_to_config_when_unreachable(tmp_path, monkeypatch):
    """Daemon alive but health unreachable / predates the field → fall back to
    the configured global [channels.*]."""
    project = init_project(tmp_path / "p", name="p")
    _write_global_telegram(project)
    monkeypatch.setattr(dpd, "is_alive", lambda pid: True)
    monkeypatch.setattr(dpd, "_fetch_health", lambda e: None)
    assert dpd._entry_channels(_entry(str(project.root), pid=4321)) == ["telegram"]


def test_entry_channels_stopped_daemon_uses_config_without_network(tmp_path, monkeypatch):
    """A stopped daemon (pid not alive) goes straight to config — no health
    probe at all, so the picker never blocks on a dead daemon."""
    project = init_project(tmp_path / "p", name="p")
    _write_global_telegram(project)
    called: list = []
    monkeypatch.setattr(dpd, "_fetch_health", lambda e: called.append(e) or None)
    assert dpd._entry_channels(_entry(str(project.root), pid=0)) == ["telegram"]
    assert called == []
