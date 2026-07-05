"""M134: runtime-session data model + config + resolver foundation.

`RuntimeSessionStore` is the project's registry of long-lived agent
runtimes (daemon | tui) above the conversation layer; `[daemon.<name>]`
config declares a named daemon's settings (restart source-of-truth);
`model_resolver` gains a per-daemon cascade layer so each daemon session
can pin its own provider/model without reintroducing the M125/M127/M130
provider-mismatch class.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from veles.core.model_resolver import (
    resolve_effective_model,
    resolve_effective_provider,
)
from veles.core.project import init_project
from veles.core.project_config import (
    get_daemon_session_config,
    list_daemon_session_names,
    save_project_config,
)
from veles.core.runtime_sessions import (
    RuntimeSessionExists,
    RuntimeSessionStore,
)

# ---- RuntimeSessionStore ----


def _store() -> RuntimeSessionStore:
    return RuntimeSessionStore(":memory:")


def test_create_and_get_roundtrip():
    s = _store()
    rec = s.create("api", "daemon", model="qwen3:4b-instruct", provider="ollama", port=8765)
    assert rec.kind == "daemon"
    assert rec.status == "created"
    assert rec.deleted is False
    got = s.get(rec.id)
    assert got is not None and got.model == "qwen3:4b-instruct" and got.port == 8765


def test_duplicate_live_name_rejected_but_kinds_independent():
    s = _store()
    s.create("main", "daemon")
    with pytest.raises(RuntimeSessionExists):
        s.create("main", "daemon")
    # Same name, different kind is allowed (a daemon and a tui can share a name).
    s.create("main", "tui")
    assert {r.kind for r in s.list()} == {"daemon", "tui"}


def test_soft_delete_hides_but_keeps_row():
    s = _store()
    rec = s.create("api", "daemon")
    assert s.soft_delete(rec.id) is True
    assert s.list() == []  # hidden from active listing
    deleted = s.list(include_deleted=True)
    assert len(deleted) == 1 and deleted[0].deleted is True
    # Name freed for reuse after soft-delete.
    again = s.create("api", "daemon")
    assert again.id != rec.id
    # Second soft-delete of an already-deleted id is a no-op.
    assert s.soft_delete(rec.id) is False


def test_lifecycle_started_stopped():
    s = _store()
    rec = s.create("api", "daemon")
    s.mark_started(rec.id, pid=4242, now=100.0)
    r = s.get(rec.id)
    assert r.status == "running" and r.pid == 4242 and r.last_started_at == 100.0
    s.mark_stopped(rec.id, now=200.0)
    r = s.get(rec.id)
    assert r.status == "stopped" and r.pid is None and r.last_stopped_at == 200.0


def test_update_settings_only_writes_non_none():
    s = _store()
    rec = s.create("api", "daemon", model="m1", provider="ollama")
    s.update_settings(rec.id, model="m2")  # provider untouched
    r = s.get(rec.id)
    assert r.model == "m2" and r.provider == "ollama"


# ---- [daemon.<name>] config helpers ----


def test_list_and_get_daemon_session_config_distinguish_scalars(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    save_project_config(
        project,
        {
            "daemon": {
                "enabled": True,  # legacy single-daemon scalar — NOT a session
                "host": "127.0.0.1",
                "api": {"model": "qwen3:4b-instruct", "provider": "ollama", "port": 8765},
                "research": {"model": "claude-sonnet-4.6", "provider": "openrouter"},
            }
        },
    )
    from veles.core.project_config import load_project_config

    cfg = load_project_config(project)
    assert list_daemon_session_names(cfg) == ["api", "research"]
    assert get_daemon_session_config(cfg, "api")["model"] == "qwen3:4b-instruct"
    assert get_daemon_session_config(cfg, "missing") == {}


# ---- model_resolver per-daemon layer ----


def _ns(**kw) -> argparse.Namespace:
    return argparse.Namespace(**kw)


def test_daemon_session_provider_model_beats_project_provider(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    save_project_config(
        project,
        {
            "engine": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4.6"},
            "daemon": {"local": {"provider": "ollama", "model": "qwen3:4b-instruct"}},
        },
    )
    args = _ns(provider=None, model=None)
    # Without daemon_session → project [engine] base.
    assert resolve_effective_provider(args, project) == "openrouter"
    assert resolve_effective_model(args, project) == "anthropic/claude-sonnet-4.6"
    # With daemon_session=local → the [daemon.local] pins win.
    assert resolve_effective_provider(args, project, daemon_session="local") == "ollama"
    assert resolve_effective_model(args, project, daemon_session="local") == "qwen3:4b-instruct"


def test_explicit_flag_still_beats_daemon_session(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    save_project_config(project, {"daemon": {"local": {"provider": "ollama", "model": "qwen3"}}})
    args = _ns(provider="anthropic", model="claude-opus-4-8")
    assert resolve_effective_provider(args, project, daemon_session="local") == "anthropic"
    assert resolve_effective_model(args, project, daemon_session="local") == "claude-opus-4-8"


def test_daemon_session_without_pins_falls_through(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    save_project_config(
        project,
        {
            "engine": {"provider": "openrouter", "model": "x/y"},
            "daemon": {"bare": {"port": 8770}},  # no provider/model pins
        },
    )
    args = _ns(provider=None, model=None)
    assert resolve_effective_provider(args, project, daemon_session="bare") == "openrouter"
    assert resolve_effective_model(args, project, daemon_session="bare") == "x/y"
