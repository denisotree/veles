"""M63 — autopilot dispatch writes `op=autopilot-<tool>` to the system-ops journal."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from veles.core.agent import _dispatch
from veles.core.autopilot import activate
from veles.core.context import reset_active_project, set_active_project
from veles.core.project import Project, init_project
from veles.core.provider import ToolCall
from veles.core.tools.registry import Registry, ToolEntry


# User-home isolation comes from the autouse `_hermetic_user_home`
# fixture in tests/conftest.py; only the trust bypass needs clearing here.
@pytest.fixture(autouse=True)
def _no_trust_auto_allow(monkeypatch):
    monkeypatch.delenv("VELES_TRUST_AUTO_ALLOW", raising=False)


@pytest.fixture()
def project(tmp_path: Path):
    proj = init_project(tmp_path / "demo", name="demo")
    token = set_active_project(proj)
    yield proj
    reset_active_project(token)


def _make_entry(name: str, *, sensitive: bool, handler) -> ToolEntry:
    return ToolEntry(
        name=name,
        description=name,
        parameter_schema={"type": "object", "properties": {}},
        handler=handler,
        is_async=False,
        sensitive=sensitive,
    )


@pytest.fixture()
def sensitive_registry() -> Registry:
    """Fresh isolated registry — bypass the @tool global side effects."""
    reg = Registry()
    reg.register(_make_entry("fake_shell", sensitive=True, handler=lambda cmd: f"ran: {cmd}"))
    reg.register(
        _make_entry("safe_read", sensitive=False, handler=lambda path: f"contents of {path}")
    )
    return reg


def _noop_log(*_a, **_kw) -> None:
    return None


def test_autopilot_dispatch_logs_to_log_md(project: Project, sensitive_registry: Registry) -> None:
    activate(time.time() + 3600)
    call = ToolCall(id="t1", name="fake_shell", arguments={"cmd": "ls"})
    msg = _dispatch(sensitive_registry, call, log=_noop_log)
    assert "ran: ls" in (msg.content or "")
    log = (project.memory_dir / "LOG.md").read_text(encoding="utf-8")
    assert "autopilot-fake_shell" in log


def test_non_autopilot_grant_does_not_log_autopilot_op(
    project: Project, sensitive_registry: Registry
) -> None:
    """A user-scope grant must NOT mark the dispatch as autopilot."""
    from veles.core.trust_store import TrustStore, user_trust_path

    TrustStore.load(user_trust_path()).grant("fake_shell")
    call = ToolCall(id="t1", name="fake_shell", arguments={"cmd": "ls"})
    _dispatch(sensitive_registry, call, log=_noop_log)
    log_path = project.memory_dir / "LOG.md"
    log = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    assert "autopilot-fake_shell" not in log


def test_non_sensitive_tool_under_autopilot_does_not_log(
    project: Project, sensitive_registry: Registry
) -> None:
    """Autopilot is per-sensitive-dispatch; safe tools never went through the trust path."""
    activate(time.time() + 3600)
    call = ToolCall(id="t1", name="safe_read", arguments={"path": "/tmp/x"})
    _dispatch(sensitive_registry, call, log=_noop_log)
    log_path = project.memory_dir / "LOG.md"
    log = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    assert "autopilot-safe_read" not in log


def test_autopilot_dispatch_records_failure_in_log(
    project: Project,
) -> None:
    """If the tool itself raises, autopilot still records the dispatch (with failure note)."""

    def _boom() -> str:
        raise RuntimeError("explosion")

    reg = Registry()
    reg.register(_make_entry("boom", sensitive=True, handler=_boom))

    activate(time.time() + 3600)
    call = ToolCall(id="t1", name="boom", arguments={})
    msg = _dispatch(reg, call, log=_noop_log)
    assert "explosion" in (msg.content or "")
    log = (project.memory_dir / "LOG.md").read_text(encoding="utf-8")
    assert "autopilot-boom" in log
    assert "failed" in log
