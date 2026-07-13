"""Daemon process/lifecycle helpers (M153 — moved from `commands/daemon.py`).

Everything that deals with the daemon as an OS process: bootstrap
(ContextVars + chdir + file logging), pid/info sidecar files, the M97
cross-project registry entry, detach-and-poll startup, graceful
SIGTERM→SIGKILL stop, per-(project, name) instance path resolution and
named-session `runtime_sessions` row marking. The `cmd_daemon` verb
handlers in `commands/daemon.py` compose these; all names remain
re-exported there for historic import sites.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time

from veles.daemon.logging import setup_daemon_logging as _setup_daemon_logging
from veles.daemon.paths import (
    daemon_log_path,
)
from veles.daemon.paths import (
    info_path as _info_path,
)
from veles.daemon.paths import (
    instance_info_path as _instance_info_path,
)
from veles.daemon.paths import (
    instance_pid_path as _instance_pid_path,
)
from veles.daemon.paths import (
    pid_path as _pid_path,
)


def _bootstrap_daemon(project, *, name: str | None = None) -> None:
    """ContextVar + module registry + file logging.

    Done first so every subsequent step (token store, agent factory,
    aiohttp handlers, channel runners) sees the active project and
    routes its diagnostics into `~/.veles/logs/daemon-<slug>.log`. For a
    named session the slug is `<project>-<name>` so each instance gets
    its own log file (`instance_log_path`)."""
    from veles.cli import _load_project_modules
    from veles.core.context import set_active_project
    from veles.core.modules import set_module_registry

    set_active_project(project)
    set_module_registry(_load_project_modules(project))

    # Any relative path a tool resolves at runtime (`pwd`, `cat foo`,
    # skill scripts) should land inside the project. Without this chdir
    # the daemon would inherit the CWD of whoever spawned it — typically
    # `~` or `~/.veles` under systemd / Docker / a wizard autostart.
    os.chdir(str(project.root))

    # Read `[daemon.logging]` from project.toml so users can dial the
    # noise level / rotation cap without touching code or env vars.
    from veles.core.project_config import get_section, load_project_config

    _log_cfg = get_section(load_project_config(project), "daemon", "logging")
    log_path = _setup_daemon_logging(
        _instance_log_slug(project, name),
        level=str(_log_cfg.get("level") or "INFO"),
        max_bytes=int(_log_cfg.get("max_bytes") or 10 * 1024 * 1024),
        backup_count=int(_log_cfg.get("backup_count") or 5),
    )
    import logging as _logging

    _logging.getLogger("veles.daemon").info(
        "daemon starting in project %s at %s (cwd=%s)",
        project.name,
        project.root,
        os.getcwd(),
    )
    print(f"daemon log: {log_path}", file=sys.stderr)


def _write_pid_and_info(state, args, project, *, pid_path, info_path) -> int:
    """Single-instance lock + metadata sidecar. Returns 0 on success,
    1 when another daemon already holds the pid file."""
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    if pid_path.is_file():
        try:
            other_pid = int(pid_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            other_pid = 0
        if other_pid and _process_alive(other_pid):
            print(
                f"error: daemon already running with pid {other_pid} (see {pid_path}).",
                file=sys.stderr,
            )
            return 1
    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    info_path.write_text(
        json.dumps(
            {
                "host": args.host,
                "port": args.port,
                "project_root": str(project.root),
                "project_name": project.name,
                "started_at": state.started_at,
                "pid": os.getpid(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


def _register_in_registry(state, args, project, info_path) -> None:
    """M97 multi-daemon registry — best-effort upsert. Never blocks
    startup; a failed registry write just means `veles daemon list`
    won't see this instance, which is recoverable."""
    try:
        from veles.daemon.registry import DaemonEntry, DaemonRegistry

        registry = DaemonRegistry.load()
        registry.upsert(
            DaemonEntry(
                slug=project.name,
                project_path=str(project.root),
                project_name=project.name,
                pid=os.getpid(),
                host=args.host,
                port=args.port,
                started_at=state.started_at,
                info_file=str(info_path),
            )
        )
        registry.save()
    except OSError as exc:
        print(f"warning: registry update failed: {exc}", file=sys.stderr)


def _cleanup_daemon_exit(
    project, *, pid_path, info_path, store, jobs_store, name: str | None = None
) -> None:
    """Best-effort teardown in `finally`. Each step swallows OSError
    so a partial cleanup doesn't mask the underlying exit reason.

    The M97 registry entry is **deliberately left in place** on exit (the
    pid/info sidecars are removed, but the registry row stays): a stopped
    daemon should remain visible in `veles daemon list` / the TUI picker
    showing `stopped` (`status_for` derives that from `is_alive(pid)`), and
    disappear only on an explicit `veles daemon delete` / picker `d`. A later
    start re-`upsert`s the same slug. Named sessions mark their
    `runtime_sessions` row stopped (this runs in the foreground child, which
    owns the row) — same "stop keeps, delete removes" model — and were never in
    the M97 registry anyway (slug-keyed → would clobber siblings)."""
    pid_path.unlink(missing_ok=True)
    info_path.unlink(missing_ok=True)
    if name is not None:
        _mark_session_stopped(project, name)
    store.close()
    jobs_store.close()


