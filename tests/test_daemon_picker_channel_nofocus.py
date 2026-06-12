"""Regression (M138-followup bugfix): `c`/`x` in the daemon picker are
focus-aware and work on the **registry** daemon row that holds default focus —
the running unnamed daemon (e.g. `mind-palace`). Earlier the keys either no-op'd
(focus gate) or targeted the wrong list (the kind=tui runtime row), so a user
looking at a running registry daemon couldn't add/remove a channel.

A registry row targets the project's global `[channels.<type>]` (session=None);
a named runtime daemon session targets `[daemon.<name>.channels.<type>]` (covered
by `test_tui_daemon_m138.py`)."""

from __future__ import annotations

from veles.cli.channel_wizard import apply_channel
from veles.core.project import init_project
from veles.core.project_config import get_section, load_project_config
from veles.core.secrets import get_provider_key
from veles.daemon.registry import DaemonEntry, DaemonRegistry
from veles.tui.screens.daemon_picker import DaemonPickerApp


def _seed_registry_for(project) -> None:
    reg = DaemonRegistry()
    reg.upsert(
        DaemonEntry(
            slug="mind-palace",
            project_path=str(project.root),
            project_name=project.name,
            pid=0,
            host="127.0.0.1",
            port=8765,
            started_at=1.0,
        )
    )
    reg.save()


async def test_add_channel_to_focused_registry_daemon(tmp_path, monkeypatch):
    """The user's case: a running registry daemon holds default focus; `c`
    writes the project's GLOBAL [channels.telegram] (the unnamed daemon)."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "p", name="p")
    _seed_registry_for(project)

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()  # let the cursor land on the 'default' daemon node
        # The cursor starts on the project's unnamed/'default' daemon.
        await pilot.press("c")
        await pilot.pause()
        await pilot.press("enter")        # ChoiceScreen → telegram (default)
        await pilot.pause()
        await pilot.press(*"tok123")
        await pilot.press("enter")        # bot token
        await pilot.pause()
        await pilot.press("enter")        # whitelist blank
        await pilot.pause()

        # Visible feedback: status line / last_action confirms the add.
        screen = pilot.app.screen
        assert "added telegram" in screen.last_action

    cfg = load_project_config(project)
    # Global block (session=None), NOT under [daemon.<name>].
    assert get_section(cfg, "channels", "telegram").get("enabled") is True
    assert get_provider_key("telegram", project=project.name) == "tok123"
    # The daemon row now surfaces the channel (the user's "I can't tell" gap):
    # `_entry_channels` reads it and the formatter renders a `chans=…` suffix.
    from veles.tui.screens.daemon_picker import DaemonRowFormatter, _entry_channels

    entry = DaemonRegistry.load().get("mind-palace")
    assert _entry_channels(entry) == ["telegram"]
    assert "telegram" in DaemonRowFormatter.render(entry, 0.0, channels=["telegram"])


async def test_add_channel_failure_does_not_crash(tmp_path, monkeypatch):
    """A persistence failure in the worker must surface as a status line, not
    crash the app (Textual `exit_on_error=True` would otherwise panic)."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "p", name="p")
    _seed_registry_for(project)

    import veles.cli.channel_wizard as cw

    monkeypatch.setattr(cw, "apply_channel", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()  # cursor lands on the 'default' daemon node
        await pilot.press("c")
        await pilot.pause()
        await pilot.press("enter")        # telegram
        await pilot.pause()
        await pilot.press(*"tok")
        await pilot.press("enter")        # token
        await pilot.pause()
        await pilot.press("enter")        # whitelist blank
        await pilot.pause()
        screen = pilot.app.screen
        assert "failed to add telegram" in screen.last_action
    # App exited cleanly (no panic/crash).
    assert app.return_code in (None, 0)


async def test_remove_channel_from_focused_registry_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "p", name="p")
    _seed_registry_for(project)
    apply_channel(project, session=None, channel="telegram", secrets={"bot_token": "t"}, config_fields={})
    assert get_section(load_project_config(project), "channels", "telegram").get("enabled") is True

    app = DaemonPickerApp(project=project)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()  # cursor lands on the 'default' daemon node
        await pilot.press("x")            # cursor on the daemon → pick-from-list flow
        await pilot.pause()
        await pilot.press("enter")        # ChoiceScreen → telegram (only one)
        await pilot.pause()

    assert get_section(load_project_config(project), "channels") == {}
