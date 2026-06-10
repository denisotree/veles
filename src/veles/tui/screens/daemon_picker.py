"""M98: `veles daemon` (bare) TUI picker.

Lists every daemon from `~/.veles/daemons.json` with status + uptime
and lets the user trigger common actions per row:

    Enter      → connect (M99 — stub message for now)
    s          → start the highlighted daemon (no-op if running)
    t          → stop (SIGTERM)
    r          → restart (stop + spawn)
    d          → delete (with confirmation)
    q / Esc    → exit
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import ClassVar

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView

from veles.daemon.registry import (
    DaemonEntry,
    DaemonRegistry,
    is_alive,
)

# Data/formatting helpers live in `_daemon_picker_data` (M154 carve-out).
# Names unused here are re-exported for tests that import them from this
# module (tests/tui/test_daemon_picker.py, tests/tui/test_daemon_row_formatter.py,
# tests/test_daemon_picker_channel_nofocus.py).
from veles.tui.screens._daemon_picker_data import (
    DaemonRowFormatter,
    _enabled_channel_names,  # noqa: F401 — re-export for tests
    _entry_channels,
    _entry_model,
    _fmt_model,  # noqa: F401 — re-export for tests
    _fmt_runtime_row,
    _fmt_uptime,  # noqa: F401 — re-export for tests
    _live_active_model,  # noqa: F401 — re-export for tests
    _live_channels,  # noqa: F401 — re-export for tests
    _runtime_channels,
    runtime_session_action,
    runtime_session_records,
    runtime_session_rows,  # noqa: F401 — re-export for tests
)


class DaemonPickerScreen(Screen[None]):
    """Single-screen daemon control surface."""

    DEFAULT_CSS = """
    DaemonPickerScreen { background: $surface; }
    DaemonPickerScreen Vertical { padding: 1 2; }
    DaemonPickerScreen Label.title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    DaemonPickerScreen Label.hint {
        color: $text-muted;
        margin-top: 1;
    }
    DaemonPickerScreen Label.empty {
        color: $text-muted;
        margin: 2;
    }
    DaemonPickerScreen ListView {
        height: 1fr;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "quit", priority=True),
        Binding("escape", "quit", "quit", priority=True),
        Binding("s", "start_one", "start", priority=True),
        Binding("t", "stop_one", "stop", priority=True),
        Binding("r", "restart_one", "restart", priority=True),
        Binding("d", "delete_one", "delete", priority=True),
        Binding("c", "add_channel", "add channel", priority=True),
        Binding("x", "remove_channel", "remove channel", priority=True),
        Binding("f5", "refresh_list", "refresh", priority=True),
        # OSC52 fallback for terminals that forward the copy shortcut as
        # a key event instead of doing native drag-select. Mirrors the
        # main chat TUI (veles/tui/app.py:61-74) — `screen.copy_text` is
        # Textual's built-in action that emits OSC52. macOS Terminal.app
        # users instead get native drag-select + ⌘C since mouse
        # reporting is off (DaemonPickerApp().run(mouse=False)).
        Binding("super+c", "screen.copy_text", "copy", priority=True, show=False),
        Binding(
            "ctrl+shift+c",
            "screen.copy_text",
            "copy",
            priority=True,
            show=False,
        ),
    ]

    def __init__(self, *, standalone: bool = True, project=None) -> None:
        super().__init__()
        # standalone=True → the picker IS the app (`DaemonPickerApp`, bare
        # `veles daemon`), so quit exits the process. standalone=False → pushed
        # onto the main TUI via `/daemon`, so quit pops back to the chat.
        self._standalone = standalone
        # M138-followup: when set, show + manage this project's runtime_sessions
        # (named daemon sessions + the kind=tui row) below the cross-project
        # registry. Tab moves focus to that list; s/t/r/d then act on it.
        self._project = project
        self._entries: list[DaemonEntry] = []
        self._runtime_records: list = []
        # Track the last action result so tests / users can inspect it.
        self.last_action: str = ""
        # M111: signature of the last structural state we rendered.
        # Tuple of (slug, pid, status_for(entry)) per entry — if the
        # signature is unchanged on the next refresh tick, we update
        # the uptime label in place instead of rebuilding the ListView.
        # Rebuilding destroys child widgets and races with Textual's
        # focus tracking, which is what was making the cursor go dark
        # 1-2s after opening the picker.
        self._last_signature: tuple[tuple[str, int, str], ...] = ()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Label("Veles daemons", classes="title")
            self._listview = ListView(id="daemon-list")
            yield self._listview
            self._empty = Label(
                "no daemons registered. Run `veles daemon start` in a project.",
                classes="empty",
            )
            self._empty.display = False
            yield self._empty
            # M138-followup: project-local runtime sessions (named daemon
            # sessions + the kind=tui row), selectable + manageable. Shown only
            # when a project is in scope (always when opened via `/daemon`).
            self._runtime_title = Label("Project runtime sessions (Tab)", classes="title")
            self._runtime_listview = ListView(id="runtime-list")
            self._runtime_empty = Label("  (none)", classes="empty")
            if self._project is None:
                self._runtime_title.display = False
                self._runtime_listview.display = False
                self._runtime_empty.display = False
            yield self._runtime_title
            yield self._runtime_listview
            yield self._runtime_empty
            # Status line: the latest action result (mirrors `last_action`), so
            # every keypress gives visible feedback even when no row changes.
            self._status = Label("", classes="hint")
            yield self._status
            yield Label(
                "Enter=log · s=start · t=stop · r=restart · d=delete · "
                "c=add chan · x=rm chan · F5=refresh · q=quit",
                classes="hint",
            )
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(2.0, self._refresh)

    def _refresh(self) -> None:
        registry = DaemonRegistry.load()
        self._entries = registry.list()
        now = time.time()
        if self._project is not None:
            self._refresh_runtime_list()
        models = [_entry_model(e) for e in self._entries]
        channels = [_entry_channels(e) for e in self._entries]
        signature = tuple(
            DaemonRowFormatter.signature(e, model=m, channels=c)
            for e, m, c in zip(self._entries, models, channels, strict=True)
        )

        if signature == self._last_signature and self._entries:
            # Structure unchanged — update only the uptime portion of
            # each row's label in place. ListView children are not
            # recreated, so focus is preserved by construction.
            for i, (entry, model, chans) in enumerate(
                zip(self._entries, models, channels, strict=True)
            ):
                try:
                    item = self._listview.children[i]
                    label = item.query_one(Label)
                except Exception:  # noqa: BLE001 — defensive against Textual reflow
                    continue
                label.update(
                    DaemonRowFormatter.render(entry, now, model=model, channels=chans)
                )
            self._empty.display = False
            return

        # Structural change: rebuild. clear() destroys the
        # previously-focused child widget; we re-focus the ListView
        # *after* Textual finishes reflow via call_after_refresh, which
        # is race-free (unlike calling focus() inline).
        self._last_signature = signature
        prev_index = self._listview.index or 0
        self._listview.clear()
        for entry, model, chans in zip(self._entries, models, channels, strict=True):
            self._listview.append(
                ListItem(
                    Label(
                        DaemonRowFormatter.render(entry, now, model=model, channels=chans)
                    )
                )
            )
        self._empty.display = not self._entries
        if self._entries:
            self._listview.index = min(prev_index, len(self._entries) - 1)
            # B: don't steal focus back to the registry list if the user has
            # Tab'd to the runtime list (the 2 s tick would otherwise yank it).
            if not self._runtime_focused():
                self.call_after_refresh(self._listview.focus)
        elif (
            # E: registry empty but the project has runtime sessions → focus the
            # runtime list so s/t/r/d/c/x act on it instead of silently no-op'ing.
            self._project is not None
            and self._runtime_records
            and self.focused is not self._runtime_listview
        ):
            self.call_after_refresh(self._runtime_listview.focus)

    def _selected(self) -> DaemonEntry | None:
        idx = self._listview.index or 0
        if 0 <= idx < len(self._entries):
            return self._entries[idx]
        return None

    def _refresh_runtime_list(self) -> None:
        """Rebuild the runtime-session ListView from the store. Simpler than
        the registry list's diff machinery — this list is short and the user
        isn't holding focus on it during the 2 s tick in the common case."""
        records = runtime_session_records(self._project)
        chan_map = {r.id: _runtime_channels(self._project, r) for r in records}
        # Skip rebuild when nothing structural changed (preserve focus/cursor).
        sig = tuple(
            (r.id, r.status, r.pid, r.port, tuple(chan_map[r.id])) for r in records
        )
        if sig == getattr(self, "_runtime_signature", None) and self._runtime_records:
            return
        self._runtime_signature = sig
        self._runtime_records = records
        prev = self._runtime_listview.index or 0
        self._runtime_listview.clear()
        for r in records:
            self._runtime_listview.append(
                ListItem(Label(_fmt_runtime_row(r, channels=chan_map[r.id])))
            )
        self._runtime_empty.display = not records
        self._runtime_listview.display = bool(records)
        if records:
            self._runtime_listview.index = min(prev, len(records) - 1)

    def _runtime_focused(self) -> bool:
        return self.focused is self._runtime_listview

    def _runtime_selected(self):
        idx = self._runtime_listview.index or 0
        if 0 <= idx < len(self._runtime_records):
            return self._runtime_records[idx]
        return None

    def _do_runtime_action(self, action: str) -> bool:
        """Dispatch a runtime-session action when that list has focus.
        Returns True if it handled the key (so the registry path is skipped)."""
        if self._project is None or not self._runtime_focused():
            return False
        rec = self._runtime_selected()
        if rec is None:
            self._set_action("no runtime session selected", severity="warning")
            return True
        result = runtime_session_action(self._project, rec, action)
        severity = "error" if "failed" in result else "information"
        self._set_action(result, severity=severity)
        self._refresh()
        return True

    def action_add_channel(self) -> None:
        """`c`: attach a channel to the selected daemon. Focus-aware — a
        registry row (default focus, e.g. the running `mind-palace` daemon)
        targets that project's global `[channels.<type>]` (session=None); a
        named runtime daemon session targets `[daemon.<name>.channels.<type>]`.
        Launches a worker because `push_screen_wait` must run off the message
        pump (Textual requirement)."""
        target = self._channel_target()
        if target is None:
            return  # _channel_target already notified
        project, session, label = target
        self.run_worker(self._add_channel_flow(project, session, label), exclusive=True)

    def _channel_target(self):
        """Resolve `(project, session_name | None, label)` for a channel action
        from the focused list. Registry row → that daemon's project + global
        channels (session=None); runtime daemon row → (this project, name).
        Notifies and returns None when nothing actionable is selected."""
        if self._runtime_focused():
            rec = self._runtime_selected()
            if rec is None:
                self._notify("No runtime session selected.")
                return None
            if rec.kind != "daemon":
                self._notify("Channels attach to daemon sessions, not the TUI session.")
                return None
            if self._project is None:
                self._notify("Open the picker inside a project to manage channels.")
                return None
            return (self._project, rec.name, rec.name)
        entry = self._selected()
        if entry is None:
            self._notify("No daemon selected.")
            return None
        from veles.core.project import load_project

        try:
            project = load_project(Path(entry.project_path))
        except Exception:  # noqa: BLE001 — bad/missing project path
            self._notify(f"can't load project at {entry.project_path}")
            return None
        # Registry daemons are the unnamed (legacy) daemon → global [channels.*].
        return (project, None, entry.slug)

    async def _add_channel_flow(self, project, session, label) -> None:
        """Modal channel wizard: pick type → collect creds → write the channel
        block (global `[channels.<type>]` when session is None, else
        `[daemon.<name>.channels.<type>]`) + keychain secret (M137 from TUI)."""
        from veles.channels.platform_registry import (
            ensure_builtins_registered,
            get_platform,
            list_platforms,
        )
        from veles.cli.channel_wizard import apply_channel
        from veles.tui.wizard.screens.choice import ChoiceItem, ChoiceScreen
        from veles.tui.wizard.screens.input import InputScreen
        from veles.tui.wizard.step import CANCEL_SENTINEL

        ensure_builtins_registered()
        platforms = list_platforms()
        if not platforms:
            self._set_action("no channel platforms registered", severity="warning")
            return
        channel = await self.app.push_screen_wait(
            ChoiceScreen(
                f"Add channel to {label}",
                [ChoiceItem(p, p) for p in platforms],
                default=platforms[0],
            )
        )
        if not channel or channel == CANCEL_SENTINEL:
            return
        entry = get_platform(channel)
        secrets: dict[str, str] = {}
        config_fields: dict[str, object] = {}
        for field in entry.cred_fields:
            value = await self.app.push_screen_wait(
                InputScreen(f"{channel}: {field.label}", password=field.secret)
            )
            if value == CANCEL_SENTINEL:
                return
            value = (value or "").strip()
            if not value:
                if field.required:
                    self._set_action(
                        f"{label}: {field.label} required — cancelled", severity="warning"
                    )
                    return
                continue
            if field.secret:
                secrets[field.key] = value
            elif field.list_value:
                config_fields[field.key] = [x.strip() for x in value.split(",") if x.strip()]
            else:
                config_fields[field.key] = value
        try:
            apply_channel(
                project,
                session=session,
                channel=channel,
                secrets=secrets,
                config_fields=config_fields,
            )
        except Exception as exc:  # noqa: BLE001 — surface, never crash the worker/app
            self._set_action(
                f"{label}: failed to add {channel}: {exc}", severity="error"
            )
            return
        self._set_action(f"{label}: added {channel} channel (restart to apply)")
        self._refresh()

    def action_remove_channel(self) -> None:
        """`x`: remove a channel binding from the selected daemon. Focus-aware,
        same target resolution as `action_add_channel`."""
        target = self._channel_target()
        if target is None:
            return
        project, session, label = target
        self.run_worker(self._remove_channel_flow(project, session, label), exclusive=True)

    def _notify(self, message: str, *, severity: str = "warning") -> None:
        """Best-effort toast — `App.notify` is unavailable in some headless
        contexts, so never let a missing notifier break the action."""
        try:
            self.app.notify(message, severity=severity)
        except Exception:  # noqa: BLE001
            pass

    def _set_action(self, message: str, *, severity: str = "information") -> None:
        """Record + surface an action result: update `last_action`, the on-screen
        status line, and toast it. The single place every action reports through
        so the user always sees what happened (no more silent no-ops)."""
        self.last_action = message
        status = getattr(self, "_status", None)
        if status is not None:
            try:
                status.update(message)
            except Exception:  # noqa: BLE001 — status label is best-effort
                pass
        self._notify(message, severity=severity)

    async def _remove_channel_flow(self, project, session, label) -> None:
        """Pick one of the target's configured channels and drop its block —
        global `[channels.*]` when session is None, else
        `[daemon.<name>.channels.*]`."""
        from veles.cli.channel_wizard import delete_channel_block
        from veles.core.project_config import get_section, load_project_config
        from veles.tui.wizard.screens.choice import ChoiceItem, ChoiceScreen
        from veles.tui.wizard.step import CANCEL_SENTINEL

        cfg = load_project_config(project)
        channels = (
            get_section(cfg, "daemon", session, "channels")
            if session
            else get_section(cfg, "channels")
        )
        names = sorted(k for k, v in channels.items() if isinstance(v, dict))
        if not names:
            self._set_action(f"{label}: no channels configured to remove", severity="warning")
            return
        channel = await self.app.push_screen_wait(
            ChoiceScreen(
                f"Remove channel from {label}",
                [ChoiceItem(n, n) for n in names],
                default=names[0],
            )
        )
        if not channel or channel == CANCEL_SENTINEL:
            return
        try:
            removed = delete_channel_block(project, channel, session=session)
        except Exception as exc:  # noqa: BLE001
            self._set_action(f"{label}: failed to remove {channel}: {exc}", severity="error")
            return
        self._set_action(
            f"{label}: removed {channel} channel (restart to apply)"
            if removed
            else f"{label}: no {channel} channel",
            severity="information" if removed else "warning",
        )
        self._refresh()

    # ---------------- actions ----------------

    def action_quit(self) -> None:
        if self._standalone:
            self.app.exit(None)
        else:
            self.dismiss(None)

    def action_refresh_list(self) -> None:
        self._refresh()

    def action_start_one(self) -> None:
        if self._do_runtime_action("start"):
            return
        entry = self._selected()
        if entry is None:
            self._set_action("no daemon selected", severity="warning")
            return
        if is_alive(entry.pid):
            self._set_action(f"{entry.slug}: already running", severity="warning")
            return
        ok = _spawn_daemon(entry)
        self._set_action(
            f"{entry.slug}: start spawned" if ok else f"{entry.slug}: start failed",
            severity="information" if ok else "error",
        )
        self._refresh()

    def action_stop_one(self) -> None:
        if self._do_runtime_action("stop"):
            return
        entry = self._selected()
        if entry is None:
            self._set_action("no daemon selected", severity="warning")
            return
        if not is_alive(entry.pid):
            self._set_action(f"{entry.slug}: not running", severity="warning")
            return
        try:
            os.kill(entry.pid, signal.SIGTERM)
            self._set_action(f"{entry.slug}: SIGTERM sent (stays listed, stopped)")
        except OSError as exc:
            self._set_action(f"{entry.slug}: stop failed: {exc}", severity="error")
        self._refresh()

    def action_restart_one(self) -> None:
        if self._do_runtime_action("restart"):
            return
        entry = self._selected()
        if entry is None:
            self._set_action("no daemon selected", severity="warning")
            return
        if is_alive(entry.pid):
            try:
                os.kill(entry.pid, signal.SIGTERM)
            except OSError:
                pass
            # Wait briefly for shutdown so the spawn doesn't fight for the port.
            for _ in range(20):
                if not is_alive(entry.pid):
                    break
                time.sleep(0.05)
        ok = _spawn_daemon(entry)
        self._set_action(
            f"{entry.slug}: restart spawned" if ok else f"{entry.slug}: restart failed",
            severity="information" if ok else "error",
        )
        self._refresh()

    def action_delete_one(self) -> None:
        """`d`: delete the selected daemon/session — behind a confirm prompt
        (destructive, and unlike `t`/stop it removes the row). Runs as a worker
        to await the modal. Both lists supported via `_channel_target`-style
        focus resolution."""
        self.run_worker(self._delete_flow(), exclusive=True)

    async def _delete_flow(self) -> None:
        from veles.tui.wizard.screens.confirm import ConfirmScreen

        runtime = self._runtime_focused()
        if runtime:
            rec = self._runtime_selected()
            if rec is None:
                self._set_action("no runtime session selected", severity="warning")
                return
            label = rec.name
        else:
            entry = self._selected()
            if entry is None:
                self._set_action("no daemon selected", severity="warning")
                return
            label = entry.slug
        ok = await self.app.push_screen_wait(
            ConfirmScreen("Delete", f"Delete '{label}'? (removes it from the list)", default=False)
        )
        if ok is not True:
            self._set_action(f"{label}: delete cancelled")
            return
        if runtime:
            # Runtime path graceful-stops a live process then soft-deletes (C).
            result = runtime_session_action(self._project, rec, "delete")
            self._set_action(result)
        else:
            if is_alive(entry.pid):
                try:
                    os.kill(entry.pid, signal.SIGTERM)
                except OSError:
                    pass
                for _ in range(20):
                    if not is_alive(entry.pid):
                        break
                    time.sleep(0.05)
            registry = DaemonRegistry.load()
            registry.remove(entry.slug)
            registry.save()
            self._set_action(f"{entry.slug}: deleted")
        self._refresh()

    def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            if self._runtime_focused():
                # Open the named session's own log (`instance_log_path`).
                rec = self._runtime_selected()
                if rec is not None and rec.kind == "daemon" and self._project is not None:
                    from veles.daemon.paths import instance_log_path
                    from veles.tui.screens.daemon_log import DaemonLogScreen

                    slug = f"{self._project.name}-{rec.name}"
                    self.app.push_screen(
                        DaemonLogScreen(
                            instance_log_path(self._project.name, rec.name), slug=slug
                        )
                    )
                    self.last_action = f"{rec.name}: log view opened"
                return
            entry = self._selected()
            if entry is not None:
                # M110: Enter opens the live log view for the selected
                # daemon. The picker stays in the screen stack underneath
                # so `q` in the log view pops back to the same row.
                from veles.daemon.paths import daemon_log_path
                from veles.tui.screens.daemon_log import DaemonLogScreen

                self.app.push_screen(
                    DaemonLogScreen(
                        daemon_log_path(entry.project_name),
                        slug=entry.project_name,
                    )
                )
                self.last_action = f"{entry.slug}: log view opened"


