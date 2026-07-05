"""M200 — autopilot is not silent: autonomous network egress reaches the review
journal.

VISION §8: every autonomous action is written to the project-memory journal for
later review. `run_shell` (approval_required) already lands in LOG.md when
autopilot bypasses the trust ladder — but `fetch_url`/`web_search` are builtin-
`allow` (M124, to avoid attended-mode prompt fatigue), so they skip the trust
ladder and were never journaled. Under an active autopilot window they must be.

Also pins the two "already covered" claims that let M200 shrink to this line:
sensitive tools under autopilot are journaled, and deletes outside the project
are refused by the sandbox (no gate to add).
"""

from __future__ import annotations

import time
from pathlib import Path

from veles.core.autopilot import activate
from veles.core.context import reset_active_project, set_active_project
from veles.core.project import init_project
from veles.core.provider import ToolCall
from veles.core.risk import RiskClass
from veles.core.tool_dispatch import _dispatch
from veles.core.tools.registry import Registry, ToolEntry


def _registry_with(name: str, risk_class: RiskClass, *, sensitive: bool = False) -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name=name,
            description="d",
            parameter_schema={"type": "object"},
            handler=lambda **_kw: "ok",
            is_async=False,
            sensitive=sensitive,
            risk_class=risk_class,
        )
    )
    return reg


def _log_text(project) -> str:
    logs = list(project.root.rglob("LOG.md"))
    return "\n".join(p.read_text() for p in logs) if logs else ""


def test_egress_tool_under_autopilot_is_journaled(tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="t")
    token = set_active_project(project)
    activate(time.time() + 3600)
    try:
        reg = _registry_with("fetch_url", RiskClass.NETWORK_OPEN_WORLD)  # builtin-allow policy
        call = ToolCall(id="c1", name="fetch_url", arguments={"url": "http://example.com"})
        _dispatch(reg, call, log=lambda *_a, **_k: None)
        assert "fetch_url" in _log_text(project)
    finally:
        reset_active_project(token)


def test_egress_tool_without_autopilot_is_not_journaled(tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="t")
    token = set_active_project(project)
    # no autopilot window
    try:
        reg = _registry_with("fetch_url", RiskClass.NETWORK_OPEN_WORLD)
        call = ToolCall(id="c1", name="fetch_url", arguments={"url": "http://example.com"})
        _dispatch(reg, call, log=lambda *_a, **_k: None)
        assert "fetch_url" not in _log_text(project)  # attended: allow, no autopilot audit
    finally:
        reset_active_project(token)


def test_sensitive_tool_under_autopilot_is_journaled(tmp_path: Path) -> None:
    """Pin: the pre-existing autopilot audit (approval_required + sensitive tool
    dispatched via the autopilot window) still lands in LOG.md."""
    project = init_project(tmp_path / "proj", name="t")
    token = set_active_project(project)
    activate(time.time() + 3600)
    try:
        reg = _registry_with("run_shell", RiskClass.PROCESS_EXECUTION, sensitive=True)
        call = ToolCall(id="c1", name="run_shell", arguments={"command": "echo hi"})
        _dispatch(reg, call, log=lambda *_a, **_k: None)
        assert "run_shell" in _log_text(project)
    finally:
        reset_active_project(token)


def test_delete_outside_project_is_refused_by_sandbox(tmp_path: Path) -> None:
    """Pin: no gate needed for 'delete outside project' — path_guard already
    refuses any path outside the sandbox, so autopilot can never reach a
    cross-boundary delete/move (file_ops resolves through `resolve_safe`)."""
    import pytest

    from veles.core.path_guard import SandboxViolation, resolve_safe

    project = init_project(tmp_path / "proj", name="t")
    token = set_active_project(project)
    try:
        with pytest.raises(SandboxViolation):
            resolve_safe("/etc/hosts")
    finally:
        reset_active_project(token)
