"""Layout-pack manifest model and TOML reader.

A layout-pack's `layout.toml` looks like:

    [layout]
    name = "llm-wiki"
    description = "Karpathy-style LLM Wiki: sources/, wiki/, INDEX, LOG"
    version = "1.0"
    # Optional (M162): file injected into the stable system prompt.
    context_file = "INDEX.md"

    # Optional (M162): core content engines this pack activates.
    [layout.engines]
    wiki = true

    # Optional (M162): what `veles init` scaffolds for this pack.
    [layout.scaffold]
    dirs = ["notes/"]
    agents_md_template = "templates/AGENTS.md"   # inside the pack root

    [[layout.writable_zones]]
    path = "wiki/"
    description = "LLM-generated knowledge, the only zone the agent writes to"

    [[layout.writable_zones]]
    path = "sources/"
    readonly = true
    description = "Raw immutable source material"

    [[layout.operations]]
    name = "ingest"
    skill = "ingest"
    description = "Read a source URL or file and write a wiki page"

    [[layout.operations]]
    name = "query"
    skill = "query"
    description = "Answer a question from the wiki via search + read"

The manifest doesn't include the skill bodies themselves — those live
in the pack's `skills/<name>/SKILL.md` files alongside the manifest.
The dispatcher (M117.4 / M120) wires `operations[*].skill` to the
matching SKILL by name when the pack is mounted.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class LayoutManifestError(ValueError):
    """Raised when `layout.toml` is missing required fields or has the
    wrong shape. Carries the manifest path so the caller can surface
    a helpful error."""

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path


@dataclass(frozen=True, slots=True)
class LayoutWritableZone:
    """One directory the layout pack declares — either writable by the
    agent or read-only. Paths are relative to the project root and
    trailing slashes are preserved verbatim (so `wiki/` and `wiki`
    are normalised by the consumer, not the parser)."""

    path: str
    description: str = ""
    readonly: bool = False


@dataclass(frozen=True, slots=True)
class LayoutOperation:
    """A named operation the layout exposes (`ingest`, `query`, …).
    `skill` is the name of a SKILL.md inside the same pack that
    implements the operation. The runtime mounts these as callable
    skills when the pack is active."""

    name: str
    skill: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class LayoutManifest:
    """Typed view of one layout pack's `layout.toml`."""

    name: str
    description: str = ""
    version: str = "0.0"
    writable_zones: tuple[LayoutWritableZone, ...] = field(default_factory=tuple)
    operations: tuple[LayoutOperation, ...] = field(default_factory=tuple)
    # M162: names of core content engines this pack activates (only
    # `[layout.engines]` keys with a `true` value). Today the only
    # engine core ships is `wiki`.
    engines: tuple[str, ...] = field(default_factory=tuple)
    # M162: project-root-relative file injected into the stable system
    # prompt (e.g. the wiki's `INDEX.md`). None → no injection.
    context_file: str | None = None
    # M188: pack-root-relative path of a behavioural-prompt `.md` file
    # injected into the stable system prompt (e.g. `templates/behaviour.md`).
    # Unlike `context_file` (read from the PROJECT root), this is read from
    # the PACK root so a pack edit reaches existing projects. Engine-
    # independent — any pack may declare it. None → no injection.
    prompt_file: str | None = None
    # M162: directories `veles init` creates for this pack (relative to
    # the project root).
    scaffold_dirs: tuple[str, ...] = field(default_factory=tuple)
    # M162: pack-root-relative path of an AGENTS.md template ({name} is
    # substituted). None → core's layout-agnostic default template.
    agents_md_template: str | None = None
    # Extra wiki categories this pack adds on top of the core defaults
    # (`[layout.wiki].categories`). Nested paths like `projects/work` allowed.
    # Empty → the core default category set only. Sourced by `Wiki` so the
    # allowed category list is pack-configurable, not a hardcoded constant.
    wiki_categories: tuple[str, ...] = field(default_factory=tuple)
    # Source path of the manifest file. Useful for error messages and
    # for the discovery layer to compute the pack's root directory.
    source: Path | None = None

    def engine_enabled(self, engine: str) -> bool:
        return engine in self.engines

    def writable_path_strings(self) -> tuple[str, ...]:
        """Just the `path` strings of the non-readonly zones — handy for
        path-guard configuration (M117 follow-up wires this into
        `core/path_guard.py`)."""
        return tuple(z.path for z in self.writable_zones if not z.readonly)

    def operation(self, name: str) -> LayoutOperation | None:
        for op in self.operations:
            if op.name == name:
                return op
        return None


