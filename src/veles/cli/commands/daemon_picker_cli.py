"""Keyboard-only daemon picker for bare `veles daemon`, on prompt_toolkit.

Replaces the retired Textual picker (M197). Renders the project→daemons→
channels tree from `veles.daemon.picker_data.build_daemon_tree` and drives
the same Textual-free lifecycle helpers (`spawn_daemon_node`,
`runtime_session_action`, `soft_delete_runtime`). Structured as a loop of
one-shot `prompt_toolkit` Applications (mirroring the REPL's inline
`_choice_picker`): each keypress exits the Application returning the chosen
action + the selected daemon, the outer loop performs it (blocking kill/wait
is fine in a standalone CLI), prints a status line, then re-renders.

Bindings: ↑/↓ move · s start · t stop · r restart · d delete (confirm) ·
Enter show log path · F5 refresh · q/Esc quit.

Dropped vs the Textual picker (v1): channel add/remove (manage via
`veles channel add` / the project wizard) and the live in-app log tail
(Enter now prints the log path; use `veles daemon status`).
"""

from __future__ import annotations

import contextlib
import os
import signal
import time

from veles.daemon.picker_data import (
    DaemonNode,
    build_daemon_tree,
    channel_leaf_label,
    daemon_node_label,
    is_alive,
    runtime_session_action,
    soft_delete_runtime,
    spawn_daemon_node,
)

_KILL_POLL_INTERVAL = 0.05
_KILL_TIMEOUT = 5.0


def _resolve_theme():
    """Active TUI theme (user config → everforest fallback), reused so the
    picker's colours match the REPL."""
    from veles.cli.tui_theme import THEMES, load_theme
    from veles.core.user_config import load_user_config

    cfg = load_user_config()
    name = (getattr(cfg, "tui_theme", "") if cfg else "") or "everforest"
    return load_theme(name) or THEMES["everforest"]


def _flatten(tree) -> list[DaemonNode]:
    """Selectable daemon nodes in display order: current project first,
    then other projects."""
    return [*tree.current, *tree.others]


def _run_picker_once(theme, tree, sel: int) -> tuple[str, int]:
    """Render the tree once and block until a key exits. Returns
    (action, selection-index). Actions: start/stop/restart/delete/log/
    refresh/quit."""
    from prompt_toolkit import Application
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    nodes = _flatten(tree)
    state = {"sel": sel if nodes else 0, "action": "quit"}
    kb = KeyBindings()

    @kb.add("up")
    def _u(e) -> None:
        if nodes:
            state["sel"] = (state["sel"] - 1) % len(nodes)

    @kb.add("down")
    def _d(e) -> None:
        if nodes:
            state["sel"] = (state["sel"] + 1) % len(nodes)

    def _bind(key: str, action: str) -> None:
        @kb.add(key)
        def _(e, _action=action) -> None:
            state["action"] = _action
            e.app.exit()

    _bind("s", "start")
    _bind("t", "stop")
    _bind("r", "restart")
    _bind("d", "delete")
    _bind("enter", "log")
    _bind("f5", "refresh")

    @kb.add("q")
    @kb.add("escape")
    @kb.add("c-c")
    def _q(e) -> None:
        state["action"] = "quit"
        e.app.exit()

    now = time.time()

    def _text():
        lines: list[tuple[str, str]] = [("bold", "veles daemons\n\n")]
        if not nodes:
            lines.append(("ansibrightblack", "  no daemons registered.\n"))
        idx = 0
        proj = tree.project_name or "current project"
        if tree.current:
            lines.append((f"bold {theme.accent}", f"  {proj}\n"))
            idx = _render_section(lines, tree.current, idx, state["sel"], theme, now)
        if tree.others:
            lines.append((f"bold {theme.accent}", "  other projects\n"))
            idx = _render_section(lines, tree.others, idx, state["sel"], theme, now)
        lines.append(
            (
                "ansibrightblack",
                "\n  ↑↓ move · s start · t stop · r restart · d delete · "
                "Enter log · F5 refresh · q quit\n",
            )
        )
        return FormattedText(lines)

    Application(
        layout=Layout(Window(FormattedTextControl(_text, focusable=True))),
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
    ).run()
    return str(state["action"]), int(state["sel"])


def _render_section(lines, section, idx, sel, theme, now) -> int:
    for node in section:
        selected = idx == sel
        style = f"bold {theme.accent}" if selected else ""
        marker = "❯" if selected else " "
        lines.append((style, f"  {marker} {daemon_node_label(node, now)}\n"))
        for chan in node.channels:
            lines.append(("ansibrightblack", f"        {channel_leaf_label(chan)}\n"))
        idx += 1
    return idx


