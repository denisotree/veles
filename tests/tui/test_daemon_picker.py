"""DaemonPickerScreen — project → daemons → channels tree (M159, was M98 list).

Pilot tests drive the Textual `Tree` rewrite: the cursor starts on the first
daemon, s/t/r/d/c/x act on the daemon (or parent daemon of a channel leaf) under
the cursor, and — the core of the focus regression — the cursor + focus survive
the 2 s refresh and structural changes because `Tree` keys the cursor by node
identity (no `clear()` rebuild). Data-layer unit tests (runtime rows/actions)
live at the bottom.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from veles.core.project import init_project
from veles.core.runtime_sessions import RuntimeSessionStore
from veles.daemon.registry import DaemonEntry, DaemonRegistry
from veles.tui.screens.daemon_picker import (
    DaemonPickerApp,
    DaemonPickerScreen,
    _Row,
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


def _entry(
    slug: str, *, project_path: str | None = None, pid: int = 0, port: int = 8765
) -> DaemonEntry:
    return DaemonEntry(
        slug=slug,
        project_path=project_path or f"/proj/{slug}",
        project_name=slug,
        pid=pid,
        host="127.0.0.1",
        port=port,
        started_at=1.0,
    )


def _daemon_nodes(screen: DaemonPickerScreen) -> list:
    """Every daemon-kind tree node, flattened across sections."""
    out = []
    for section in (screen._sec_current, screen._sec_other):
        if section is None:
            continue
        for child in section.children:
            row = child.data
            if isinstance(row, _Row) and row.kind == "daemon" and row.node is not None:
                out.append(child)
    return out


def _node_named(screen: DaemonPickerScreen, name: str):
    for child in _daemon_nodes(screen):
        if child.data.node.name == name:
            return child
    return None


# ---------------- empty / listing ----------------


async def test_picker_shows_empty_message_when_no_daemons() -> None:
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        assert screen._empty.display is True
        assert screen._tree.display is False


async def test_picker_lists_project_daemon(tmp_path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        # The project's unnamed daemon renders as "default" under the project.
        assert [c.data.node.name for c in _daemon_nodes(screen)] == ["default"]
        assert screen._empty.display is False


async def test_cursor_starts_on_first_daemon(tmp_path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        daemon = screen._cursor_daemon()
        assert daemon is not None and daemon.name == "default"
        assert screen._tree.has_focus is True


async def test_q_quits() -> None:
    _seed_registry([_entry("x")])
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    assert app.return_code in (None, 0)


# ---------------- lifecycle actions ----------------


async def test_delete_removes_daemon_from_registry(tmp_path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")  # confirm
        await pilot.pause()
    assert "p" not in DaemonRegistry.load().entries


async def test_delete_cancelled_keeps_daemon(tmp_path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("n")  # decline
        await pilot.pause()
        screen = pilot.app.screen
        assert "cancelled" in screen.last_action
    assert "p" in DaemonRegistry.load().entries


async def test_stop_on_non_running_records_skip(tmp_path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"), pid=999_999)])
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()
        screen = pilot.app.screen
        assert "not running" in screen.last_action


async def test_start_does_not_spawn_when_running(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"), pid=os.getpid())])
    called = {"n": 0}
    monkeypatch.setattr(
        "veles.tui.screens.daemon_picker.spawn_daemon_node",
        lambda node: (called.__setitem__("n", called["n"] + 1), True)[1],
    )
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        screen = pilot.app.screen
        assert "already running" in screen.last_action
        assert called["n"] == 0


async def test_start_spawns_when_stopped(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"), pid=999_999)])
    called = {"n": 0}
    monkeypatch.setattr(
        "veles.tui.screens.daemon_picker.spawn_daemon_node",
        lambda node: (called.__setitem__("n", called["n"] + 1), True)[1],
    )
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        screen = pilot.app.screen
        assert called["n"] == 1
        assert "start spawned" in screen.last_action


async def test_enter_opens_log_view(tmp_path) -> None:
    from veles.tui.screens.daemon_log import DaemonLogScreen

    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(pilot.app.screen, DaemonLogScreen)
        await pilot.press("q")
        await pilot.pause()
        assert isinstance(pilot.app.screen, DaemonPickerScreen)


# ---------------- focus / cursor survival (issue 2 regression guard) ----------------


async def test_cursor_and_focus_survive_refresh(tmp_path) -> None:
    """The 2 s tick reconciles nodes in place — the cursor node object and the
    tree's focus must be unchanged (the old ListView rebuild lost both)."""
    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        before = screen._tree.cursor_node
        screen._refresh()
        await pilot.pause()
        assert screen._tree.cursor_node is before
        assert screen._tree.has_focus is True


async def test_cursor_survives_structural_change(tmp_path) -> None:
    """A new daemon appearing must not move the cursor off the user's row."""
    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        before = screen._tree.cursor_node
        assert before.data.node.name == "default"
        # A daemon from another project shows up between ticks.
        _seed_registry(
            [
                _entry("p", project_path=str(tmp_path / "p")),
                _entry("other", project_path=str(tmp_path / "other"), port=8770),
            ]
        )
        screen._refresh()
        await pilot.pause()
        assert screen._tree.cursor_node is before  # same node object
        assert screen._tree.has_focus is True


