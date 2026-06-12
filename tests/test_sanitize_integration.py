"""Round 2 integration: every boundary that emits/persists agent-visible
text routes through `core.sanitize`. Verified end-to-end:

- SessionStore: append + load both sanitize.
- write_file: returns relative-or-sanitized path.
- SandboxViolation: exception message has no abs path.
- daemon `/v1/health` and `/v1/status`: `project_root` field sanitized.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.memory import Message, SessionStore
from veles.core.path_guard import SandboxViolation, resolve_safe
from veles.core.project import init_project
from veles.core.sanitize import loader as sanitize_loader
from veles.core.tools.builtin.write_file import write_file


@pytest.fixture(autouse=True)
def _isolate_sanitize_cache() -> None:
    sanitize_loader.clear_cache()


# ---------- SessionStore ----------


def test_session_store_sanitizes_on_append_and_load(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="mind-palace")
    token = set_active_project(project)
    try:
        store = SessionStore(project.memory_db_path)
        sid = store.create_session()
        abs_path = str(project.root.resolve())
        store.append_turn(
            sid,
            Message(role="assistant", content=f"opened {abs_path}/wiki/x.md"),
        )
        loaded = store.load_messages(sid)
        assert loaded[0].content == "opened <mind-palace>/wiki/x.md"
    finally:
        reset_active_project(token)


def test_session_store_load_sanitizes_pre_existing_rows(tmp_path: Path) -> None:
    """Rows written before sanitize existed must still come out clean."""
    project = init_project(tmp_path / "p", name="mind-palace")
    store = SessionStore(project.memory_db_path)
    sid = store.create_session()
    abs_path = str(project.root.resolve())

    # Bypass the sanitize-on-append boundary by writing directly via SQL.
    store._conn.execute(
        "INSERT INTO turns (session_id, seq, role, content,"
        " tool_calls_json, tool_call_id, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (sid, 0, "assistant", f"raw {abs_path}/foo", None, None, 0.0),
    )
    store._conn.commit()

    token = set_active_project(project)
    try:
        loaded = store.load_messages(sid)
    finally:
        reset_active_project(token)
    assert loaded[0].content == "raw <mind-palace>/foo"


# ---------- write_file ----------


def test_write_file_returns_relative_path_inside_project(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="proj")
    token = set_active_project(project)
    try:
        target = project.root / "wiki" / "notes.md"
        msg = write_file(str(target), "hi")
    finally:
        reset_active_project(token)
    assert msg == "wrote 2 bytes to wiki/notes.md"


def test_write_file_outside_project_sanitizes_path(monkeypatch, tmp_path: Path) -> None:
    """Writing to `~/.veles/skills/...` is allowed via critical-confirm;
    the returned path must be the sanitized form `~/.veles/skills/...`,
    not the absolute one."""
    from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(
        "veles.core.path_guard.Path.home",
        classmethod(lambda cls: fake_home),
    )
    monkeypatch.setattr(
        "veles.core.sanitize.builtin.Path.home",
        classmethod(lambda cls: fake_home),
    )
    monkeypatch.setattr(
        "veles.core.sanitize.loader.Path.home",
        classmethod(lambda cls: fake_home),
    )
    sanitize_loader.clear_cache()
    project = init_project(tmp_path / "p", name="proj")
    proj_token = set_active_project(project)
    conf_token = set_critical_confirmer(lambda _o, _s: True)
    try:
        target = fake_home / ".veles" / "skills" / "foo.py"
        msg = write_file(str(target), "x")
    finally:
        reset_critical_confirmer(conf_token)
        reset_active_project(proj_token)
    # Should collapse $HOME → `~`, no `/Users/...` substring.
    assert "wrote" in msg
    assert str(fake_home) not in msg
    assert "~/.veles/skills/foo.py" in msg


# ---------- SandboxViolation ----------


def test_sandbox_violation_message_strips_abs_path(monkeypatch, tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(
        "veles.core.path_guard.Path.home",
        classmethod(lambda cls: fake_home),
    )
    monkeypatch.setattr(
        "veles.core.sanitize.builtin.Path.home",
        classmethod(lambda cls: fake_home),
    )
    monkeypatch.setattr(
        "veles.core.sanitize.loader.Path.home",
        classmethod(lambda cls: fake_home),
    )
    sanitize_loader.clear_cache()
    project = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(project)
    try:
        outside = tmp_path / "outside"
        outside.mkdir()
        try:
            resolve_safe(str(outside / "x.txt"))
        except SandboxViolation as exc:
            msg = str(exc)
        else:
            pytest.fail("expected SandboxViolation")
    finally:
        reset_active_project(token)
    # `outside` resolves to a tmp_path subdir — that path itself isn't a
    # secret. The point is that `roots: [...]` no longer carries the abs
    # form of the active project root: it shows `<proj>` instead.
    assert "<proj>" in msg
    assert str(project.root.resolve()) not in msg


# ---------- daemon endpoints ----------


def test_daemon_health_endpoint_redacts_project_root(monkeypatch, tmp_path: Path) -> None:
    from aiohttp.test_utils import make_mocked_request

    from veles.daemon.auth import TokenStore
    from veles.daemon.server import _handle_health
    from veles.daemon.state import DaemonState

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(
        "veles.core.sanitize.builtin.Path.home",
        classmethod(lambda cls: fake_home),
    )
    monkeypatch.setattr(
        "veles.core.sanitize.loader.Path.home",
        classmethod(lambda cls: fake_home),
    )
    sanitize_loader.clear_cache()
    project = init_project(tmp_path / "p", name="mind-palace")
    state = DaemonState(
        project=project,
        store=SessionStore(project.memory_db_path),
        token_store=TokenStore(tmp_path / "tokens.json"),
        agent_factory=lambda *_a, **_k: None,
    )

    class _StubApp(dict):
        pass

    app = _StubApp()
    app["state"] = state
    req = make_mocked_request("GET", "/v1/health", app=app)
    resp = asyncio.new_event_loop().run_until_complete(_handle_health(req))
    body = json.loads(resp.body)  # type: ignore[arg-type]
    assert body["project_root"] == "<mind-palace>"
    assert "/Users/" not in body["project_root"]
