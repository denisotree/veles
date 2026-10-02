"""`veles registry validate` — the one implementation of a registry's CI checks.

A registry's workflow runs `uvx --with pytest veles-ai==<pin> registry validate`,
so authors, reviewers and CI all run the same code. `errors` block the merge;
`review` is a non-blocking report posted on the PR for the human reviewer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from veles.core.frontmatter import parse_frontmatter
from veles.core.layout.manifest import LayoutManifestError, read_manifest
from veles.core.module_manifest import ManifestError, entrypoint_file, parse_manifest
from veles.core.registry.hashing import bytecode_paths, git_dirs, tree_sha256
from veles.core.registry.model import (
    EXTENSION_FILE,
    REGISTRY_FILE,
    Extension,
    ExtensionError,
    RegistryMeta,
    load_registry_meta,
    parse_extension,
    scan_registry,
)
from veles.core.registry.repo import RegistryRepoError, changed_paths, fetch_git_source, file_at
from veles.core.registry.scan import native_binaries, non_sdk_imports, scan_python
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


def _provides_prefixes() -> tuple[str, ...]:
    """`hook:` plus one `<point>:` per declared contribution point."""
    from veles.core.contributions import CONTRIBUTION_POINTS

    return ("hook:", *(f"{p}:" for p in CONTRIBUTION_POINTS))


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
    root: Path, *, base: str | None = None, run_code: bool = False, install_requires: bool = False
) -> ValidationReport:
    """`run_code=False` (the default for a local run) never executes the extension:
    static checks plus the reviewer scan only. CI passes `--run-code` to also import
    modules (`register()` vs `provides`) and run their tests — PR code must not run on
    a reviewer's machine just because they validated it. `install_requires` (with
    `run_code`) first installs each module's `requires` into a throwaway dir on its
    PYTHONPATH, so tests that drive a real SDK run instead of skipping.

    The code phase runs only after every static check, and only in subprocesses: a
    PR's `register()` must not be able to exit or patch the validator into a green,
    report-less run."""
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
    report.errors += _check_dependencies(entries, meta.name)
    touched: frozenset[str] = frozenset()
    if base is None:
        targets = entries
    else:
        selected = _select_targets(root, base, entries, report)
        if selected is None:
            return report
        targets, touched = selected
    runnable: list[tuple[Extension, Path, Path]] = []
    try:
        for ext in targets:
            work = root / ".tmp" / "validate" / ext.name
            errors, payload = _check(ext, meta, report, work)
            report.errors += [f"{ext.group}/{ext.name}: {e}" for e in errors]
            if run_code and ext.kind == "module" and not errors and payload is not None:
                runnable.append((ext, payload, work))
            # A version bump is only owed by an extension whose own directory
            # changed — not by every extension a registry.toml-triggered full
            # revalidation happens to touch (registry.toml itself carries no
            # per-extension version to compare against).
            if base is not None and ext.dir is not None and _rel(ext.dir, root) in touched:
                report.errors += [
                    f"{ext.group}/{ext.name}: {e}" for e in _check_bump(ext, root, base)
                ]
        for ext, payload, work in runnable:
            report.errors += [
                f"{ext.group}/{ext.name}: {e}"
                for e in _run_module(ext, payload, work, install_requires=install_requires)
            ]
    finally:
        shutil.rmtree(root / ".tmp" / "validate", ignore_errors=True)
    return report


def _check_dependencies(entries: list[Extension], registry: str) -> list[str]:
    """Every `requires_extensions` ref into this registry names a real extension,
    and those refs form no cycle. Refs into other registries can't be checked here."""
    by_ref = {f"{registry}:{e.group}/{e.name}": e for e in entries}
    errors: list[str] = []
    for ext in by_ref.values():
        for dep in ext.requires_extensions:
            if dep.startswith(f"{registry}:") and dep not in by_ref:
                errors.append(f"{ext.group}/{ext.name}: requires_extensions: no extension {dep}")
    done: set[str] = set()

    def visit(ref: str, stack: list[str]) -> None:
        if ref in stack:
            errors.append(f"requires_extensions cycle: {' → '.join([*stack, ref])}")
            return
        if ref in done or ref not in by_ref:
            return
        for dep in by_ref[ref].requires_extensions:
            visit(dep, [*stack, ref])
        done.add(ref)

    for ref in by_ref:
        visit(ref, [])
    return errors


