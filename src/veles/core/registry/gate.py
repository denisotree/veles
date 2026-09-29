"""Module load gate: a module runs only if its files still hash to what the user approved.

Approval = an install record (registry install, `veles module add`, or
`veles module approve`). The agent can write into `.veles/modules/`, but it cannot
write `~/.veles/extensions.json`, so it cannot make its own edits load.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from veles.core.module_manifest import ManifestError, entrypoint_file, parse_manifest
from veles.core.registry.hashing import (
    bytecode_paths,
    git_dirs,
    strip_bytecode,
    tree_sha256,
)
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


def admit_module(module_dir: Path) -> str | None:
    """Why the module may not load, or None when it may. `module_approved`, then no
    `.git` anywhere (outside the hash), then drop the module's bytecode so the import
    that follows compiles the reviewed source instead of running a planted `.pyc`.
    Fails closed: bytecode that can't be removed refuses the module."""
    if not module_approved(module_dir):
        return "not approved, or changed since approval"
    try:
        found = git_dirs(module_dir)
        if found:
            rel = found[0].relative_to(module_dir).as_posix()
            return f"remove the .git directory ({rel}): it is outside the approval hash"
        strip_bytecode(module_dir)
    except OSError:
        return "its bytecode cannot be removed"
    return "its bytecode cannot be removed" if bytecode_paths(module_dir) else None


def approve_module(
    module_dir: Path, *, name: str, project_root: Path, expected_sha256: str | None = None
) -> InstallRecord:
    """Record `module_dir`'s current hash as approved. `expected_sha256` is the hash
    the user was shown: if the files changed since, nothing is approved. A module
    whose entrypoint is invalid or missing is refused."""
    try:
        manifest = parse_manifest((module_dir / "module.toml").read_text(encoding="utf-8"))
        entry, _ = entrypoint_file(module_dir, manifest.entrypoint)
    except ManifestError as exc:
        raise ValueError(f"{module_dir}: {exc}") from exc
    if not entry.is_file():
        raise ValueError(f"{module_dir}: entrypoint file {entry.name!r} not found")
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
