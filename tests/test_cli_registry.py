from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.registry_helpers import make_git_registry
from veles.cli import main
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.project import init_project


@pytest.fixture(autouse=True)
def _yes() -> Iterator[None]:
    token = set_critical_confirmer(lambda op, summary: True)
    yield
    reset_critical_confirmer(token)


def test_full_cycle(tmp_path: Path, capsys, monkeypatch) -> None:
    remote = tmp_path / "remote"
    make_git_registry(remote, skills=("alpha",))
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(project.root)
    assert main(["registry", "remove", "public"]) == 0
    assert main(["registry", "add", str(remote)]) == 0
    assert main(["registry", "list"]) == 0
    assert "private" in capsys.readouterr().out
    assert main(["registry", "search", "alp"]) == 0
    assert "private:official/alpha" in capsys.readouterr().out
    assert main(["registry", "install", "alpha"]) == 0
    assert (project.skills_dir / "alpha" / "SKILL.md").is_file()
    assert main(["registry", "verify"]) == 0
    assert main(["registry", "uninstall", "alpha"]) == 0


def test_install_unknown_is_error_not_traceback(tmp_path: Path, capsys, monkeypatch) -> None:
    remote = tmp_path / "remote"
    make_git_registry(remote)
    monkeypatch.chdir(init_project(tmp_path / "p", name="p").root)
    main(["registry", "remove", "public"])
    main(["registry", "add", str(remote)])
    assert main(["registry", "install", "zeta"]) == 1
    assert "no extension" in capsys.readouterr().err


def test_init_scaffold_validate(tmp_path: Path) -> None:
    root = tmp_path / "reg"
    assert main(["registry", "init", str(root), "--name", "acme", "--ci", "none"]) == 0
    assert main(["registry", "scaffold", "skill", "notes", "--root", str(root)]) == 0
    assert (
        main(["registry", "validate", str(root), "--run-code", "--report", str(tmp_path / "r.md")])
        == 0
    )
    assert "all checks passed" in (tmp_path / "r.md").read_text(encoding="utf-8")


def test_browse_is_gone() -> None:
    with pytest.raises(SystemExit):
        main(["browse", "skills"])
