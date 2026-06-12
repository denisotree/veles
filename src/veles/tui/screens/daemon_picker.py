"""`veles daemon` (bare) TUI picker — project → daemons → channels tree (M159).

Originally a flat `ListView` of cross-project daemons (M98) plus a second list
of project runtime sessions (M138). M159 unifies both into a single Textual
`Tree`, reflecting the real shape: a project has several daemons, and a daemon
has several channels. Layout:

    Project: <name>                 ← section (when opened inside a project)
      default   running …           ← the project's unnamed/"default" daemon
        chan: telegram              ← channels as leaves
      api       stopped …           ← a named daemon session
        chan: discord
      tui  (tui) …                  ← the interactive session row (no channels)
    Other projects                  ← section
      other-proj  running …
        chan: telegram

Per-row keys (focus-aware — they act on the daemon under the cursor, or the
parent daemon of a channel leaf):

    Enter      → open that daemon's live log
    s          → start          t → stop (SIGTERM)        r → restart
    d          → delete (confirm)
    c          → add a channel   x → remove the channel under the cursor
    F5         → refresh         q / Esc → exit

`Tree` keys the cursor by node identity, so the 2 s refresh reconciles nodes in
place (add/remove/relabel) without ever calling `clear()` — the cursor and focus
survive structural change for free (the old `ListView` rebuild lost them).
"""

from __future__ import annotations

import asyncio
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Tree
from textual.widgets.tree import TreeNode

from veles.daemon.registry import (
    DaemonRegistry,
    is_alive,
)

# Data/formatting helpers live in `_daemon_picker_data`. Names unused here are
# re-exported for the test suites that import them from this module
# (tests/tui/test_daemon_picker.py, test_daemon_row_formatter.py,
# test_daemon_tree_model.py, tests/test_daemon_picker_channel_nofocus.py).
from veles.tui.screens._daemon_picker_data import (
    DaemonNode,
    DaemonRowFormatter,  # noqa: F401 — re-export for tests
    _enabled_channel_names,  # noqa: F401 — re-export for tests
    _entry_channels,  # noqa: F401 — re-export for tests
    _entry_model,  # noqa: F401 — re-export for tests
    _fmt_model,  # noqa: F401 — re-export for tests
    _fmt_runtime_row,  # noqa: F401 — re-export for tests
    _fmt_uptime,  # noqa: F401 — re-export for tests
    _live_active_model,  # noqa: F401 — re-export for tests
    _live_channels,  # noqa: F401 — re-export for tests
    _runtime_channels,  # noqa: F401 — re-export for tests
    build_daemon_tree,
    channel_leaf_label,
    daemon_node_label,
    runtime_session_action,
    runtime_session_records,  # noqa: F401 — re-export for tests
    runtime_session_rows,  # noqa: F401 — re-export for tests
    soft_delete_runtime,
    spawn_daemon_node,
)


@dataclass(slots=True)
class _Row:
    """`TreeNode.data` payload tagging what a row represents.

    - "section": a grouping header (current project / other projects).
    - "daemon":  a daemon; `node` is its `DaemonNode`.
    - "channel": a channel leaf; `node` is the **parent** daemon, `channel` the
      channel name — so per-channel keys can act without walking the tree."""

    kind: str
    node: DaemonNode | None = None
    channel: str | None = None


_KILL_POLL_INTERVAL = 0.05
_KILL_TIMEOUT = 5.0


