"""Create registries and extensions from the template shipped inside the package.

The template is versioned with Veles, so a new registry always matches the current
schema and pins the Veles version its CI validates with. Works for any git host.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from veles import __version__
from veles.core.io_utils import dump_toml
from veles.core.registry.catalog import Found
from veles.core.registry.model import EXTENSION_FILE, KINDS

_TEMPLATE = Path(__file__).resolve().parent.parent.parent / "registry_template"
CI_CHOICES = ("github", "gitlab", "none")


class TemplateError(RuntimeError):
    pass


def init_registry(dest: Path, *, name: str, ci: str = "github", public: bool = False) -> Path:
    if ci not in CI_CHOICES:
        raise TemplateError(f"--ci must be one of {', '.join(CI_CHOICES)}")
    if dest.exists() and any(dest.iterdir()):
        raise TemplateError(f"{dest} is not empty")
    shutil.copytree(_TEMPLATE / "base", dest, dirs_exist_ok=True)
    (dest / "gitignore.tmpl").rename(dest / ".gitignore")
    if ci == "github":
        shutil.copytree(_TEMPLATE / "github", dest / ".github")
    elif ci == "gitlab":
        shutil.copy2(_TEMPLATE / "gitlab" / "gitlab-ci.yml", dest / ".gitlab-ci.yml")
    _strip_tmpl(dest)
    _render(
        dest,
        {"@@NAME@@": name, "@@VELES_VERSION@@": __version__, "@@PUBLIC@@": str(public).lower()},
    )
    return dest


def scaffold_extension(root: Path, kind: str, name: str, *, group: str = "internal") -> Path:
    if kind not in KINDS:
        raise TemplateError(f"kind must be one of {', '.join(KINDS)}")
    dest = root / "extensions" / group / name
    if dest.exists():
        raise TemplateError(f"{dest} already exists")
    module = name.replace("-", "_")
    shutil.copytree(_TEMPLATE / "scaffold" / kind, dest)
    for path in sorted(dest.rglob("*@@MODULE@@*")):
        path.rename(path.with_name(path.name.replace("@@MODULE@@", module)))
    _strip_tmpl(dest)
    _render(dest, {"@@EXT@@": name, "@@MODULE@@": module})
    return dest


def vendor_extension(found: Found, into: Path, *, group: str = "vendor") -> Path:
    """Copy an extension into another registry as a `path` source that remembers its upstream."""
    ext = found.ext
    dest = into / "extensions" / group / ext.name
    if dest.exists():
        raise TemplateError(f"{dest} already exists")
    from veles.core.registry.install import materialise

    materialise(found, dest)
    table: dict[str, Any] = {
        "name": ext.name,
        "kind": ext.kind,
        "version": ext.version,
        "description": ext.description,
        "license": ext.license,
        "requires_veles": ext.requires_veles,
        "upstream": f"{found.registry}:{ext.name}@{found.commit}",
    }
    for key in ("tags", "provides", "requires"):
        values = getattr(ext, key)
        if values:
            table[key] = list(values)
    data: dict[str, Any] = {"extension": table, "source": {"type": "path"}}
    if ext.mcp:
        data["mcp"] = ext.mcp
    (dest / EXTENSION_FILE).write_text(dump_toml(data), encoding="utf-8")
    return dest


def _strip_tmpl(root: Path) -> None:
    """`foo.py.tmpl` → `foo.py`. Template code is stored with the suffix so the Veles
    repo's own ruff/pylint never mistake it for Veles code."""
    for path in sorted(root.rglob("*.tmpl")):
        path.rename(path.with_name(path.name.removesuffix(".tmpl")))


def _render(root: Path, values: dict[str, str]) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rendered = text
        for key, value in values.items():
            rendered = rendered.replace(key, value)
        if rendered != text:
            path.write_text(rendered, encoding="utf-8")
