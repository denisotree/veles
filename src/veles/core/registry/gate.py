"""Module load gate: a module runs only if its files still hash to what the user approved.

Approval = an install record (registry install, `veles module add`, or
`veles module approve`). The agent can write into `.veles/modules/`, but it cannot
write `~/.veles/extensions.json`, so it cannot make its own edits load.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from veles.core.registry.hashing import strip_bytecode, tree_sha256
from veles.core.registry.records import InstallRecord, put_record, record_for_path


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


def admit_module(module_dir: Path) -> bool:
    """`module_approved`, then drop the module's bytecode so the import that follows
    compiles the reviewed source instead of running a planted `.pyc`."""
    if not module_approved(module_dir):
        return False
    strip_bytecode(module_dir)
    return True


def approve_module(
    module_dir: Path, *, name: str, project_root: Path, expected_sha256: str | None = None
) -> InstallRecord:
    """Record `module_dir`'s current hash as approved. `expected_sha256` is the hash
    the user was shown: if the files changed since, nothing is approved."""
    digest = tree_sha256(module_dir)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"{module_dir} changed while it was being reviewed — review it again")
    existing = record_for_path(str(module_dir.resolve()))
    rec = InstallRecord(
        name=name,
        kind="module",
        path=str(module_dir.resolve()),
        tree_sha256=digest,
        project=str(project_root.resolve()),
        registry=existing.registry if existing else None,
        group=existing.group if existing else "",
        version=existing.version if existing else "",
        commit=existing.commit if existing else "",
        installed_at=now_iso(),
    )
    put_record(rec)
    return rec
