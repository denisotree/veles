"""Install / remove / promote / demote skills.

Closes TASK.md #2.6 (project-scope install) and VISION §5.5 (user-level
skills + promotion, M40). `install_skill_from_source` validates the
frontmatter via `discover_skills` after copy/clone and rolls back the
target directory on any failure. The `scope` parameter chooses between
project-local (`<project>/.veles/skills/`) and user-global
(`~/.veles/skills/`); on name collision, project wins at discovery time.

`promote_skill` copies project → user (resetting telemetry by default
since per-project counters shouldn't leak into user-global scope).
`demote_skill` copies user → project (preserving telemetry as audit
trail). Both refuse on collision at the destination.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from veles.core.project import Project
from veles.core.skills import (
    _SKILL_FILENAME,
    Skill,
    discover_skills,
    parse_frontmatter,
    render_frontmatter,
    user_skills_dir,
)
from veles.core.wiki import _normalize_slug


class SkillInstallError(RuntimeError):
    pass


class SkillNotFoundError(RuntimeError):
    pass


_GIT_URL_RE = re.compile(r"^(git@|git://|ssh://|https?://)")
_GIT_TIMEOUT_SEC = 300


def _is_git_url(source: str) -> bool:
    return bool(_GIT_URL_RE.match(source)) or source.endswith(".git")


def _derive_name(source: str) -> str:
    if _is_git_url(source):
        last = source.rstrip("/").split("/")[-1]
        last = last.removesuffix(".git")
        return _normalize_slug(last) or "installed-skill"
    return Path(source).resolve().name


def install_skill_from_source(
    source: str,
    *,
    project: Project,
    name_override: str | None = None,
    scope: str = "project",
) -> Skill:
    """Clone (git URL) or copy (local dir) → validate → return Skill.

    `scope`: "project" (default; writes to `<project>/.veles/skills/`) or
    "user" (writes to `~/.veles/skills/`, shared across projects).
    Raises SkillInstallError on any failure; cleans up the partially-installed
    target directory.
    """
    target_dir = _scope_dir(project, scope)
    name = name_override or _derive_name(source)
    target = target_dir / name
    if target.exists() and any(target.iterdir()):
        raise SkillInstallError(
            f"target directory {target} already exists and is non-empty; "
            "remove the existing skill first"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if _is_git_url(source):
            _git_clone(source, target)
        else:
            src_path = Path(source).resolve()
            if not src_path.is_dir():
                raise SkillInstallError(f"source {source!r} is neither a git URL nor a directory")
            shutil.copytree(src_path, target, symlinks=False)
        if not (target / _SKILL_FILENAME).is_file():
            raise SkillInstallError(f"installed source has no {_SKILL_FILENAME} at {target}")
        match = next(
            (s for s in discover_skills(project) if s.name == name and s.scope == scope),
            None,
        )
        if match is None:
            raise SkillInstallError(
                f"installed source at {target} did not pass discover_skills; "
                f"check SKILL.md frontmatter (name='{name}', description required)"
            )
        return match
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


def _git_clone(url: str, target: Path) -> None:
    if shutil.which("git") is None:
        raise SkillInstallError("git executable not found in PATH")
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target)],
            check=True,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SEC,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.decode("utf-8", "replace").strip() if exc.stderr else "(no stderr)"
        raise SkillInstallError(f"git clone failed: {msg}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SkillInstallError(f"git clone timed out after {_GIT_TIMEOUT_SEC}s") from exc


def remove_skill(name: str, *, project: Project, scope: str = "project") -> None:
    """Delete `<scope>/skills/<name>/` recursively. Scope: "project" or "user"."""
    target = _scope_dir(project, scope) / name
    if not target.is_dir():
        raise SkillNotFoundError(f"no {scope}-scope skill named {name!r} at {target}")
    shutil.rmtree(target)


def promote_skill(name: str, *, project: Project, reset_telemetry: bool = True) -> Path:
    """Copy `<project>/.veles/skills/<name>/` → `~/.veles/skills/<name>/`.

    Telemetry counters (`use_count`, `success_count`, `error_count`,
    `last_used`, `last_error_at`) are reset by default — per-project usage
    counts shouldn't leak into user-global scope. Pass
    `reset_telemetry=False` to preserve them. Refuses if the target
    already exists at user scope.
    """
    src = project.skills_dir / name
    if not src.is_dir():
        raise SkillNotFoundError(f"no project-scope skill named {name!r} at {src}")
    dst = user_skills_dir() / name
    if dst.exists():
        raise SkillInstallError(
            f"user-scope skill {name!r} already exists at {dst}; remove it first or pick a new name"
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, symlinks=False)
    if reset_telemetry:
        _reset_skill_telemetry(dst / _SKILL_FILENAME)
    return dst


def demote_skill(name: str, *, project: Project) -> Path:
    """Copy `~/.veles/skills/<name>/` → `<project>/.veles/skills/<name>/`.

    Telemetry is preserved (audit trail). Refuses if the target already
    exists at project scope.
    """
    src = user_skills_dir() / name
    if not src.is_dir():
        raise SkillNotFoundError(f"no user-scope skill named {name!r} at {src}")
    dst = project.skills_dir / name
    if dst.exists():
        raise SkillInstallError(
            f"project-scope skill {name!r} already exists at {dst}; "
            "remove it first or pick a new name"
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, symlinks=False)
    return dst


def _scope_dir(project: Project, scope: str) -> Path:
    if scope == "project":
        return project.skills_dir
    if scope == "user":
        return user_skills_dir()
    raise SkillInstallError(f"unknown scope {scope!r}; expected 'project' or 'user'")


def _reset_skill_telemetry(skill_path: Path) -> None:
    """Zero out use/success/error counts and timestamps in SKILL.md frontmatter."""
    raw = skill_path.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(raw)
    if not fm:
        return
    fm["use_count"] = 0
    fm["success_count"] = 0
    fm["error_count"] = 0
    fm["last_used"] = None
    fm["last_error_at"] = None
    skill_path.write_text(render_frontmatter(fm, body), encoding="utf-8")
