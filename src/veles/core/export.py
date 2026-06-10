"""Export / import (M45) — backup, migrate, share Veles project state.

Three commands cover three use cases:

- `veles export full <bundle.tar.gz>` packs the whole project (`AGENTS.md`
  + `.veles/`) into a tarball for backup or migration to another machine.
  Excludes runtime ephemera (`*.lock` and `budget.state.json` reflect the
  live loop, not durable state).

- `veles export template <bundle.tar.gz>` packs a sanitised subset for
  sharing or publishing: schema (`AGENTS.md` + `project.toml`), knowledge
  artefacts (`wiki/{concepts,entities,insights,queries}`), installed
  skills/modules, routing + subprojects metadata. Excludes: `memory.db`
  (session transcripts), `sources/` (raw materials), `wiki/sessions/`
  (per-session pages), `trust.json` (user grants), `curator.state.json`
  (cursor). Every text file is run through PII regex sanitisation —
  emails, IPs, common API-key shapes, bearer tokens are replaced with
  placeholders.

- `veles import <bundle.tar.gz> [--into <dir>]` validates the bundle
  (manifest version + no path-escape entries) and unpacks into the
  target directory. Refuses if the target already contains `.veles/`
  unless `--force` is given (which removes the existing state first).

Bundle layout (both modes):

    MANIFEST.json
    AGENTS.md
    .veles/<contents per mode>

PII sanitisation is best-effort: regex replacement, not deterministic
redaction. The user should still review templates before publishing.
"""

from __future__ import annotations

import datetime as _dt
import io
import json
import re
import shutil
import tarfile
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from veles.core.project import Project, load_project

_VELES_BUNDLE_VERSION = "0.0.1"
_BUNDLE_SCHEMA_VERSION = 1
_MANIFEST_FILENAME = "MANIFEST.json"

_RUNTIME_EXCLUDED_NAMES: frozenset[str] = frozenset({"budget.state.json"})
_TEMPLATE_EXCLUDED_FILES: frozenset[str] = frozenset(
    {"memory.db", "trust.json", "curator.state.json"}
)
_TEMPLATE_EXCLUDED_PREFIXES: tuple[str, ...] = (
    # v2: wiki + sources live in the project root.
    "sources/",
    "sources",
    "wiki/sessions/",
    "wiki/sessions",
    # v1 leftovers — kept for any still-unmigrated bundle.
    ".veles/sources/",
    ".veles/sources",
    ".veles/wiki/sessions/",
    ".veles/wiki/sessions",
)

_PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "<EMAIL>"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"), "Bearer <TOKEN>"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"), "<API_KEY>"),
    (re.compile(r"\bAIza[A-Za-z0-9_\-]{30,}\b"), "<GOOGLE_API_KEY>"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"), "<GITHUB_TOKEN>"),
    (re.compile(r"\bxox[abpsr]-[A-Za-z0-9\-]{10,}\b"), "<SLACK_TOKEN>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<IP>"),
)

_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".toml", ".json", ".txt", ".py", ".rst", ".yml", ".yaml", ".ini"}
)


class ExportError(RuntimeError):
    pass


class ImportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExportManifest:
    veles_version: str
    schema_version: int
    exported_at: str
    mode: str
    project_name: str


def export_full(project: Project, bundle_path: Path) -> None:
    _export(project, bundle_path, mode="full")


def export_template(project: Project, bundle_path: Path) -> None:
    _export(project, bundle_path, mode="template")


