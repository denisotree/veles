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
import unicodedata
from pathlib import Path

from veles.core.context import current_project
from veles.core.user_paths import user_home

_SANDBOX_ENV = "VELES_SANDBOX_ROOTS"
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
    user_root = user_home()
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


def _closed_user_path(resolved: Path) -> bool:
    """Inside `user_home()` but outside the whitelisted subdirs. Checked on its own,
    not via the roots: a project root that contains `user_home()` (a project at `~`, or
    `VELES_USER_HOME` inside the project) would otherwise swallow the whitelist in
    `_dedupe` and open approvals, trust and modules to the agent. Decided by file
    identity (`_same_place`), not by spelling."""
    home = user_home()
    if not _same_place(resolved, home, fold=True):  # refusing side: fold, over-refuse
        return False
    # Allowing side: exact names for a missing tail, so folding never widens the
    # whitelist (on a case-sensitive FS `SKILLS` is a different, closed dir).
    return not any(_same_place(resolved, home / n, fold=False) for n in _USER_ROOT_WHITELIST)


def _same_place(target: Path, directory: Path, *, fold: bool) -> bool:
    """Is `target` inside `directory`, as the filesystem sees it? `resolve()` keeps the
    caller's spelling, and on a case- or normalization-insensitive FS (macOS APFS)
    `.VELES` or an NFD `café` *is* the same dir — so the comparison is by identity
    (`samefile`) of the nearest existing ancestor of `directory`. `directory` is
    resolved first (a dangling `~/.veles -> dotfiles/veles` link then points at the
    real, not yet created, location). The part of it that does not exist yet is
    compared by name: case- and NFC-folded when `fold` (answers "yes" more often —
    right for the refusing check), exactly otherwise (right for the allowing check)."""

    def names(p: Path) -> list[str]:
        parts = p.parts
        return [unicodedata.normalize("NFC", s).casefold() for s in parts] if fold else list(parts)

    directory = directory.resolve()
    anchor = directory
    while not anchor.exists() and anchor != anchor.parent:
        anchor = anchor.parent
    missing = names(directory.relative_to(anchor))
    for ancestor in (target, *target.parents):
        try:
            if not ancestor.samefile(anchor):
                continue
        except OSError:  # this ancestor does not exist
            continue
        return names(target.relative_to(ancestor))[: len(missing)] == missing
    return False


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
    # M243: a relative path is resolved against the SANDBOX root, not the
    # process cwd. `Path.resolve()` uses `os.getcwd()`, which is only the
    # project root when the user happened to launch from there — a daemon, a
    # job runner, a channel gateway or `veles run --project-root` all run from
    # somewhere else, and `write_file("notes.md")` then landed outside the
    # sandbox and was refused. `run_shell` never had this problem because it
    # already pins cwd to `sandbox_cwd()`; this makes every other tool agree
    # with it, so "relative means relative to the project" holds everywhere.
    #
    # Observed live 2026-09-01: the model tried `guimaraes.md`, then
    # `/guimaraes/guimaraes.md`, then `<guimaraes>/guimaraes.md` — copying the
    # sanitized placeholder out of the error message as if it were a real path,
    # because nothing in the refusal told it where the project actually was.
    if not p.is_absolute():
        p = sandbox_cwd() / p
    try:
        resolved = p.resolve(strict=False)
    except OSError as exc:
        raise SandboxViolation(f"cannot resolve {sanitize(raw)!r}: {exc}") from exc
    if _closed_user_path(resolved):
        raise SandboxViolation(
            f"path {sanitize(str(resolved))} is Veles' own user state; only "
            f"{', '.join(_USER_ROOT_WHITELIST)} under it are open to tools"
        )
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
