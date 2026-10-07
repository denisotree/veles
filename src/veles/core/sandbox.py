"""OS sandbox for the agent's `run_shell` (release F).

The protected set comes from `writable.shell_guard` — the file-tool rules plus the
user's auto-run files. macOS runs the command under `sandbox-exec` with a generated
profile; Linux under `bwrap` with read-only binds. Where neither works, the command runs
as before and a warning says why (once per process). Deny-list only: the project,
caches, temp dirs and the network stay usable.
"""

from __future__ import annotations

import contextlib
import functools
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from veles.core.layout.writable import ShellGuard, shell_guard
from veles.core.project import Project

# EBUSY: on Linux a rename onto a read-only bind mount (git writing `.git/config`).
_DENIED = ("Operation not permitted", "Read-only file system", "Device or resource busy")
_HINT = (
    "<sandbox: if this was a write to a protected path, it is read-only for the agent's "
    "shell — ask the user to change it>"
)
_WRAPPERS = ("sandbox-exec:", "bwrap:")
_REGEX_META = frozenset(".^$*+?()[]{}|\\")
_warned: set[str] = set()


@dataclass(frozen=True, slots=True)
class SandboxStatus:
    kind: str | None
    active: bool
    reason: str = ""
    disabled: bool = False


@dataclass(frozen=True, slots=True)
class Wrapped:
    argv: list[str]
    active: bool
    watch: tuple[Path, ...] = ()


def _enabled() -> bool:
    """Read from `~/.veles/config.toml` only — a cloned project can't switch it off."""
    from veles.core.user_config import get_user_section

    return get_user_section("sandbox").get("enabled", True) is not False


@functools.cache
def _probe() -> SandboxStatus:
    if sys.platform == "darwin":
        kind = "sandbox-exec"
        cmd = ["sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"]
    elif sys.platform.startswith("linux"):
        kind, cmd = "bwrap", ["bwrap", "--dev-bind", "/", "/", "--", "true"]
    else:
        return SandboxStatus(None, False, f"no OS sandbox on {sys.platform}")
    if shutil.which(cmd[0]) is None:
        extra = " — install bubblewrap" if kind == "bwrap" else ""
        return SandboxStatus(kind, False, f"`{kind}` is not installed{extra}")
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=False, stdin=subprocess.DEVNULL
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return SandboxStatus(kind, False, str(exc))
    if proc.returncode != 0:
        first = (proc.stderr.strip().splitlines() or [f"exit {proc.returncode}"])[0]
        return SandboxStatus(kind, False, first)
    return SandboxStatus(kind, True)


def sandbox_status() -> SandboxStatus:
    if not _enabled():
        return SandboxStatus(None, False, "disabled in ~/.veles/config.toml", disabled=True)
    return _probe()


def wrap(argv: list[str], project: Project | None) -> Wrapped:
    status = sandbox_status()
    if not status.active:
        if not status.disabled:
            _warn_once(f"warning: run_shell is not sandboxed: {status.reason}")
        return Wrapped(list(argv), False)
    guard = shell_guard(project)
    if status.kind == "sandbox-exec":
        profile = sbpl_profile(guard)
        return Wrapped(["sandbox-exec", "-p", profile, *argv], True, _watch(guard, linux=False))
    # bwrap binds only existing paths: under a read-only `.veles/` a missing hole could
    # never be created, so Veles makes its own agent dirs first.
    for hole in guard.holes:
        with contextlib.suppress(OSError):
            hole.mkdir(parents=True, exist_ok=True)
    return Wrapped(bwrap_argv(guard, argv), True, _watch(guard, linux=True))


def notes(wrapped: Wrapped, *, returncode: int, output: str, project: Project | None) -> str:
    """What to append to run_shell's output: whether the sandbox itself failed to start
    (the command didn't run — the user is told once), a hint when a write was refused,
    and a report of protected paths the command created — ones that didn't exist, which
    Linux can't block, and a new repo at the root — also told to the user on stderr and
    in the memory log."""
    if not wrapped.active:
        return ""
    if returncode != 0 and output.startswith(_WRAPPERS):
        reason = output.splitlines()[0]
        _warn_once(f"warning: run_shell's sandbox failed to start, nothing ran: {reason}")
        return (
            "<sandbox: the sandbox couldn't start, so the command didn't run — "
            "the user has been told>"
        )
    out: list[str] = []
    if returncode != 0 and any(marker in output for marker in _DENIED):
        out.append(_HINT)
    for path in wrapped.watch:
        if not os.path.lexists(path):
            continue
        shown = _display(path, project)
        print(
            f"warning: the agent's shell created {shown} — review it (the sandbox can't "
            "block a path that didn't exist yet)",
            file=sys.stderr,
        )
        if project is not None:
            from veles.core.memory.artefacts import append_memory_log

            append_memory_log(project, op="sandbox", summary=f"run_shell created {shown}")
        out.append(f"<sandbox: created {shown} — the user has been told>")
    return "\n".join(out)


