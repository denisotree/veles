"""Install and uninstall registry extensions.

One path for every kind: resolve → compatibility → confirm (always, via the
critical-ops gate) → materialise → hash → record. The record is the approval the
module load gate checks, so a module installed here runs; one edited afterwards
does not.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from veles import __version__
from veles.core.critical_ops import confirm_critical
from veles.core.io_utils import atomic_write_text, dump_toml, load_optional_toml
from veles.core.project import Project
from veles.core.project_config import (
    get_section,
    load_project_config,
    project_config_path,
    save_project_config,
)
from veles.core.registry.catalog import Found
from veles.core.registry.gate import now_iso
from veles.core.registry.hashing import copy_ignore, tree_sha256
from veles.core.registry.model import EXTENSION_FILE
from veles.core.registry.records import InstallRecord, drop_record, load_records, put_record
from veles.core.registry.repo import RegistryRepoError, fetch_git_source
from veles.core.registry.versions import satisfies
from veles.core.user_paths import user_home, user_skills_dir


class InstallError(RuntimeError):
    pass


def describe(found: Found) -> str:
    ext = found.ext
    lines = [
        f"{found.ref}  {ext.version}  ({ext.kind})",
        f"  {ext.description}",
        f"  license: {ext.license}   requires Veles: {ext.requires_veles}",
        f"  source: {ext.source.type}"
        + (f" {ext.source.url}@{ext.source.commit}" if ext.source.type == "git" else ""),
    ]
    if ext.provides:
        lines.append(f"  provides: {', '.join(ext.provides)}")
    if ext.requires:
        lines.append(f"  pip requirements: {', '.join(ext.requires)}")
    if ext.kind == "module":
        lines.append("  A module's code runs inside Veles on every turn. Review it first.")
    return "\n".join(lines)


def pip_hint(found: Found) -> str | None:
    if not found.ext.requires:
        return None
    withs = " ".join(f"--with {r!r}" for r in found.ext.requires)
    return f"this module needs extra packages: uv tool install veles-ai {withs}"


def install(
    found: Found,
    *,
    project: Project | None,
    user_scope: bool = False,
    force: bool = False,
    confirmed: bool = False,
) -> InstallRecord:
    ext = found.ext
    if ext.yanked and not force:
        raise InstallError(f"{found.ref} is yanked: {ext.yanked} (pass --force to install anyway)")
    try:
        compatible = satisfies(__version__, ext.requires_veles)
    except ValueError as exc:
        raise InstallError(f"{found.ref}: bad requires_veles: {exc}") from exc
    if not compatible:
        raise InstallError(
            f"{found.ref} requires Veles {ext.requires_veles}; this is {__version__}"
        )
    needs_project = ext.kind in ("module", "mcp") or (ext.kind == "skill" and not user_scope)
    if needs_project and project is None:
        raise InstallError(f"installing a {ext.kind} needs a project (run inside one)")
    # Cheap collision checks run before the confirmation prompt — no point asking the
    # user to confirm an install that is going to fail on a name clash anyway.
    _check_collision(found, project, user_scope=user_scope)
    if not confirmed and not confirm_critical(
        f"install {found.ref} {ext.version}", describe(found)
    ):
        raise InstallError("aborted")
    if ext.kind == "mcp":
        assert project is not None
        return _install_mcp(found, project)
    target = _target_dir(found, project, user_scope=user_scope)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        materialise(found, target)
        digest = tree_sha256(target)
    except (RegistryRepoError, OSError, ValueError) as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise InstallError(f"{found.ref}: {exc}") from exc
    if ext.source.type == "git" and digest != ext.source.sha256:
        shutil.rmtree(target, ignore_errors=True)
        raise InstallError(
            f"{found.ref}: hash mismatch — expected {ext.source.sha256}, got {digest}"
        )
    rec = _record(found, path=str(target.resolve()), digest=digest, project=project)
    try:
        put_record(rec)
    except OSError as exc:
        # An install that materialised but never got recorded is untracked: a retry
        # sees `target.exists()` and refuses, and `uninstall` can't find it either.
        # Roll the copy back so a failed install leaves nothing behind.
        shutil.rmtree(target, ignore_errors=True)
        raise InstallError(f"{found.ref}: could not record install: {exc}") from exc
    return rec


def _check_collision(found: Found, project: Project | None, *, user_scope: bool) -> None:
    ext = found.ext
    if ext.kind == "mcp":
        assert project is not None
        servers = get_section(load_project_config(project), "mcp", "servers")
        if ext.name in servers:
            raise InstallError(
                f"[mcp.servers.{ext.name}] already exists in {project_config_path(project)}"
            )
        return
    target = _target_dir(found, project, user_scope=user_scope)
    if target.exists():
        raise InstallError(f"{target} already exists — uninstall it or use `registry upgrade`")


def installed_records(project: Project | None) -> list[InstallRecord]:
    """Records for this project plus the user-scoped ones (skills with --user, layouts)."""
    root = str(project.root.resolve()) if project is not None else None
    return [r for r in load_records() if r.project in (None, root)]


def resolve_one_record(name: str, *, project: Project | None) -> InstallRecord:
    """The single installed record for `name`, or raise if it's missing/ambiguous.

    Shared by `uninstall` and `registry.maintenance.upgrade` — both need exactly
    one installed record for a bare name before they can act on it.
    """
    matches = [r for r in installed_records(project) if r.name == name]
    if not matches:
        raise InstallError(f"{name!r} is not installed here")
    if len(matches) > 1:
        kinds = ", ".join(sorted(r.kind for r in matches))
        raise InstallError(f"{name!r} is installed as several kinds ({kinds}); remove by hand")
    return matches[0]


def uninstall(name: str, *, project: Project | None) -> InstallRecord:
    rec = resolve_one_record(name, project=project)
    remove_installed(rec)
    return rec


def remove_installed(rec: InstallRecord) -> None:
    """Delete the installed payload, then drop the record.

    A deletion failure leaves the record in place — the install is still there on
    disk, so the approval that lets it run must stay too. Only "already gone" is
    treated as success (nothing to clean up, safe to drop the record)."""
    if rec.kind == "mcp":
        config_path, _, _ = rec.path.partition("#")
        try:
            _drop_mcp_server(Path(config_path), rec.name)
        except OSError as exc:
            raise InstallError(f"could not remove {rec.path}: {exc}") from exc
    else:
        path = Path(rec.path)
        if path.exists():
            try:
                shutil.rmtree(path)
            except OSError as exc:
                raise InstallError(f"could not remove {rec.path}: {exc}") from exc
    drop_record(rec.path)


def _target_dir(found: Found, project: Project | None, *, user_scope: bool) -> Path:
    name, kind = found.ext.name, found.ext.kind
    if kind == "layout":
        return user_home() / "layouts" / name
    if kind == "skill" and user_scope:
        return user_skills_dir() / name
    assert project is not None
    return (project.modules_dir if kind == "module" else project.skills_dir) / name


def materialise(found: Found, target: Path) -> None:
    """Copy (path source) or fetch (git source) an extension's payload into `target`."""
    ext = found.ext
    if ext.source.type == "git":
        fetch_git_source(ext.source, target)
        return
    assert ext.dir is not None
    shutil.copytree(
        ext.dir,
        target,
        symlinks=True,
        ignore=copy_ignore(EXTENSION_FILE),
    )


