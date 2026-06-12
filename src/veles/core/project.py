"""Project — per-cwd workspace with its own memory, wiki, and AGENTS.md.

A Veles project is a directory that contains a `.veles/` state folder and an
`AGENTS.md` at the same level. Discovery walks up from cwd looking for the
state folder, mirroring how git finds `.git/`.

Layout:

    <root>/
    ├── AGENTS.md             project context
    ├── CLAUDE.md → AGENTS.md
    ├── GEMINI.md → AGENTS.md
    ├── INDEX.md, LOG.md      (Wiki — user content, llm-wiki layout)
    ├── wiki/, sources/       (user content, llm-wiki layout)
    └── .veles/
        ├── project.toml      {name, created_at, schema_version, layout}
        ├── memory.db         (SessionStore — populated lazily on first run)
        ├── memory/           agent's own artefacts (M160): LOG.md journal,
        │                     insights/, sessions/, proposals/
        ├── jobs/             scheduled-job outputs
        └── skills/, modules/, tmp/

System-level config (defaults shared across projects) lives separately at
`~/.veles/config.toml` and is NOT touched by this module.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from veles.core.safety import scan_for_injection

_STATE_DIR = ".veles"
_PROJECT_TOML = "project.toml"
_AGENTS_MD = "AGENTS.md"
_SYMLINK_TARGETS = ("CLAUDE.md", "GEMINI.md")
# v2: wiki content moved out of `.veles/` into `<root>/wiki/`.
# `.veles/` keeps daemon-internal state only: project.toml, memory.db,
# registries, tmp. (The v1→v2 migrator itself was removed in M149.)
_SCHEMA_VERSION = 2
# M34: keep the constant for any external callers that imported it,
# but produce content via agents_md_schema.default_template() so the
# fresh-init AGENTS.md passes `validate()` out of the box.


class ProjectAlreadyExists(RuntimeError):
    pass


class ProjectNotFound(RuntimeError):
    pass


@dataclass(slots=True)
class Project:
    root: Path
    name: str
    created_at: float
    schema_version: int = _SCHEMA_VERSION
    # M117: which layout-pack organises the user-content side of the
    # project. Default `"llm-wiki"` (the builtin Karpathy pack); users
    # can switch via the wizard (M117 follow-up) or by editing the
    # `layout` key in project.toml directly. Resolved at load time —
    # callers like the daemon factory and `veles init` read it via
    # `discover_layouts(project)`.
    layout_name: str = "llm-wiki"

    @property
    def state_dir(self) -> Path:
        return self.root / _STATE_DIR

    @property
    def memory_db_path(self) -> Path:
        return self.state_dir / "memory.db"

    @property
    def wiki_root(self) -> Path:
        """Container for the knowledge-base tree. `Wiki` writes pages
        under `<wiki_root>/wiki/<category>/` and raw originals under
        `<wiki_root>/sources/`. v2: moved from `.veles/` to the project
        root, so users see `wiki/` next to AGENTS.md/INDEX.md/LOG.md
        instead of buried under daemon state. Customising the inner
        dir name (e.g. `WIKI/` uppercase for Obsidian vaults) is a
        follow-up — for now the layout is the Karpathy default."""
        return self.root

    @property
    def memory_dir(self) -> Path:
        """The agent's own memory artefacts (system-ops journal, insight
        views, session compactions, proposals) — system-owned and
        layout-independent (VISION §5.1). Owned by
        `core/memory/artefacts.py`; never part of user content."""
        return self.state_dir / "memory"

    @property
    def jobs_dir(self) -> Path:
        """Scheduled-job outputs (`veles job` + daemon JobRunner)."""
        return self.state_dir / "jobs"

    @property
    def skills_dir(self) -> Path:
        return self.state_dir / "skills"

    @property
    def modules_dir(self) -> Path:
        return self.state_dir / "modules"

    @property
    def agents_md_path(self) -> Path:
        return self.root / _AGENTS_MD

    @property
    def project_toml_path(self) -> Path:
        return self.state_dir / _PROJECT_TOML

    @property
    def trust_path(self) -> Path:
        return self.state_dir / "trust.json"

    @property
    def tmp_dir(self) -> Path:
        """Runtime artifacts the agent stores during a session — clipboard
        pastes, web-fetch caches, Telegram-channel attachments. Sits
        under `.veles/` so it gets the same backup/sync treatment as the
        rest of project state, but `iter_project_files` excludes it
        from `veles export` by default. Created lazily by the caller."""
        return self.state_dir / "tmp"


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from `start` (default: cwd) looking for `<level>/.veles/project.toml`."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / _STATE_DIR / _PROJECT_TOML).is_file():
            return candidate
    return None


def load_project(root: Path) -> Project:
    """Read `<root>/.veles/project.toml` and return a Project. Runs
    pending schema migrations (v1→v2 wiki layout move) before returning,
    so callers always see a project at the current schema version."""
    toml_path = root / _STATE_DIR / _PROJECT_TOML
    if not toml_path.is_file():
        raise ProjectNotFound(f"no project.toml at {toml_path}")
    with toml_path.open("rb") as f:
        data = tomllib.load(f)
    proj = data.get("project") or {}
    layout_name = proj.get("layout")
    if not isinstance(layout_name, str) or not layout_name.strip():
        layout_name = "llm-wiki"
    project = Project(
        root=root,
        name=str(proj.get("name") or root.name),
        created_at=float(proj.get("created_at_epoch") or 0.0),
        schema_version=int(proj.get("schema_version") or 1),
        layout_name=layout_name.strip(),
    )
    # Lazy import — `core.migrations` may itself touch project state and
    # would create a cycle otherwise.
    from veles.core.migrations import run_pending_migrations

    return run_pending_migrations(project)


def init_project(
    root: Path,
    *,
    name: str | None = None,
    force: bool = False,
    layout: str = "llm-wiki",
) -> Project:
    """Create the project skeleton. Returns the new Project.

    The "already initialised" guard keys on the `project.toml` marker —
    not the mere existence of `.veles/`. A `.veles/` left behind without a
    `project.toml` (e.g. a daemon's dream/curator cycle recreating the
    state dir of a deleted project via `mkdir(parents=True, exist_ok=True)`,
    writing only `curator.state.json` / `dream.lock`) is treated as an
    *incomplete* project and healed in place: the missing skeleton is
    written and any leftover state files are kept. `force` always wipes
    and recreates from scratch. This is what lets the wizard and
    `veles init` recover such a half-existing dir instead of dead-ending
    on `ProjectAlreadyExists` → `load_project` → `ProjectNotFound`.

    M162: the user-content skeleton is owned by the chosen layout pack
    (`apply_scaffold`) — core no longer assumes the wiki shape. An
    unknown `layout` degrades to a bare scaffold (default AGENTS.md, no
    content dirs) with a stderr warning.
    """
    root = root.resolve()
    state_dir = root / _STATE_DIR
    project_toml = state_dir / _PROJECT_TOML
    if project_toml.is_file():
        # A real (complete) project already lives here.
        if not force:
            raise ProjectAlreadyExists(
                f"project already initialized at {state_dir} (use force=True to reset)"
            )
        _remove_dir_recursive(state_dir)
    elif force and state_dir.exists():
        # Partial / corrupt state dir (no project.toml) — force resets it
        # cleanly. Without force we fall through and complete it in place.
        _remove_dir_recursive(state_dir)

    resolved_name = _normalize_project_name(name or root.name)
    now = time.time()

    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "skills").mkdir(parents=True, exist_ok=True)
    _write_project_toml(
        state_dir / _PROJECT_TOML,
        name=resolved_name,
        created_at=now,
        layout_name=layout,
    )

    # Lazy import — `core.layout.discovery` imports Project from this
    # module; importing it at the top would be a cycle.
    from veles.core.layout.discovery import find_layout
    from veles.core.layout.scaffold import apply_scaffold

    pack = find_layout(layout, project=None)
    if pack is None:
        print(
            f"warning: layout pack {layout!r} not found; initialising without a content scaffold",
            file=sys.stderr,
        )
    apply_scaffold(pack, root, resolved_name)

    _ensure_symlinks(root)

    project = Project(
        root=root,
        name=resolved_name,
        created_at=now,
        schema_version=_SCHEMA_VERSION,
        layout_name=layout,
    )
    # M118b: warm the project_tree cache on init so the first
    # `veles run` doesn't pay a cold-scan cost. The scanner is
    # idempotent on unchanged trees, so subsequent runs only update
    # changed entries.
    try:
        from veles.core.project_tree_runner import scan_project_tree

        scan_project_tree(project)
    except Exception:
        # Init must always succeed; the cache is an optimisation,
        # not a contract.
        pass

    return project


_DEFAULT_FILE_PICKER_EXCLUDES: frozenset[str] = frozenset(
    {".git", ".venv", "venv", "__pycache__", "node_modules", "tmp", "dist", "build"}
)


def iter_project_files(
    root: Path,
    *,
    excludes: frozenset[str] = _DEFAULT_FILE_PICKER_EXCLUDES,
    include_veles_tmp: bool = True,
    cap: int = 5000,
) -> list[Path]:
    """M78: enumerate files under `root` for the TUI `@` file picker.

    Excludes top-level dirs by name (passed as a set). The `.veles/`
    project state dir is always excluded EXCEPT for `.veles/tmp/`,
    which holds runtime artifacts (clipboard pastes, web fetches) the
    user may want to reference back. Returns paths relative to `root`,
    sorted alphabetically. Caps at `cap` to keep the picker responsive.
    """
    root = root.resolve()
    results: list[Path] = []

    def _walk(dir_path: Path) -> None:
        if len(results) >= cap:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: p.name)
        except OSError:
            return
        for entry in entries:
            if len(results) >= cap:
                return
            name = entry.name
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            if is_dir:
                if name in excludes:
                    continue
                # Special-case .veles: drop the dir but keep .veles/tmp if asked.
                if name == ".veles":
                    if include_veles_tmp:
                        tmp_dir = entry / "tmp"
                        if tmp_dir.is_dir():
                            _walk(tmp_dir)
                    continue
                _walk(entry)
            else:
                try:
                    results.append(entry.relative_to(root))
                except ValueError:
                    continue

    _walk(root)
    return results


def load_agents_md(project: Project, *, max_bytes: int = 50_000) -> str | None:
    p = project.agents_md_path
    if not p.is_file():
        return None
    raw = p.read_text(encoding="utf-8", errors="replace")
    cleaned, _ = scan_for_injection(raw, source_label="AGENTS.md")
    return cleaned[:max_bytes]


# --- internals -----------------------------------------------------------


_NAME_NORMALIZE = re.compile(r"[^a-zA-Z0-9._-]+")


def _normalize_project_name(raw: str) -> str:
    cleaned = _NAME_NORMALIZE.sub("-", raw).strip("-_.")
    return cleaned or "project"


def _write_project_toml(
    path: Path,
    *,
    name: str,
    created_at: float,
    schema_version: int = _SCHEMA_VERSION,
    layout_name: str = "llm-wiki",
) -> None:
    iso = _dt.datetime.fromtimestamp(created_at, tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = (
        f"[project]\n"
        f'name = "{_toml_escape(name)}"\n'
        f'created_at = "{iso}"\n'
        f"created_at_epoch = {created_at}\n"
        f"schema_version = {schema_version}\n"
        f'layout = "{_toml_escape(layout_name)}"\n'
    )
    path.write_text(body, encoding="utf-8")


def _toml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _ensure_symlinks(root: Path) -> None:
    target = root / _AGENTS_MD
    for name in _SYMLINK_TARGETS:
        link = root / name
        if link.is_symlink():
            continue
        if link.exists():
            print(
                f"warning: {name} exists at {root} and is not a symlink; leaving it alone",
                file=sys.stderr,
                flush=True,
            )
            continue
        try:
            os.symlink(target.name, link)  # relative symlink: AGENTS.md
        except OSError as exc:
            print(
                f"warning: failed to create symlink {name} -> AGENTS.md: {exc}",
                file=sys.stderr,
                flush=True,
            )


def _remove_dir_recursive(path: Path) -> None:
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    path.rmdir()