def _spawn_daemon(entry: DaemonEntry) -> bool:
    """Spawn `veles daemon start` in the entry's project root, detached."""
    from veles.daemon.spawn import spawn_daemon as _spawn

    return _spawn(project_root=entry.project_path, host=entry.host, port=entry.port) is not None


class DaemonPickerApp(App[None]):
    """Wrapper App that mounts the picker as its only screen.

    Native terminal text-selection is enabled by the caller passing
    `mouse=False` to `.run()` — see `veles/cli/commands/daemon.py`
    (`_cmd_daemon_picker`). This mirrors the main chat TUI policy in
    `veles/tui/app.py:158-163`: with mouse reporting off the terminal
    handles drag-select + the system copy shortcut. The keyboard
    bindings on `DaemonPickerScreen` add an OSC52 copy fallback for
    terminals that forward the shortcut as a key event."""

    CSS = "Screen { background: $surface; }"

    def __init__(self, *, project=None) -> None:
        super().__init__()
        self._project = project

    def on_mount(self) -> None:
        # Match WizardApp.on_mount — pick up the user's theme so the
        # picker visually matches the wizard and the main TUI REPL.
        # Fallback to 'everforest' on first run / unreadable config.
        from veles.core.user_config import load_user_config
        from veles.tui.theme_bridge import apply_to_app

        cfg = load_user_config()
        apply_to_app(self, (cfg.tui_theme if cfg else None) or "everforest")
        self.push_screen(DaemonPickerScreen(project=self._project))


__all__ = ["DaemonPickerApp", "DaemonPickerScreen"]
