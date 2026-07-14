"""Daemon startup must set `current_project()` ContextVar so wiki/tool
helpers see the right project. Verified by checking the var inside the
agent factory (the same place Agent.__init__ reads it) and after a
to_thread hop (where workers actually run Agent.run).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from veles.core.context import current_project, reset_active_project, set_active_project
from veles.core.project import init_project


def test_set_active_project_visible_in_factory_closure(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="ctxtest")
    token = set_active_project(project)
    try:
        seen: list[object] = []

        def factory(session_id, *, prompt=None):
            seen.append(current_project())
            return None  # we don't actually build an Agent here

        factory(None)
        assert seen == [project]
    finally:
        reset_active_project(token)


def test_set_active_project_propagates_to_to_thread(tmp_path: Path) -> None:
    """`asyncio.to_thread` should carry the ContextVar via `copy_context`."""
    project = init_project(tmp_path, name="ctxthread")
    token = set_active_project(project)
    try:

        async def run() -> object:
            return await asyncio.to_thread(current_project)

        seen = asyncio.run(run())
        assert seen is project
    finally:
        reset_active_project(token)


def test_bootstrap_daemon_chdirs_to_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tools resolving relative paths (`pwd`, `cat foo`, skills) must
    land inside the project regardless of where the daemon process was
    spawned. `_bootstrap_daemon` is the single point that guarantees it.
    """
    from veles.cli.commands.daemon import _bootstrap_daemon

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles-home"))
    project_root = tmp_path / "proj"
    project = init_project(project_root, name="chdirtest")

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert Path(os.getcwd()) == elsewhere

    from veles.core.modules import set_module_registry

    # This test exercises the real _bootstrap_daemon only for its chdir
    # side effect; suppress the stdio funnel so it doesn't permanently swap
    # sys.stdout/stderr and leak into later tests.
    monkeypatch.setattr("veles.daemon.logging.install_stdio_funnel", lambda: False)

    original_cwd = Path.cwd()
    try:
        _bootstrap_daemon(project)
        assert Path(os.getcwd()).resolve() == project.root.resolve()
    finally:
        # `_bootstrap_daemon` sets process-wide ContextVars (active
        # project, module registry) and chdir's into the project. All
        # three leak into later tests (e.g. `image_describe` walks up
        # from CWD and reads `current_project()`). Clear explicitly.
        os.chdir(str(original_cwd))
        set_active_project(None)  # type: ignore[arg-type]
        set_module_registry(None)  # type: ignore[arg-type]
