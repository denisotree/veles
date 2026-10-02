"""Keep installed extensions honest: `verify` finds drift, `upgrade` moves to a newer version."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from veles.core.critical_ops import confirm_critical
from veles.core.io_utils import atomic_write_text, dump_toml, load_optional_toml
from veles.core.project import Project
from veles.core.registry.catalog import Found, resolve, scan_source
from veles.core.registry.config import RegistryConfigError, list_sources
from veles.core.registry.hashing import tree_sha256
from veles.core.registry.install import (
    InstallError,
    describe,
    install,
    installed_records,
    record_ref,
    remove_installed,
    resolve_one_record,
)
from veles.core.registry.records import InstallRecord
from veles.core.registry.repo import RegistryRepoError, diff_stat
from veles.core.registry.versions import is_newer
from veles.mcp.approvals import approve, recipe_hash


@dataclass(frozen=True, slots=True)
class Issue:
    record: InstallRecord
    problem: str
    detail: str


def verify(project: Project | None) -> list[Issue]:
    """Drift is computed for every record first; the registry catalog only adds
    yanked/outdated/removed/upstream-ahead, so a broken registry can't hide drift."""
    found, readable, broken = _catalog()
    issues: list[Issue] = []
    records = installed_records(project)
    have = {record_ref(r) for r in records}
    for rec in records:
        issues += [
            Issue(rec, "missing-dependency", f"needs {ref} — `veles registry install {ref}`")
            for ref in rec.requires_extensions
            if ref not in have
        ]
        drift = _drift(rec)
        if drift is not None:
            issues.append(drift)
            continue
        if rec.registry is None:
            issues.append(Issue(rec, "unreviewed", "installed from a raw source, not a registry"))
            continue
        current = next(iter(_lookup(found, rec.registry, rec.group, rec.name)), None)
        if current is None:
            # Revoking by deleting the directory is as valid as `yanked` — but only a
            # readable clone can tell "deleted" from "not fetched" or "broken manifest".
            unparsable = any(_same(k, rec.registry, rec.group, rec.name) for k in broken)
            if rec.registry in readable and not unparsable:
                issues.append(Issue(rec, "removed", f"no longer in registry {rec.registry!r}"))
            continue
        if current.ext.yanked:
            issues.append(Issue(rec, "yanked", current.ext.yanked))
        elif is_newer(current.ext.version, rec.version):
            issues.append(Issue(rec, "outdated", f"{rec.version} → {current.ext.version}"))
        ahead = _upstream_ahead(current, found)
        if ahead is not None:
            issues.append(Issue(rec, "upstream-ahead", ahead))
    return issues


def _catalog() -> tuple[list[Found], set[str], set[tuple[str, str, str]]]:
    """What the fetched registries offer, which registries could be read, and the
    `(registry, group, name)` of every unparsable manifest (never called removed).
    Never touches the network and never raises."""
    found: list[Found] = []
    readable: set[str] = set()
    broken: set[tuple[str, str, str]] = set()
    try:
        sources = list_sources()
    except (RegistryConfigError, OSError):
        return found, readable, broken
    for source in sources:
        try:
            entries, errors = scan_source(source, sync_missing=False)
        except (RegistryRepoError, OSError):
            continue
        readable.add(source.name)
        found += entries
        broken |= {(source.name, p.parent.parent.name, p.parent.name) for p, _ in errors}
    return found, readable, broken


def _same(key: tuple[str, str, str], registry: str, group: str, name: str) -> bool:
    """`registry:group/name` equality; a record without a group matches by name."""
    return key[0] == registry and key[2] == name and (not group or key[1] == group)


def _lookup(found: list[Found], registry: str, group: str, name: str) -> list[Found]:
    return [f for f in found if _same((f.registry, f.ext.group, f.ext.name), registry, group, name)]


def _upstream_ahead(current: Found, found: list[Found]) -> str | None:
    """A vendored copy carries `upstream = "<registry>:<name>@<sha>"` (what `vendor`
    writes; `<registry>:<group>/<name>` is accepted too). When that registry is
    fetched and its entry is newer than the vendored version, say so."""
    if not current.ext.upstream:
        return None
    ref = current.ext.upstream.rpartition("@")[0]
    registry, _, rest = ref.partition(":")
    group, _, name = rest.rpartition("/")
    matches = _lookup(found, registry, group, name)
    if len(matches) != 1 or not is_newer(matches[0].ext.version, current.ext.version):
        return None
    return f"{ref} is at {matches[0].ext.version}; the vendored copy is {current.ext.version}"


def upgrade(
    name: str, *, project: Project | None, user_scope: bool | None = None
) -> InstallRecord | None:
    rec = resolve_one_record(name, project=project, user_scope=user_scope)
    if rec.registry is None:
        raise InstallError(
            f"{name!r} was installed from a raw source; reinstall it from a registry"
        )
    found = resolve(f"{rec.registry}:{rec.group}/{name}" if rec.group else f"{rec.registry}:{name}")
    if not is_newer(found.ext.version, rec.version):
        return None
    summary = describe(found)
    if found.ext.source.type == "path" and rec.commit and found.ext.dir is not None:
        rel = found.ext.dir.relative_to(found.root).as_posix()
        try:
            stat = diff_stat(found.root, rec.commit, found.commit, rel) or "(no file changes)"
        except RegistryRepoError as exc:
            stat = f"(diff unavailable: {exc})"
        summary += "\n\n" + stat
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
            user_scope=rec.project is None and rec.kind in ("module", "skill"),
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
        if recipe_hash(recipe) != rec.tree_sha256:
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
    from veles.core.registry.records import load_records, put_record

    if any(r.path == rec.path for r in load_records()):
        # Another install of this extension finished between our remove and our
        # install — its copy and record are not ours to replace. (A copy left by
        # an interrupted install of ours has no record, and is replaced below.)
        _cleanup_backup(backup)
        return
    if backup.dir is not None:
        shutil.rmtree(rec.path, ignore_errors=True)
        backup.dir.rename(rec.path)
    elif backup.mcp is not None:
        config_path, recipe = backup.mcp
        data = load_optional_toml(config_path)
        data.setdefault("mcp", {}).setdefault("servers", {})[rec.name] = recipe
        atomic_write_text(config_path, dump_toml(data))
        # Uninstall revoked the approval; give it back only for the recipe the
        # install confirmed — a hand-edited one stays unapproved (fail closed).
        if rec.project is not None and recipe_hash(recipe) == rec.tree_sha256:
            approve(Path(rec.project), rec.name, recipe)
    put_record(rec)