def _detach_and_report(
    args: argparse.Namespace, project, *, name: str | None = None, timeout: float = 5.0
) -> int:
    """M113: spawn `veles daemon start --foreground` detached, then
    poll until the child has fully bootstrapped (or failed). Parent
    prints a summary and returns to the shell.

    "Bootstrapped" means TWO things (live 2026-07-09): the child wrote its
    pid file AND it actually LISTENS on the bind port. The pid file alone is
    not proof of life — a child used to appear (pid written), get reported
    as "daemon started", then die one second later on `web.run_app` (port
    still held by a dying predecessor), leaving a registry entry pointing
    at a corpse. The child's stdout/stderr are routed into the daemon log
    via `spawn_daemon(log_path=…)` so that crash is visible in the tail we
    print on failure.

    The polling loop is needed because `subprocess.Popen` returns
    immediately, but the child still has to import veles, resolve the
    project, set up logging, build the aiohttp app, write the pid
    file, and call `web.run_app`. `timeout` (5s default) is generous —
    typical startup is ~300-500 ms.

    For a named session the parent watches the per-instance pid path and
    re-execs the child with `--name <name>` so both agree on that path.
    """
    from veles.daemon.spawn import spawn_daemon

    pid_path, info_path = _resolve_instance_paths(project, name)
    log_slug = _instance_log_slug(project, name)
    if pid_path.is_file():
        try:
            other = int(pid_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            other = 0
        if other and _process_alive(other):
            print(
                f"error: daemon already running with pid {other} (see {pid_path}).",
                file=sys.stderr,
            )
            return 1

    proc = spawn_daemon(
        project_root=project.root,
        host=args.host,
        port=args.port,
        name=name,
        log_path=daemon_log_path(log_slug),
    )
    if proc is None:
        print("error: failed to spawn `veles daemon start --foreground`.", file=sys.stderr)
        return 1

    # Phase 1: poll until the child writes its pid file AND the pid is alive.
    deadline = time.time() + timeout
    child_pid: int | None = None
    while time.time() < deadline:
        if pid_path.is_file():
            try:
                written = int(pid_path.read_text(encoding="utf-8").strip() or "0")
            except ValueError:
                written = 0
            if written and written != os.getpid() and _process_alive(written):
                child_pid = written
                break
        if proc.poll() is not None:
            # Child exited before writing its pid file — startup failure.
            break
        time.sleep(0.1)

    if child_pid is None:
        print(
            f"error: daemon did not start within {timeout:g}s. Recent log:",
            file=sys.stderr,
        )
        _print_log_tail(log_slug)
        return 1

    # Phase 2: the pid file is necessary but not sufficient — wait until OUR
    # child serves `/v1/health` (matched by pid) before declaring success. A
    # plain TCP probe is not enough: in the live failure a dying predecessor
    # still held the port, so the socket connected fine while the new child
    # crashed on bind. A child that dies here is a loud failure with the log
    # tail, not a phantom "daemon started".
    connect_host = "127.0.0.1" if args.host in ("0.0.0.0", "::", "") else args.host
    health_url = f"http://{connect_host}:{int(args.port)}/v1/health"
    serving = False
    imposter_pid: int | None = None
    while time.time() < deadline:
        # `proc.poll()` reaps our direct child (a dead-but-unreaped zombie still
        # passes the kill(pid, 0) probe); `_process_alive` covers a pid-file pid
        # that isn't our Popen child.
        if proc.poll() is not None or not _process_alive(child_pid):
            print(
                f"error: daemon (pid {child_pid}) died while starting up. Recent log:",
                file=sys.stderr,
            )
            _print_log_tail(log_slug)
            return 1
        seen_pid = _health_pid(health_url)
        if seen_pid == child_pid:
            serving = True
            break
        if seen_pid is not None:
            imposter_pid = seen_pid
        time.sleep(0.1)
    if not serving:
        if imposter_pid is not None:
            print(
                f"error: {connect_host}:{args.port} is served by another process "
                f"(pid {imposter_pid}) and the new daemon (pid {child_pid}) never "
                f"took over within {timeout:g}s. Recent log:",
                file=sys.stderr,
            )
        else:
            print(
                f"error: daemon (pid {child_pid}) is up but not serving on "
                f"{connect_host}:{args.port} after {timeout:g}s. Recent log:",
                file=sys.stderr,
            )
        _print_log_tail(log_slug)
        return 1

    host = args.host
    port = args.port
    try:
        info_data = json.loads(info_path.read_text(encoding="utf-8"))
        host = info_data.get("host", host)
        port = info_data.get("port", port)
    except (OSError, json.JSONDecodeError):
        pass
    log_path = daemon_log_path(log_slug)
    print(f"daemon started (pid {child_pid}) on http://{host}:{port}/")
    print(f"log: {log_path}")
    return 0


def _health_pid(url: str) -> int | None:
    """GET the daemon's unauthenticated `/v1/health` and return the serving
    process's pid — None when nothing (or something that isn't a Veles
    daemon) answers. Sync on purpose: the detach parent is a plain CLI."""
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=0.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return int(data.get("pid") or 0) or None
    except Exception:
        return None


def _print_log_tail(log_slug: str, *, lines: int = 20) -> None:
    try:
        log_text = daemon_log_path(log_slug).read_text(encoding="utf-8")
        print("\n".join(log_text.splitlines()[-lines:]), file=sys.stderr)
    except OSError:
        print("  (no log file written yet)", file=sys.stderr)


def _stop_status_paths(args: argparse.Namespace):
    """Resolve (pid_path, info_path) for stop/status from the cwd project:
    per-(slug, name) instance paths with `--name`, else the project's
    unnamed-daemon paths (per-slug since M209 — stop/status address THIS
    project's daemon; other projects' daemons are managed via `veles
    daemon list/restart/delete`). Returns None outside a project."""
    from veles.cli import _resolve_active_project

    project = _resolve_active_project(args)
    if project is None:
        print("error: no Veles project found here.", file=sys.stderr)
        return None
    return _resolve_instance_paths(project, getattr(args, "name", None) or None)


def _restart_named_session(args: argparse.Namespace, name: str) -> int:
    """`veles daemon restart --name <name>` — stop this project's named
    session (per-instance pid) and respawn it from its `[daemon.<name>]`
    block. Project-local; does not touch the M97 cross-project registry."""
    from veles.cli import _resolve_active_project
    from veles.core.project_config import get_daemon_session_config, load_project_config
    from veles.daemon.spawn import spawn_daemon

    project = _resolve_active_project(args)
    if project is None:
        print("error: no Veles project found here.", file=sys.stderr)
        return 2
    pid_path, _info = _resolve_instance_paths(project, name)
    if pid_path.is_file():
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            pid = 0
        if pid and _process_alive(pid):
            _graceful_stop(pid, timeout=5.0)
    block = get_daemon_session_config(load_project_config(project), name)
    host = str(block.get("host") or "127.0.0.1")
    port = int(block.get("port") or 8765)
    proc = spawn_daemon(
        project_root=project.root,
        host=host,
        port=port,
        name=name,
        log_path=daemon_log_path(_instance_log_slug(project, name)),
    )
    if proc is None:
        print("error: failed to respawn named daemon session.", file=sys.stderr)
        return 1
    print(f"restarted daemon session {name!r} (new pid {proc.pid}).")
    return 0


def _graceful_stop(pid: int, *, timeout: float = 10.0) -> bool:
    """Send SIGTERM, poll until the pid exits or `timeout` elapses,
    escalate to SIGKILL as a last resort. Returns True on clean exit,
    False if even SIGKILL didn't bring the process down (rare — usually
    means the process is a zombie waiting on parent reap)."""
    from veles.daemon.registry import is_alive

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True  # already gone
    except OSError as exc:
        print(f"warning: failed to SIGTERM pid {pid}: {exc}", file=sys.stderr)
        return False

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_alive(pid):
            return True
        time.sleep(0.1)
    # Escalate.
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError as exc:
        print(f"warning: failed to SIGKILL pid {pid}: {exc}", file=sys.stderr)
        return False
    # Brief wait after SIGKILL for the kernel to reap.
    for _ in range(20):
        if not is_alive(pid):
            return True
        time.sleep(0.05)
    return False


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _resolve_instance_paths(project, name: str | None):
    """Return ``(pid_path, info_path)``: per-(project, name) instance paths
    when ``name`` is set, else the project's unnamed-daemon paths — per-slug
    since M209, so one unnamed daemon per *project*, not per machine."""
    if name:
        return (
            _instance_pid_path(project.name, name),
            _instance_info_path(project.name, name),
        )
    return (_pid_path(project.name), _info_path(project.name))


def _instance_log_slug(project, name: str | None) -> str:
    """Slug for `setup_daemon_logging`/`daemon_log_path`. Composite for named
    sessions so `daemon_log_path(f"{slug}-{name}")` == `instance_log_path`."""
    return f"{project.name}-{name}" if name else project.name


def _mark_session_running(project, name: str | None, *, pid: int) -> None:
    """Best-effort: stamp the named ``runtime_sessions`` row 'running'. No-op
    when unnamed or the row is absent — the legacy daemon has no store row."""
    if not name:
        return
    from veles.core.runtime_sessions import RuntimeSessionStore

    store = RuntimeSessionStore(project.memory_db_path)
    try:
        rec = store.get_by_name(name, kind="daemon")
        if rec is not None:
            store.mark_started(rec.id, pid=pid)
    finally:
        store.close()


def _mark_session_stopped(project, name: str | None) -> None:
    """Companion to `_mark_session_running` — runs in the child's exit path."""
    if not name:
        return
    from veles.core.runtime_sessions import RuntimeSessionStore

    store = RuntimeSessionStore(project.memory_db_path)
    try:
        rec = store.get_by_name(name, kind="daemon")
        if rec is not None:
            store.mark_stopped(rec.id)
    finally:
        store.close()
