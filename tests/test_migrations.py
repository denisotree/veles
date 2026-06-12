"""Schema-migration framework for projects on disk.

M149 removed the v1 → v2 migrator (no pre-v2 installations exist), so
`_STEPS` is empty. The framework remains: these tests cover the
"already current → no-op" path and the "no supported migrator → warn
and leave as-is" path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.migrations import run_pending_migrations
from veles.core.project import (
    _SCHEMA_VERSION,
    Project,
    _write_project_toml,
    load_project,
)


def _make_v1_project(tmp_path: Path) -> Project:
    """Synthesise an unsupported v1-shaped project: project.toml with
    schema_version=1, legacy wiki under `.veles/`."""
    state_dir = tmp_path / ".veles"
    state_dir.mkdir()
    _write_project_toml(
        state_dir / "project.toml",
        name="alpha",
        created_at=1000.0,
        schema_version=1,
    )
    (state_dir / "wiki" / "concepts").mkdir(parents=True)
    (state_dir / "wiki" / "concepts" / "x.md").write_text("# X\nlegacy page\n", encoding="utf-8")
    return Project(
        root=tmp_path,
        name="alpha",
        created_at=1000.0,
        schema_version=1,
    )


def test_current_schema_is_a_noop(tmp_path: Path) -> None:
    state_dir = tmp_path / ".veles"
    state_dir.mkdir()
    _write_project_toml(
        state_dir / "project.toml",
        name="cur",
        created_at=1.0,
        schema_version=_SCHEMA_VERSION,
    )
    project = Project(root=tmp_path, name="cur", created_at=1.0, schema_version=_SCHEMA_VERSION)
    migrated = run_pending_migrations(project)
    assert migrated is project
    assert migrated.schema_version == _SCHEMA_VERSION


def test_unsupported_old_schema_warns_and_leaves_as_is(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A project below the oldest supported schema has no migrator: the
    framework logs a warning suggesting `veles init --force` and leaves
    the on-disk layout untouched."""
    project = _make_v1_project(tmp_path)
    with caplog.at_level("WARNING", logger="veles.core.migrations"):
        migrated = run_pending_migrations(project)
    assert "no supported migrator" in caplog.text
    assert "veles init --force" in caplog.text
    # Nothing moved, version not bumped.
    assert migrated.schema_version == 1
    assert (tmp_path / ".veles" / "wiki" / "concepts" / "x.md").is_file()
    assert not (tmp_path / "wiki").exists()
    body = (tmp_path / ".veles" / "project.toml").read_text(encoding="utf-8")
    assert "schema_version = 1" in body


def test_load_project_does_not_crash_on_old_schema(tmp_path: Path) -> None:
    """`load_project()` still auto-invokes the migrator; with no migrator
    available it degrades gracefully rather than raising."""
    _make_v1_project(tmp_path)
    project = load_project(tmp_path)
    assert project.schema_version == 1