def _install_mcp(found: Found, project: Project) -> InstallRecord:
    name = found.ext.name
    cfg = load_project_config(project)
    servers = cfg.setdefault("mcp", {}).setdefault("servers", {})
    if name in servers:
        raise InstallError(f"[mcp.servers.{name}] already exists in {project_config_path(project)}")
    assert found.ext.mcp is not None
    servers[name] = dict(found.ext.mcp)
    save_project_config(project, cfg)
    rec = _record(
        found,
        path=f"{project_config_path(project).resolve()}#mcp.servers.{name}",
        digest=recipe_sha256(found.ext.mcp),
        project=project,
    )
    try:
        put_record(rec)
    except OSError as exc:
        _drop_mcp_server(project_config_path(project), name)
        raise InstallError(f"{found.ref}: could not record install: {exc}") from exc
    return rec


def recipe_sha256(recipe: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()


def _drop_mcp_server(config_path: Path, name: str) -> None:
    data = load_optional_toml(config_path)
    servers = data.get("mcp", {}).get("servers", {})
    if isinstance(servers, dict) and servers.pop(name, None) is not None:
        atomic_write_text(config_path, dump_toml(data))


def _record(found: Found, *, path: str, digest: str, project: Project | None) -> InstallRecord:
    project_root = str(project.root.resolve()) if project is not None else None
    user_scoped = (
        found.ext.kind == "layout" or project_root is None or not path.startswith(project_root)
    )
    return InstallRecord(
        name=found.ext.name,
        kind=found.ext.kind,
        path=path,
        tree_sha256=digest,
        project=None if user_scoped else project_root,
        registry=found.registry,
        group=found.ext.group,
        version=found.ext.version,
        commit=found.commit,
        installed_at=now_iso(),
    )
