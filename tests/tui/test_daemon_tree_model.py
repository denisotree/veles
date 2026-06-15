"""M159: `build_daemon_tree` — the project → daemons → channels model behind
the rewritten picker.

Pure data layer (no Textual): groups the cross-project registry + the project's
`runtime_sessions` into current-project vs other-project daemons, each carrying
its channels. These assertions pin the issue-3 fix (the unnamed daemon must land
under the current project, even across a symlinked path) and the channel-as-leaf
data shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import init_project
from veles.core.project_config import load_project_config, save_project_config
from veles.core.runtime_sessions import RuntimeSessionStore
from veles.daemon.registry import DaemonEntry, DaemonRegistry
from veles.tui.screens._daemon_picker_data import build_daemon_tree


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles"))


def _seed_registry(*entries: DaemonEntry) -> None:
    reg = DaemonRegistry()
    for e in entries:
        reg.upsert(e)
    reg.save()


def _entry(slug: str, project_path: str, *, pid: int = 0, port: int = 8765) -> DaemonEntry:
    return DaemonEntry(
        slug=slug,
        project_path=project_path,
        project_name=slug,
        pid=pid,
        host="127.0.0.1",
        port=port,
        started_at=1.0,
    )


def test_unnamed_daemon_lands_under_current_project_across_symlink(tmp_path):
    """Issue 3 core: the registry entry whose path resolves to project.root is
    the project's 'default' daemon — even when the registry stored a symlinked
    or trailing-slash variant of the path."""
    real = tmp_path / "real"
    project = init_project(real, name="mind-palace")
    link = tmp_path / "linked"
    link.symlink_to(real, target_is_directory=True)

    # Registry stored the symlinked path (the mind-palace/obsidian case).
    _seed_registry(_entry("mind-palace", str(link)))

    tree = build_daemon_tree(project)
    assert [n.name for n in tree.current] == ["default"]
    assert tree.current[0].kind == "registry"
    assert tree.others == []


def test_unnamed_daemon_trailing_slash_still_current(tmp_path):
    real = tmp_path / "p"
    project = init_project(real, name="p")
    _seed_registry(_entry("p", str(real) + "/"))
    tree = build_daemon_tree(project)
    assert [n.name for n in tree.current] == ["default"]


def test_other_project_daemons_go_to_others(tmp_path):
    project = init_project(tmp_path / "mine", name="mine")
    _seed_registry(
        _entry("mine", str(tmp_path / "mine")),
        _entry("elsewhere", str(tmp_path / "elsewhere"), port=8770),
    )
    tree = build_daemon_tree(project)
    assert [n.name for n in tree.current] == ["default"]
    assert [n.name for n in tree.others] == ["elsewhere"]


def test_channels_attach_to_daemon_node(tmp_path):
    project = init_project(tmp_path / "p", name="p")
    cfg = load_project_config(project)
    cfg.setdefault("channels", {})["telegram"] = {"enabled": True}
    save_project_config(project, cfg)
    _seed_registry(_entry("p", str(tmp_path / "p")))

    tree = build_daemon_tree(project)
    assert tree.current[0].channels == ["telegram"]


def test_named_and_live_tui_sessions_under_current_project(tmp_path, monkeypatch):
    project = init_project(tmp_path / "p", name="p")
    _seed_registry(_entry("p", str(tmp_path / "p")))
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", provider="ollama", model="qwen3:4b", port=8801)
    tui = store.create("tui", "tui")
    store.mark_started(tui.id, pid=999_001)  # a live REPL
    store.close()
    # The tui row shows only while its pid is alive.
    monkeypatch.setattr(
        "veles.tui.screens._daemon_picker_data.is_alive", lambda pid: pid == 999_001
    )

    tree = build_daemon_tree(project)
    by_name = {n.name: n for n in tree.current}
    # default (registry) + api (named) + tui (tui)
    assert set(by_name) == {"default", "api", "tui"}
    assert by_name["api"].kind == "named"
    assert by_name["tui"].kind == "tui"
    assert by_name["tui"].channels == []
    # Order: default first, then named, then tui last.
    assert [n.name for n in tree.current] == ["default", "api", "tui"]


def test_stopped_or_orphaned_tui_is_hidden(tmp_path, monkeypatch):
    """Regression: a tui REPL that exited (or was SIGKILLed, leaving a stale
    `running`/dead-pid row) must not linger in the picker. The row is reused
    and never deleted, so a visible stopped tui would be permanent, unmanageable
    clutter showing a pid that no longer exists."""
    project = init_project(tmp_path / "p", name="p")
    _seed_registry(_entry("p", str(tmp_path / "p")))
    store = RuntimeSessionStore(project.memory_db_path)
    # Orphaned crash: status left at 'running' with a now-dead pid (mark_stopped
    # never ran). `created` (never started) and a clean-exit 'stopped' are both
    # covered by the same is_alive→False path.
    tui = store.create("tui", "tui")
    store.mark_started(tui.id, pid=45_171)
    store.close()
    monkeypatch.setattr("veles.tui.screens._daemon_picker_data.is_alive", lambda pid: False)

    tree = build_daemon_tree(project)
    assert [n.name for n in tree.current] == ["default"]
    assert all(n.kind != "tui" for n in tree.current)


def test_named_daemon_channels_from_daemon_block(tmp_path):
    project = init_project(tmp_path / "p", name="p")
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["api"] = {
        "port": 8801,
        "channels": {"telegram": {"enabled": True}},
    }
    save_project_config(project, cfg)
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    tree = build_daemon_tree(project)
    api = next(n for n in tree.current if n.name == "api")
    assert api.channels == ["telegram"]


def test_no_project_puts_everything_in_others(tmp_path):
    _seed_registry(
        _entry("a", str(tmp_path / "a")),
        _entry("b", str(tmp_path / "b")),
    )
    tree = build_daemon_tree(None)
    assert tree.current == []
    assert sorted(n.name for n in tree.others) == ["a", "b"]
    assert tree.project_name is None
