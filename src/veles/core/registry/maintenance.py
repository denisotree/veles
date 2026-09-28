"""Keep installed extensions honest: `verify` finds drift, `upgrade` moves to a newer version."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from veles.core.critical_ops import confirm_critical
from veles.core.io_utils import atomic_write_text, dump_toml, load_optional_toml
from veles.core.project import Project
from veles.core.registry.catalog import available, resolve
from veles.core.registry.hashing import tree_sha256
from veles.core.registry.install import (
    InstallError,
    describe,
    install,
    installed_records,
    recipe_sha256,
    remove_installed,
)
from veles.core.registry.records import InstallRecord
from veles.core.registry.repo import diff_stat
from veles.core.registry.versions import is_newer


@dataclass(frozen=True, slots=True)
class Issue:
    record: InstallRecord
    problem: str
    detail: str


def verify(project: Project | None) -> list[Issue]:
    found, _warnings = available(sync_missing=False)
    index = {(f.registry, f.ext.name): f for f in found}
    issues: list[Issue] = []
    for rec in installed_records(project):
        drift = _drift(rec)
        if drift is not None:
            issues.append(drift)
            continue
        if rec.registry is None:
            issues.append(Issue(rec, "unreviewed", "installed from a raw source, not a registry"))
            continue
        current = index.get((rec.registry, rec.name))
        if current is None:
            continue
        if current.ext.yanked:
            issues.append(Issue(rec, "yanked", current.ext.yanked))
        elif is_newer(current.ext.version, rec.version):
            issues.append(Issue(rec, "outdated", f"{rec.version} → {current.ext.version}"))
    return issues


def upgrade(name: str, *, project: Project | None) -> InstallRecord | None:
    matches = [r for r in installed_records(project) if r.name == name]
    if not matches:
        raise InstallError(f"{name!r} is not installed here")
    if len(matches) > 1:
        kinds = ", ".join(sorted(r.kind for r in matches))
        raise InstallError(f"{name!r} is installed as several kinds ({kinds}); remove by hand")
    rec = matches[0]
    if rec.registry is None:
        raise InstallError(
            f"{name!r} was installed from a raw source; reinstall it from a registry"
        )
    found = resolve(f"{rec.registry}:{name}")
    if not is_newer(found.ext.version, rec.version):
        return None
    summary = describe(found)
    if found.ext.source.type == "path" and rec.commit and found.ext.dir is not None:
        rel = found.ext.dir.relative_to(found.root).as_posix()
        summary += "\n\n" + (
            diff_stat(found.root, rec.commit, found.commit, rel) or "(no file changes)"
        )
    if not confirm_critical(f"upgrade {found.ref} {rec.version} → {found.ext.version}", summary):
        raise InstallError("aborted")
    backup = _backup(rec)
    try:
        remove_installed(rec)
    except InstallError:
        # Nothing was actually removed (remove_installed raises and keeps the
        # record when deletion fails) — there is nothing to restore, only the
        # backup copy to clean up before the error propagates.
        _cleanup_backup(backup)
        raise
    except OSError as exc:
        # `remove_installed`'s trailing `drop_record` call is not itself wrapped
        # in a try/except, so a disk failure there surfaces as a bare OSError
        # rather than InstallError. Same handling either way: clean the backup,
        # re-raise as the InstallError callers of `upgrade` expect.
        _cleanup_backup(backup)
        raise InstallError(f"could not remove {rec.path}: {exc}") from exc
    try:
        new = install(
            found,
            project=project,
            user_scope=rec.project is None and rec.kind == "skill",
            confirmed=True,
        )
    except BaseException:
        # Not just InstallError: a Ctrl+C or any other interruption mid-fetch must
        # still restore the backup — `remove_installed` above already dropped both
        # the old payload and its record, so anything short of full restore here
        # leaves the extension gone with no trace, not just "upgrade failed".
        _restore(rec, backup)
        raise
    _cleanup_backup(backup)
    return new


def _drift(rec: InstallRecord) -> Issue | None:
    if rec.kind == "mcp":
        config_path, _, _ = rec.path.partition("#")
        recipe = _read_mcp_recipe(Path(config_path), rec.name)
        if recipe is None:
            return Issue(rec, "missing", f"[mcp.servers.{rec.name}] is gone from {config_path}")
        if recipe_sha256(recipe) != rec.tree_sha256:
            return Issue(rec, "modified", f"[mcp.servers.{rec.name}] was edited")
        return None
    path = Path(rec.path)
    if not path.is_dir():
        return Issue(rec, "missing", f"{path} no longer exists")
    try:
        digest = tree_sha256(path)
    except ValueError as exc:
        return Issue(rec, "modified", str(exc))
    if digest != rec.tree_sha256:
        return Issue(rec, "modified", f"files under {path} changed since install")
    return None


@dataclass(frozen=True, slots=True)
class _Backup:
    """What `_restore` needs to put an upgrade's old install back.

    Exactly one of `dir` (skill/module/layout: a copy of the install directory) or
    `mcp` (the config path + the recipe dict that was under `[mcp.servers.<name>]`)
    is set, matching `rec.kind`. One shape covers both so `upgrade` doesn't need a
    second restore path for mcp installs."""

    dir: Path | None = None
    mcp: tuple[Path, dict[str, object]] | None = None


def _read_mcp_recipe(config_path: Path, name: str) -> dict[str, object] | None:
    recipe = load_optional_toml(config_path).get("mcp", {}).get("servers", {}).get(name)
    return recipe if isinstance(recipe, dict) else None


def _backup(rec: InstallRecord) -> _Backup:
    if rec.kind == "mcp":
        config_path, _, _ = rec.path.partition("#")
        path = Path(config_path)
        recipe = _read_mcp_recipe(path, rec.name)
        return _Backup(mcp=(path, recipe) if recipe is not None else None)
    src = Path(rec.path)
    dest = src.with_name(f".{src.name}.upgrade-backup")
    shutil.rmtree(dest, ignore_errors=True)
    try:
        shutil.copytree(src, dest, symlinks=True)
    except OSError as exc:
        # A copy that dies partway through must not leave a half-written backup
        # behind — that would both violate "never left behind" and, worse, look
        # like a real backup to a later `_restore`.
        shutil.rmtree(dest, ignore_errors=True)
        raise InstallError(f"could not back up {src} before upgrading: {exc}") from exc
    return _Backup(dir=dest)


def _cleanup_backup(backup: _Backup) -> None:
    if backup.dir is not None:
        shutil.rmtree(backup.dir, ignore_errors=True)


def _restore(rec: InstallRecord, backup: _Backup) -> None:
    from veles.core.registry.records import put_record

    if backup.dir is not None:
        shutil.rmtree(rec.path, ignore_errors=True)
        backup.dir.rename(rec.path)
    elif backup.mcp is not None:
        config_path, recipe = backup.mcp
        data = load_optional_toml(config_path)
        data.setdefault("mcp", {}).setdefault("servers", {})[rec.name] = recipe
        atomic_write_text(config_path, dump_toml(data))
    put_record(rec)
