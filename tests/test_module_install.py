"""Unit tests for module install/remove. Mirrors test_skill_install.py."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from veles.core.module_install import (
    ModuleInstallError,
    ModuleNotFoundError,
    install_module_from_source,
    remove_module,
)
from veles.core.module_install import derive_module_name as _derive_name
from veles.core.project import init_project
from veles.core.source_install import is_git_url as _is_git_url


def _make_module_fixture(
    root: Path, *, name: str = "logger", version: str | None = "0.1.0"
) -> Path:
    mod_dir = root / f"fixture-{name}"
    mod_dir.mkdir(parents=True, exist_ok=True)
    version_line = f'version = "{version}"\n' if version else ""
    (mod_dir / "module.toml").write_text(
        f"[module]\n"
        f'name = "{name}"\n'
        f'description = "Log every tool call"\n'
        f'entrypoint = "main.py:register"\n'
        f"{version_line}",
        encoding="utf-8",
    )
    (mod_dir / "main.py").write_text("def register(api): pass\n", encoding="utf-8")
    return mod_dir


def test_is_git_url_recognises_common_schemes() -> None:
    assert _is_git_url("https://github.com/u/r.git")
    assert _is_git_url("git@github.com:u/r.git")
    assert not _is_git_url("/local/path")
    assert not _is_git_url("just-a-name")


def test_derive_name_strips_dot_git_suffix() -> None:
    assert _derive_name("https://github.com/u/foo-mod.git") == "foo-mod"


@pytest.mark.parametrize("dirname", ["demo.git", "demo"])  # git clone / directory copy
def test_module_add_from_git_repo_drops_dot_git(tmp_path: Path, dirname: str) -> None:
    import argparse
    import os

    from tests.registry_helpers import commit_all
    from veles.cli._project import _load_project_modules
    from veles.cli.commands.modules import cmd_module
    from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer

    project = init_project(tmp_path / "p", name="p")
    src = _make_module_fixture(tmp_path, name="demo")
    src = src.rename(tmp_path / dirname)
    commit_all(src, "module")
    token = set_critical_confirmer(lambda op, summary: True)
    try:
        args = argparse.Namespace(module_command="add", source=str(src), name=None)
        assert cmd_module(args, project) == 0
    finally:
        reset_critical_confirmer(token)
    installed = project.modules_dir / "demo"
    assert sorted(os.listdir(installed)) == ["main.py", "module.toml"]
    assert _load_project_modules(project).modules == ["demo"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_failed_dot_git_removal_rolls_back_completely(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _make_module_fixture(tmp_path, name="demo")
    locked = src / ".git" / "locked"
    locked.mkdir(parents=True)
    (locked / "obj").write_bytes(b"x")
    locked.chmod(0o555)  # copytree keeps the mode, so the copy's .git can't be emptied
    try:
        with pytest.raises(OSError):
            install_module_from_source(str(src), project=project)
    finally:
        locked.chmod(0o755)
    assert not (project.modules_dir / "fixture-demo").exists()


def test_install_from_local_directory_succeeds(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _make_module_fixture(tmp_path / "src", name="logger")
    handle = install_module_from_source(str(src), project=project, name_override="logger")
    assert handle.name == "logger"
    assert (project.modules_dir / "logger" / "module.toml").is_file()
    assert (project.modules_dir / "logger" / "main.py").is_file()


def test_install_rejects_existing_non_empty_target(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _make_module_fixture(tmp_path / "src", name="logger")
    install_module_from_source(str(src), project=project, name_override="logger")
    with pytest.raises(ModuleInstallError, match="already exists"):
        install_module_from_source(str(src), project=project, name_override="logger")


def test_install_cleans_up_when_manifest_missing(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = tmp_path / "bad-src"
    src.mkdir()
    (src / "main.py").write_text("def register(api): pass", encoding="utf-8")
    with pytest.raises(ModuleInstallError, match=r"no module\.toml"):
        install_module_from_source(str(src), project=project, name_override="bad")
    assert not (project.modules_dir / "bad").exists()


def test_install_cleans_up_when_entrypoint_file_missing(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = tmp_path / "missing-entry"
    src.mkdir()
    (src / "module.toml").write_text(
        '[module]\nname = "mod"\ndescription = "x"\nentrypoint = "missing.py:register"\n',
        encoding="utf-8",
    )
    with pytest.raises(ModuleInstallError, match="entrypoint file"):
        install_module_from_source(str(src), project=project, name_override="mod")
    assert not (project.modules_dir / "mod").exists()


def test_install_cleans_up_when_manifest_invalid(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = tmp_path / "bad-toml"
    src.mkdir()
    (src / "module.toml").write_text("[module\nname = 'broken'", encoding="utf-8")
    with pytest.raises(ModuleInstallError, match="manifest validation"):
        install_module_from_source(str(src), project=project, name_override="broken")
    assert not (project.modules_dir / "broken").exists()


def test_install_rejects_entrypoint_outside_module(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _make_module_fixture(tmp_path / "src", name="esc")
    (tmp_path / "outside.py").write_text("def register(api): pass\n", encoding="utf-8")
    manifest = src / "module.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("main.py", "../../../../outside.py"),
        encoding="utf-8",
    )
    with pytest.raises(ModuleInstallError, match="outside"):
        install_module_from_source(str(src), project=project, name_override="esc")
    assert not (project.modules_dir / "esc").exists()


def test_install_rejects_unknown_source_format(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    with pytest.raises(ModuleInstallError, match="neither a git URL nor a directory"):
        install_module_from_source("nonexistent-thing-xyz", project=project)


def test_remove_existing_module_deletes_directory(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _make_module_fixture(tmp_path / "src", name="logger")
    install_module_from_source(str(src), project=project, name_override="logger")
    assert (project.modules_dir / "logger").is_dir()
    remove_module("logger", project=project)
    assert not (project.modules_dir / "logger").exists()


def test_remove_nonexistent_module_raises(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    with pytest.raises(ModuleNotFoundError):
        remove_module("ghost", project=project)