async def test_cursor_and_focus_survive_stop_action(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reported bug: stopping a daemon must not drop focus/cursor. The stop
    flips status running→stopped (structural relabel), which previously rebuilt
    the list; now the node is relabelled in place."""
    import veles.tui.screens.daemon_picker as dp

    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"), pid=4242)])
    alive = {"v": True}
    # Patch is_alive in all three bindings so `status_for` (in registry) uses
    # the flag instead of a real os.kill(pid, 0) — otherwise the global os.kill
    # patch below would flip the flag during the very first refresh.
    monkeypatch.setattr(dp, "is_alive", lambda pid: alive["v"])
    monkeypatch.setattr(
        "veles.tui.screens._daemon_picker_data.is_alive", lambda pid: alive["v"]
    )
    monkeypatch.setattr("veles.daemon.registry.is_alive", lambda pid: alive["v"])
    monkeypatch.setattr(dp.os, "kill", lambda pid, sig: alive.__setitem__("v", False))

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        before = screen._tree.cursor_node
        await pilot.press("t")
        await pilot.pause()
        await pilot.pause()
        assert "SIGTERM" in screen.last_action
        assert screen._tree.cursor_node is before
        assert screen._tree.has_focus is True


async def test_restart_kills_before_spawn_and_keeps_focus(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Restart runs in a worker (non-blocking poll) and must SIGTERM the old
    process *before* spawning the new one, or the spawn races it for the port.
    Cursor + focus survive (the reported freeze/focus-loss is gone)."""
    import veles.tui.screens.daemon_picker as dp

    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"), pid=4242)])
    alive = {"v": True}
    seq: list[str] = []
    monkeypatch.setattr(dp, "is_alive", lambda pid: alive["v"])
    monkeypatch.setattr("veles.tui.screens._daemon_picker_data.is_alive", lambda pid: alive["v"])
    monkeypatch.setattr("veles.daemon.registry.is_alive", lambda pid: alive["v"])

    def fake_kill(pid, sig):
        seq.append("kill")
        alive["v"] = False  # process dies → poll exits immediately

    monkeypatch.setattr(dp.os, "kill", fake_kill)
    monkeypatch.setattr(
        dp, "spawn_daemon_node", lambda node: (seq.append("spawn"), True)[1]
    )

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        before = screen._tree.cursor_node
        await pilot.press("r")
        await pilot.pause()
        await pilot.pause()
        assert seq == ["kill", "spawn"]  # kill strictly before spawn
        assert "restart spawned" in screen.last_action
        assert screen._tree.cursor_node is before
        assert screen._tree.has_focus is True


# ---------------- named daemon sessions ----------------


async def test_named_daemon_listed_with_channels(tmp_path) -> None:
    from veles.core.project_config import load_project_config, save_project_config

    project = init_project(tmp_path / "p", name="p")
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["api"] = {
        "port": 8801,
        "channels": {"telegram": {"enabled": True}},
    }
    save_project_config(project, cfg)
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        api = _node_named(screen, "api")
        assert api is not None
        # channel leaf rendered under the named daemon
        leaves = [c.data.channel for c in api.children if isinstance(c.data, _Row)]
        assert leaves == ["telegram"]


async def test_named_daemon_delete_soft_deletes(tmp_path) -> None:
    project = init_project(tmp_path / "p", name="p")
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        screen._tree.move_cursor(_node_named(screen, "api"))
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert "deleted" in screen.last_action

    store = RuntimeSessionStore(project.memory_db_path)
    try:
        assert store.get_by_name("api", kind="daemon") is None  # hidden
        assert store.get_by_name("api", kind="daemon", include_deleted=True) is not None
    finally:
        store.close()


async def test_enter_opens_named_session_log(tmp_path) -> None:
    from veles.tui.screens.daemon_log import DaemonLogScreen

    project = init_project(tmp_path / "p", name="p")
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        screen._tree.move_cursor(_node_named(screen, "api"))
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(pilot.app.screen, DaemonLogScreen)


# ---------------- channel flows ----------------


async def test_add_channel_to_daemon(tmp_path, fake_keyring) -> None:
    from veles.core.project_config import get_section, load_project_config

    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        await pilot.press("c")  # cursor on the 'default' daemon
        await pilot.pause()
        await pilot.press("enter")  # ChoiceScreen → telegram (default)
        await pilot.pause()
        await pilot.press(*"tok123")
        await pilot.press("enter")  # bot token
        await pilot.pause()
        await pilot.press("enter")  # whitelist blank
        await pilot.pause()
        screen = pilot.app.screen
        assert "added telegram" in screen.last_action

    # Global block (session=None) for the unnamed/default daemon.
    cfg = load_project_config(project)
    assert get_section(cfg, "channels", "telegram").get("enabled") is True


async def test_remove_channel_on_leaf_directly(tmp_path, fake_keyring) -> None:
    from veles.cli.channel_wizard import apply_channel
    from veles.core.project_config import get_section, load_project_config

    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])
    apply_channel(
        project, session=None, channel="telegram", secrets={"bot_token": "t"}, config_fields={}
    )

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        # Move cursor onto the channel leaf under 'default'.
        default = _node_named(screen, "default")
        leaf = default.children[0]
        screen._tree.move_cursor(leaf)
        await pilot.pause()
        await pilot.press("x")  # deletes that channel directly (no picker)
        await pilot.pause()
        assert "removed telegram" in screen.last_action

    assert get_section(load_project_config(project), "channels") == {}