class DaemonPickerScreen(Screen[None]):
    """Single-screen daemon control surface (project → daemons → channels)."""

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
    DaemonPickerScreen Tree {
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
        # OSC52 copy fallback — mirrors the main chat TUI; macOS Terminal.app
        # gets native drag-select since the app runs with mouse=False.
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
        # standalone=True → the picker IS the app (bare `veles daemon`), quit
        # exits. standalone=False → pushed via `/daemon`, quit pops back to chat.
        self._standalone = standalone
        self._project = project
        self.last_action: str = ""
        # Fixed section nodes (created once in on_mount → stable identity). The
        # "other projects" section only exists when a project is in scope.
        self._sec_current: TreeNode | None = None
        self._sec_other: TreeNode | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Label("Veles daemons", classes="title")
            self._tree: Tree[_Row] = Tree("daemons", id="daemon-tree")
            self._tree.show_root = False
            self._tree.guide_depth = 3
            yield self._tree
            self._empty = Label(
                "no daemons registered. Run `veles daemon start` in a project.",
                classes="empty",
            )
            self._empty.display = False
            yield self._empty
            self._status = Label("", classes="hint")
            yield self._status
            yield Label(
                "Enter=log · s=start · t=stop · r=restart · d=delete · "
                "c=add chan · x=rm chan · F5=refresh · q=quit",
                classes="hint",
            )
        yield Footer()

    def on_mount(self) -> None:
        # Create the fixed section nodes once. Their daemon children are
        # reconciled on every tick; the sections themselves never move.
        if self._project is not None:
            self._sec_current = self._tree.root.add(
                f"Project: {self._project.name}", data=_Row("section"), expand=True
            )
            self._sec_other = self._tree.root.add(
                "Other projects", data=_Row("section"), expand=True
            )
        else:
            # No project in scope → one flat section with every registry daemon.
            self._sec_other = self._tree.root.add(
                "Daemons", data=_Row("section"), expand=True
            )
        self._refresh()
        self._tree.focus()
        # Defer to after the first render: a node's `line` isn't computed until
        # the tree lays out, so move_cursor() inline would land on line 0 (the
        # section header) instead of the first daemon.
        self.call_after_refresh(self._move_cursor_to_first_daemon)
        self.set_interval(2.0, self._refresh)

    def _move_cursor_to_first_daemon(self) -> None:
        """Land the cursor on the first daemon row so s/t/r/d act immediately
        (the cursor defaults to the section header under a hidden root)."""
        for section in (self._sec_current, self._sec_other):
            if section is None:
                continue
            for child in section.children:
                row = child.data
                if isinstance(row, _Row) and row.kind == "daemon":
                    self._tree.move_cursor(child)
                    return

    # ---------------- refresh / reconcile ----------------

    def _refresh(self) -> None:
        tree = build_daemon_tree(self._project)
        now = time.time()
        if self._sec_current is not None:
            self._reconcile_section(self._sec_current, tree.current, now)
        if self._sec_other is not None:
            self._reconcile_section(self._sec_other, tree.others, now)
        total = len(tree.current) + len(tree.others)
        self._empty.display = total == 0
        self._tree.display = total > 0

    def _reconcile_section(
        self, section: TreeNode, nodes: list[DaemonNode], now: float
    ) -> None:
        """Add/remove/relabel daemon children of `section` in place. Cursor and
        focus survive because `Tree` tracks the cursor by node identity, so an
        untouched node keeps the cursor even as its siblings change."""
        existing: dict[str, TreeNode] = {}
        for child in list(section.children):
            row = child.data
            if isinstance(row, _Row) and row.kind == "daemon" and row.node is not None:
                existing[row.node.key] = child
        desired = {n.key for n in nodes}
        for key, child in existing.items():
            if key not in desired:
                child.remove()
        for node in nodes:
            child = existing.get(node.key)
            if child is None:
                child = section.add(
                    daemon_node_label(node, now),
                    data=_Row("daemon", node=node),
                    expand=True,
                )
            else:
                child.set_label(daemon_node_label(node, now))
                child.data = _Row("daemon", node=node)
            self._reconcile_channels(child, node)

    def _reconcile_channels(self, daemon_child: TreeNode, node: DaemonNode) -> None:
        existing: dict[str, TreeNode] = {}
        for leaf in list(daemon_child.children):
            row = leaf.data
            if isinstance(row, _Row) and row.kind == "channel" and row.channel:
                existing[row.channel] = leaf
        desired = set(node.channels)
        for chan, leaf in existing.items():
            if chan not in desired:
                leaf.remove()
        for chan in node.channels:
            leaf = existing.get(chan)
            if leaf is None:
                daemon_child.add_leaf(
                    channel_leaf_label(chan), data=_Row("channel", node=node, channel=chan)
                )
            else:
                # Refresh the parent-daemon reference (pid/status may have moved).
                leaf.data = _Row("channel", node=node, channel=chan)

    def action_refresh_list(self) -> None:
        self._refresh()

    # ---------------- cursor resolution ----------------

    def _cursor_row(self) -> _Row | None:
        node = self._tree.cursor_node
        data = node.data if node is not None else None
        return data if isinstance(data, _Row) else None

    def _cursor_daemon(self) -> DaemonNode | None:
        """The daemon under the cursor: the daemon row itself, or the parent
        daemon of a channel leaf. None on a section header / empty tree."""
        row = self._cursor_row()
        if row is not None and row.kind in ("daemon", "channel"):
            return row.node
        return None

    # ---------------- lifecycle actions ----------------

    def action_start_one(self) -> None:
        node = self._cursor_daemon()
        if not self._actionable(node, "start"):
            return
        assert node is not None
        if node.pid and is_alive(node.pid):
            self._set_action(f"{node.name}: already running", severity="warning")
            return
        if node.kind == "named":
            self._set_action(runtime_session_action(self._project, node.record, "start"))
        else:
            ok = spawn_daemon_node(node)
            self._set_action(
                f"{node.name}: start spawned" if ok else f"{node.name}: start failed",
                severity="information" if ok else "error",
            )
        self._refresh()

    def action_stop_one(self) -> None:
        node = self._cursor_daemon()
        if not self._actionable(node, "stop"):
            return
        assert node is not None
        if not (node.pid and is_alive(node.pid)):
            self._set_action(f"{node.name}: not running", severity="warning")
            return
        if node.kind == "named":
            self._set_action(runtime_session_action(self._project, node.record, "stop"))
        else:
            try:
                os.kill(node.pid, signal.SIGTERM)
                self._set_action(f"{node.name}: SIGTERM sent (stays listed, stopped)")
            except OSError as exc:
                self._set_action(f"{node.name}: stop failed: {exc}", severity="error")
        self._refresh()

    def action_restart_one(self) -> None:
        node = self._cursor_daemon()
        if not self._actionable(node, "restart"):
            return
        # Runs as a worker so the kill→wait→spawn poll uses `asyncio.sleep` and
        # never blocks the message pump (the old inline `time.sleep` froze the
        # UI for up to a second per restart — the reported "focus disappeared").
        self.run_worker(self._restart_flow(node), exclusive=True)

    async def _restart_flow(self, node: DaemonNode) -> None:
        # Order matters: confirm the old process is gone *before* spawning, or
        # the new daemon races it for the port and silently fails to bind.
        await self._kill_and_wait(node.pid)
        ok = spawn_daemon_node(node)
        self._set_action(
            f"{node.name}: restart spawned" if ok else f"{node.name}: restart failed",
            severity="information" if ok else "error",
        )
        self._refresh()

    async def _kill_and_wait(self, pid: int | None, *, timeout: float = _KILL_TIMEOUT) -> None:
        """SIGTERM `pid` and poll (non-blocking) until it dies or `timeout`."""
        if not (pid and is_alive(pid)):
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
        for _ in range(int(timeout / _KILL_POLL_INTERVAL)):
            if not is_alive(pid):
                return
            await asyncio.sleep(_KILL_POLL_INTERVAL)

    def action_delete_one(self) -> None:
        node = self._cursor_daemon()
        if node is None:
            self._set_action("no daemon selected", severity="warning")
            return
        if node.kind == "tui":
            self._set_action(
                f"{node.name}: the TUI session can't be deleted here", severity="warning"
            )
            return
        self.run_worker(self._delete_flow(node), exclusive=True)

    async def _delete_flow(self, node: DaemonNode) -> None:
        from veles.tui.wizard.screens.confirm import ConfirmScreen

        ok = await self.app.push_screen_wait(
            ConfirmScreen(
                "Delete", f"Delete '{node.name}'? (removes it from the list)", default=False
            )
        )
        if ok is not True:
            self._set_action(f"{node.name}: delete cancelled")
            return
        await self._kill_and_wait(node.pid)
        if node.kind == "named":
            soft_delete_runtime(self._project, node.record)
            self._set_action(f"{node.name}: deleted (kept in DB for history)")
        else:
            registry = DaemonRegistry.load()
            if node.entry is not None:
                registry.remove(node.entry.slug)
                registry.save()
            self._set_action(f"{node.name}: deleted")
        self._refresh()

    def _actionable(self, node: DaemonNode | None, action: str) -> bool:
        if node is None:
            self._set_action("no daemon selected", severity="warning")
            return False
        if node.kind == "tui":
            self._set_action(
                f"{node.name}: {action} not applicable to the TUI session",
                severity="warning",
            )
            return False
        return True

    # ---------------- channel actions ----------------

    def action_add_channel(self) -> None:
        target = self._channel_target()
        if target is None:
            return
        project, session, label = target
        self.run_worker(self._add_channel_flow(project, session, label), exclusive=True)

    def action_remove_channel(self) -> None:
        row = self._cursor_row()
        target = self._channel_target()
        if target is None:
            return
        project, session, label = target
        if row is not None and row.kind == "channel" and row.channel:
            # On a channel leaf → drop exactly that channel, no picker needed.
            self.run_worker(
                self._remove_specific_channel(project, session, label, row.channel),
                exclusive=True,
            )
            return
        self.run_worker(self._remove_channel_flow(project, session, label), exclusive=True)

    def _channel_target(self):
        """Resolve `(project, session | None, label)` for a channel action from
        the daemon under the cursor. Unnamed/registry daemon → its project's
        global `[channels.*]` (session=None); named daemon → (this project,
        name) → `[daemon.<name>.channels.*]`."""
        daemon = self._cursor_daemon()
        if daemon is None:
            self._notify("No daemon selected.")
            return None
        if daemon.kind == "tui":
            self._notify("Channels attach to daemon sessions, not the TUI session.")
            return None
        if daemon.kind == "named":
            if self._project is None:
                self._notify("Open the picker inside a project to manage channels.")
                return None
            return (self._project, daemon.name, daemon.name)
        from veles.core.project import load_project

        try:
            project = load_project(Path(daemon.project_path))
        except Exception:  # noqa: BLE001 — bad/missing project path
            self._notify(f"can't load project at {daemon.project_path}")
            return None
        return (project, None, daemon.name)

    async def _add_channel_flow(self, project, session, label) -> None:
        """Modal channel wizard: pick type → collect creds → write the channel
        block (global `[channels.<type>]` when session is None, else
        `[daemon.<name>.channels.<type>]`) + keychain secret."""
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
        for cred in entry.cred_fields:
            value = await self.app.push_screen_wait(
                InputScreen(f"{channel}: {cred.label}", password=cred.secret)
            )
            if value == CANCEL_SENTINEL:
                return
            value = (value or "").strip()
            if not value:
                if cred.required:
                    self._set_action(
                        f"{label}: {cred.label} required — cancelled", severity="warning"
                    )
                    return
                continue
            if cred.secret:
                secrets[cred.key] = value
            elif cred.list_value:
                config_fields[cred.key] = [x.strip() for x in value.split(",") if x.strip()]
            else:
                config_fields[cred.key] = value
        try:
            apply_channel(
                project,
                session=session,
                channel=channel,
                secrets=secrets,
                config_fields=config_fields,
            )
        except Exception as exc:  # noqa: BLE001 — surface, never crash the worker
            self._set_action(f"{label}: failed to add {channel}: {exc}", severity="error")
            return
        self._set_action(f"{label}: added {channel} channel (restart to apply)")
        self._refresh()

    async def _remove_channel_flow(self, project, session, label) -> None:
        """Pick one of the target's configured channels and drop its block."""
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
        await self._remove_specific_channel(project, session, label, channel)

    async def _remove_specific_channel(self, project, session, label, channel) -> None:
        from veles.cli.channel_wizard import delete_channel_block

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

    # ---------------- log view (Enter) ----------------

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        row = event.node.data
        if not isinstance(row, _Row):
            return
        node = row.node
        if node is None:  # section header
            return
        self._open_log(node)

    def _open_log(self, node: DaemonNode) -> None:
        from veles.daemon.paths import daemon_log_path, instance_log_path
        from veles.tui.screens.daemon_log import DaemonLogScreen

        if node.kind == "registry":
            self.app.push_screen(
                DaemonLogScreen(daemon_log_path(node.project_name), slug=node.project_name)
            )
        elif self._project is not None:
            slug = f"{self._project.name}-{node.name}"
            self.app.push_screen(
                DaemonLogScreen(
                    instance_log_path(self._project.name, node.name), slug=slug
                )
            )
        else:
            return
        self.last_action = f"{node.name}: log view opened"

    # ---------------- quit / feedback ----------------

    def action_quit(self) -> None:
        if self._standalone:
            self.app.exit(None)
        else:
            self.dismiss(None)

    def _notify(self, message: str, *, severity: str = "warning") -> None:
        """Best-effort toast — `App.notify` is unavailable headless, so never
        let a missing notifier break the action."""
        try:
            self.app.notify(message, severity=severity)
        except Exception:  # noqa: BLE001
            pass

    def _set_action(self, message: str, *, severity: str = "information") -> None:
        """Record + surface an action result: `last_action`, the status line,
        and a toast — the single place every action reports through."""
        self.last_action = message
        status = getattr(self, "_status", None)
        if status is not None:
            try:
                status.update(message)
            except Exception:  # noqa: BLE001 — status label is best-effort
                pass
        self._notify(message, severity=severity)


class DaemonPickerApp(App[None]):
    """Wrapper App that mounts the picker as its only screen.

    Native terminal text-selection is enabled by the caller passing
    `mouse=False` to `.run()` (see `cli/commands/daemon.py::_cmd_daemon_picker`),
    mirroring the main chat TUI: with mouse reporting off the terminal handles
    drag-select + the system copy shortcut, and the screen bindings add an OSC52
    fallback."""

    CSS = "Screen { background: $surface; }"

    def __init__(self, *, project=None) -> None:
        super().__init__()
        self._project = project

    def on_mount(self) -> None:
        from veles.core.user_config import load_user_config
        from veles.tui.theme_bridge import apply_to_app

        cfg = load_user_config()
        apply_to_app(self, (cfg.tui_theme if cfg else None) or "everforest")
        self.push_screen(DaemonPickerScreen(project=self._project))


__all__ = ["DaemonPickerApp", "DaemonPickerScreen"]
