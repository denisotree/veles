"""Unit tests for module install/remove. Mirrors test_skill_install.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.module_install import (
    ModuleInstallError,
    ModuleNotFoundError,
    _derive_name,
    _is_git_url,
    install_module_from_source,
    remove_module,
)
from veles.core.project import init_project


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
