"""Install and uninstall registry extensions.

One path for every kind: resolve → compatibility → confirm (always, via the
critical-ops gate) → materialise → hash → record. The record is the approval the
module load gate checks, so a module installed here runs; one edited afterwards
does not.
"""

from __future__ import annotations

import contextlib
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
from veles.core.registry.records import (
    InstallRecord,
    drop_record,
    install_lock,
    load_records,
    put_record,
)
from veles.core.registry.repo import RegistryRepoError, fetch_git_source
from veles.core.registry.versions import satisfies
from veles.core.user_paths import user_home, user_modules_dir, user_skills_dir
from veles.mcp.approvals import approve, describe_recipe, recipe_hash, revoke


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
    if ext.requires_extensions:
        lines.append(f"  needs: {', '.join(ext.requires_extensions)}")
    if ext.kind == "module":
        lines.append("  A module's code runs inside Veles on every turn. Review it first.")
    if ext.kind == "mcp" and ext.mcp is not None:
        # Installing approves this exact recipe — the user must see all of it.
        lines.append(describe_recipe(ext.name, dict(ext.mcp)))
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
    preapproved: bool = False,
) -> InstallRecord:
    """Install `found` plus whatever it `requires_extensions` that isn't installed
    yet — dependencies first, one confirmation for the whole set; a failure removes
    everything this call installed. Returns `found`'s record. `preapproved`: the
    user already chose this (a channel declared in their config) — nothing is
    asked, for the whole set."""
    plan = _plan(found, project, user_scope=user_scope)
    for item, scope in plan:
        _preflight(item, project, user_scope=scope, force=force)
    deps = len(plan) - 1
    op = f"install {found.ref} {found.ext.version}" + (
        f" (+ {deps} dependenc{'y' if deps == 1 else 'ies'})" if deps else ""
    )
    # `confirmed`: the caller already showed `found` itself (e.g. `upgrade`) — a
    # dependency it never saw is still asked about.
    to_confirm = [] if preapproved else (plan[:-1] if confirmed else plan)
    if to_confirm and not confirm_critical(op, "\n\n".join(describe(f) for f, _ in to_confirm)):
        raise InstallError("aborted")
    done: list[InstallRecord] = []
    # ponytail: one global install lock — installs serialise across extensions too;
    # per-target locks if that ever matters (installs are rare and user-driven).
    with install_lock():
        try:
            for item, scope in plan:
                # Re-checked under the lock: another install may have finished while
                # this one waited at the confirmation prompt — its copy isn't ours.
                _check_collision(item, project, user_scope=scope)
                done.append(_install_one(item, project, user_scope=scope))
        except InstallError:
            for rec in reversed(done):
                with contextlib.suppress(InstallError):
                    remove_installed(rec)
            raise
    return done[-1]


def record_ref(rec: InstallRecord) -> str | None:
    return f"{rec.registry}:{rec.group}/{rec.name}" if rec.registry else None


def _plan(found: Found, project: Project | None, *, user_scope: bool) -> list[tuple[Found, bool]]:
    """`found` and its missing dependencies, dependencies first, each with its scope.
    A layout is user-level, so what it needs is installed for the user too."""
    from veles.core.registry.catalog import ResolveError, resolve

    have = {record_ref(r) for r in installed_records(project)}
    order: list[tuple[Found, bool]] = []
    planned: set[str] = set()

    def visit(item: Found, stack: list[str], scope: bool) -> None:
        if item.ref in stack:
            raise InstallError(f"dependency cycle: {' → '.join([*stack, item.ref])}")
        if item.ref in planned:
            return
        dep_scope = scope or item.ext.kind == "layout"
        for ref in item.ext.requires_extensions:
            if ref in have:
                continue
            try:
                dep = resolve(ref)
            except ResolveError as exc:
                raise InstallError(f"{item.ref} needs {ref}: {exc}") from exc
            visit(dep, [*stack, item.ref], dep_scope)
        planned.add(item.ref)
        order.append((item, scope))

    visit(found, [], user_scope)
    return order


def _preflight(found: Found, project: Project | None, *, user_scope: bool, force: bool) -> None:
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
    needs_project = ext.kind == "mcp" or (ext.kind in ("module", "skill") and not user_scope)
    if needs_project and project is None:
        raise InstallError(f"installing a {ext.kind} needs a project (run inside one)")
    # Cheap collision checks run before the confirmation prompt — no point asking the
    # user to confirm an install that is going to fail on a name clash anyway.
    _check_collision(found, project, user_scope=user_scope)


def _install_one(found: Found, project: Project | None, *, user_scope: bool) -> InstallRecord:
    ext = found.ext
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


def resolve_one_record(
    name: str, *, project: Project | None, user_scope: bool | None = None
) -> InstallRecord:
    """The single installed record for `name`, or raise if it's missing/ambiguous.
    `user_scope` narrows to the user-level (True) or this project's (False) installs.

    Shared by `uninstall` and `registry.maintenance.upgrade` — both need exactly
    one installed record for a bare name before they can act on it.
    """
    matches = [r for r in installed_records(project) if r.name == name]
    if user_scope is not None:
        matches = [r for r in matches if (r.project is None) == user_scope]
    if not matches:
        raise InstallError(f"{name!r} is not installed here")
    if len(matches) > 1:
        if len({r.project is None for r in matches}) > 1:
            raise InstallError(
                f"{name!r} is installed both for the user and in this project — pass --user "
                "for the user-level one, or --project for this project's"
            )
        kinds = ", ".join(sorted(r.kind for r in matches))
        raise InstallError(f"{name!r} is installed as several kinds ({kinds}); remove by hand")
    return matches[0]


def uninstall(
    name: str, *, project: Project | None, force: bool = False, user_scope: bool | None = None
) -> InstallRecord:
    rec = resolve_one_record(name, project=project, user_scope=user_scope)
    ref = record_ref(rec)
    dependants = [r.name for r in load_records() if ref and ref in r.requires_extensions]
    if dependants and not force:
        raise InstallError(
            f"{', '.join(sorted(dependants))} {'needs' if len(dependants) == 1 else 'need'} "
            f"{name!r} — uninstall {'it' if len(dependants) == 1 else 'them'} first "
            "(or pass --force)"
        )
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
        if rec.project is not None:
            revoke(Path(rec.project), rec.name)
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
    if kind == "module" and user_scope:
        return user_modules_dir() / name
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
        digest=recipe_hash(found.ext.mcp),
        project=project,
    )
    try:
        put_record(rec)
    except OSError as exc:
        _drop_mcp_server(project_config_path(project), name)
        raise InstallError(f"{found.ref}: could not record install: {exc}") from exc
    # The install passed `confirm_critical` on this exact recipe — that is the approval.
    approve(project.root, name, servers[name])
    return rec


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
        requires_extensions=found.ext.requires_extensions,
    )
