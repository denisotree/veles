"""OS sandbox for the agent's `run_shell` (release F).

The protected set comes from `writable.shell_guard` — the file-tool rules plus the
user's auto-run files. macOS runs the command under `sandbox-exec` with a generated
profile; Linux under `bwrap` with read-only binds. Where neither works, the command runs
as before and a warning says why (once per process). Deny-list only: the project,
caches, temp dirs and the network stay usable.
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from veles.core.layout.writable import ShellGuard, shell_guard
from veles.core.project import Project

_DENIED = ("Operation not permitted", "Read-only file system")
_HINT = "<sandbox: this path is read-only for the agent's shell — ask the user to change it>"
_REGEX_META = frozenset(".^$*+?()[]{}|\\")
_WALK_DEPTH = 4  # ponytail: bwrap binds only existing paths; deeper names aren't walked
_WALK_SKIP = frozenset({".git", "node_modules"})
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
        if not status.disabled and status.reason not in _warned:
            _warned.add(status.reason)
            print(f"warning: run_shell is not sandboxed: {status.reason}", file=sys.stderr)
        return Wrapped(list(argv), False)
    guard = shell_guard(project)
    if status.kind == "sandbox-exec":
        return Wrapped(["sandbox-exec", "-p", sbpl_profile(guard), *argv], True)
    return Wrapped(bwrap_argv(guard, argv), True, _absent_root_entries(guard))


def notes(wrapped: Wrapped, *, returncode: int, output: str, project: Project | None) -> str:
    """What to append to run_shell's output: a hint when a write was refused, and a
    report of protected root entries the command created (Linux can't block a path that
    didn't exist) — also told to the user on stderr and in the memory log."""
    if not wrapped.active:
        return ""
    out: list[str] = []
    if returncode != 0 and any(marker in output for marker in _DENIED):
        out.append(_HINT)
    for path in wrapped.watch:
        if not os.path.lexists(path):
            continue
        print(
            f"warning: the agent's shell created {path.name} in the project — review it "
            "(the sandbox can't block a path that didn't exist)",
            file=sys.stderr,
        )
        if project is not None:
            from veles.core.memory.artefacts import append_memory_log

            append_memory_log(project, op="sandbox", summary=f"run_shell created {path.name}")
        out.append(f"<sandbox: created {path.name} — the user has been told>")
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
        out += ["--bind-try", str(p), str(p)]
    for p in (*guard.readonly, *_named_paths(guard)):
        out += ["--ro-bind-try", str(p), str(p)]
    for h in guard.holes:
        out += ["--bind-try", str(h), str(h)]
    if guard.relock_prefix is not None:
        prefix = guard.relock_prefix
        for d in sorted(prefix.parent.glob(prefix.name + "*")):
            out += ["--ro-bind-try", str(d), str(d)]
    return [*out, "--die-with-parent", "--", *argv]


def _no_rename(guard: ShellGuard) -> list[Path]:
    """`literal` denies: the pinned dirs and every ancestor of every protected path —
    renaming an ancestor would move the protected path out from under the profile."""
    out: dict[Path, None] = dict.fromkeys(guard.pinned)
    for p in (*guard.pinned, *guard.readonly):
        for parent in p.parents:
            if parent != Path(parent.anchor):
                out[parent] = None
    return list(out)


def _named_paths(guard: ShellGuard) -> list[Path]:
    """Existing paths matching `readonly_names` under the root (bwrap binds only what
    exists), walking `_WALK_DEPTH` levels and skipping `.git` internals and node_modules."""
    if guard.root is None:
        return []
    found: list[Path] = []
    firsts = {n.split("/")[0].casefold() for n in guard.readonly_names}
    for dirpath, dirnames, filenames in os.walk(guard.root):
        here = Path(dirpath)
        depth = len(here.relative_to(guard.root).parts)
        for entry in (*dirnames, *filenames):
            for name in guard.readonly_names:
                first, _, rest = name.partition("/")
                if first.casefold() != entry.casefold():
                    continue
                candidate = here / entry / rest if rest else here / entry
                if os.path.lexists(candidate) and candidate not in guard.readonly:
                    found.append(candidate)
        dirnames[:] = [
            d
            for d in dirnames
            if depth < _WALK_DEPTH and d not in _WALK_SKIP and d.casefold() not in firsts
        ]
    return found


def _absent_root_entries(guard: ShellGuard) -> tuple[Path, ...]:
    if guard.root is None:
        return ()
    root = guard.root
    return tuple(
        root / n for n in guard.readonly_names if "/" not in n and not os.path.lexists(root / n)
    )


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
