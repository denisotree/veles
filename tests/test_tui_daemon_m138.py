"""M138: `/daemon` slash command opens the daemon control panel.

`/daemon` opens the daemon control panel (push `DaemonPickerScreen(standalone=
False)` so quit pops back to chat).

This file covers the dispatch contract and the focus-behaviour regressions.
Picker-internal behaviour (init flags, runtime rows/actions, pilot flows)
lives in `tests/tui/test_daemon_picker.py` (M150 consolidation).

(The `/daemon`-adjacent `kind=tui` runtime-session registration this file
used to also cover was removed with the chat TUI in M187 — the interactive
run's session-tracking helper had no production caller once the chat TUI's
boot entry point was deleted.)
"""

from __future__ import annotations

from veles.cli.repl.slash.builtin import build_default_registry
from veles.core.project import init_project
from veles.core.runtime_sessions import RuntimeSessionStore

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


def _named(screen, name):
    from veles.tui.screens.daemon_picker import _Row

    for section in (screen._sec_current, screen._sec_other):
        if section is None:
            continue
        for child in section.children:
            row = child.data
            if (
                isinstance(row, _Row)
                and row.kind == "daemon"
                and row.node is not None
                and row.node.name == name
            ):
                return child
    return None


async def test_refresh_keeps_focus_and_cursor_on_named_daemon(tmp_path, monkeypatch):
    """M159: the 2 s refresh reconciles tree nodes in place — the cursor stays on
    the named daemon the user selected, and the tree keeps focus."""
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
        await pilot.pause()
        screen = pilot.app.screen
        screen._tree.move_cursor(_named(screen, "api"))
        await pilot.pause()
        before = screen._tree.cursor_node
        screen._refresh()  # the structural tick
        await pilot.pause()
        assert screen._tree.cursor_node is before
        assert screen._tree.has_focus is True


async def test_named_daemon_actionable_when_no_registry_entry(tmp_path, monkeypatch):
    """M159: with only a named session (no registry/unnamed daemon), the cursor
    still lands on a daemon so s/t/r/d act on it instead of a silent no-op."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    import veles.daemon.spawn as spawn_mod
    from veles.tui.screens.daemon_picker import DaemonPickerApp

    monkeypatch.setattr(spawn_mod, "spawn_daemon", lambda **kw: object())  # no real subprocess
    project = init_project(tmp_path / "p", name="p")
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        screen = pilot.app.screen
        daemon = screen._cursor_daemon()
        assert daemon is not None and daemon.name == "api"
        await pilot.press("s")  # start the named session (not a silent no-op)
        await pilot.pause()
        assert "api" in screen.last_action