def _kill_and_wait(pid: int | None, *, timeout: float = _KILL_TIMEOUT) -> None:
    """SIGTERM `pid` and poll until it dies or `timeout` (blocking — fine in a
    standalone CLI picker)."""
    if not (pid and is_alive(pid)):
        return
    with contextlib.suppress(OSError):
        os.kill(pid, signal.SIGTERM)
    for _ in range(int(timeout / _KILL_POLL_INTERVAL)):
        if not is_alive(pid):
            return
        time.sleep(_KILL_POLL_INTERVAL)


def _do_start(project, node: DaemonNode) -> str:
    if not node.manageable:
        return f"{node.name}: start not applicable to a {node.kind} session"
    if node.pid and is_alive(node.pid):
        return f"{node.name}: already running"
    if node.kind == "named":
        return runtime_session_action(project, node.record, "start")
    return (
        f"{node.name}: start spawned" if spawn_daemon_node(node) else f"{node.name}: start failed"
    )


def _do_stop(project, node: DaemonNode) -> str:
    if not node.manageable:
        return f"{node.name}: stop not applicable to a {node.kind} session"
    if not (node.pid and is_alive(node.pid)):
        return f"{node.name}: not running"
    if node.kind == "named":
        return runtime_session_action(project, node.record, "stop")
    try:
        os.kill(node.pid, signal.SIGTERM)
        return f"{node.name}: SIGTERM sent (stays listed, stopped)"
    except OSError as exc:
        return f"{node.name}: stop failed: {exc}"


def _do_restart(project, node: DaemonNode) -> str:
    del project
    if not node.manageable:
        return f"{node.name}: restart not applicable to a {node.kind} session"
    _kill_and_wait(node.pid)
    ok = spawn_daemon_node(node)
    return f"{node.name}: restart spawned" if ok else f"{node.name}: restart failed"


def _do_delete(project, node: DaemonNode, theme) -> str:
    if node.kind == "tui":
        return f"{node.name}: the interactive session can't be deleted here"
    from veles.cli.repl.simple import _choice_picker

    answer = _choice_picker(
        theme, f"Delete '{node.name}'? (removes it from the list)", ["Yes", "No"]
    )
    if answer != "Yes":
        return f"{node.name}: delete cancelled"
    _kill_and_wait(node.pid)
    if node.kind == "named":
        soft_delete_runtime(project, node.record)
        return f"{node.name}: deleted (kept in DB for history)"
    from veles.daemon.registry import DaemonRegistry

    registry = DaemonRegistry.load()
    if node.entry is not None:
        registry.remove(node.entry.slug)
        registry.save()
    return f"{node.name}: deleted"


def _log_hint(node: DaemonNode) -> str:
    """Print-friendly pointer to a daemon's log (replaces the Textual live
    tail). Registry/unnamed → cross-project `daemon-<slug>.log`; named → the
    per-session `daemon-<slug>-<name>.log`."""
    from veles.daemon.paths import daemon_log_path, instance_log_path

    if node.kind == "registry" and node.entry is not None:
        path = daemon_log_path(node.entry.slug)
    elif node.kind == "named" and node.project_name:
        # A named daemon logs to daemon-<project_slug>-<name>.log (mirrors
        # `_instance_log_slug` = f"{project.name}-{name}").
        path = instance_log_path(node.project_name, node.name)
    else:
        return f"{node.name}: no dedicated log (try `veles daemon status`)"
    return f"{node.name}: log at {path}  (tail it, or `veles daemon status`)"


def run_daemon_picker(project, theme=None, console=None) -> None:
    """Interactive loop for bare `veles daemon`. Caller must have verified a
    real TTY (the non-TTY path prints the daemon list instead). Standalone —
    no REPL status Live to suspend, so the picker Application owns the
    terminal directly."""
    if theme is None:
        theme = _resolve_theme()
    if console is None:
        from rich.console import Console

        console = Console()

    sel = 0
    while True:
        tree = build_daemon_tree(project)
        nodes = _flatten(tree)
        if sel >= len(nodes):
            sel = max(0, len(nodes) - 1)
        action, sel = _run_picker_once(theme, tree, sel)
        if action == "quit":
            return
        if action == "refresh":
            continue
        if not nodes:
            continue
        node = nodes[sel]
        if action == "start":
            msg = _do_start(project, node)
        elif action == "stop":
            msg = _do_stop(project, node)
        elif action == "restart":
            msg = _do_restart(project, node)
        elif action == "delete":
            msg = _do_delete(project, node, theme)
        elif action == "log":
            msg = _log_hint(node)
        else:
            continue
        console.print(msg, style=theme.muted, markup=False)


__all__ = ["run_daemon_picker"]
