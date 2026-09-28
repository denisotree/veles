"""`veles registry validate` — the one implementation of a registry's CI checks.

A registry's workflow runs `uvx --with pytest veles-ai==<pin> registry validate`,
so authors, reviewers and CI all run the same code. `errors` block the merge;
`review` is a non-blocking report posted on the PR for the human reviewer.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from veles.core.frontmatter import parse_frontmatter
from veles.core.layout.manifest import LayoutManifestError, read_manifest
from veles.core.module_manifest import ManifestError, parse_entrypoint, parse_manifest
from veles.core.modules import (
    HOOK_NAMES,
    ModuleHandle,
    ModuleLoadError,
    ModuleRegistry,
    load_module,
)
from veles.core.registry.hashing import tree_sha256
from veles.core.registry.model import (
    EXTENSION_FILE,
    Extension,
    ExtensionError,
    RegistryMeta,
    load_registry_meta,
    parse_extension,
    scan_registry,
)
from veles.core.registry.repo import RegistryRepoError, changed_paths, fetch_git_source, file_at
from veles.core.registry.scan import scan_python
from veles.core.registry.versions import is_newer, satisfies

PERMISSIVE_LICENSES = frozenset(
    {
        "Apache-2.0",
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "0BSD",
        "Zlib",
        "Unlicense",
        "MPL-2.0",
    }
)
_PROVIDES_PREFIXES = ("hook:", "tool:", "platform:", "provider:")


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    review: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_markdown(self) -> str:
        lines = ["## Veles registry validation", ""]
        lines += [f"- ❌ {e}" for e in self.errors] or ["- ✅ all checks passed"]
        if self.review:
            lines += ["", "### For the reviewer (not blocking)", ""]
            lines += [f"- {r}" for r in self.review]
        return "\n".join(lines) + "\n"


def validate_registry(
    root: Path, *, base: str | None = None, run_code: bool = False
) -> ValidationReport:
    """`run_code=False` (the default for a local run) never executes the extension:
    static checks plus the reviewer scan only. CI passes `--run-code` to also import
    modules (`register()` vs `provides`) and run their tests — PR code must not run on
    a reviewer's machine just because they validated it."""
    report = ValidationReport()
    try:
        meta = load_registry_meta(root)
    except ExtensionError as exc:
        report.errors.append(str(exc))
        return report
    entries, parse_errors = scan_registry(root)
    report.errors += [f"{p.relative_to(root)}: {msg}" for p, msg in parse_errors]
    seen: dict[str, Extension] = {}
    for ext in entries:
        if ext.name in seen:
            report.errors.append(
                f"duplicate name {ext.name!r}: {ext.group}/ and {seen[ext.name].group}/"
            )
        seen.setdefault(ext.name, ext)
    targets = entries if base is None else _changed(root, base, entries)
    for ext in targets:
        report.errors += [
            f"{ext.group}/{ext.name}: {e}" for e in _check(ext, meta, root, report, run_code)
        ]
        if base is not None:
            report.errors += [f"{ext.group}/{ext.name}: {e}" for e in _check_bump(ext, root, base)]
    return report


def _check(
    ext: Extension, meta: RegistryMeta, root: Path, report: ValidationReport, run_code: bool
) -> list[str]:
    errors: list[str] = []
    assert ext.dir is not None
    if ext.dir.name != ext.name:
        errors.append(f"directory name {ext.dir.name!r} differs from [extension].name")
    try:
        satisfies("0.0.0", ext.requires_veles)
    except ValueError as exc:
        errors.append(f"requires_veles: {exc}")
    if meta.public and ext.license not in PERMISSIVE_LICENSES:
        errors.append(f"license {ext.license!r} is not allowed in a public registry")
    work = root / ".tmp" / "validate" / ext.name
    shutil.rmtree(work, ignore_errors=True)
    try:
        payload = _payload(ext, work)
        digest = tree_sha256(payload)
        if ext.source.type == "git" and digest != ext.source.sha256:
            errors.append(f"sha256 mismatch: declared {ext.source.sha256}, actual {digest}")
        errors += _check_kind(ext, payload, run_code)
        report.review += [f"{ext.group}/{ext.name}: {f}" for f in scan_python(payload)]
        if ext.requires:
            report.review.append(
                f"{ext.group}/{ext.name}: pip requirements {', '.join(ext.requires)}"
            )
    except (RegistryRepoError, ValueError, OSError) as exc:
        errors.append(str(exc))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return errors


