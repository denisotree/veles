"""`veles daemon` (M51) — long-lived agent server + token CRUD.

Subcommands:

    veles daemon start [--host HOST] [--port PORT]
    veles daemon stop
    veles daemon status
    veles daemon token add <NAME>
    veles daemon token list
    veles daemon token remove <NAME>

`start` detaches by default (M113): the parent spawns itself with
`--foreground` via `daemon/spawn.py::spawn_daemon`, polls the pid file
until the child is up, prints a summary, and returns the shell to the
user. Pass `--foreground` explicitly for terminal-attached mode (e.g.
`systemctl Type=simple`, Docker, interactive debugging) — there the
process stays in the current terminal and Ctrl+C / `daemon stop`
terminates it.

Project scope: a single project per daemon, resolved at startup via the
same `_resolve_active_project` helper used by every other verb.

M153 decomposition: this module keeps only the `cmd_daemon` dispatcher
and the thin `_cmd_daemon_*` verb handlers. The moved clusters:

- building agents for turns (`FactorySettings`, `make_agent_factory`, the
  post-turn and verify hooks, …) → `veles.daemon.agent_factory`, and the
  job/reminder/dream runners → `veles.daemon.background`;
- process/lifecycle helpers (pid/info sidecars, registry, detach,
  graceful stop, instance paths, named-session marking) →
  `veles.cli.commands.daemon_lifecycle`;
- token-store bootstrap + `token` CRUD →
  `veles.cli.commands.daemon_tokens`.

Import those names from their own modules; this one imports only what it uses.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import sys
import time
from pathlib import Path

from aiohttp import web

from veles.cli.commands.daemon_lifecycle import (
    _bootstrap_daemon,
    _cleanup_daemon_exit,
    _detach_and_report,
    _graceful_stop,
    _mark_session_running,
    _register_in_registry,
    _resolve_instance_paths,
    _restart_named_session,
    _stop_status_paths,
    _write_pid_and_info,
)
from veles.cli.commands.daemon_tokens import _cmd_daemon_token, _initialise_token_store
from veles.core.defaults import DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT
from veles.daemon.agent_factory import (
    factory_settings_from_args,
    make_agent_factory,
    make_post_turn_hook,
    make_verify_hook,
    make_worker_agent_factory,
)
from veles.daemon.background import attach_background_runners
from veles.daemon.paths import daemon_log_path, read_pid
from veles.daemon.registry import is_alive


def cmd_daemon(args: argparse.Namespace) -> int:
    sub = args.daemon_command
    if sub is None:
        # M98: `veles daemon` (bare) opens the TUI picker.
        return _cmd_daemon_picker(args)
    if sub == "start":
        return _cmd_daemon_start(args)
    if sub == "stop":
        return _cmd_daemon_stop(args)
    if sub == "status":
        return _cmd_daemon_status(args)
    if sub == "token":
        return _cmd_daemon_token(args)
    if sub == "list":
        return _cmd_daemon_list(args)
    if sub == "restart":
        return _cmd_daemon_restart(args)
    if sub == "delete":
        return _cmd_daemon_delete(args)
    if sub == "session":
        from veles.cli.commands.daemon_session import cmd_daemon_session

        return cmd_daemon_session(args)
    print(f"error: unknown daemon subcommand: {sub!r}", file=sys.stderr)
    return 2


# ---- start / stop / status ----


def _warn_on_security_config_typos(project) -> None:
    """M201: before the daemon serves unattended, loudly flag unknown keys in
    security-relevant config sections — a typo (`whitlist` → `whitelist`)
    silently disables an access control (e.g. leaves a channel open to all)."""
    try:
        from veles.core.config_schema import validate_config
        from veles.core.project_config import load_project_config

        findings = validate_config(load_project_config(project))
    except Exception:
        return
    for f in findings:
        print(
            f"WARNING: config [{f.section}] has unknown key {f.key!r} — likely a typo, "
            f"silently ignored. Known keys: {', '.join(f.known)}. "
            "Fix before serving, or a security control may be disabled.",
            file=sys.stderr,
        )


def _cmd_daemon_start(args: argparse.Namespace) -> int:
    from veles.cli._console import ensure_api_key as _ensure_api_key
    from veles.cli._project import _resolve_active_project
    from veles.core.memory import SessionStore
    from veles.daemon.server import build_state, make_app

    project = _resolve_active_project(args)
    if project is None:
        # M129: bootstrap like every other agent command. `daemon` is
        # dispatched before main()'s generic wizard path, so without this
        # `veles daemon start` dead-ended on an uninitialised dir while a
        # bare `veles` ran the wizard — a confusing asymmetry. Suppress the
        # wizard's own daemon-autostart: we own the daemon lifecycle here,
        # and the project's single-instance pid would otherwise race a
        # double-start.
        from veles.cli.project_wizard import maybe_run_project_wizard

        args._suppress_wizard_daemon_autostart = True
        project = maybe_run_project_wizard(args, Path.cwd())
    if project is None:
        if getattr(args, "_wizard_user_chose_no_project", False):
            print("<no project initialised; nothing to do.>", file=sys.stderr)
            return 0
        print(
            f"error: no Veles project found at {Path.cwd()} or any parent.\n"
            "       Run `veles init` to create one in the current directory.",
            file=sys.stderr,
        )
        return 2

    _warn_on_security_config_typos(project)

    # Named daemon session (M135): must already be declared (config block or
    # runtime_sessions row). Its `[daemon.<name>]` block is the declarative
    # source-of-truth for host/port — resolve them here so the whole
    # downstream flow (pid/info write, run_app, detach report) uses the right
    # values without further plumbing. provider/model flow through the
    # resolver's `daemon_session=` layer (M134).
    name = getattr(args, "name", None)
    if name:
        from veles.core.project_config import (
            get_daemon_session_config,
            load_project_config,
        )
        from veles.core.runtime_sessions import RuntimeSessionStore

        block = get_daemon_session_config(load_project_config(project), name)
        rt_store = RuntimeSessionStore(project.memory_db_path)
        try:
            row = rt_store.get_by_name(name, kind="daemon")
        finally:
            rt_store.close()
        if row is None and not block:
            print(
                f"error: no daemon session named {name!r}. "
                f"Create it first: `veles daemon session create {name}`.",
                file=sys.stderr,
            )
            return 2

    # M173: host/port cascade — explicit flag > config block > 127.0.0.1:8765.
    # Generalised from the named-session-only override so the unnamed daemon
    # honours the `[daemon] host/port` the project wizard writes (previously it
    # silently ignored them and always bound the argparse default).
    _resolve_daemon_bind(args, project, name)

    # M130: resolve via the unified cascade (project [engine] → user
    # [user] → DEFAULT) so the API-key check targets the provider the
    # daemon will actually boot on — not a bare `args.provider` that is
    # `None` when no `--provider` was passed. M135: named sessions add a
    # `[daemon.<name>] provider` layer below an explicit `--provider`.
    from veles.core.model_resolver import resolve_effective_provider

    provider_name = resolve_effective_provider(args, project, daemon_session=name)
    if not _ensure_api_key(provider_name, project=project.name):
        return 2
    # M184: reflect the resolved provider (incl. any `[daemon.<name>]` override)
    # back into `args`, mirroring `cmd_run`. The post-turn learning loop — built
    # below and reused by every channel via `state.post_turn_hook` — gates the
    # continuous curator on `args.provider`; a bare None silently disables it.
    args.provider = provider_name

    # M173/M208: in an already-initialised project with no channel configured,
    # run the Textual start wizard (bind + channel) before we detach. The
    # fresh-project path already offers a channel inside the project wizard;
    # this closes the gap for `daemon start` on an existing project. Parent
    # only — the detached child re-enters with `--foreground` and must not
    # re-prompt.
    if not getattr(args, "foreground", False):
        _maybe_run_start_wizard(args, project, session=name)

    # M113: detach by default. The child re-enters this function with
    # `--foreground` set and falls through to the real server loop.
    if not getattr(args, "foreground", False):
        return _detach_and_report(args, project, name=name)

    _bootstrap_daemon(project, name=name)
    token_store = _initialise_token_store()

    store = SessionStore(project.memory_db_path)
    worker_agent_factory = make_worker_agent_factory(
        args, project=project, store=store, daemon_session=name
    )
    # M126: build state first (with a placeholder) so the agent factory
    # closure can capture it for per-session override lookup. Replace
    # the factory immediately after.
    settings_for_health = factory_settings_from_args(args, project, daemon_session=name)
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=lambda *a, **kw: None,  # placeholder, replaced below
        provider=provider_name,
        default_model=settings_for_health.model,
        session_name=name,
    )
    agent_factory = make_agent_factory(
        args, project=project, store=store, state=state, daemon_session=name
    )
    state.agent_factory = agent_factory
    state.post_turn_hook = make_post_turn_hook(args, project)
    state.verify_hook = make_verify_hook(args, project=project, store=store, daemon_session=name)
    state.worker_agent_factory = worker_agent_factory
    jobs_store = attach_background_runners(
        state, project, agent_factory, provider_name, args=args, store=store
    )

    app = make_app(state)

    pid_path, info_path = _resolve_instance_paths(project, name)
    rc = _write_pid_and_info(state, args, project, pid_path=pid_path, info_path=info_path)
    if rc != 0:
        store.close()
        jobs_store.close()
        return rc
    if name is None:
        _register_in_registry(state, args, project, info_path)
    else:
        # Child owns the runtime_sessions row; mark it running with our pid and
        # the settings this process actually resolved, so the picker shows them.
        _mark_session_running(
            project,
            name,
            pid=os.getpid(),
            host=args.host,
            port=args.port,
            provider=provider_name,
            model=settings_for_health.model,
        )

    print(
        f"veles daemon listening on http://{args.host}:{args.port}/ "
        f"(project: {project.name}, root: {project.root})",
        file=sys.stderr,
    )
    try:
        _run_app_logged(app, host=args.host, port=args.port)
    finally:
        _cleanup_daemon_exit(
            project,
            pid_path=pid_path,
            info_path=info_path,
            store=store,
            jobs_store=jobs_store,
            name=name,
        )
    return 0


def _run_app_logged(app, *, host, port) -> None:
    """`web.run_app` with crashes written to the daemon log before re-raising.

    A detached child's stderr historically went to /dev/null, so a failure
    inside run_app — most commonly "address already in use" while a dying
    predecessor still holds the socket — killed the daemon with zero trace
    (live 2026-07-09: the parent had already said "daemon started", and the
    log ended at "daemon starting"). `spawn_daemon(log_path=…)` now catches
    raw stderr too; this hook puts a structured traceback in the rotated log
    regardless of fd plumbing."""
    import logging

    try:
        web.run_app(
            app,
            host=host,
            port=port,
            print=lambda *_, **__: None,
            handle_signals=True,
        )
    except Exception:
        logging.getLogger("veles.daemon").exception(
            "daemon crashed in run_app (host=%s port=%s)", host, port
        )
        raise


def _resolve_daemon_bind(args: argparse.Namespace, project, name: str | None) -> None:
    """Apply the host/port cascade in place on `args` (M173): an explicit
    `--host`/`--port` wins; else the project's `[daemon]` (unnamed) or
    `[daemon.<name>]` (named session) config block; else 127.0.0.1 and the
    first free port from 8765 upward (M209 — daemons of different projects
    no longer contend for one hardcoded port; each daemon's effective port
    is persisted in its registry entry / info sidecar, which is where the
    picker and `daemon restart` read it back).

    Argparse defaults host/port to None so "not given" is distinguishable from
    a value that equals the hardcoded default — mirroring the model/provider
    cascade."""
    from veles.core.project_config import load_project_config

    cfg = load_project_config(project)
    if name:
        from veles.core.project_config import get_daemon_session_config

        block = get_daemon_session_config(cfg, name)
    else:
        block = cfg.get("daemon")
        if not isinstance(block, dict):
            block = {}
    if args.host is None:
        args.host = str(block.get("host") or "127.0.0.1")
    if args.port is None:
        cfg_port = block.get("port")
        if cfg_port is None:
            args.port = _find_free_port(args.host)
        else:
            args.port = _resolve_config_port(int(cfg_port), args.host, project)


def _resolve_config_port(port: int, host: str, project) -> int:
    """M211: a `[daemon] port` from config is normally used verbatim — but the
    project wizard writes its default (8765) into every project it creates, so
    two wizard-made projects "pin" the same port without the user ever choosing
    one (live 2026-07-13: the second project's daemon crashed on bind with
    `address already in use`). When the configured port is busy AND its
    occupant identifies as the veles daemon of a *different* project, treat it
    as that default collision: roll to the next free port with a loud warning.
    Any other occupant (foreign service, dying predecessor, same project —
    the pid-file check owns that message) keeps the pin, and the detach
    health-probe reports the bind failure loudly rather than silently drifting
    off a port the user may have wired into a proxy or firewall rule."""
    if _port_is_free(host, port):
        return port
    occupant = _veles_daemon_on_port(host, port)
    if occupant is None:
        return port
    other_name, other_root = occupant
    if other_name == project.name or other_root == str(project.root):
        return port
    free = _find_free_port(host, start=port + 1)
    print(
        f"warning: [daemon] port {port} is already used by the daemon of project "
        f"{other_name!r} ({other_root}); starting on {free} instead. Give each "
        "project a unique `[daemon] port` in .veles/config.toml to silence this.",
        file=sys.stderr,
    )
    return free


def _veles_daemon_on_port(host: str, port: int) -> tuple[str, str] | None:
    """`(project_name, project_root)` of the veles daemon serving `host:port`,
    or None when the occupant isn't identifiable as one. Sync + short timeout
    on purpose — this runs in the CLI parent, mirroring `_health_pid`."""
    import urllib.request

    connect_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    url = f"http://{connect_host}:{int(port)}/v1/health"
    try:
        with urllib.request.urlopen(url, timeout=0.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        name = data.get("project")
        root = data.get("project_root")
        if not name and not root:
            return None
        return (str(name or ""), str(root or ""))
    except Exception:
        return None


def _port_is_free(host: str, port: int) -> bool:
    """Can we bind `host:port` right now? Strict probe (no SO_REUSEADDR) so a
    listener — or a lingering TIME_WAIT socket — reads as busy, the same view
    `web.run_app` will get a moment later."""
    import socket

    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
    except OSError:
        return False
    return True


def _find_free_port(host: str, *, start: int = DEFAULT_DAEMON_PORT, tries: int = 100) -> int:
    """First bindable port in [start, start+tries) — the M209 multi-project
    default. Racy by nature (another process can grab the port between probe
    and bind), which is fine: the detach health-probe reports a lost race
    loudly. Falls back to `start` when the whole window is busy — same loud
    failure path."""
    for port in range(start, start + tries):
        if _port_is_free(host, port):
            return port
    return start


def _maybe_run_start_wizard(args: argparse.Namespace, project, *, session: str | None) -> None:
    """M208: an interactive `daemon start` with no channel configured walks the
    Textual start wizard — bind (host/port, persisted to the project config)
    then the registry-driven channel flow, the same modal shape as the project
    wizard and the daemon picker — instead of a bare stdin `[y/N]` prompt
    (live 2026-07-09). Host/port picked in the wizard apply to THIS launch.

    Skips silently when non-interactive, opted out (`--no-wizard` /
    `VELES_NO_WIZARD=1`), or a channel already exists. Falls back to the
    legacy stdin offer (M173, shared `add_channel` flow) when Textual is
    unavailable or the TUI fails."""
    if getattr(args, "no_wizard", False) or os.environ.get("VELES_NO_WIZARD") == "1":
        return
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return
    from veles.core.project_config import get_section, load_project_config

    cfg = load_project_config(project)
    channels = (
        get_section(cfg, "daemon", session, "channels") if session else get_section(cfg, "channels")
    )
    if any(isinstance(v, dict) for v in channels.values()):
        return  # a channel is already configured for this daemon

    host = str(getattr(args, "host", None) or DEFAULT_DAEMON_HOST)
    try:
        port = int(getattr(args, "port", None) or DEFAULT_DAEMON_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_DAEMON_PORT
    try:
        from veles.tui.wizard.daemon_runner import run_daemon_start_wizard_tui

        answers = run_daemon_start_wizard_tui(project, session=session, host=host, port=port)
    except Exception as exc:
        print(
            f"warning: daemon start wizard failed ({type(exc).__name__}: {exc}); "
            "falling back to stdin prompts.",
            file=sys.stderr,
        )
        _offer_channel_stdin(project, session=session)
        return
    if not answers:
        return  # cancelled (Ctrl+Q) → start with what we already have
    bind = answers.get("daemon_bind")
    if isinstance(bind, dict):
        args.host = str(bind.get("host") or args.host)
        with contextlib.suppress(TypeError, ValueError):
            args.port = int(bind.get("port") or args.port)


def _offer_channel_stdin(project, *, session: str | None) -> None:
    """Legacy stdin channel offer (M173) — the degraded-terminal fallback."""
    from veles.cli.project_wizard import _ask_yes_no, _default_prompter

    if not _ask_yes_no(
        _default_prompter,
        "No channel is connected to this daemon. Connect one now (e.g. Telegram)?",
        default=False,
    ):
        return
    from veles.cli.channel_wizard import add_channel

    add_channel(project, session=session)


def _cmd_daemon_stop(args: argparse.Namespace) -> int:
    resolved = _stop_status_paths(args)
    if resolved is None:
        return 2
    pid_path, info_path = resolved
    if not pid_path.is_file():
        print("no veles daemon pid file found.", file=sys.stderr)
        return 1
    pid = read_pid(pid_path)
    if pid is None:
        print(f"error: failed to read pid file {pid_path}", file=sys.stderr)
        return 1
    if not is_alive(pid):
        print(f"daemon pid {pid} not running; removing stale pid file.", file=sys.stderr)
        pid_path.unlink(missing_ok=True)
        info_path.unlink(missing_ok=True)
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        print(f"error: failed to signal pid {pid}: {exc}", file=sys.stderr)
        return 1
    print(f"sent SIGTERM to veles daemon pid {pid}.", file=sys.stderr)
    return 0


def _cmd_daemon_status(args: argparse.Namespace) -> int:
    resolved = _stop_status_paths(args)
    if resolved is None:
        return 2
    pid_path, info_path = resolved
    if not pid_path.is_file():
        print("not running.")
        return 1
    pid = read_pid(pid_path)
    if pid is None:
        print("pid file unreadable; daemon state unknown.")
        return 1
    if not is_alive(pid):
        print(f"pid {pid} not alive (stale pid file at {pid_path}).")
        return 1
    info: dict[str, object] = {}
    if info_path.is_file():
        try:
            info = json.loads(info_path.read_text(encoding="utf-8")) or {}
        except (OSError, json.JSONDecodeError):
            info = {}
    host = info.get("host", "?")
    port = info.get("port", "?")
    project = info.get("project_name", "?")
    root = info.get("project_root", "?")
    started_at = info.get("started_at")
    uptime = ""
    if isinstance(started_at, int | float):
        uptime = f"  uptime: {time.time() - float(started_at):.1f}s"
    print(f"running  pid={pid}  http://{host}:{port}/  project={project}{uptime}")
    print(f"  root: {root}")
    return 0


# ---- bare `veles daemon` opens a TUI picker ----


def _cmd_daemon_picker(args: argparse.Namespace) -> int:
    # Non-TTY (piped / redirected / no controlling terminal): the Textual
    # picker needs a real terminal or it hangs forever. Fall back to the plain
    # daemon list instead of launching a full-screen app into nothing.
    # (Regression guard — the M197 revert dropped this; restored 2026-07-07.)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return _cmd_daemon_list(args)
    try:
        from veles.tui.screens.daemon_picker import DaemonPickerApp
    except ImportError as exc:
        print(f"error: TUI picker unavailable: {exc}", file=sys.stderr)
        return 1
    # Resolve the project from cwd (best-effort) so the picker can also show
    # this project's runtime sessions (named daemons + the kind=tui row);
    # None just hides that section (M138-followup).
    from veles.cli._project import _resolve_active_project

    project = _resolve_active_project(args)
    # Disable Textual mouse-mode so the terminal handles drag-to-select +
    # the system clipboard shortcut — same fix M115.3/.5 applied to the
    # main chat TUI (see veles/tui/app.py:158-163). Trade-off: no
    # scroll-wheel / click-to-focus, but the daemon picker is keyboard-only
    # anyway (s/t/r/d/F5/q).
    DaemonPickerApp(project=project).run(mouse=False)
    return 0


# ---- multi-daemon list / restart / delete ----


def _cmd_daemon_list(args: argparse.Namespace) -> int:
    """`veles daemon list` — table of every registered daemon."""
    del args
    from veles.daemon.registry import DaemonRegistry, status_for, uptime_seconds

    registry = DaemonRegistry.load()
    entries = registry.list()
    if not entries:
        print("no daemons registered. Run `veles daemon start` in a project.")
        return 0
    rows = [
        ("NAME", "PROJECT", "PORT", "PID", "STATUS", "UPTIME"),
    ]
    now = time.time()
    for entry in entries:
        st = status_for(entry)
        up = uptime_seconds(entry, now=now)
        if up <= 0:
            up_s = "-"
        elif up < 3600:
            up_s = f"{up / 60:.0f}m"
        elif up < 86400:
            up_s = f"{up / 3600:.1f}h"
        else:
            up_s = f"{up / 86400:.1f}d"
        rows.append((entry.slug, entry.project_path, str(entry.port), str(entry.pid), st, up_s))
    widths = [max(len(str(r[c])) for r in rows) for c in range(len(rows[0]))]
    for row in rows:
        print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))
    return 0


def _cmd_daemon_restart(args: argparse.Namespace) -> int:
    """`veles daemon <id> restart` — stop the running daemon (SIGTERM, then
    SIGKILL), then respawn it detached at the same host/port, logging to its
    own log file.

    With `--name` it operates on this project's named session instead of
    the cross-project registry."""
    name = getattr(args, "name", None)
    if name:
        return _restart_named_session(args, name)

    from veles.daemon.registry import DaemonRegistry
    from veles.daemon.spawn import spawn_daemon

    slug = _resolve_target_slug(args)
    if slug is None:
        return 1
    registry = DaemonRegistry.load()
    entry = registry.get(slug)
    if entry is None:
        print(f"error: no daemon named {slug!r} in registry.", file=sys.stderr)
        return 1
    if is_alive(entry.pid) and not _graceful_stop(entry.pid, timeout=5.0):
        print(f"error: daemon pid {entry.pid} did not stop.", file=sys.stderr)
        return 1
    proc = spawn_daemon(
        project_root=entry.project_path,
        host=entry.host,
        port=entry.port,
        log_path=daemon_log_path(entry.project_name),
    )
    if proc is None:
        print("error: failed to respawn daemon.", file=sys.stderr)
        return 1
    print(f"restarted daemon {slug!r} (new pid {proc.pid}).")
    return 0


def _cmd_daemon_delete(args: argparse.Namespace) -> int:
    """`veles daemon delete <id>` — confirm, graceful-stop if running,
    then remove from the registry. Does NOT delete the project's
    `.veles/` data — that's the user's content. Use `--yes`/`-y` to
    skip the prompt for scripted use (CI, ansible)."""
    from veles.cli._console import confirm as _confirm
    from veles.daemon.registry import DaemonRegistry

    slug = _resolve_target_slug(args)
    if slug is None:
        return 1
    registry = DaemonRegistry.load()
    entry = registry.get(slug)
    if entry is None:
        print(f"error: no daemon named {slug!r} in registry.", file=sys.stderr)
        return 1

    skip_prompt = bool(getattr(args, "yes", False))
    if not skip_prompt:
        # Surface the most useful identifying details so the user sees
        # which project / port they're about to lose before typing y.
        running_str = "running" if is_alive(entry.pid) else "stopped"
        prompt = (
            f"Delete daemon '{entry.slug}' "
            f"(project: {entry.project_name}, port: {entry.port}, "
            f"pid: {entry.pid}, status: {running_str})? [y/N]"
        )
        if not _confirm(prompt):
            print("aborted.")
            return 0

    if is_alive(entry.pid):
        ok = _graceful_stop(entry.pid, timeout=10.0)
        if not ok:
            print(
                f"warning: daemon pid {entry.pid} did not exit within 10s; "
                "removing from registry anyway.",
                file=sys.stderr,
            )
    registry.remove(entry.slug)
    registry.save()
    print(f"deleted daemon {slug!r} from registry.")
    return 0


def _resolve_target_slug(args: argparse.Namespace) -> str | None:
    """Per-subcommand `target` arg is required for restart/delete."""
    slug = getattr(args, "target", None) or getattr(args, "name", None)
    if not slug:
        print(
            "error: this command needs a daemon id or name. See `veles daemon list`.",
            file=sys.stderr,
        )
        return None
    return str(slug)
