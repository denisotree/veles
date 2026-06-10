"""M98: DaemonPickerScreen actions + render."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from veles.daemon.registry import DaemonEntry, DaemonRegistry
from veles.tui.screens.daemon_picker import (
    DaemonPickerApp,
    DaemonPickerScreen,
)


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles"))
    return tmp_path


def _seed_registry(entries: list[DaemonEntry]) -> None:
    reg = DaemonRegistry()
    for e in entries:
        reg.upsert(e)
    reg.save()


def _entry(slug: str, *, pid: int = 0, port: int = 8765, started_at: float = 1.0) -> DaemonEntry:
    return DaemonEntry(
        slug=slug,
        project_path=f"/proj/{slug}",
        project_name=slug,
        pid=pid,
        host="127.0.0.1",
        port=port,
        started_at=started_at,
    )


# ---------------- empty state ----------------


async def test_picker_shows_empty_message_when_no_daemons() -> None:
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        assert screen._empty.display is True


async def test_picker_lists_registered_daemons() -> None:
    _seed_registry([_entry("alpha"), _entry("beta", port=8766)])
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        assert [e.slug for e in screen._entries] == ["alpha", "beta"]
        assert screen._empty.display is False


# ---------------- actions ----------------


async def test_q_quits() -> None:
    _seed_registry([_entry("x")])
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    assert app.return_code in (None, 0)


async def test_delete_removes_entry_from_registry() -> None:
    _seed_registry([_entry("alpha", pid=0), _entry("beta", pid=0)])
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")  # confirm the delete prompt (M138-followup)
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    reloaded = DaemonRegistry.load()
    # First entry (alpha) deleted; beta survives.
    assert "alpha" not in reloaded.entries
    assert "beta" in reloaded.entries


async def test_delete_cancelled_keeps_entry() -> None:
    """`d` then `n` (or Esc) cancels — the entry is NOT removed."""
    _seed_registry([_entry("alpha", pid=0)])
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("n")  # decline
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        assert "cancelled" in screen.last_action
        await pilot.press("q")
        await pilot.pause()
    assert "alpha" in DaemonRegistry.load().entries


async def test_stop_on_non_running_records_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_registry([_entry("alpha", pid=999_999)])
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        assert "not running" in screen.last_action
        await pilot.press("q")
        await pilot.pause()


async def test_start_does_not_spawn_when_running(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_registry([_entry("alpha", pid=os.getpid())])
    called = {"n": 0}

    def fake_spawn(_entry):
        called["n"] += 1
        return True

    monkeypatch.setattr("veles.tui.screens.daemon_picker._spawn_daemon", fake_spawn)
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        assert "already running" in screen.last_action
        assert called["n"] == 0
        await pilot.press("q")
        await pilot.pause()


async def test_start_spawns_when_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    """`s` on a STOPPED daemon (dead pid, kept in the registry after stop) must
    restart it — the registry path reaches `_spawn_daemon`."""
    _seed_registry([_entry("alpha", pid=999_999)])  # dead pid → status "stopped"
    called = {"n": 0}

    def fake_spawn(_entry):
        called["n"] += 1
        return True

    monkeypatch.setattr("veles.tui.screens.daemon_picker._spawn_daemon", fake_spawn)
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        assert called["n"] == 1
        assert "start spawned" in screen.last_action
        await pilot.press("q")
        await pilot.pause()


async def test_enter_opens_log_view() -> None:
    """M110: Enter pushes DaemonLogScreen onto the screen stack; q
    inside that screen pops back to the picker (same row preserved)."""
    from veles.tui.screens.daemon_log import DaemonLogScreen

    _seed_registry([_entry("alpha")])
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        # Now the log screen sits on top of the picker.
        assert isinstance(pilot.app.screen, DaemonLogScreen)
        # Back via q.
        await pilot.press("q")
        await pilot.pause()
        assert isinstance(pilot.app.screen, DaemonPickerScreen)
        await pilot.press("q")
        await pilot.pause()


# ---------------- M104: focus survives refresh + theme applied ----------------


async def test_focus_survives_refresh_tick() -> None:
    """The 2s `set_interval(_refresh)` rebuilds ListView items; the screen
    must refocus the widget so ↑/↓ keep working after every tick."""
    _seed_registry([_entry("alpha"), _entry("beta")])
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        # Manual refresh — emulates one interval tick without waiting 2s.
        screen._refresh()
        await pilot.pause()
        assert screen._listview.has_focus is True
        assert screen._listview.index == 0
        await pilot.press("q")
        await pilot.pause()


async def test_refresh_skips_clear_when_signature_same(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M111: diff-based refresh. Tick #2 with no structural changes
    must update labels in place — `_listview.clear()` is NOT called."""
    _seed_registry([_entry("alpha", pid=0), _entry("beta", pid=0)])
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        # Initial mount already populated; signature should be set now.
        sig_before = screen._last_signature
        assert sig_before  # populated
        # Patch clear() to detect any subsequent rebuild.
        cleared: list[bool] = []
        original_clear = screen._listview.clear
        monkeypatch.setattr(
            screen._listview,
            "clear",
            lambda: (cleared.append(True), original_clear())[1],
        )
        # Tick again with the same registry contents.
        screen._refresh()
        await pilot.pause()
        assert cleared == []
        assert screen._listview.has_focus is True
        await pilot.press("q")
        await pilot.pause()


