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


@pytest.mark.parametrize("target", [".veles", "."])
def test_symlinked_allowed_subdir_does_not_open_state(project, target: str) -> None:
    """`.veles/tmp -> .veles` (or -> the project root) must not make
    trust.json / config.toml writable through or next to it."""
    tmp = project.state_dir / "tmp"
    if tmp.exists():
        tmp.rmdir()
    tmp.symlink_to((project.root / target).resolve(), target_is_directory=True)
    project.trust_path.unlink(missing_ok=True)
    if target == ".veles":
        assert _refused(write_file(".veles/tmp/trust.json", _GRANT))
    # (with tmp -> root, `.veles/tmp/trust.json` is just `<root>/trust.json`,
    # ordinary content Veles never reads)
    assert _refused(write_file(".veles/trust.json", _GRANT))
    assert _refused(write_file(".veles/config.toml", "x"))
    assert not project.trust_path.exists()
    assert not _run_shell_granted()


def test_allowed_subdir_symlink_elsewhere_is_not_allow_listed(project) -> None:
    """An allow-listed name that is a symlink at all loses its allow-list pass:
    the pass exists for Veles' own dirs, and a link can be retargeted later."""
    for name in ("artifacts", "plans"):
        if (project.state_dir / name).exists():
            (project.state_dir / name).rmdir()
    modules = project.state_dir / "modules"
    modules.mkdir(exist_ok=True)
    (project.state_dir / "artifacts").symlink_to(modules, target_is_directory=True)
    assert _refused(write_file(".veles/artifacts/evil.py", "x"))
    assert not (modules / "evil.py").exists()
    # A link to ordinary content resolves outside .veles — the usual zone
    # rules decide there, exactly as for any other in-project symlink.
    notes = project.root / "notes"
    notes.mkdir()
    (project.state_dir / "plans").symlink_to(notes, target_is_directory=True)
    assert write_file(".veles/plans/a.md", "x").startswith("wrote")


def test_in_project_symlink_to_state_file_refused(project) -> None:
    config = project.state_dir / "config.toml"
    config.write_text("[engine]\n", encoding="utf-8")
    link = project.root / "cfg.toml"
    link.symlink_to(config)
    assert _refused(write_file("cfg.toml", "x"))
    assert _refused(edit_file("cfg.toml", "engine", "evil"))
    assert _refused(delete_file("cfg.toml"))
    assert config.read_text(encoding="utf-8") == "[engine]\n"


def test_wiki_rename_page_cannot_take_state_files(project) -> None:
    import veles.modules.wiki.tools as wt

    config = project.state_dir / "config.toml"
    config.write_text("[engine]\n", encoding="utf-8")
    msg = wt.wiki_rename_page(".veles/config.toml", "concepts", "stolen")
    assert msg.startswith("<"), msg
    assert config.read_text(encoding="utf-8") == "[engine]\n"
    assert not (project.root / "wiki" / "concepts" / "stolen.md").exists()


def test_wiki_rename_page_only_moves_wiki_pages(project) -> None:
    import veles.modules.wiki.tools as wt

    readme = project.root / "README.md"
    readme.write_text("# R\n", encoding="utf-8")
    assert wt.wiki_rename_page("README.md", "concepts", "r").startswith("<")
    assert readme.exists()


def _page(project, rel: str = "wiki/concepts/a.md", body: str = "# A\n\nkeep me\n") -> Path:
    from veles.modules.wiki.wiki import Wiki

    Wiki(project.wiki_root).ensure_layout()
    page = project.root / rel
    page.write_text(body, encoding="utf-8")
    return page


@pytest.mark.parametrize(
    "spelling",
    [
        "wiki/concepts/a.md",
        "wiki//concepts/a.md",
        "wiki/./concepts/a.md",
        "./wiki/concepts/a.md",
        "WIKI/concepts/a.md",
        "wiki/Concepts/a.md",
    ],
)
def test_wiki_rename_onto_itself_is_a_noop(project, spelling: str) -> None:
    import veles.modules.wiki.tools as wt

    page = _page(project)
    if spelling != spelling.lower() and not (project.root / spelling).exists():
        pytest.skip("case-sensitive filesystem")
    msg = wt.wiki_rename_page(spelling, "concepts", "a")
    assert msg.startswith("<error:") and "same page" in msg, msg
    assert page.read_text(encoding="utf-8") == "# A\n\nkeep me\n"


def test_wiki_write_page_through_symlinked_wiki_dir_refused(project) -> None:
    import veles.modules.wiki.tools as wt

    wiki_dir = project.root / "wiki"
    if wiki_dir.exists():
        import shutil

        shutil.rmtree(wiki_dir)
    wiki_dir.symlink_to(project.state_dir, target_is_directory=True)
    (project.state_dir / "concepts").mkdir(exist_ok=True)
    msg = wt.wiki_write_page("concepts", "pwn", "Pwn", "x")
    assert _refused(msg), msg
    (project.root / "src.md").write_text("# Pwn\n", encoding="utf-8")
    msg = wt.wiki_ingest("src.md", category="concepts", slug="pwn")
    assert _refused(msg), msg
    assert not (project.state_dir / "concepts" / "pwn.md").exists()


def test_wiki_rename_link_repair_skips_guarded_pages(project, monkeypatch) -> None:
    """The link-rewrite loop runs every page it edits through the write guard."""
    import veles.modules.wiki.tools as wt

    _page(project, "wiki/concepts/old.md", "# Old\n")
    other = _page(project, "wiki/concepts/other.md", "see [[old]]\n")
    real_guard = wt.guard_write
    seen: list[Path] = []

    def spy(p, proj):
        seen.append(p)
        return "<refused: test>" if p.name == "other.md" else real_guard(p, proj)

    monkeypatch.setattr(wt, "guard_write", spy)
    assert wt.wiki_rename_page("wiki/concepts/old.md", "concepts", "new").startswith("renamed")
    assert other.read_text(encoding="utf-8") == "see [[old]]\n"
    assert any(p.name == "other.md" for p in seen)


def test_wiki_rename_under_symlinked_project_root_needs_no_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import veles.core.tools.builtin.fs_write_guard as g
    import veles.modules.wiki.tools as wt
    from veles.core.project import load_project

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    real = init_project(tmp_path / "real", name="real")
    link = tmp_path / "link"
    link.symlink_to(real.root, target_is_directory=True)
    project = load_project(link)
    token = set_active_project(project)
    try:

        def no_confirm(*_a, **_k):
            raise AssertionError("in-project rename must not ask for confirmation")

        monkeypatch.setattr(g, "confirm_critical", no_confirm)
        _page(project, "wiki/concepts/a.md")
        msg = wt.wiki_rename_page("wiki/concepts/a.md", "concepts", "b")
        assert msg.startswith("renamed"), msg
        assert (real.root / "wiki" / "concepts" / "b.md").exists()
    finally:
        reset_active_project(token)


def test_lookalike_dir_is_not_state(project) -> None:
    """`.veles-notes/` is ordinary project content, not Veles state."""
    assert "wrote" in write_file(".veles-notes/a.md", "x")
