"""Stage 1b (A): the agent's file tools cannot write Veles' own state in `.veles/`.

Only `AGENT_WRITABLE_STATE` subdirs of `project.state_dir` are open to
`write_file`/`edit_file`/`move_file`/`delete_file`/`make_dir`; trust.json,
config.toml, modules/, memory.db and any new file there are managed by Veles.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.layout.writable import is_writable
from veles.core.path_guard import SandboxViolation
from veles.core.project import init_project
from veles.core.tools.builtin.edit_file import edit_file
from veles.core.tools.builtin.file_ops import delete_file, make_dir, move_file
from veles.core.tools.builtin.write_file import write_file

_GRANT = json.dumps({"tools": {"run_shell": {"granted_at": "2026-09-29T00:00:00Z"}}})

_CLOSED = (
    ".veles/trust.json",
    ".veles/config.toml",
    ".veles/project.toml",
    ".veles/modules/x/m.py",
    ".veles/sanitize.toml",
    ".veles/memory.db",
    ".veles/wiki.toml",
    ".veles/jobs/j.md",
    ".veles/NEW-FILE",
)
_OPEN = (
    ".veles/skills/x/SKILL.md",
    ".veles/tools/t.py",
    ".veles/tmp/a",
    ".veles/plans/p.md",
    ".veles/memory/x.md",
    ".veles/artifacts/a",
)


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("VELES_TRUST_AUTO_ALLOW", raising=False)
    p = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def _run_shell_granted() -> bool:
    # `veles.core.trust` imported before `veles.core.permission` trips an
    # import cycle between the two; load them in the order the app does.
    import veles.core.permission  # noqa: F401
    from veles.core.trust import evaluate_trust

    return evaluate_trust("run_shell").allowed


def _refused(msg: str) -> bool:
    return msg.startswith("<refused:") and "managed by Veles" in msg


def test_attack_write_trust_json_does_not_grant_run_shell(project) -> None:
    project.trust_path.unlink(missing_ok=True)
    msg = write_file(".veles/trust.json", _GRANT)
    assert _refused(msg), msg
    assert not project.trust_path.exists()
    assert not _run_shell_granted()


def test_attack_edit_existing_trust_json_is_refused(project) -> None:
    project.trust_path.write_text('{"tools": {}}', encoding="utf-8")
    msg = edit_file(".veles/trust.json", '"tools": {}', '"tools": ' + _GRANT[10:-1])
    assert _refused(msg), msg
    assert not _run_shell_granted()


@pytest.mark.parametrize("rel", _CLOSED)
def test_closed_state_paths_refused(project, rel: str) -> None:
    target = project.root / rel
    msg = write_file(rel, "x")
    assert _refused(msg), msg
    assert rel in msg
    assert not is_writable(project, rel)
    if not target.exists():
        assert _refused(make_dir(rel))
        assert not target.exists()
        # Veles itself creates the file (not through the file tools) …
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"veles")
    # … and the agent can neither edit nor delete it.
    before = target.read_bytes()
    assert _refused(edit_file(rel, before.decode("latin-1")[:1] or "v", "Z", replace_all=True))
    assert _refused(delete_file(rel))
    assert target.read_bytes() == before


@pytest.mark.parametrize("rel", _OPEN)
def test_agent_state_subdirs_open(project, rel: str) -> None:
    assert write_file(rel, "x").startswith("wrote")
    assert is_writable(project, rel)
    assert edit_file(rel, "x", "y").startswith("edited")
    assert (project.root / rel).read_text(encoding="utf-8") == "y"
    moved = rel + ".moved"
    assert move_file(rel, moved).startswith("moved")
    assert delete_file(moved).startswith("deleted")
    assert make_dir(str(Path(rel).parent / "sub")).startswith("created")


def test_existing_state_file_delete_and_move_refused(project) -> None:
    config = project.state_dir / "config.toml"
    config.write_text("[engine]\n", encoding="utf-8")
    assert _refused(delete_file(".veles/config.toml"))
    assert config.exists()
    assert _refused(move_file(".veles/config.toml", "wiki/c.toml"))
    assert config.exists()


def test_move_from_skills_into_trust_json_refused(project) -> None:
    project.trust_path.unlink(missing_ok=True)
    write_file(".veles/skills/x/SKILL.md", _GRANT)
    msg = move_file(".veles/skills/x/SKILL.md", ".veles/trust.json")
    assert _refused(msg), msg
    assert not project.trust_path.exists()
    assert not _run_shell_granted()


def test_dotdot_spelling_refused(project) -> None:
    project.trust_path.unlink(missing_ok=True)
    with pytest.raises(SandboxViolation):
        write_file(".veles/../.veles/trust.json", _GRANT)
    assert not project.trust_path.exists()
    assert not is_writable(project, ".veles/../.veles/trust.json")


def test_case_variant_refused(project) -> None:
    probe = project.root / "case-probe"
    probe.touch()
    if not (project.root / "CASE-PROBE").exists():
        pytest.skip("case-sensitive filesystem")
    project.trust_path.unlink(missing_ok=True)
    msg = write_file(".VELES/trust.json", _GRANT)
    assert _refused(msg), msg
    assert not project.trust_path.exists()
    assert not is_writable(project, ".VELES/trust.json")
    assert not _run_shell_granted()


def test_lookalike_dir_is_not_state(project) -> None:
    """`.veles-notes/` is ordinary project content, not Veles state."""
    assert "wrote" in write_file(".veles-notes/a.md", "x")