def sbpl_profile(guard: ShellGuard) -> str:
    deny = [f'(subpath "{_quoted(p)}")' for p in guard.readonly]
    deny += [f'(literal "{_quoted(p)}")' for p in _no_rename(guard)]
    if guard.root is not None:
        root = _regex(str(guard.root))
        deny += [
            f'(regex "{_quoted(f"^{root}/(.*/)?{_any_case(n)}(/|$)")}")'
            for n in guard.readonly_names
        ]
    lines = ["(version 1)", "(allow default)", f"(deny file-write* {' '.join(deny)})"]
    if guard.holes:
        holes = " ".join(f'(subpath "{_quoted(h)}")' for h in guard.holes)
        lines.append(f"(allow file-write* {holes})")
    if guard.relock_prefix is not None:
        relock = _quoted("^" + _regex(str(guard.relock_prefix)))
        lines.append(f'(deny file-write* (regex "{relock}"))')
    return "\n".join(lines)


def bwrap_argv(guard: ShellGuard, argv: list[str]) -> list[str]:
    out = ["bwrap", "--dev-bind", "/", "/"]
    for p in guard.pinned:  # a mount point can't be renamed (spike: the `mv .git` hole)
        flag = "--bind-try" if p.is_dir() and not p.is_symlink() else "--ro-bind-try"
        out += [flag, str(p), str(p)]
    for p in guard.readonly:
        if _bindable(p):
            out += ["--ro-bind-try", str(p), str(p)]
    for h in guard.holes:
        if _bindable(h):
            out += ["--bind-try", str(h), str(h)]
    if guard.relock_prefix is not None:
        prefix = guard.relock_prefix
        for d in sorted(prefix.parent.glob(prefix.name + "*")):
            out += ["--ro-bind-try", str(d), str(d)]
    return [*out, "--die-with-parent", "--", *argv]


def _bindable(p: Path) -> bool:
    """`-try` binds skip a missing path but fail on one under a file (ENOTDIR) — e.g.
    `.git/hooks` where `.git` is a worktree's file — and that broke every command."""
    return not any(os.path.lexists(a) and not a.is_dir() for a in p.parents)


def _no_rename(guard: ShellGuard) -> list[Path]:
    """`literal` denies: the pinned dirs, the links, and every *existing* ancestor of a
    protected path — renaming one would move the path out from under the profile. A
    missing ancestor is left creatable (a literal deny would block `mkdir ~/.config`)."""
    out: dict[Path, None] = dict.fromkeys((*guard.pinned, *guard.links))
    for p in (*guard.pinned, *guard.readonly, *guard.links):
        for parent in p.parents:
            if parent != Path(parent.anchor) and os.path.lexists(parent):
                out[parent] = None
    return list(out)


def _watch(guard: ShellGuard, *, linux: bool) -> tuple[Path, ...]:
    """Protected paths that don't exist yet and that the command may create, to report:
    a repo at the root (allowed — its hooks aren't protected until the next command);
    on Linux, which binds only what exists, also the root-level names and home entries."""
    home = Path(os.path.realpath(Path.home()))
    candidates: list[Path] = []
    if guard.root is not None:
        candidates.append(guard.root / ".git")
        if linux:
            candidates += [guard.root / n for n in guard.readonly_names]
    if linux:
        candidates += [
            p
            for p in guard.readonly
            if p.is_relative_to(home) and (guard.root is None or not p.is_relative_to(guard.root))
        ]
    return tuple(dict.fromkeys(p for p in candidates if not os.path.lexists(p)))


def _display(path: Path, project: Project | None) -> str:
    if project is not None and path.is_relative_to(Path(os.path.realpath(project.root))):
        return str(path.relative_to(Path(os.path.realpath(project.root))))
    home = Path(os.path.realpath(Path.home()))
    return f"~/{path.relative_to(home)}" if path.is_relative_to(home) else str(path)


def _warn_once(message: str) -> None:
    if message not in _warned:
        _warned.add(message)
        print(message, file=sys.stderr)


def _quoted(text: Path | str) -> str:
    """An SBPL string body. Regexes go in the string form too: the `#"…"` literal can't
    hold a `"` (a project dir named `my "odd" dir` broke the profile)."""
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def _regex(text: str) -> str:
    return "".join("\\" + c if c in _REGEX_META else c for c in text)


def _any_case(name: str) -> str:
    """macOS volumes are case-insensitive: `.ENVRC` is `.envrc`."""
    return "".join(f"[{c.lower()}{c.upper()}]" if c.isalpha() else _regex(c) for c in name)


__all__ = [
    "SandboxStatus",
    "Wrapped",
    "bwrap_argv",
    "notes",
    "sandbox_status",
    "sbpl_profile",
    "wrap",
]
