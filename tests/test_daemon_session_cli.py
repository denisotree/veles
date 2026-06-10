"""M135: `veles daemon session {create,list,delete}` — named daemon sessions.

Additive to the legacy single daemon: declares per-project named daemon
sessions in `runtime_sessions` (RuntimeSessionStore) + `[daemon.<name>]`
config, with soft-delete. Does not touch the global-pid daemon lifecycle.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from veles.cli.commands.daemon_session import cmd_daemon_session
from veles.core.project import init_project
from veles.core.project_config import (
    get_daemon_session_config,
    load_project_config,
)
from veles.core.runtime_sessions import RuntimeSessionStore


def _args(**kw) -> argparse.Namespace:
    base = {"host": "127.0.0.1", "port": None, "model": None, "provider": None, "mode": None}
    base.update(kw)
    return argparse.Namespace(**base)


def _mk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(project.root)
    return project


def test_create_writes_config_and_store(tmp_path, monkeypatch):
    project = _mk(tmp_path, monkeypatch)
    rc = cmd_daemon_session(
        _args(
            daemon_session_command="create",
            name="api",
            port=8770,
            model="qwen3:4b-instruct",
            provider="ollama",
        )
    )
    assert rc == 0
    cfg = load_project_config(project)
    block = get_daemon_session_config(cfg, "api")
    assert block["model"] == "qwen3:4b-instruct"
    assert block["provider"] == "ollama"
    assert block["port"] == 8770
    store = RuntimeSessionStore(project.memory_db_path)
    rec = store.get_by_name("api", kind="daemon")
    assert rec is not None and rec.status == "created"


def test_create_rejects_duplicate(tmp_path, monkeypatch):
    _mk(tmp_path, monkeypatch)
    assert cmd_daemon_session(_args(daemon_session_command="create", name="api")) == 0
    assert cmd_daemon_session(_args(daemon_session_command="create", name="api")) == 2


def test_create_rejects_port_clash(tmp_path, monkeypatch):
    _mk(tmp_path, monkeypatch)
    assert cmd_daemon_session(_args(daemon_session_command="create", name="a", port=8800)) == 0
    rc = cmd_daemon_session(_args(daemon_session_command="create", name="b", port=8800))
    assert rc == 2


def test_delete_soft_deletes_and_drops_config(tmp_path, monkeypatch):
    project = _mk(tmp_path, monkeypatch)
    cmd_daemon_session(_args(daemon_session_command="create", name="api", model="m"))
    rc = cmd_daemon_session(_args(daemon_session_command="delete", name="api"))
    assert rc == 0
    # Config block removed.
    cfg = load_project_config(project)
    assert get_daemon_session_config(cfg, "api") == {}
    # Row kept in DB (soft delete) — visible only with include_deleted.
    store = RuntimeSessionStore(project.memory_db_path)
    assert store.get_by_name("api", kind="daemon") is None
    assert any(r.name == "api" and r.deleted for r in store.list(kind="daemon", include_deleted=True))
    # Name freed: re-create works.
    assert cmd_daemon_session(_args(daemon_session_command="create", name="api")) == 0


def test_delete_unknown_returns_error(tmp_path, monkeypatch):
    _mk(tmp_path, monkeypatch)
    assert cmd_daemon_session(_args(daemon_session_command="delete", name="ghost")) == 1


def test_list_runs(tmp_path, monkeypatch):
    _mk(tmp_path, monkeypatch)
    cmd_daemon_session(_args(daemon_session_command="create", name="api", model="m"))
    assert cmd_daemon_session(_args(daemon_session_command="list", all=False)) == 0