async def test_refresh_rebuilds_on_structural_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a daemon appears or disappears, the ListView is rebuilt and
    focus is restored via call_after_refresh."""
    _seed_registry([_entry("alpha", pid=0)])
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        # New daemon shows up between ticks.
        _seed_registry([_entry("alpha", pid=0), _entry("beta", pid=0, port=8766)])
        cleared: list[bool] = []
        original_clear = screen._listview.clear
        monkeypatch.setattr(
            screen._listview,
            "clear",
            lambda: (cleared.append(True), original_clear())[1],
        )
        screen._refresh()
        await pilot.pause()
        assert cleared == [True]
        # Focus survives the rebuild.
        assert screen._listview.has_focus is True
        await pilot.press("q")
        await pilot.pause()


async def test_theme_applied_on_mount() -> None:
    """`DaemonPickerApp.on_mount` should apply the user's saved theme so
    the picker matches the wizard / main TUI palette. We don't assert a
    specific palette — just that `app.theme` is set to a non-empty name
    after mount (default fallback is 'everforest')."""
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Textual's App.theme reflects the active theme name.
        assert isinstance(pilot.app.theme, str) and pilot.app.theme
        await pilot.press("q")
        await pilot.pause()


# ---------------- M138: init contract + runtime-session rows ----------------
# (moved here from tests/test_tui_daemon_m138.py — M150 consolidation)


def test_daemon_picker_standalone_flag_defaults_true() -> None:
    """`/daemon` pushes the picker with standalone=False so quit pops back
    to chat; the CLI entry keeps the standalone default."""
    assert DaemonPickerScreen()._standalone is True
    assert DaemonPickerScreen(standalone=False)._standalone is False


def test_runtime_session_rows_none_project() -> None:
    from veles.tui.screens.daemon_picker import runtime_session_rows

    assert runtime_session_rows(None) == []


def test_runtime_session_rows_lists_named_and_tui(tmp_path: Path) -> None:
    from veles.core.project import init_project
    from veles.core.runtime_sessions import RuntimeSessionStore
    from veles.tui.screens.daemon_picker import runtime_session_rows

    project = init_project(tmp_path / "p", name="p")
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", provider="ollama", model="qwen3:4b-instruct", port=8801)
    store.create("tui", "tui")
    store.close()

    rows = runtime_session_rows(project)
    assert len(rows) == 2
    joined = "\n".join(rows)
    assert "api" in joined and "daemon" in joined and "8801" in joined
    assert "tui" in joined
    assert "ollama:qwen3:4b-instruct" in joined


# ---------------- M138-followup: runtime-session action controller ----------------


def _daemon_rec(**kw):
    from veles.core.runtime_sessions import RuntimeSessionRecord

    base = dict(
        id="rt-1", name="api", kind="daemon", model=None, provider=None,
        host="127.0.0.1", port=8801, mode=None, status="created", pid=None,
        created_at=0.0, last_started_at=None, last_stopped_at=None, deleted_at=None,
    )
    base.update(kw)
    return RuntimeSessionRecord(**base)


def test_runtime_action_start_spawns(tmp_path, monkeypatch):
    import veles.daemon.spawn as spawn_mod
    import veles.tui.screens._daemon_picker_data as picker_mod
    from veles.core.project import init_project
    from veles.tui.screens.daemon_picker import runtime_session_action

    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setattr(picker_mod, "is_alive", lambda pid: False)
    calls = {}
    monkeypatch.setattr(
        spawn_mod, "spawn_daemon", lambda **kw: calls.update(kw) or object()
    )
    msg = runtime_session_action(project, _daemon_rec(pid=None), "start")
    assert "start spawned" in msg
    assert calls["name"] == "api"  # re-execs the named child


def test_runtime_action_start_already_running(tmp_path, monkeypatch):
    import veles.tui.screens._daemon_picker_data as picker_mod
    from veles.core.project import init_project
    from veles.tui.screens.daemon_picker import runtime_session_action

    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setattr(picker_mod, "is_alive", lambda pid: True)
    msg = runtime_session_action(project, _daemon_rec(pid=4321), "start")
    assert "already running" in msg


def test_runtime_action_stop_sends_sigterm(tmp_path, monkeypatch):
    import veles.tui.screens._daemon_picker_data as picker_mod
    from veles.core.project import init_project
    from veles.tui.screens.daemon_picker import runtime_session_action

    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setattr(picker_mod, "is_alive", lambda pid: True)
    killed = {}
    monkeypatch.setattr(picker_mod.os, "kill", lambda pid, sig: killed.update(pid=pid, sig=sig))
    msg = runtime_session_action(project, _daemon_rec(pid=4321), "stop")
    assert "SIGTERM sent" in msg and killed["pid"] == 4321


def test_runtime_action_tui_is_noop(tmp_path):
    from veles.core.project import init_project
    from veles.tui.screens.daemon_picker import runtime_session_action

    project = init_project(tmp_path / "p", name="p")
    msg = runtime_session_action(project, _daemon_rec(kind="tui", name="tui"), "start")
    assert "not applicable" in msg


def test_runtime_action_delete_soft_deletes(tmp_path):
    from veles.core.project import init_project
    from veles.core.runtime_sessions import RuntimeSessionStore
    from veles.tui.screens.daemon_picker import runtime_session_action

    project = init_project(tmp_path / "p", name="p")
    store = RuntimeSessionStore(project.memory_db_path)
    rec = store.create("api", "daemon", port=8801)
    store.close()

    msg = runtime_session_action(project, rec, "delete")
    assert "deleted" in msg
    store = RuntimeSessionStore(project.memory_db_path)
    try:
        assert store.get_by_name("api", kind="daemon") is None  # hidden
        assert store.get_by_name("api", kind="daemon", include_deleted=True) is not None
    finally:
        store.close()


# ---------------- M138-followup: runtime list pilot flows ----------------


async def test_picker_runtime_list_populated_and_focus_delete(tmp_path):
    """End-to-end: the runtime list renders the project's sessions, and a
    delete keystroke while it's focused soft-deletes (not the registry path)."""
    from veles.core.project import init_project
    from veles.core.runtime_sessions import RuntimeSessionStore

    project = init_project(tmp_path / "p", name="p")
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        assert [r.name for r in screen._runtime_records] == ["api"]
        screen._runtime_listview.focus()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")  # confirm the delete prompt (M138-followup)
        await pilot.pause()
        assert "deleted" in screen.last_action

    store = RuntimeSessionStore(project.memory_db_path)
    try:
        assert store.get_by_name("api", kind="daemon") is None
    finally:
        store.close()


