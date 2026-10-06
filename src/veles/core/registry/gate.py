"""Module load gate: a module runs only if its files still hash to what the user approved.

Approval = an install record (registry install, `veles module add`, or
`veles module approve`). The agent can write into `.veles/modules/`, but it cannot
write `~/.veles/extensions.json`, so it cannot make its own edits load.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from veles.core.critical_ops import refuse_in_agent_shell
from veles.core.module_manifest import ManifestError, entrypoint_file, parse_manifest
from veles.core.registry.hashing import (
    bytecode_paths,
    git_dirs,
    strip_bytecode,
    tree_sha256,
)
from veles.core.registry.records import InstallRecord, put_record, record_for_path
from veles.core.text import shown


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def module_approved(module_dir: Path) -> bool:
    rec = record_for_path(str(module_dir.resolve()))
    if rec is None:
        return False
    try:
        return tree_sha256(module_dir) == rec.tree_sha256
    except (OSError, ValueError):
        return False


_LINKED = "its directory is a symlink; a module dir must be a real directory"
# The one refusal that `veles module approve` fixes.
NOT_APPROVED = "not approved, or changed since approval"


def is_linked(module_dir: Path) -> bool:
    """Records are keyed by resolved path, so a symlinked module dir would borrow the
    approval of whatever it points at (and approving or removing it would act on that
    target). Symlinked ancestors (a project under a linked dir) are fine: they are
    resolved the same way on the approval and the load side."""
    return module_dir.is_symlink() or module_dir.resolve() != (
        module_dir.parent.resolve() / module_dir.name
    )


def admit_module(module_dir: Path, *, project_root: Path | None) -> str | None:
    """Why the module may not load, or None when it may. `project_root` is the scope it
    is being loaded in (None = user scope). The dir must be a real dir in its modules
    dir (no symlink borrowing another dir's approval), approved for this very scope,
    and unchanged (`module_approved`); then no `.git` anywhere (outside the hash), then
    drop the module's bytecode so the import that follows compiles the reviewed source
    instead of running a planted `.pyc`. Fails closed: bytecode that can't be removed
    refuses the module."""
    if sys.pycache_prefix:
        # Bytecode would then be read from outside the module dir, where no strip reaches.
        return "PYTHONPYCACHEPREFIX (sys.pycache_prefix) is set; unset it to load modules"
    if is_linked(module_dir):
        return _LINKED
    rec = record_for_path(str(module_dir.resolve()))
    scope = str(project_root.resolve()) if project_root is not None else None
    if rec is not None and rec.project != scope:
        where = "user scope" if rec.project is None else "another project"
        return f"it was approved for {where}, not for where it is loading"
    if not module_approved(module_dir):
        return NOT_APPROVED
    try:
        found = git_dirs(module_dir)
        if found:
            rel = found[0].relative_to(module_dir).as_posix()
            return f"remove the .git directory ({shown(rel)}): it is outside the approval hash"
        strip_bytecode(module_dir)
        left = bytecode_paths(module_dir)
    except (OSError, ValueError) as exc:
        return f"its files cannot be checked: {shown(exc)}"
    return "its bytecode cannot be removed" if left else None


def approve_module(
    module_dir: Path,
    *,
    name: str,
    project_root: Path | None,
    expected_sha256: str | None = None,
) -> InstallRecord:
    """Record `module_dir`'s current hash as approved. `expected_sha256` is the hash
    the user was shown: if the files changed since, nothing is approved. A module
    whose entrypoint is invalid or missing, or whose dir is a symlink, is refused."""
    refuse_in_agent_shell(f"approving module {name}")
    if is_linked(module_dir):
        raise ValueError(f"{shown(module_dir)}: {_LINKED}")
    try:
        manifest = parse_manifest((module_dir / "module.toml").read_text(encoding="utf-8"))
        entry, _ = entrypoint_file(module_dir, manifest.entrypoint)
    except ManifestError as exc:
        raise ValueError(f"{shown(module_dir)}: {shown(exc)}") from exc
    if not entry.is_file():
        raise ValueError(f"{shown(module_dir)}: entrypoint file {entry.name!r} not found")
    digest = tree_sha256(module_dir)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(
            f"{shown(module_dir)} changed while it was being reviewed — review it again"
        )
    existing = record_for_path(str(module_dir.resolve()))
    scope = str(project_root.resolve()) if project_root is not None else None
    if existing is not None and existing.project != scope:
        # Re-scoping would un-approve it where it was approved (e.g. reached through a
        # linked modules dir of another project).
        where = "user scope" if existing.project is None else shown(existing.project)
        raise ValueError(f"{shown(module_dir)} is already approved for another scope ({where})")
    rec = InstallRecord(
        name=name,
        kind="module",
        path=str(module_dir.resolve()),
        tree_sha256=digest,
        project=scope,
        registry=existing.registry if existing else None,
        group=existing.group if existing else "",
        version=existing.version if existing else "",
        commit=existing.commit if existing else "",
        installed_at=now_iso(),
    )
    put_record(rec)
    return rec
