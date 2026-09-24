"""Data/formatting layer for the daemon picker (M154).

Non-TUI helpers carved out of `daemon_picker.py`: the daemon tree model
and labels, runtime-session record access/actions, and per-entry
model/channel resolution. Nothing here touches Textual — `DaemonPickerScreen`
imports from this module and re-exports the names for tests.
"""

from __future__ import annotations

import json
import os
import signal
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from veles.core.defaults import DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT
from veles.core.project_config import read_provider_model_at
from veles.daemon.registry import (
    DaemonEntry,
    DaemonRegistry,
    is_alive,
    status_for,
    uptime_seconds,
)


def _fmt_uptime(seconds: float) -> str:
    if seconds <= 0:
        return "-"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def runtime_session_records(project) -> list:
    """The project's `runtime_sessions` records (named daemon sessions from
    M135 + the kind=tui row from M138). Best-effort: [] on no project or any
    store error so the picker never crashes."""
    if project is None:
        return []
    try:
        from veles.core.runtime_sessions import RuntimeSessionStore

        store = RuntimeSessionStore(project.memory_db_path)
        try:
            return store.list()
        finally:
            store.close()
    except Exception:
        return []


def runtime_session_action(project, record, action: str) -> str:
    """Start or stop a named runtime daemon session and return a status
    string for `last_action`. Start re-reads host/port from the session's
    config block; restart and delete run async in the picker itself. The
    kind=tui row and unknown actions return an explanatory no-op."""
    if record.kind != "daemon":
        return f"{record.name}: {action} not applicable to a {record.kind} session"

    from veles.core.project_config import get_daemon_session_config, load_project_config
    from veles.daemon.spawn import spawn_daemon

    block = get_daemon_session_config(load_project_config(project), record.name)
    host = str(block.get("host") or record.host or DEFAULT_DAEMON_HOST)
    port = int(block.get("port") or record.port or DEFAULT_DAEMON_PORT)
    pid = record.pid or 0

    def _spawn() -> bool:
        from veles.daemon.paths import daemon_log_path

        return (
            spawn_daemon(
                project_root=project.root,
                host=host,
                port=port,
                name=record.name,
                log_path=daemon_log_path(f"{project.name}-{record.name}"),
            )
            is not None
        )

    if action == "start":
        if pid and is_alive(pid):
            return f"{record.name}: already running"
        return f"{record.name}: start spawned" if _spawn() else f"{record.name}: start failed"
    if action == "stop":
        if not (pid and is_alive(pid)):
            return f"{record.name}: not running"
        try:
            os.kill(pid, signal.SIGTERM)
            return f"{record.name}: SIGTERM sent"
        except OSError as exc:
            return f"{record.name}: stop failed: {exc}"
    return f"{record.name}: unknown action {action!r}"