def _payload(ext: Extension, work: Path) -> Path:
    if ext.source.type == "git":
        work.parent.mkdir(parents=True, exist_ok=True)
        fetch_git_source(ext.source, work)
        return work
    assert ext.dir is not None
    return ext.dir


def _check_kind(ext: Extension, payload: Path, run_code: bool) -> list[str]:
    if ext.kind == "skill":
        skill = payload / "SKILL.md"
        if not skill.is_file():
            return ["SKILL.md is missing"]
        fm, _body = parse_frontmatter(skill.read_text(encoding="utf-8"))
        if not isinstance(fm.get("description"), str) or not fm.get("description"):
            return ["SKILL.md frontmatter needs a non-empty 'description'"]
        return []
    if ext.kind == "layout":
        try:
            read_manifest(payload / "layout.toml")
        except (LayoutManifestError, OSError) as exc:
            return [f"layout.toml: {exc}"]
        return []
    if ext.kind == "mcp":
        from veles.mcp.config import parse_server

        assert ext.mcp is not None
        return [] if parse_server(ext.name, ext.mcp) is not None else ["[mcp] recipe is invalid"]
    return _check_module(ext, payload, run_code)


def _check_module(ext: Extension, payload: Path, run_code: bool) -> list[str]:
    errors: list[str] = []
    bad = [p for p in ext.provides if not p.startswith(_PROVIDES_PREFIXES)]
    if bad:
        errors.append(f"provides entries must start with {', '.join(_PROVIDES_PREFIXES)}: {bad}")
    try:
        manifest = parse_manifest((payload / "module.toml").read_text(encoding="utf-8"))
        file_part, _ = parse_entrypoint(manifest.entrypoint)
    except (OSError, ManifestError) as exc:
        return [*errors, f"module.toml: {exc}"]
    if not (payload / file_part).is_file():
        return [*errors, f"entrypoint file {file_part!r} not found"]
    if not run_code:
        return errors
    registry = ModuleRegistry()
    try:
        load_module(ModuleHandle(name=manifest.name, manifest=manifest, dir=payload), registry)
    except ModuleLoadError as exc:
        return [*errors, f"register() failed: {exc}"]
    registered = {f"hook:{h}" for h in HOOK_NAMES if any(True for _ in registry.iter_hooks(h))}
    declared = {p for p in ext.provides if p.startswith("hook:")}
    if registered != declared:
        errors.append(
            f"provides declares hooks {sorted(declared)} but register() adds {sorted(registered)}"
        )
    tests = payload / "tests"
    if tests.is_dir():
        # -c /dev/null + explicit --rootdir stop pytest from walking up from this
        # payload (which lives under <registry root>/.tmp/validate/<name>, itself
        # under the outer Veles repo's own tmp/pytest basetemp) and picking up
        # *this* repo's pyproject.toml ([tool.pytest.ini_options] addopts/
        # asyncio_mode) — the extension's tests must run in total isolation from
        # the validator's own test config. -c /dev/null alone still lets pytest
        # collect any conftest.py above the payload (confcutdir defaults past
        # it), so --confcutdir pins that too — proven with a conftest.py at the
        # registry root that raises on import. -p no:cacheprovider keeps it from
        # writing a .pytest_cache into the payload (controller ruling 2).
        try:
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "-c",
                    "/dev/null",
                    "--confcutdir",
                    str(payload),
                    "--rootdir",
                    str(payload),
                    str(tests),
                ],
                cwd=payload,
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            errors.append("tests timed out after 600s")
            return errors
        if run.returncode != 0:
            tail = "\n".join((run.stdout + run.stderr).strip().splitlines()[-5:])
            errors.append(f"tests failed:\n{tail}")
    return errors


def _changed(root: Path, base: str, entries: list[Extension]) -> list[Extension]:
    touched = {
        "/".join(p.split("/")[:3]) for p in changed_paths(root, base) if p.startswith("extensions/")
    }
    return [
        e for e in entries if e.dir is not None and e.dir.relative_to(root).as_posix() in touched
    ]


def _check_bump(ext: Extension, root: Path, base: str) -> list[str]:
    assert ext.dir is not None
    rel = (ext.dir / EXTENSION_FILE).relative_to(root).as_posix()
    old_text = file_at(root, base, rel)
    if old_text is None:
        return []
    try:
        old = parse_extension(old_text)
    except ExtensionError:
        return []
    if not is_newer(ext.version, old.version):
        return [f"changed but version {ext.version} is not greater than {old.version}"]
    return []
