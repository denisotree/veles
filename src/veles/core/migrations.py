"""Schema migrations for Veles projects.

A project's `schema_version` (in `<root>/.veles/project.toml`) ratchets
forward as the on-disk layout evolves. `load_project()` calls
`run_pending_migrations()` immediately after parsing the TOML, so any
caller that holds a `Project` object sees the current layout — no flag
to remember, no manual `veles project migrate` step.

Each migrator is **idempotent**: running it twice on the same project
must produce the same result. That gives us safety on partial failures
and lets tests assert it explicitly.

Migration steps live as `_migrate_vN_to_vN1(project)` helpers and are
dispatched by `_STEPS`. Adding a new schema bump: increment
`_SCHEMA_VERSION` in `project.py`, append the handler here.

M149: the v1 → v2 migrator (wiki out of `.veles/`) was removed — no
pre-v2 installations exist. A project stuck below the oldest supported
schema gets a clear log message suggesting `veles init --force`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from veles.core.project import _SCHEMA_VERSION, Project

logger = logging.getLogger(__name__)


_Step = Callable[[Project], None]


def run_pending_migrations(project: Project) -> Project:
    """Run all migrations needed to bring `project` to `_SCHEMA_VERSION`.

    Returns the project unchanged in shape; only on-disk layout and the
    `schema_version` field in `project.toml` move forward. The in-memory
    `Project.schema_version` is updated to match."""
    if project.schema_version >= _SCHEMA_VERSION:
        return project
    current = project.schema_version
    while current < _SCHEMA_VERSION:
        step = _STEPS.get(current)
        if step is None:
            logger.warning(
                "project %r is on schema v%d which has no supported migrator "
                "to v%d; re-create the project with `veles init --force`",
                project.name,
                current,
                current + 1,
            )
            break
        logger.info(
            "migrating project %r from schema v%d to v%d",
            project.name,
            current,
            current + 1,
        )
        step(project)
        current += 1
        _update_schema_version(project, current)
    project.schema_version = current
    return project


# No active migration steps. Append `_migrate_vN_to_vN1` handlers here on
# the next schema bump (see module docstring).
_STEPS: dict[int, _Step] = {}


def _update_schema_version(project: Project, version: int) -> None:
    """Rewrite `project.toml` with the new schema_version. Other fields
    (name, created_at) are preserved by re-emitting through
    `_write_project_toml`, which has a stable shape."""
    from veles.core.project import _write_project_toml

    _write_project_toml(
        project.project_toml_path,
        name=project.name,
        created_at=project.created_at,
        schema_version=version,
    )


__all__ = ["run_pending_migrations"]