def read_manifest(path: Path) -> LayoutManifest:
    """Parse `<path>/layout.toml` (or `<path>` itself if it's the toml
    file) into a `LayoutManifest`. Raises `LayoutManifestError` on
    structural problems; `FileNotFoundError` if the file doesn't exist."""
    toml_path = path if path.is_file() else path / "layout.toml"
    if not toml_path.is_file():
        raise FileNotFoundError(f"layout manifest not found: {toml_path}")

    with toml_path.open("rb") as fh:
        try:
            data = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            raise LayoutManifestError(
                f"layout.toml is not valid TOML: {exc}", path=toml_path
            ) from exc

    layout_section = data.get("layout")
    if not isinstance(layout_section, dict):
        raise LayoutManifestError("layout.toml must contain a [layout] section", path=toml_path)

    name = layout_section.get("name")
    if not isinstance(name, str) or not name.strip():
        raise LayoutManifestError("[layout].name must be a non-empty string", path=toml_path)

    description = layout_section.get("description", "")
    if not isinstance(description, str):
        raise LayoutManifestError("[layout].description must be a string", path=toml_path)

    version = layout_section.get("version", "0.0")
    if not isinstance(version, (str, int, float)):
        raise LayoutManifestError("[layout].version must be a string", path=toml_path)

    context_file = layout_section.get("context_file")
    if context_file is not None and (not isinstance(context_file, str) or not context_file.strip()):
        raise LayoutManifestError(
            "[layout].context_file must be a non-empty string", path=toml_path
        )

    prompt_file = layout_section.get("prompt_file")
    if prompt_file is not None and (not isinstance(prompt_file, str) or not prompt_file.strip()):
        raise LayoutManifestError("[layout].prompt_file must be a non-empty string", path=toml_path)

    zones = _parse_zones(layout_section.get("writable_zones", []), toml_path)
    operations = _parse_operations(layout_section.get("operations", []), toml_path)
    engines = _parse_engines(layout_section.get("engines", {}), toml_path)
    scaffold_dirs, agents_md_template = _parse_scaffold(
        layout_section.get("scaffold", {}), toml_path
    )
    wiki_categories = _parse_wiki_categories(layout_section.get("wiki", {}), toml_path)

    return LayoutManifest(
        name=name.strip(),
        description=description.strip(),
        version=str(version),
        writable_zones=zones,
        operations=operations,
        engines=engines,
        context_file=context_file.strip() if isinstance(context_file, str) else None,
        prompt_file=prompt_file.strip() if isinstance(prompt_file, str) else None,
        scaffold_dirs=scaffold_dirs,
        agents_md_template=agents_md_template,
        wiki_categories=wiki_categories,
        source=toml_path,
    )


def _parse_wiki_categories(raw: object, toml_path: Path) -> tuple[str, ...]:
    """Parse `[layout.wiki].categories` — a list of extra wiki category paths
    (nested like `projects/work` allowed) the pack adds to the core defaults.
    Each entry must be a safe project-relative path (no leading `/`, no `..`)."""
    if not isinstance(raw, dict):
        raise LayoutManifestError("[layout.wiki] must be a table", path=toml_path)
    cats_raw = raw.get("categories", [])
    if not isinstance(cats_raw, list) or not all(
        isinstance(c, str) and c.strip() for c in cats_raw
    ):
        raise LayoutManifestError(
            "[layout.wiki].categories must be a list of non-empty strings", path=toml_path
        )
    out: list[str] = []
    for c in cats_raw:
        clean = c.strip().strip("/")
        if not clean or ".." in Path(clean).parts:
            raise LayoutManifestError(
                f"[layout.wiki].categories entry escapes the wiki root: {c!r}", path=toml_path
            )
        out.append(clean)
    return tuple(out)


