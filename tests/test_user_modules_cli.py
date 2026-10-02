from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.registry_helpers import commit_all, make_git_registry, write_extension
from veles.cli import main
from veles.cli._project import _load_project_modules
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.project import init_project
from veles.core.registry.gate import approve_module
from veles.core.registry.records import load_records
from veles.core.user_paths import user_modules_dir

_FILES = {
    "module.toml": '[module]\nname = "demo"\ndescription = "d"\nentrypoint = "demo.py:register"\n',
    "demo.py": "def register(api):\n    api.add_hook('pre_turn', lambda **kw: None)\n",
}


@pytest.fixture(autouse=True)
def _yes() -> Iterator[None]:
    token = set_critical_confirmer(lambda op, summary: True)
    yield
    reset_critical_confirmer(token)


def test_registry_install_user_module_loads_everywhere(tmp_path: Path, monkeypatch) -> None:
    remote = tmp_path / "remote"
    make_git_registry(remote, skills=())
    write_extension(
        remote,
        "official",
        "demo",
        kind="module",
        files=_FILES,
        extra_ext='provides = ["hook:pre_turn"]',
    )
    commit_all(remote, "demo")
    a = init_project(tmp_path / "a", name="a")
    b = init_project(tmp_path / "b", name="b")
    monkeypatch.chdir(a.root)
    assert main(["registry", "remove", "public"]) == 0
    assert main(["registry", "add", str(remote)]) == 0
    assert main(["registry", "install", "--user", "demo"]) == 0
    assert (user_modules_dir() / "demo" / "demo.py").is_file()
    [rec] = [r for r in load_records() if r.name == "demo"]
    assert rec.project is None
    assert _load_project_modules(b).modules == ["demo"]


def test_module_cli_user_scope(tmp_path: Path, monkeypatch, capsys) -> None:
    src = tmp_path / "src-demo"
    src.mkdir()
    for rel, body in _FILES.items():
        (src / rel).write_text(body, encoding="utf-8")
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(project.root)
    assert main(["module", "add", "--user", str(src), "--name", "demo"]) == 0
    assert (user_modules_dir() / "demo").is_dir()
    assert main(["module", "list"]) == 0
    out = capsys.readouterr().out
    assert "demo" in out and "user" in out
    (user_modules_dir() / "demo" / "demo.py").write_text(
        _FILES["demo.py"] + "# edited\n", encoding="utf-8"
    )
    assert _load_project_modules(project).modules == []
    assert main(["module", "approve", "--user", "demo"]) == 0
    assert _load_project_modules(project).modules == ["demo"]
    assert main(["module", "remove", "--user", "--yes", "demo"]) == 0
    assert not (user_modules_dir() / "demo").exists()
    assert [r for r in load_records() if r.name == "demo"] == []


def _write_module(d: Path, name: str, body: str = _FILES["demo.py"]) -> Path:
    d.mkdir(parents=True)
    (d / "module.toml").write_text(
        f'[module]\nname = "{name}"\ndescription = "d"\nentrypoint = "demo.py:register"\n',
        encoding="utf-8",
    )
    (d / "demo.py").write_text(body, encoding="utf-8")
    return d


