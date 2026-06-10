"""Sandbox enforcement for builtin file/shell tools.

The agent sees only the active subproject's tree plus a *narrow*
whitelist inside `~/.veles/`. Symlinks pointing outside this envelope
are rejected. This module is the gatekeeper that turns that statement
into refused tool calls.

Allowed roots, in order:
1. Active project root (from `current_project()` ContextVar). Includes
   the whole subtree, so vertical subprojects are covered automatically.
2. A narrow whitelist of subdirectories under `~/.veles/`:
   - `~/.veles/skills/`  — user-installed global skills, must remain
     readable from any project (VISION §8).
   - `~/.veles/locales/` — i18n overrides.
   Everything else under `~/.veles/` (the projects registry, daemon
   tokens, daemon logs, daemon config, secrets) is **not** exposed —
   that is daemon-internal state, not subproject content. Closes the
   leak where the agent could `read_file` `~/.veles/projects/registry.json`
   and enumerate other projects.
3. `VELES_SANDBOX_ROOTS` (`:`-separated paths) — opt-in override for
   tests / CI / advanced users. Replaces the default roots entirely.
4. When no active project is set AND no env override, fall back to
   `Path.cwd()` so unit tests of tools-in-isolation still work. This
   only triggers in test/dev contexts; the CLI always sets active
   project before dispatching tools.

Resolution policy:
- `Path.resolve(strict=False)` follows symlinks (so a link inside
  the sandbox pointing outside is rejected) and accepts non-existent
  targets (so `write_file` for a fresh file works).
- A literal `..` segment in the input string is refused before
  resolution — defence in depth against the case where a symlink
  inside the sandbox points to a parent (resolve would still catch
  it, but the explicit refusal gives a clearer error).

`fetch_url` does not use this module — it has its own SSRF deny-list
on URL hostnames; file-system sandbox doesn't apply.
"""

from __future__ import annotations

import os
from pathlib import Path

from veles.core.context import current_project

_SANDBOX_ENV = "VELES_SANDBOX_ROOTS"
_USER_ROOT_REL = ".veles"
# Subdirectories of `~/.veles/` the agent is allowed to read. Adding to
# this list expands the agent's reach across all projects — think hard
# before extending. The daemon itself still reaches into `~/.veles/`
# directly (it doesn't go through `resolve_safe`), so daemon-internal
# files stay accessible to the daemon process.
_USER_ROOT_WHITELIST = ("skills", "locales")


class SandboxViolation(RuntimeError):
    """Raised when a tool tries to access a path outside the sandbox."""


def _get_sandbox_roots() -> list[Path]:
    """Return the list of allowed roots, resolved and de-duplicated.

    Always non-empty: at minimum returns `[Path.cwd().resolve()]`.
    """
    override = os.environ.get(_SANDBOX_ENV)
    if override:
        roots = [Path(p).expanduser().resolve() for p in override.split(":") if p]
        return _dedupe(roots)
    roots: list[Path] = []
    project = current_project()
    if project is not None:
        roots.append(project.root.resolve())
    user_root = Path.home() / _USER_ROOT_REL
    for name in _USER_ROOT_WHITELIST:
        # Whitelist subdirs are admitted whether or not they exist on disk —
        # `resolve_safe` itself supports non-existent targets (write_file
        # for a fresh skill file under `~/.veles/skills/foo.py` must work).
        roots.append((user_root / name).resolve())
    if project is None:
        roots.append(Path.cwd().resolve())
    return _dedupe(roots)


def _dedupe(roots: list[Path]) -> list[Path]:
    """Drop ancestor-of-existing entries to keep the list minimal."""
    out: list[Path] = []
    for r in roots:
        if any(_is_within(r, existing) for existing in out):
            continue
        out = [e for e in out if not _is_within(e, r)]
        out.append(r)
    return out


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def resolve_safe(path: str | Path) -> Path:
    """Resolve `path` and raise `SandboxViolation` if it escapes the sandbox.

    `..` traversal in the literal input is refused before resolution.
    Symlinks pointing outside the sandbox are caught after resolution.
    Non-existent targets are allowed (write_file needs that).

    Exception messages run through `core.sanitize` so abs paths
    (project root, $HOME) don't leak into tool errors that the agent
    persists into conversation history.
    """
    from veles.core.sanitize import sanitize

    raw = str(path)
    p = Path(raw).expanduser()
    if ".." in p.parts:
        raise SandboxViolation(
            f"path {sanitize(raw)!r} contains '..' segment; sandbox refuses traversal"
        )
    try:
        resolved = p.resolve(strict=False)
    except OSError as exc:
        raise SandboxViolation(f"cannot resolve {sanitize(raw)!r}: {exc}") from exc
    roots = _get_sandbox_roots()
    for root in roots:
        if _is_within(resolved, root):
            return resolved
    raise SandboxViolation(
        f"path {sanitize(str(resolved))} is outside sandbox; "
        f"allowed roots: {[sanitize(str(r)) for r in roots]}"
    )


def sandbox_cwd() -> Path:
    """Return the directory in which `run_shell` should execute commands.

    First sandbox root — i.e. the active project root when one is set,
    `Path.cwd()` otherwise. `run_shell` cannot be sandboxed at the
    shell level (commands can `cat /etc/passwd` regardless of cwd), so
    this is best-effort: pinning cwd at least keeps relative paths
    inside the project. M38 trust-ladder + M39 always-confirm provide
    the real guard for shell.
    """
    roots = _get_sandbox_roots()
    return roots[0]
