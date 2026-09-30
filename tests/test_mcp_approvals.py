"""Stage 1b (B) — project MCP servers start only after the user approved their recipe.

Opening a cloned project must not run the `command` its `[mcp.servers.*]` names:
the approval (a hash of the raw recipe) lives in `~/.veles/mcp-approvals.json`,
outside the agent sandbox, and only `veles mcp approve` or a registry install
records one.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from veles.cli.commands import mcp as mcp_cmd
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.project import Project, init_project
from veles.core.tools.registry import Registry
from veles.mcp import approvals, runtime
from veles.mcp.config import load_raw_mcp_servers


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


@pytest.fixture(autouse=True)
def _no_leaked_manager() -> Iterator[None]:
    yield
    runtime.shutdown_mcp()


def _write_config(project: Project, text: str) -> None:
    (project.state_dir / "config.toml").write_text(text, encoding="utf-8")


def _touch_server(project: Project, marker: Path, *, extra: str = "") -> None:
    _write_config(
        project,
        "[mcp.servers.evil]\n"
        f'command = "{sys.executable}"\n'
        f"args = [\"-c\", \"open(r'{marker}', 'w').close()\"{extra}]\n"
        "connect_timeout_s = 10\n",
    )


def _approve_current(project: Project, name: str) -> None:
    approvals.approve(project.root, name, load_raw_mcp_servers(project)[name])


def _ns(**fields):
    return type("A", (), fields)()


# ---- the attack ----


def test_unapproved_server_is_never_spawned(project: Project, tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    _touch_server(project, marker)
    assert runtime.mount_mcp_tools(Registry(), project) == []
    assert not marker.exists()


def test_approved_server_is_spawned(project: Project, tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    _touch_server(project, marker)
    _approve_current(project, "evil")
    runtime.mount_mcp_tools(Registry(), project)  # not an MCP server: connect fails
    assert marker.exists()


def test_changed_args_after_approval_are_not_spawned(project: Project, tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    _touch_server(project, tmp_path / "harmless")
    _approve_current(project, "evil")
    _touch_server(project, marker)
    raw = load_raw_mcp_servers(project)["evil"]
    assert approvals.approval_state(project.root, "evil", raw) == "changed"
    runtime.mount_mcp_tools(Registry(), project)
    assert not marker.exists()


def test_unapproved_warns_once_per_process_with_escaped_name(
    project: Project, tmp_path: Path, caplog
) -> None:
    _touch_server(project, tmp_path / "m")
    with caplog.at_level(logging.WARNING, logger="veles.mcp"):
        runtime.mount_mcp_tools(Registry(), project)
        runtime.mount_mcp_tools(Registry(), project)
    hits = [r for r in caplog.records if "not approved" in r.getMessage()]
    assert len(hits) == 1
    assert "veles mcp approve evil" in hits[0].getMessage()


# ---- the store ----


def test_env_values_are_not_hashed_or_stored(project: Project, tmp_path: Path, monkeypatch) -> None:
    _write_config(
        project,
        '[mcp.servers.gh]\ncommand = "x"\nenv = { TOKEN = "${VELES_TEST_SECRET}" }\n',
    )
    monkeypatch.setenv("VELES_TEST_SECRET", "s3cr3t-value")
    _approve_current(project, "gh")
    assert "s3cr3t-value" not in approvals.store_path().read_text(encoding="utf-8")
    monkeypatch.setenv("VELES_TEST_SECRET", "another-value")
    raw = load_raw_mcp_servers(project)["gh"]
    assert approvals.approval_state(project.root, "gh", raw) == "yes"


def test_corrupt_store_approves_nothing(project: Project) -> None:
    raw = {"command": "x"}
    approvals.approve(project.root, "s", raw)
    assert approvals.approval_state(project.root, "s", raw) == "yes"
    approvals.store_path().write_text("{not json", encoding="utf-8")
    assert approvals.approval_state(project.root, "s", raw) == "no"
    approvals.store_path().write_text(f'{{"{project.root.resolve()}": ["s"]}}', encoding="utf-8")
    assert approvals.approval_state(project.root, "s", raw) == "no"


def test_revoke(project: Project) -> None:
    raw = {"command": "x"}
    approvals.approve(project.root, "s", raw)
    approvals.revoke(project.root, "s")
    assert approvals.approval_state(project.root, "s", raw) == "no"


# ---- CLI ----


def test_cli_approve_then_list_and_test(project: Project, capsys) -> None:
    _write_config(
        project,
        '[mcp.servers.gh]\ncommand = "/nonexistent/veles-no-such-binary"\n'
        'args = ["--flag"]\nenv = { TOKEN = "${VELES_TEST_SECRET}" }\n'
        "connect_timeout_s = 5\n",
    )
    rc = mcp_cmd.cmd_mcp(_ns(mcp_command="test", server="gh"), project)
    assert rc == 1
    assert "veles mcp approve gh" in capsys.readouterr().err

    seen: list[str] = []

    def confirmer(op: str, summary: str) -> bool:
        seen.append(summary)
        return True

    token = set_critical_confirmer(confirmer)
    try:
        assert mcp_cmd.cmd_mcp(_ns(mcp_command="approve", server="gh"), project) == 0
    finally:
        reset_critical_confirmer(token)
    assert "/nonexistent/veles-no-such-binary" in seen[0]
    assert "--flag" in seen[0]
    assert "TOKEN" in seen[0]
    assert "${VELES_TEST_SECRET}" in seen[0]  # a reference is shown verbatim, not expanded

    rc = mcp_cmd.cmd_mcp(_ns(mcp_command="list", connect_timeout=5.0), project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "gh" in out and "yes" in out


def test_cli_approve_shows_env_values_that_steer_execution(project: Project) -> None:
    """`PATH` in `env` decides which `npx` runs — the user must see it."""
    _write_config(
        project,
        '[mcp.servers.gh]\ncommand = "npx"\ncwd = "/some/dir"\n'
        'env = { PATH = "/repo/evilbin:/usr/bin", TOKEN = "${GH_TOKEN}" }\n'
        'weird = "a\\u001b[31mb"\n',
    )
    seen: list[str] = []
    token = set_critical_confirmer(lambda op, summary: seen.append(summary) or False)
    try:
        mcp_cmd.cmd_mcp(_ns(mcp_command="approve", server="gh"), project)
    finally:
        reset_critical_confirmer(token)
    assert "/repo/evilbin:/usr/bin" in seen[0]
    assert "${GH_TOKEN}" in seen[0]
    assert "/some/dir" in seen[0]
    assert "\x1b" not in seen[0]  # untrusted values are escaped


def test_cli_list_does_not_probe_unapproved(project: Project, tmp_path: Path, capsys) -> None:
    marker = tmp_path / "pwned"
    _touch_server(project, marker)
    assert mcp_cmd.cmd_mcp(_ns(mcp_command="list", connect_timeout=5.0), project) == 0
    assert not marker.exists()
    row = next(line for line in capsys.readouterr().out.splitlines() if "evil" in line)
    assert row.split()[2] == "no"  # name, transport, approved
    _approve_current(project, "evil")
    _touch_server(project, marker, extra=', "x"')
    mcp_cmd.cmd_mcp(_ns(mcp_command="list", connect_timeout=5.0), project)
    row = next(line for line in capsys.readouterr().out.splitlines() if "evil" in line)
    assert row.split()[2] == "changed"
    assert not marker.exists()


def test_cli_approve_refuses_recipe_changed_during_review(project: Project, tmp_path: Path) -> None:
    _touch_server(project, tmp_path / "harmless")

    def swap(op: str, summary: str) -> bool:
        _touch_server(project, tmp_path / "pwned")
        return True

    token = set_critical_confirmer(swap)
    try:
        assert mcp_cmd.cmd_mcp(_ns(mcp_command="approve", server="evil"), project) == 1
    finally:
        reset_critical_confirmer(token)
    raw = load_raw_mcp_servers(project)["evil"]
    assert approvals.approval_state(project.root, "evil", raw) == "no"


def test_cli_approve_declined_records_nothing(project: Project, tmp_path: Path) -> None:
    _touch_server(project, tmp_path / "m")
    token = set_critical_confirmer(lambda op, summary: False)
    try:
        assert mcp_cmd.cmd_mcp(_ns(mcp_command="approve", server="evil"), project) == 1
    finally:
        reset_critical_confirmer(token)
    raw = load_raw_mcp_servers(project)["evil"]
    assert approvals.approval_state(project.root, "evil", raw) == "no"


def test_cli_approve_unknown_server_rc2(project: Project) -> None:
    assert mcp_cmd.cmd_mcp(_ns(mcp_command="approve", server="nope"), project) == 2


def test_parser_accepts_approve() -> None:
    from veles.cli._parsers import build_parser

    args = build_parser().parse_args(["mcp", "approve", "gh"])
    assert args.mcp_command == "approve" and args.server == "gh"


def test_concurrent_approvals_are_not_lost(tmp_path: Path, monkeypatch) -> None:
    """Two writers that both read the old store must not drop each other's approval."""
    import contextlib
    import threading

    from veles.mcp import approvals as mod

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    root = tmp_path / "proj"
    root.mkdir()
    real_load = mod._load
    barrier = threading.Barrier(2)

    def slow_load():
        data = real_load()
        # Unlocked, both writers get here with the same old state; locked, the
        # second waits on the lock and the barrier just times out.
        with contextlib.suppress(threading.BrokenBarrierError):
            barrier.wait(timeout=0.5)
        return data

    monkeypatch.setattr(mod, "_load", slow_load)
    threads = [
        threading.Thread(target=mod.approve, args=(root, n, {"command": n})) for n in ("a", "b")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    monkeypatch.setattr(mod, "_load", real_load)
    assert mod.approval_state(root, "a", {"command": "a"}) == "yes"
    assert mod.approval_state(root, "b", {"command": "b"}) == "yes"
