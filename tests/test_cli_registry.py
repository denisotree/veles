from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from tests.registry_helpers import commit_all, git, make_git_registry, write_extension
from veles.cli import main
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.project import init_project
from veles.core.registry.install import InstallError, installed_records
from veles.core.registry.records import put_record


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


def test_empty_registry_does_not_break_the_cli(tmp_path: Path, capsys, monkeypatch) -> None:
    remote = tmp_path / "remote"
    make_git_registry(remote, skills=("alpha",))
    empty = tmp_path / "empty.git"
    empty.mkdir()
    git(empty, "init", "-q", "--bare")
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(project.root)
    main(["registry", "remove", "public"])
    assert main(["registry", "add", str(remote)]) == 0
    assert main(["registry", "add", str(empty), "--name", "empty"]) == 0
    capsys.readouterr()
    assert main(["registry", "list"]) == 0
    assert "unreadable" in capsys.readouterr().out
    assert main(["registry", "search", "alp"]) == 0
    out = capsys.readouterr()
    assert "private:official/alpha" in out.out and "empty:" in out.err
    assert main(["registry", "install", "alpha"]) == 0
    assert main(["registry", "verify"]) == 0


def test_os_errors_are_reported_not_raised(tmp_path: Path, capsys) -> None:
    from tests.registry_helpers import write_registry

    root = write_registry(tmp_path / "r")
    write_extension(root, "official", "alpha")
    report = tmp_path / "no-such-dir" / "report.md"
    assert main(["registry", "validate", str(root), "--report", str(report)]) == 1
    assert "error:" in capsys.readouterr().err
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    assert main(["registry", "init", str(blocker / "reg"), "--name", "acme"]) == 1
    assert "error:" in capsys.readouterr().err


def test_install_by_full_ref(tmp_path: Path, capsys, monkeypatch) -> None:
    remote = tmp_path / "remote"
    make_git_registry(remote, skills=("alpha",))
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(project.root)
    main(["registry", "remove", "public"])
    main(["registry", "add", str(remote)])
    assert main(["registry", "install", "private:official/alpha"]) == 0
    assert (project.skills_dir / "alpha" / "SKILL.md").is_file()


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


def test_upgrade_all_isolates_failures(tmp_path: Path, capsys, monkeypatch) -> None:
    remote = tmp_path / "remote"
    make_git_registry(remote, skills=("alpha", "beta"))
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(project.root)
    main(["registry", "remove", "public"])
    main(["registry", "add", str(remote)])
    main(["registry", "install", "alpha"])
    main(["registry", "install", "beta"])
    write_extension(remote, "official", "alpha", version="0.2.0")
    write_extension(remote, "official", "beta", version="0.2.0")
    commit_all(remote, "bump")
    main(["registry", "update"])
    capsys.readouterr()

    import veles.cli.commands.registry as registry_cmd

    real_upgrade = registry_cmd.upgrade

    def flaky(name, *, project, user_scope=None):
        if name == "alpha":
            raise InstallError("boom")
        return real_upgrade(name, project=project, user_scope=user_scope)

    monkeypatch.setattr(registry_cmd, "upgrade", flaky)

    assert main(["registry", "upgrade"]) == 1
    out = capsys.readouterr()
    assert "alpha: error: boom" in out.err
    assert "beta: upgraded to 0.2.0" in out.out


def test_verify_corrupt_version_is_error_not_traceback(tmp_path: Path, capsys, monkeypatch) -> None:
    remote = tmp_path / "remote"
    make_git_registry(remote, skills=("alpha",))
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(project.root)
    main(["registry", "remove", "public"])
    main(["registry", "add", str(remote)])
    main(["registry", "install", "alpha"])
    [rec] = [r for r in installed_records(project) if r.name == "alpha"]
    put_record(replace(rec, version=""))

    assert main(["registry", "verify"]) == 1
    assert "error:" in capsys.readouterr().err
