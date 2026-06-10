"""M138: TUI `/daemon` slash command + TUI registered as a runtime session.

`/daemon` opens the daemon control panel (push `DaemonPickerScreen(standalone=
False)` so quit pops back to chat); the interactive run registers a kind=tui
`runtime_sessions` row visible alongside daemon sessions.

This file covers the dispatch contract, the runtime-session lifecycle, and the
focus-behaviour regressions. Picker-internal behaviour (init flags, runtime
rows/actions, pilot flows) lives in `tests/tui/test_daemon_picker.py`
(M150 consolidation).
"""

from __future__ import annotations

from pathlib import Path

from veles.core.project import init_project
from veles.core.runtime_sessions import RuntimeSessionStore
from veles.tui.slash.builtin import build_default_registry


# ---- /daemon slash command ----


def test_daemon_slash_registered_and_opens_picker():
    reg = build_default_registry()
    handler = reg._commands.get("/daemon") if hasattr(reg, "_commands") else None
    # Fall back to dispatch if the internal dict name differs.
    result = reg.dispatch("/daemon", _DummyCtx())
    assert result is not None
    assert result.open_picker == "daemon"
    assert handler is None or callable(getattr(handler, "handler", handler))


class _DummyCtx:
    """Minimal SlashContext stand-in — `/daemon` ignores ctx entirely."""

    state = None
    project = None
    store = None


# ---- TUI as a runtime session ----


def test_register_tui_session_creates_running_row(tmp_path: Path):
    from veles.tui import _register_tui_session

    project = init_project(tmp_path / "p", name="p")
    result = _register_tui_session(project)
    assert result is not None
    store, rid = result
    try:
        rec = store.get_by_name("tui", kind="tui")
        assert rec is not None and rec.status == "running" and rec.pid is not None
    finally:
        store.close()


def test_register_tui_session_reuses_row(tmp_path: Path):
    from veles.tui import _register_tui_session

    project = init_project(tmp_path / "p", name="p")
    s1, rid1 = _register_tui_session(project)
    s1.close()
    s2, rid2 = _register_tui_session(project)
    s2.close()
    assert rid1 == rid2  # same logical TUI row reused across launches

    # Exactly one live tui session.
    store = RuntimeSessionStore(project.memory_db_path)
    try:
        assert len(store.list(kind="tui")) == 1
    finally:
        store.close()


def test_tui_session_marked_stopped(tmp_path: Path):
    from veles.tui import _register_tui_session

    project = init_project(tmp_path / "p", name="p")
    store, rid = _register_tui_session(project)
    store.mark_stopped(rid)
    rec = store.get_by_name("tui", kind="tui")
    assert rec is not None and rec.status == "stopped" and rec.pid is None
    store.close()


# ---- focus behaviour (M138-followup bugfixes B + E) ----


def _seed_registry_entry(project) -> None:
    from veles.daemon.registry import DaemonEntry, DaemonRegistry

    reg = DaemonRegistry()
    reg.upsert(
        DaemonEntry(
            slug="reg",
            project_path=str(project.root),
            project_name=project.name,
            pid=0,
            host="127.0.0.1",
            port=8765,
            started_at=1.0,
        )
    )
    reg.save()


async def test_refresh_does_not_steal_focus_from_runtime_list(tmp_path, monkeypatch):
    """B: the 2s refresh must not yank focus back to the registry list when the
    user has Tab'd to the runtime list."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    from veles.tui.screens.daemon_picker import DaemonPickerApp

    project = init_project(tmp_path / "p", name="p")
    _seed_registry_entry(project)
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        screen._runtime_listview.focus()
        await pilot.pause()
        screen._refresh()  # the structural tick
        await pilot.pause()
        assert screen._runtime_listview.has_focus is True


async def test_default_focus_runtime_when_registry_empty(tmp_path, monkeypatch):
    """E: with no registry daemons but a runtime session, the runtime list gets
    default focus so s/t/r/d act on it instead of silently no-op'ing."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    from veles.tui.screens.daemon_picker import DaemonPickerApp

    project = init_project(tmp_path / "p", name="p")
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert screen._runtime_listview.has_focus is True
        await pilot.press("s")  # start the named session (not a silent no-op)
        await pilot.pause()
        assert "api" in screen.last_action