def import_bundle(source: Path, target_dir: Path, *, force: bool = False) -> Project:
    """Validate `source` and extract into `target_dir`. Returns the loaded Project.

    Refuses if the target already hosts a project unless `force=True`
    (which removes the existing `.veles/` first). Refuses any tarball
    entry whose name escapes the target dir (`..`, absolute paths).
    """
    if not source.is_file():
        raise ImportError(f"bundle {source} not found")
    target_dir = target_dir.resolve()
    state_dir = target_dir / ".veles"
    if state_dir.exists():
        if not force:
            raise ImportError(
                f"target {target_dir} already has a Veles project; "
                "rerun with `--force` to overwrite, or pick an empty directory"
            )
        shutil.rmtree(state_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(source, "r:gz") as tf:
        members = tf.getmembers()
        for m in members:
            if not _is_safe_member_name(m.name):
                raise ImportError(f"unsafe path in bundle: {m.name!r}")
        manifest = _read_manifest(tf, members)
        if manifest.schema_version != _BUNDLE_SCHEMA_VERSION:
            raise ImportError(
                f"unsupported bundle schema version {manifest.schema_version} "
                f"(this Veles supports {_BUNDLE_SCHEMA_VERSION})"
            )
        if manifest.mode not in {"full", "template"}:
            raise ImportError(f"unknown bundle mode {manifest.mode!r}")
        for m in members:
            if m.name == _MANIFEST_FILENAME:
                continue
            tf.extract(m, target_dir, filter="data")

    if not (state_dir / "project.toml").is_file():
        raise ImportError("extracted bundle does not contain .veles/project.toml")
    return load_project(target_dir)


def sanitize_pii(text: str) -> str:
    """Replace common PII patterns with placeholder tokens. Best-effort, regex-only."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---- internals ----


def _export(project: Project, bundle_path: Path, *, mode: str) -> None:
    bundle_path = bundle_path.expanduser()
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = ExportManifest(
        veles_version=_VELES_BUNDLE_VERSION,
        schema_version=_BUNDLE_SCHEMA_VERSION,
        exported_at=_dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        mode=mode,
        project_name=project.name,
    )
    manifest_bytes = (json.dumps(asdict(manifest), indent=2) + "\n").encode("utf-8")

    with tarfile.open(bundle_path, "w:gz") as tf:
        info = tarfile.TarInfo(name=_MANIFEST_FILENAME)
        info.size = len(manifest_bytes)
        info.mtime = int(_dt.datetime.now().timestamp())
        tf.addfile(info, fileobj=io.BytesIO(manifest_bytes))

        for path, arcname in _iter_project_files(project, mode=mode):
            if path.is_symlink():
                tf.add(path, arcname=arcname, recursive=False)
                continue
            if not path.is_file():
                continue
            if mode == "template" and _is_text_file(path):
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    tf.add(path, arcname=arcname, recursive=False)
                    continue
                data = sanitize_pii(text).encode("utf-8")
                info = tarfile.TarInfo(name=arcname)
                info.size = len(data)
                info.mtime = int(path.stat().st_mtime)
                tf.addfile(info, fileobj=io.BytesIO(data))
            else:
                tf.add(path, arcname=arcname, recursive=False)


def _iter_project_files(project: Project, *, mode: str) -> Iterator[tuple[Path, str]]:
    root = project.root
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        p = root / name
        if p.is_symlink() or p.is_file():
            yield p, name

    state = project.state_dir
    if not state.is_dir():
        return
    for path in sorted(state.rglob("*")):
        if not (path.is_file() or path.is_symlink()):
            continue
        rel = path.relative_to(root)
        rel_str = rel.as_posix()
        if _is_excluded(rel_str, path.name, mode=mode):
            continue
        yield path, rel_str


def _is_excluded(rel_path: str, name: str, *, mode: str) -> bool:
    if name in _RUNTIME_EXCLUDED_NAMES:
        return True
    if name.endswith(".lock"):
        return True
    if mode == "template":
        if name in _TEMPLATE_EXCLUDED_FILES:
            return True
        for prefix in _TEMPLATE_EXCLUDED_PREFIXES:
            if rel_path == prefix or rel_path.startswith(prefix):
                return True
    return False


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in _TEXT_EXTENSIONS


def _is_safe_member_name(name: str) -> bool:
    if name.startswith("/"):
        return False
    return ".." not in Path(name).parts


def _read_manifest(tf: tarfile.TarFile, members: list[tarfile.TarInfo]) -> ExportManifest:
    member = next((m for m in members if m.name == _MANIFEST_FILENAME), None)
    if member is None:
        raise ImportError(f"bundle missing {_MANIFEST_FILENAME}")
    fh = tf.extractfile(member)
    if fh is None:
        raise ImportError(f"could not read {_MANIFEST_FILENAME} from bundle")
    try:
        data = json.loads(fh.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ImportError(f"invalid {_MANIFEST_FILENAME}: {exc}") from exc
    if not isinstance(data, dict):
        raise ImportError(f"{_MANIFEST_FILENAME} root is not an object")
    try:
        return ExportManifest(
            veles_version=str(data.get("veles_version") or ""),
            schema_version=int(data.get("schema_version") or 0),
            exported_at=str(data.get("exported_at") or ""),
            mode=str(data.get("mode") or ""),
            project_name=str(data.get("project_name") or ""),
        )
    except (TypeError, ValueError) as exc:
        raise ImportError(f"malformed {_MANIFEST_FILENAME}: {exc}") from exc