def _check(
    ext: Extension, meta: RegistryMeta, report: ValidationReport, work: Path
) -> tuple[list[str], Path | None]:
    """Static checks only. Returns the errors and the payload dir (a git source's
    payload is fetched into `work`, which the caller removes after the code phase)."""
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
    shutil.rmtree(work, ignore_errors=True)
    payload: Path | None = None
    try:
        payload = _payload(ext, work)
        digest = tree_sha256(payload)
        if ext.source.type == "git" and digest != ext.source.sha256:
            errors.append(f"sha256 mismatch: declared {ext.source.sha256}, actual {digest}")
        bytecode = [p.relative_to(payload).as_posix() for p in bytecode_paths(payload)]
        if bytecode:
            # The hash ignores bytecode, so a committed .pyc would be unreviewed code.
            errors.append(f"bytecode is not allowed in an extension (delete it): {bytecode}")
        git = [p.relative_to(payload).as_posix() for p in git_dirs(payload)]
        if git:
            # `.git` is outside the hash, so anything in it would be unreviewed.
            errors.append(f".git is not allowed in an extension payload: {git}")
        errors += _check_kind(ext, payload)
        report.review += [f"{ext.group}/{ext.name}: {f}" for f in scan_python(payload)]
        report.review += [f"{ext.group}/{ext.name}: {f}" for f in native_binaries(payload)]
        if ext.requires:
            report.review.append(
                f"{ext.group}/{ext.name}: pip requirements {', '.join(ext.requires)}"
            )
    except (RegistryRepoError, ValueError, OSError) as exc:
        errors.append(str(exc))
    return errors, payload


def _payload(ext: Extension, work: Path) -> Path:
    if ext.source.type == "git":
        work.parent.mkdir(parents=True, exist_ok=True)
        fetch_git_source(ext.source, work)
        return work
    assert ext.dir is not None
    return ext.dir


def _check_kind(ext: Extension, payload: Path) -> list[str]:
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
    return _check_module(ext, payload)


def _check_module(ext: Extension, payload: Path) -> list[str]:
    errors: list[str] = []
    prefixes = _provides_prefixes()
    bad = [p for p in ext.provides if not p.startswith(prefixes)]
    if bad:
        errors.append(f"provides entries must start with {', '.join(prefixes)}: {bad}")
    errors += [f"{hit} — import from veles.sdk instead" for hit in non_sdk_imports(payload)]
    try:
        manifest = parse_manifest((payload / "module.toml").read_text(encoding="utf-8"))
        entry, _ = entrypoint_file(payload, manifest.entrypoint)
    except (OSError, ManifestError) as exc:
        return [*errors, f"module.toml: {exc}"]
    if not entry.is_file():
        return [*errors, f"entrypoint file {entry.relative_to(payload).as_posix()!r} not found"]
    return errors


# Run in a child interpreter: the hooks and memory providers it registers come
# back as a JSON object on the last stdout line. The child can still lie about
# them — this checks `provides` against reality for honest authors; it is not
# a security boundary (the human review is).
_DRY_RUN = """\
import json, sys
from pathlib import Path
from veles.core.module_manifest import parse_manifest
from veles.core.modules import HOOK_NAMES, ModuleHandle, ModuleRegistry, load_module
payload = Path(sys.argv[1])
manifest = parse_manifest((payload / "module.toml").read_text(encoding="utf-8"))
registry = ModuleRegistry()
load_module(ModuleHandle(manifest.name, manifest, payload), registry)
from veles.core.contributions import CONTRIBUTION_POINTS
print(json.dumps({
    "hooks": [h for h in HOOK_NAMES if any(True for _ in registry.iter_hooks(h))],
    "contributions": [
        f"{p}:{c.name}" for p in CONTRIBUTION_POINTS for c in registry.contributions(p)
    ],
}))
"""
_CODE_TIMEOUT_S = 600
_INSTALL_TIMEOUT_S = 600