async def test_add_channel_failure_does_not_crash(
    tmp_path, monkeypatch: pytest.MonkeyPatch, fake_keyring
) -> None:
    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])

    import veles.cli.channel_wizard as cw

    monkeypatch.setattr(
        cw, "apply_channel", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        await pilot.press("enter")  # telegram
        await pilot.pause()
        await pilot.press(*"tok")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")  # whitelist blank
        await pilot.pause()
        screen = pilot.app.screen
        assert "failed to add telegram" in screen.last_action
    assert app.return_code in (None, 0)


# ---------------- theme + flags ----------------


async def test_theme_applied_on_mount() -> None:
    app = DaemonPickerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(pilot.app.theme, str) and pilot.app.theme
        await pilot.press("q")
        await pilot.pause()


def test_daemon_picker_standalone_flag_defaults_true() -> None:
    assert DaemonPickerScreen()._standalone is True
    assert DaemonPickerScreen(standalone=False)._standalone is False


async def test_pushed_screen_mounts_and_cursor_lands(tmp_path) -> None:
    """The `/daemon` slash path pushes DaemonPickerScreen(standalone=False) onto
    the host TUI (app.py:330). Verify that entry point mounts the tree, lands the
    cursor on a daemon, and quit pops back instead of exiting the host app."""
    from textual.app import App

    project = init_project(tmp_path / "p", name="p")
    _seed_registry([_entry("p", project_path=str(tmp_path / "p"))])

    class _Host(App[None]):
        def on_mount(self) -> None:
            self.push_screen(DaemonPickerScreen(standalone=False, project=project))

    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, DaemonPickerScreen)
        daemon = screen._cursor_daemon()
        assert daemon is not None and daemon.name == "default"
        assert screen._tree.has_focus is True
        # quit pops back to the host (does not exit the app).
        await pilot.press("q")
        await pilot.pause()
        assert not isinstance(pilot.app.screen, DaemonPickerScreen)
        assert app.return_code is None


# ---------------- data layer: runtime rows / actions ----------------


def test_runtime_session_rows_none_project() -> None:
    from veles.tui.screens.daemon_picker import runtime_session_rows

    assert runtime_session_rows(None) == []


def test_runtime_session_rows_lists_named_and_tui(tmp_path: Path) -> None:
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
    from veles.tui.screens.daemon_picker import runtime_session_action

    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setattr(picker_mod, "is_alive", lambda pid: False)
    calls = {}
    monkeypatch.setattr(
        spawn_mod, "spawn_daemon", lambda **kw: calls.update(kw) or object()
    )
    msg = runtime_session_action(project, _daemon_rec(pid=None), "start")
    assert "start spawned" in msg
    assert calls["name"] == "api"


def test_runtime_action_start_already_running(tmp_path, monkeypatch):
    import veles.tui.screens._daemon_picker_data as picker_mod
    from veles.tui.screens.daemon_picker import runtime_session_action

    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setattr(picker_mod, "is_alive", lambda pid: True)
    msg = runtime_session_action(project, _daemon_rec(pid=4321), "start")
    assert "already running" in msg


def test_runtime_action_stop_sends_sigterm(tmp_path, monkeypatch):
    import veles.tui.screens._daemon_picker_data as picker_mod
    from veles.tui.screens.daemon_picker import runtime_session_action

    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setattr(picker_mod, "is_alive", lambda pid: True)
    killed = {}
    monkeypatch.setattr(picker_mod.os, "kill", lambda pid, sig: killed.update(pid=pid, sig=sig))
    msg = runtime_session_action(project, _daemon_rec(pid=4321), "stop")
    assert "SIGTERM sent" in msg and killed["pid"] == 4321


def test_runtime_action_tui_is_noop(tmp_path):
    from veles.tui.screens.daemon_picker import runtime_session_action

    project = init_project(tmp_path / "p", name="p")
    msg = runtime_session_action(project, _daemon_rec(kind="tui", name="tui"), "start")
    assert "not applicable" in msg


def test_runtime_action_delete_soft_deletes(tmp_path):
    from veles.tui.screens.daemon_picker import runtime_session_action

    project = init_project(tmp_path / "p", name="p")
    store = RuntimeSessionStore(project.memory_db_path)
    rec = store.create("api", "daemon", port=8801)
    store.close()

    msg = runtime_session_action(project, rec, "delete")
    assert "deleted" in msg
    store = RuntimeSessionStore(project.memory_db_path)
    try:
        assert store.get_by_name("api", kind="daemon") is None
        assert store.get_by_name("api", kind="daemon", include_deleted=True) is not None
    finally:
        store.close()