async def test_picker_add_channel_flow(tmp_path, fake_keyring):
    """`c` on a focused runtime daemon session walks the modal channel wizard
    and writes `[daemon.<name>.channels.telegram]` + the keychain secret."""
    from veles.core.project import init_project
    from veles.core.project_config import get_section, load_project_config, save_project_config
    from veles.core.runtime_sessions import RuntimeSessionStore
    from veles.core.secrets import get_provider_key

    project = init_project(tmp_path / "p", name="p")
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["api"] = {"port": 8801}
    save_project_config(project, cfg)
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        screen._runtime_listview.focus()
        await pilot.pause()
        await pilot.press("c")  # opens ChoiceScreen (default = telegram)
        await pilot.pause()
        await pilot.press("enter")  # pick telegram
        await pilot.pause()
        # InputScreen #1 — bot token (required secret).
        await pilot.press(*"tok123")
        await pilot.press("enter")
        await pilot.pause()
        # InputScreen #2 — whitelist (optional); leave blank.
        await pilot.press("enter")
        await pilot.pause()

    block = get_section(load_project_config(project), "daemon", "api", "channels", "telegram")
    assert block.get("enabled") is True
    assert get_provider_key("telegram", project=project.name) == "tok123"


async def test_picker_remove_channel_flow(tmp_path, fake_keyring):
    """`x` on a focused runtime daemon session removes a configured channel."""
    from veles.cli.channel_wizard import apply_channel
    from veles.core.project import init_project
    from veles.core.project_config import get_section, load_project_config, save_project_config
    from veles.core.runtime_sessions import RuntimeSessionStore

    project = init_project(tmp_path / "p", name="p")
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["api"] = {"port": 8801}
    save_project_config(project, cfg)
    apply_channel(project, session="api", channel="telegram", secrets={"bot_token": "t"}, config_fields={})
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        screen._runtime_listview.focus()
        await pilot.pause()
        await pilot.press("x")  # opens ChoiceScreen of configured channels
        await pilot.pause()
        await pilot.press("enter")  # pick telegram (only one)
        await pilot.pause()

    assert get_section(load_project_config(project), "daemon", "api", "channels") == {}


async def test_picker_enter_opens_named_session_log(tmp_path):
    """Enter on a focused runtime daemon session opens its instance log view."""
    from veles.core.project import init_project
    from veles.core.runtime_sessions import RuntimeSessionStore
    from veles.tui.screens.daemon_log import DaemonLogScreen

    project = init_project(tmp_path / "p", name="p")
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        screen._runtime_listview.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(pilot.app.screen, DaemonLogScreen)