def _install_requires(requires: tuple[str, ...], target: Path) -> str | None:
    """Install an extension's `requires` into `target` (a throwaway dir put on
    PYTHONPATH for its dry run and tests). None on success, else an error.

    `target` goes first on PYTHONPATH, so a package it shares with Veles must
    keep Veles's version: the running env is frozen into a constraints file, and a
    real conflict fails here with the resolver's message. `--` keeps a `requires`
    entry from ever being read as an option (`--index-url=…`)."""
    uv = shutil.which("uv")
    pip = [uv, "pip"] if uv else [sys.executable, "-m", "pip"]
    python = ["--python", sys.executable] if uv else []
    try:
        frozen = subprocess.run(
            [*pip, "freeze", *python], capture_output=True, text=True, check=False, timeout=120
        )
        constraints = target.parent / "constraints.txt"
        constraints.parent.mkdir(parents=True, exist_ok=True)
        pins = [ln for ln in frozen.stdout.splitlines() if "==" in ln and not ln.startswith("-")]
        constraints.write_text("".join(f"{ln}\n" for ln in pins), encoding="utf-8")
        cmd = [*pip, "install", *python, "--target", str(target), "-c", str(constraints)]
        run = subprocess.run(
            [*cmd, "--", *requires],
            capture_output=True,
            text=True,
            check=False,
            timeout=_INSTALL_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"could not install requires: {exc}"
    return None if run.returncode == 0 else f"could not install requires:\n{_tail(run)}"


def _run_code(
    args: list[str], cwd: Path, *, extra_path: Path | None = None
) -> subprocess.CompletedProcess[str] | str:
    """The completed child, or an error string when it timed out. No bytecode is
    written, so a local `--run-code` can't make the next run fail the bytecode check.
    `extra_path` (installed `requires`) goes first on PYTHONPATH."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if extra_path is not None:
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(extra_path), env.get("PYTHONPATH")]))
    try:
        return subprocess.run(
            [sys.executable, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=_CODE_TIMEOUT_S,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return f"timed out after {_CODE_TIMEOUT_S}s"
    except OSError as exc:
        return f"could not run: {exc}"


def _tail(run: subprocess.CompletedProcess[str]) -> str:
    return "\n".join((run.stdout + run.stderr).strip().splitlines()[-5:])


def _registered(run: subprocess.CompletedProcess[str]) -> set[str] | None:
    """Parses the dry run's last stdout line into `{"hook:<name>", "<point>:<name>"}`.
    Untrusted output (the module can lie) — any shape mismatch is a `None`, never
    an exception."""
    lines = run.stdout.strip().splitlines()
    if run.returncode != 0 or not lines:
        return None
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    hooks = payload.get("hooks")
    added = payload.get("contributions")
    if not isinstance(hooks, list) or not all(isinstance(h, str) for h in hooks):
        return None
    if not isinstance(added, list) or not all(isinstance(a, str) for a in added):
        return None
    return {f"hook:{h}" for h in hooks} | set(added)


def _run_module(
    ext: Extension, payload: Path, work: Path, *, install_requires: bool = False
) -> list[str]:
    errors: list[str] = []
    try:
        work.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [f"could not create {work}: {exc}"]
    deps: Path | None = None
    if install_requires and ext.requires:
        deps = work / "deps"
        failed = _install_requires(ext.requires, deps)
        if failed is not None:
            return [failed]
    run = _run_code(["-c", _DRY_RUN, str(payload)], work, extra_path=deps)
    if isinstance(run, str):
        return [f"register() {run}"]
    registered = _registered(run)
    if registered is None:
        return [f"register() failed (no hook/provider list from the dry run):\n{_tail(run)}"]
    declared = {p for p in ext.provides if p.startswith(_provides_prefixes())}
    if registered != declared:
        errors.append(
            f"provides declares {sorted(declared)} but register() adds {sorted(registered)}"
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
        # writing a .pytest_cache into the payload (controller ruling 2). Without
        # --basetemp, a `tmp_path`-using test falls through to pytest's own
        # default (the OS temp dir) once -c /dev/null drops this repo's own
        # `--basetemp=./tmp/pytest` addopts — pin it under `work` so every temp
        # path this validation run touches stays inside the repo, per the
        # project's temp-dir rule.
        tests_run = _run_code(
            [
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
                "--basetemp",
                str(work / "pytest-tmp"),
                str(tests),
            ],
            payload,
            extra_path=deps,
        )
        if isinstance(tests_run, str):
            errors.append(f"tests {tests_run}")
        elif tests_run.returncode != 0:
            errors.append(f"tests failed:\n{_tail(tests_run)}")
    return errors


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _select_targets(
    root: Path, base: str, entries: list[Extension], report: ValidationReport
) -> tuple[list[Extension], frozenset[str]] | None:
    """Returns `(targets, touched)`: `touched` is the set of `extensions/<group>/
    <name>` paths whose own directory actually changed — the version-bump check
    (`_check_bump`) only applies to those, even when `registry.toml` changing
    widens `targets` to every extension (a bump makes no sense for one that
    wasn't itself touched). `None` means `base` couldn't be resolved — an error
    is already on `report` and the caller must stop rather than validate
    against a made-up change set."""
    try:
        changed = changed_paths(root, base)
    except RegistryRepoError as exc:
        report.errors.append(f"cannot compute changes against {base}: {exc}")
        return None
    touched = frozenset("/".join(p.split("/")[:3]) for p in changed if p.startswith("extensions/"))
    if REGISTRY_FILE in changed:
        # registry.toml carries [registry].public — a flip there can change
        # what every extension's license must satisfy, so re-check them all.
        return entries, touched
    targets = [e for e in entries if e.dir is not None and _rel(e.dir, root) in touched]
    return targets, touched


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
