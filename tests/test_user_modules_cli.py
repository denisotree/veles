from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.registry_helpers import commit_all, make_git_registry, write_extension
from veles.cli import main
from veles.cli._project import _load_project_modules
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.project import init_project
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