def test_module_add_never_approves_a_planted_same_named_module(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The agent plants `.veles/modules/aaa2/` declaring name "bar2"; the user installs
    their own "bar2". The planted dir sorts first — it must never be the one approved."""
    project = init_project(tmp_path / "p", name="p")
    planted = _write_module(
        project.modules_dir / "aaa2", "bar2", "raise SystemExit('planted code ran')\n"
    )
    src = _write_module(tmp_path / "bar2", "bar2")
    monkeypatch.chdir(project.root)
    assert main(["module", "add", str(src)]) == 1
    assert "aaa2" in capsys.readouterr().err
    assert not (project.modules_dir / "bar2").exists()
    assert [r for r in load_records() if r.path == str(planted.resolve())] == []
    assert _load_project_modules(project).modules == []


def test_module_add_shows_and_pins_the_approved_hash(tmp_path: Path, monkeypatch, capsys) -> None:
    """The confirmation shows the installed files' hash; files swapped while the user is
    confirming are refused (and removed), never approved."""
    project = init_project(tmp_path / "p", name="p")
    src = _write_module(tmp_path / "src-demo", "demo")
    monkeypatch.chdir(project.root)
    seen: list[str] = []

    def swap_during_review(op: str, summary: str) -> bool:
        seen.append(summary)
        (project.modules_dir / "demo" / "demo.py").write_text(
            "raise SystemExit('swapped')\n", encoding="utf-8"
        )
        return True

    token = set_critical_confirmer(swap_during_review)
    try:
        assert main(["module", "add", str(src), "--name", "demo"]) == 1
    finally:
        reset_critical_confirmer(token)
    assert "Files hash:" in seen[0]
    assert "changed while it was being reviewed" in capsys.readouterr().err
    assert not (project.modules_dir / "demo").exists()
    assert load_records() == []


def test_module_add_declined_leaves_nothing(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _write_module(tmp_path / "src-demo", "demo")
    monkeypatch.chdir(project.root)
    token = set_critical_confirmer(lambda op, summary: False)
    try:
        assert main(["module", "add", str(src), "--name", "demo"]) == 1
    finally:
        reset_critical_confirmer(token)
    assert not (project.modules_dir / "demo").exists()
    assert load_records() == []


def test_module_add_interrupted_leaves_nothing(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _write_module(tmp_path / "src-demo", "demo")
    monkeypatch.chdir(project.root)

    def ctrl_c(op: str, summary: str) -> bool:
        raise KeyboardInterrupt

    token = set_critical_confirmer(ctrl_c)
    try:
        with pytest.raises(KeyboardInterrupt):
            main(["module", "add", str(src), "--name", "demo"])
    finally:
        reset_critical_confirmer(token)
    assert not (project.modules_dir / "demo").exists()


def test_module_remove_refuses_a_symlinked_module_dir(tmp_path: Path, monkeypatch, capsys) -> None:
    """Removing through a link would delete (or un-approve) whatever it points at."""
    project = init_project(tmp_path / "p", name="p")
    other = init_project(tmp_path / "other", name="other")
    real = _write_module(other.modules_dir / "linked", "linked")
    approve_module(real, name="linked", project_root=other.root)
    project.modules_dir.mkdir(parents=True, exist_ok=True)
    (project.modules_dir / "linked").symlink_to(real, target_is_directory=True)
    monkeypatch.chdir(project.root)
    assert main(["module", "remove", "--yes", "linked"]) == 1
    assert "symlink" in capsys.readouterr().err
    assert (real / "demo.py").is_file()
    assert (project.modules_dir / "linked").is_symlink()
    assert [r.path for r in load_records()] == [str(real.resolve())]


def test_approve_and_remove_stay_in_their_own_scope(tmp_path: Path, monkeypatch, capsys) -> None:
    """A's `.veles/modules` is a link to B's: `approve`/`remove` run in A must not
    re-scope or delete B's module."""
    a = init_project(tmp_path / "a", name="a")
    b = init_project(tmp_path / "b", name="b")
    guard = _write_module(b.modules_dir / "guard", "guard")
    approve_module(guard, name="guard", project_root=b.root)
    if a.modules_dir.exists():
        a.modules_dir.rmdir()
    a.modules_dir.symlink_to(b.modules_dir, target_is_directory=True)
    monkeypatch.chdir(a.root)
    assert main(["module", "approve", "guard"]) == 1
    assert main(["module", "remove", "--yes", "guard"]) == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err and err.count("error:") == 2
    assert (guard / "demo.py").is_file()
    [rec] = load_records()
    assert rec.project == str(b.root.resolve())
    assert _load_project_modules(b).modules == ["guard"]


def test_approve_module_refuses_to_rescope_a_record(tmp_path: Path) -> None:
    a = init_project(tmp_path / "a", name="a")
    b = init_project(tmp_path / "b", name="b")
    guard = _write_module(b.modules_dir / "guard", "guard")
    approve_module(guard, name="guard", project_root=b.root)
    with pytest.raises(ValueError, match="scope"):
        approve_module(guard, name="guard", project_root=a.root)
    with pytest.raises(ValueError, match="scope"):
        approve_module(guard, name="guard", project_root=None)
    approve_module(guard, name="guard", project_root=b.root)  # same scope: re-approve is fine
    [rec] = load_records()
    assert rec.project == str(b.root.resolve())


def test_module_verbs_refuse_an_ambiguous_name(tmp_path: Path, monkeypatch, capsys) -> None:
    project = init_project(tmp_path / "p", name="p")
    a = _write_module(project.modules_dir / "a-dir", "dup")
    b = _write_module(project.modules_dir / "b-dir", "dup")
    monkeypatch.chdir(project.root)
    for verb in (["approve"], ["show"], ["remove", "--yes"]):
        capsys.readouterr()
        assert main(["module", *verb, "dup"]) == 1, verb
        err = capsys.readouterr().err
        assert str(a) in err and str(b) in err, verb
    assert a.is_dir() and b.is_dir()
    assert load_records() == []


def test_module_remove_takes_the_manifest_name(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    d = _write_module(project.modules_dir / "some-dir", "demo")
    monkeypatch.chdir(project.root)
    assert main(["module", "remove", "--yes", "demo"]) == 0
    assert not d.exists()


def test_module_list_marks_what_does_not_load(tmp_path: Path, monkeypatch, capsys) -> None:
    project = init_project(tmp_path / "p", name="p")
    _write_module(user_modules_dir() / "demo", "demo")
    _write_module(project.modules_dir / "a-demo", "demo")
    _write_module(project.modules_dir / "b-demo", "demo")
    monkeypatch.chdir(project.root)
    assert main(["module", "list"]) == 0
    rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith("demo")]
    assert len(rows) == 3
    user, first, second = rows
    assert "user" in user and "shadowed by the project's" in user
    assert "project" in first and "shadowed" not in first and "duplicate" not in first
    assert "duplicate name — ignored" in second
