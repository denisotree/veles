"""Builders for on-disk extension registries used by the registry tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

_SKILL_MD = "---\nname: {name}\ndescription: Example skill {name}.\n---\n\nDo the thing.\n"


def write_registry(root: Path, *, name: str = "test", public: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "registry.toml").write_text(
        f'[registry]\nname = "{name}"\ndescription = "Test registry"\nschema = 1\n'
        f"public = {'true' if public else 'false'}\n",
        encoding="utf-8",
    )
    (root / "extensions").mkdir(exist_ok=True)
    return root


def write_extension(
    root: Path,
    group: str,
    name: str,
    *,
    kind: str = "skill",
    version: str = "0.1.0",
    extra_ext: str = "",
    source: str = 'type = "path"',
    files: dict[str, str] | None = None,
    mcp: str = "",
) -> Path:
    ext_dir = root / "extensions" / group / name
    ext_dir.mkdir(parents=True, exist_ok=True)
    text = (
        f'[extension]\nname = "{name}"\nkind = "{kind}"\nversion = "{version}"\n'
        f'description = "Extension {name}"\nlicense = "Apache-2.0"\n'
        f'requires_veles = ">=1.0,<2"\n{extra_ext}\n[source]\n{source}\n'
    )
    if mcp:
        text += f"\n[mcp]\n{mcp}\n"
    (ext_dir / "extension.toml").write_text(text, encoding="utf-8")
    payload = files
    if payload is None and kind == "skill":
        payload = {"SKILL.md": _SKILL_MD.format(name=name)}
    for rel, body in (payload or {}).items():
        target = ext_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return ext_dir


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit_all(repo: Path, message: str = "update") -> str:
    if not (repo / ".git").is_dir():
        git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")