def _fetch_health(entry: DaemonEntry) -> dict | None:
    """GET the daemon's `/v1/health` payload. Short timeout: the daemon
    row updates every 2s — we'd rather show a stale value once than block
    the UI on a hung daemon. Returns None when unreachable/malformed."""
    if not entry.host or not entry.port:
        return None
    url = f"http://{entry.host}:{entry.port}/v1/health"
    try:
        with urllib.request.urlopen(url, timeout=0.5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None
    return payload if isinstance(payload, dict) else None


def _live_active_model(entry: DaemonEntry) -> str | None:
    """The daemon's current `active_model` from `/v1/health` (per-session
    override, or default if none)."""
    payload = _fetch_health(entry)
    if payload is None:
        return None
    candidate = payload.get("active_model") or payload.get("model")
    return candidate if isinstance(candidate, str) and candidate else None


def _live_channels(entry: DaemonEntry) -> list[str] | None:
    """The daemon's actually-running channels from `/v1/health` (`channels`,
    populated from `state.channel_runners`). Returns None when the daemon is
    unreachable or predates the field (→ caller falls back to config). An
    empty list is authoritative: the daemon is up and serving no channel,
    even if config declares one (e.g. its token was missing at startup)."""
    payload = _fetch_health(entry)
    if payload is None:
        return None
    chans = payload.get("channels")
    if isinstance(chans, list):
        return sorted(str(c) for c in chans)
    return None


def _entry_model(entry: DaemonEntry) -> str | None:
    """Resolve the model to show for `entry`:

    1. If the daemon is alive, ask it via `/v1/health` → the
       `active_model` field reflects the latest `/model` swap
       (Telegram or otherwise). This is what the user expects to
       see: "what the agent will actually use on the next turn".
    2. Otherwise (stopped daemon, network hiccup), fall back to the
       static project config — same as before.

    Both lookups swallow errors so the picker never crashes on a
    missing or unreachable daemon/config."""
    if entry.pid and is_alive(entry.pid):
        live = _live_active_model(entry)
        if live is not None:
            return live
    if not entry.project_path:
        return None
    try:
        return read_provider_model_at(Path(entry.project_path))
    except Exception:
        return None


def _enabled_channel_names(channels) -> list[str]:
    """Sorted names of enabled `[channels.<type>]` / `[…channels.<type>]` blocks."""
    if not isinstance(channels, dict):
        return []
    return sorted(
        name for name, cfg in channels.items() if isinstance(cfg, dict) and cfg.get("enabled")
    )


def _entry_channels(entry: DaemonEntry) -> list[str]:
    """Channels this daemon serves. Mirrors `_entry_model`:

    1. If the daemon is alive, ask it via `/v1/health` → the `channels`
       field reflects what `state.channel_runners` *actually* started.
       This is the source of truth: config can declare a channel the
       daemon skipped (missing token) or omit one added since the last
       restart, so re-deriving from config can diverge from reality.
    2. Otherwise (stopped daemon, unreachable, or a daemon predating the
       field), fall back to the enabled global `[channels.*]`.

    Defensive: [] on any error — runs every 2 s per row."""
    if entry.pid and is_alive(entry.pid):
        live = _live_channels(entry)
        if live is not None:
            return live
    if not entry.project_path:
        return []
    try:
        from veles.core.project import load_project
        from veles.core.project_config import get_section, load_project_config

        cfg = load_project_config(load_project(Path(entry.project_path)))
        return _enabled_channel_names(get_section(cfg, "channels"))
    except Exception:
        return []


def _runtime_channels(project, record) -> list[str]:
    """Enabled `[daemon.<name>.channels.*]` for a named runtime daemon session."""
    if project is None or record.kind != "daemon":
        return []
    try:
        from veles.core.project_config import get_daemon_session_config, load_project_config

        block = get_daemon_session_config(load_project_config(project), record.name)
        return _enabled_channel_names(block.get("channels"))
    except Exception:
        return []


# ---------------- project → daemons → channels tree model ----------------
#
# The picker (rewritten onto Textual's `Tree`) renders one node per daemon with
# its channels as leaf children, grouped into the current project's daemons and
# everyone else's. `DaemonNode` is the single abstraction over the two storage
# backends a daemon can live in:
#
#   - the unnamed/"default" daemon → `daemon/registry.py` (cross-project,
#     `DaemonEntry`); its channels are the project's global `[channels.*]`;
#   - a named daemon session → `runtime_sessions` (`RuntimeSessionRecord`,
#     project-local); its channels are `[daemon.<name>.channels.*]`.
#
# Plus the `kind=tui` runtime row (no channels) so Enter still opens its log —
# shown only while the interactive REPL is actually live (a stopped/orphaned tui
# row is filtered out: it isn't manageable here and the row is never deleted).


def _resolve_path(p: str | Path | None) -> Path | None:
    """`Path.resolve()` defensively — symlinks/trailing-slash must not push a
    daemon into the wrong project bucket (the mind-palace case lives under a
    symlinked obsidian vault). Returns None on falsy/garbage input."""
    if not p:
        return None
    try:
        return Path(p).resolve()
    except (OSError, ValueError, RuntimeError):
        return None


@dataclass(slots=True)
class DaemonNode:
    """One daemon in the picker tree, unifying a registry `DaemonEntry` (unnamed
    daemon) and a `RuntimeSessionRecord` (named daemon / tui session)."""

    key: str  # stable tree identity (survives in-place reconcile)
    kind: str  # "registry" | "named" | "tui"
    name: str  # display name ("default" for the project's unnamed daemon)
    host: str | None
    port: int | None
    pid: int | None
    status: str  # "running" | "stopped" | "unknown"
    model: str | None
    channels: list[str] = field(default_factory=list)
    project_path: str = ""
    project_name: str = ""
    entry: DaemonEntry | None = None  # set when kind == "registry"
    record: object | None = None  # RuntimeSessionRecord when kind in (named, tui)

    @property
    def manageable(self) -> bool:
        """tui sessions are surfaced for their log but not start/stop/restart."""
        return self.kind in ("registry", "named")


@dataclass(slots=True)
class DaemonTree:
    """Result of `build_daemon_tree`: the current project's daemons + the rest."""

    current: list[DaemonNode]
    others: list[DaemonNode]
    project_name: str | None


def _runtime_status(record) -> str:
    """Live status for a runtime-session record: trust the pid over the stored
    status, which can lag (a crashed daemon leaves status='running')."""
    if record.pid and is_alive(record.pid):
        return "running"
    return record.status if record.status in ("stopped", "error", "created") else "stopped"


def _node_from_entry(entry: DaemonEntry, *, name: str) -> DaemonNode:
    return DaemonNode(
        key=f"reg:{entry.slug}",
        kind="registry",
        name=name,
        host=entry.host,
        port=entry.port,
        pid=entry.pid or None,
        status=status_for(entry),
        model=_entry_model(entry),
        channels=_entry_channels(entry),
        project_path=entry.project_path,
        project_name=entry.project_name,
        entry=entry,
    )


def _node_from_record(project, record) -> DaemonNode:
    is_tui = record.kind == "tui"
    return DaemonNode(
        key=f"{record.kind}:{record.id}",
        kind="tui" if is_tui else "named",
        name=record.name,
        host=record.host,
        port=record.port,
        pid=record.pid,
        status=_runtime_status(record),
        model=record.model,
        channels=[] if is_tui else _runtime_channels(project, record),
        project_path=str(getattr(project, "root", "")) if project else "",
        project_name=getattr(project, "name", "") if project else "",
        record=record,
    )


def build_daemon_tree(project) -> DaemonTree:
    """Group every known daemon into (current project, other projects).

    Current project = the cross-project registry entry whose `project_path`
    resolves to `project.root` (the unnamed/"default" daemon) **plus** the
    project's `runtime_sessions` (named daemons + the tui row). Everyone else's
    registry entries land in `others`. With no project in scope, all registry
    entries are `others` and there are no runtime sessions to read."""
    registry = DaemonRegistry.load()
    proj_root = _resolve_path(getattr(project, "root", None)) if project else None

    current: list[DaemonNode] = []
    others: list[DaemonNode] = []
    for entry in registry.list():
        belongs = proj_root is not None and _resolve_path(entry.project_path) == proj_root
        if belongs:
            # The project's own unnamed daemon → label it "default".
            current.append(_node_from_entry(entry, name="default"))
        else:
            # Other projects: identify by project name, fall back to slug.
            others.append(_node_from_entry(entry, name=entry.project_name or entry.slug))

    if project is not None:
        named: list[DaemonNode] = []
        tui: list[DaemonNode] = []
        for record in runtime_session_records(project):
            node = _node_from_record(project, record)
            if node.kind == "tui":
                # The interactive session row is meaningful only while the REPL
                # is actually alive (M138: see it beside the daemons, open its
                # log). When stopped it is unmanageable noise — and because the
                # tui row is a single reused record that's never deleted, a row
                # would otherwise linger after *every* exit. Worse, a REPL that
                # was SIGKILLed/crashed never ran `mark_stopped`, leaving a stale
                # `running`/dead-pid row the user can't clear. So show tui only
                # when its pid is live (`_runtime_status` == "running").
                if node.status == "running":
                    tui.append(node)
            else:
                named.append(node)
        named.sort(key=lambda n: n.name)
        # Order: unnamed/default daemon(s) first, then named daemons, then tui.
        current.extend(named)
        current.extend(tui)

    return DaemonTree(
        current=current,
        others=others,
        project_name=getattr(project, "name", None) if project else None,
    )


def daemon_node_label(node: DaemonNode, now: float) -> str:
    """One-line label for a daemon tree node (channels render as leaves)."""
    port = node.port if node.port is not None else "-"
    model = node.model or "-"
    bits = [f"{node.status}"]
    if node.pid:
        bits.append(f"pid={node.pid}")
    if node.kind == "registry" and node.entry is not None:
        up = _fmt_uptime(uptime_seconds(node.entry, now=now))
        if up != "-":
            bits.append(f"up {up}")
    meta = "  ".join(bits)
    tag = "" if node.kind != "tui" else "  (tui)"
    return f"{node.name}{tag}   {node.host or '-'}:{port}  {meta}  {model}"


def channel_leaf_label(channel: str) -> str:
    return f"chan: {channel}"


def spawn_daemon_node(node: DaemonNode) -> bool:
    """Spawn the daemon backing `node`, detached. Registry/unnamed → host/port
    in its own project root; named → adds `--name` so the child re-attaches its
    `runtime_sessions` row. Returns True on a live child handle."""
    from veles.daemon.paths import daemon_log_path
    from veles.daemon.spawn import spawn_daemon

    host = node.host or DEFAULT_DAEMON_HOST
    port = node.port or DEFAULT_DAEMON_PORT
    if node.kind == "named":
        return (
            spawn_daemon(
                project_root=node.project_path,
                host=host,
                port=port,
                name=node.name,
                log_path=daemon_log_path(f"{node.project_name}-{node.name}"),
            )
            is not None
        )
    return (
        spawn_daemon(
            project_root=node.project_path,
            host=host,
            port=port,
            log_path=daemon_log_path(node.project_name),
        )
        is not None
    )


def soft_delete_runtime(project, record) -> None:
    """Soft-delete a `runtime_sessions` row (kept for curator/dream history).
    The kill+wait is the caller's job (the picker does it async, off the message
    pump) — this is the bare store write."""
    from veles.core.runtime_sessions import RuntimeSessionStore

    store = RuntimeSessionStore(project.memory_db_path)
    try:
        store.soft_delete(record.id)
    finally:
        store.close()