def _parse_engines(raw: object, toml_path: Path) -> tuple[str, ...]:
    if not isinstance(raw, dict):
        raise LayoutManifestError("[layout.engines] must be a table of booleans", path=toml_path)
    out: list[str] = []
    for key, value in raw.items():
        if not isinstance(value, bool):
            raise LayoutManifestError(f"[layout.engines].{key} must be a boolean", path=toml_path)
        if value:
            out.append(str(key))
    return tuple(sorted(out))


def _parse_scaffold(raw: object, toml_path: Path) -> tuple[tuple[str, ...], str | None]:
    if not isinstance(raw, dict):
        raise LayoutManifestError("[layout.scaffold] must be a table", path=toml_path)
    dirs_raw = raw.get("dirs", [])
    if not isinstance(dirs_raw, list) or not all(
        isinstance(d, str) and d.strip() for d in dirs_raw
    ):
        raise LayoutManifestError(
            "[layout.scaffold].dirs must be a list of non-empty strings",
            path=toml_path,
        )
    dirs: list[str] = []
    for d in dirs_raw:
        clean = d.strip()
        if clean.startswith("/") or ".." in Path(clean).parts:
            raise LayoutManifestError(
                f"[layout.scaffold].dirs entry escapes the project root: {d!r}",
                path=toml_path,
            )
        dirs.append(clean)
    template = raw.get("agents_md_template")
    if template is not None:
        if not isinstance(template, str) or not template.strip():
            raise LayoutManifestError(
                "[layout.scaffold].agents_md_template must be a non-empty string",
                path=toml_path,
            )
        template = template.strip()
        if template.startswith("/") or ".." in Path(template).parts:
            raise LayoutManifestError(
                "[layout.scaffold].agents_md_template escapes the pack root",
                path=toml_path,
            )
    return tuple(dirs), template


def _parse_zones(raw: object, toml_path: Path) -> tuple[LayoutWritableZone, ...]:
    if not isinstance(raw, list):
        raise LayoutManifestError(
            "[[layout.writable_zones]] must be a list of tables", path=toml_path
        )
    out: list[LayoutWritableZone] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise LayoutManifestError(f"layout.writable_zones[{i}] must be a table", path=toml_path)
        path_value = entry.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            raise LayoutManifestError(
                f"layout.writable_zones[{i}].path must be a non-empty string",
                path=toml_path,
            )
        description = entry.get("description", "")
        if not isinstance(description, str):
            raise LayoutManifestError(
                f"layout.writable_zones[{i}].description must be a string",
                path=toml_path,
            )
        readonly = entry.get("readonly", False)
        if not isinstance(readonly, bool):
            raise LayoutManifestError(
                f"layout.writable_zones[{i}].readonly must be a boolean",
                path=toml_path,
            )
        out.append(
            LayoutWritableZone(
                path=path_value.strip(),
                description=description.strip(),
                readonly=readonly,
            )
        )
    return tuple(out)


def _parse_operations(raw: object, toml_path: Path) -> tuple[LayoutOperation, ...]:
    if not isinstance(raw, list):
        raise LayoutManifestError("[[layout.operations]] must be a list of tables", path=toml_path)
    out: list[LayoutOperation] = []
    seen: set[str] = set()
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise LayoutManifestError(f"layout.operations[{i}] must be a table", path=toml_path)
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise LayoutManifestError(
                f"layout.operations[{i}].name must be a non-empty string",
                path=toml_path,
            )
        skill = entry.get("skill")
        if not isinstance(skill, str) or not skill.strip():
            raise LayoutManifestError(
                f"layout.operations[{i}].skill must be a non-empty string",
                path=toml_path,
            )
        description = entry.get("description", "")
        if not isinstance(description, str):
            raise LayoutManifestError(
                f"layout.operations[{i}].description must be a string",
                path=toml_path,
            )
        name = name.strip()
        if name in seen:
            raise LayoutManifestError(
                f"layout.operations: duplicate operation name {name!r}",
                path=toml_path,
            )
        seen.add(name)
        out.append(
            LayoutOperation(
                name=name,
                skill=skill.strip(),
                description=description.strip(),
            )
        )
    return tuple(out)


__all__ = [
    "LayoutManifest",
    "LayoutManifestError",
    "LayoutOperation",
    "LayoutWritableZone",
    "read_manifest",
]
